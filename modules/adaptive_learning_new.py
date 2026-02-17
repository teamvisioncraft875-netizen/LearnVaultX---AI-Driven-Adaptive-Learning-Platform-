import logging
import json

logger = logging.getLogger(__name__)

class AdaptiveEngine:
    def __init__(self, db_manager):
        self.db = db_manager
        self._table_columns = {}

    def _get_table_columns(self, table_name):
        if table_name in self._table_columns:
            return self._table_columns[table_name]

        cols = set()
        try:
            pragma_rows = self.db.execute_query(f'PRAGMA table_info({table_name})')
            cols = {row.get('name') for row in pragma_rows if row.get('name')}
        except Exception:
            cols = set()
        self._table_columns[table_name] = cols
        return cols

    def update_student_metrics(self, user_id, class_id):
        """Calculate and update student metrics based on quiz performance"""
        try:
            # Get all quiz attempts for this student in this class
            attempts = self.db.execute_query('''
                SELECT qs.score, qs.total, qs.duration_seconds, qs.submitted_at
                FROM quiz_submissions qs
                JOIN quizzes q ON qs.quiz_id = q.id
                WHERE qs.student_id = ? AND q.class_id = ?
                ORDER BY qs.submitted_at DESC
            ''', (user_id, class_id))
            
            if not attempts:
                return
            
            # Calculate average score
            total_score = sum(a['score'] for a in attempts)
            total_possible = sum(a['total'] for a in attempts)
            score_avg = (total_score / total_possible * 100) if total_possible > 0 else 0
            
            # Calculate average time
            times = [a['duration_seconds'] for a in attempts if a['duration_seconds']]
            avg_time = sum(times) / len(times) if times else 0
            
            # Calculate pace score (recent performance vs overall)
            recent_attempts = attempts[:3]  # Last 3 attempts
            if len(recent_attempts) >= 2:
                recent_score = sum(a['score'] for a in recent_attempts) / sum(a['total'] for a in recent_attempts) * 100
                pace_score = recent_score / score_avg if score_avg > 0 else 1.0
            else:
                pace_score = 1.0
            
            # Calculate overall rating (0-100)
            rating = score_avg * 0.7 + (pace_score * 100) * 0.3

            metrics_cols = self._get_table_columns('student_metrics')
            if not metrics_cols:
                return
            
            # Update or insert metrics
            existing = self.db.execute_one(
                'SELECT user_id FROM student_metrics WHERE user_id = ? AND class_id = ?',
                (user_id, class_id)
            )

            # Support both schemas:
            # v1 -> score_avg/avg_time/pace_score/rating
            # v2 -> attendance_score/quiz_score/participation_score/rating
            if {'score_avg', 'avg_time', 'pace_score'}.issubset(metrics_cols):
                update_sql = '''
                    UPDATE student_metrics 
                    SET score_avg = ?, avg_time = ?, pace_score = ?, rating = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND class_id = ?
                '''
                update_params = (score_avg, avg_time, pace_score, rating, user_id, class_id)
                insert_sql = '''
                    INSERT INTO student_metrics (user_id, class_id, score_avg, avg_time, pace_score, rating)
                    VALUES (?, ?, ?, ?, ?, ?)
                '''
                insert_params = (user_id, class_id, score_avg, avg_time, pace_score, rating)
            else:
                # Fallback for schema_new.sql
                attendance_score = min(100, max(0, 100 - min(avg_time / 2, 100)))
                quiz_score = score_avg
                participation_score = min(100, max(0, pace_score * 100))
                update_sql = '''
                    UPDATE student_metrics
                    SET attendance_score = ?, quiz_score = ?, participation_score = ?, rating = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND class_id = ?
                '''
                update_params = (attendance_score, quiz_score, participation_score, rating, user_id, class_id)
                insert_sql = '''
                    INSERT INTO student_metrics (user_id, class_id, attendance_score, quiz_score, participation_score, rating)
                    VALUES (?, ?, ?, ?, ?, ?)
                '''
                insert_params = (user_id, class_id, attendance_score, quiz_score, participation_score, rating)

            if existing:
                self.db.execute_update(update_sql, update_params)
            else:
                self.db.execute_insert(insert_sql, insert_params)
                
            logger.info(f"Updated metrics for student {user_id} in class {class_id}: avg={score_avg:.1f}%, rating={rating:.1f}")
            
        except Exception as e:
            logger.error(f"Error updating student metrics: {e}")

    def analyze_knowledge_gaps(self, user_id, class_id):
        """Analyze quiz performance to identify knowledge gaps"""
        try:
            # Get all quiz questions and student answers for this class
            gaps = self.db.execute_query('''
                SELECT 
                    qq.id as question_id,
                    qq.question_text,
                    qq.correct_option_index,
                    qs.answers,
                    q.id as quiz_id,
                    q.title as quiz_title
                FROM quiz_questions qq
                JOIN quizzes q ON qq.quiz_id = q.id
                JOIN quiz_submissions qs ON qs.quiz_id = q.id
                WHERE q.class_id = ? AND qs.student_id = ?
            ''', (class_id, user_id))
            
            # Identify incorrect answers
            weak_topics = []
            for gap in gaps:
                try:
                    answers = json.loads(gap['answers'] or '{}')
                    question_id = str(gap['question_id'])
                    
                    if question_id in answers:
                        if str(answers[question_id]) != str(gap['correct_option_index']):
                            weak_topics.append({
                                'quiz': gap['quiz_title'],
                                'quiz_id': gap['quiz_id'],
                                'question': gap['question_text'][:100] + '...',
                                'severity': 'medium'
                            })
                except:
                    continue
            
            return weak_topics[:10]  # Return top 10 gaps
            
        except Exception as e:
            logger.error(f"Error analyzing knowledge gaps: {e}")
            return []

    def generate_recommendations(self, user_id, class_id):
        """Generate personalized content recommendations based on performance"""
        try:
            # Get student's weak areas
            metrics_cols = self._get_table_columns('student_metrics')
            if {'score_avg', 'pace_score', 'rating'}.issubset(metrics_cols):
                metrics = self.db.execute_one(
                    'SELECT score_avg, pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
                    (user_id, class_id)
                )
            else:
                metrics = self.db.execute_one(
                    'SELECT quiz_score as score_avg, participation_score as pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
                    (user_id, class_id)
                )
            
            recommendations = []
            
            # 1. Prioritize Knowledge Gaps (Wrong Answers)
            gaps = self.analyze_knowledge_gaps(user_id, class_id)
            for gap in gaps:
                recommendations.append({
                    'type': 'review',
                    'content_id': 0, # No specific content ID for general review, or link to quiz
                    'title': f"Revise: {gap['quiz']}",
                    'description': f"You missed questions on: {gap['question']}",
                    'reason': 'Knowledge Gap Detected',
                    'priority': 95,
                    'action': 'Review Topic'
                })

            # 2. Score-based Recommendations
            if not metrics or metrics['score_avg'] < 70:
                # Recommend lectures for review
                lectures = self.db.execute_query(
                    'SELECT id, filename FROM lectures WHERE class_id = ? ORDER BY uploaded_at ASC LIMIT 3',
                    (class_id,)
                )
                for lec in lectures:
                    recommendations.append({
                        'type': 'lecture',
                        'content_id': lec['id'],
                        'title': f"Watch: {lec['filename']}",
                        'description': 'Strengthen your foundational knowledge.',
                        'reason': 'Low Assessment Score',
                        'priority': 90,
                        'action': 'Watch Video'
                    })

            # 3. Practice Quizzes (if few recommendations)
            if len(recommendations) < 3:
                quizzes = self.db.execute_query(
                    'SELECT id, title FROM quizzes WHERE class_id = ? ORDER BY RANDOM() LIMIT 3',
                    (class_id,)
                )
                for quiz in quizzes:
                    recommendations.append({
                        'type': 'quiz',
                        'content_id': quiz['id'],
                        'title': f"Practice: {quiz['title']}",
                        'description': 'Keep your skills sharp with a quick quiz.',
                        'reason': 'Daily Practice',
                        'priority': 80,
                        'action': 'Start Quiz'
                    })
            
            recommendations = recommendations[:5]

            # Persist recommendations
            rec_cols = self._get_table_columns('recommendations')
            if rec_cols and recommendations:
                try:
                    # Clear unfinished recs for this user
                    self.db.execute_update(
                        'DELETE FROM recommendations WHERE user_id = ? AND is_completed = 0',
                        (user_id,)
                    )
                    
                    for rec in recommendations:
                        # Prepare values
                        r_type = rec.get('type', 'general')
                        r_cid = rec.get('content_id', 0)
                        r_title = rec.get('title', 'Recommendation')
                        r_desc = rec.get('description', '')
                        r_reason = rec.get('reason', '')
                        r_priority = rec.get('priority', 50)
                        r_action = rec.get('action', 'View')

                        # Check available columns and construct query
                        if 'title' in rec_cols and 'description' in rec_cols:
                            if 'action' in rec_cols:
                                self.db.execute_insert(
                                    '''INSERT INTO recommendations (user_id, content_type, content_id, title, description, action, reason, priority, is_completed)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)''',
                                    (user_id, r_type, r_cid, r_title, r_desc, r_action, r_reason, r_priority)
                                )
                            else:
                                self.db.execute_insert(
                                    '''INSERT INTO recommendations (user_id, content_type, content_id, title, description, reason, priority, is_completed)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
                                    (user_id, r_type, r_cid, r_title, r_desc, r_reason, r_priority)
                                )
                        else:
                            # Fallback to old schema
                             self.db.execute_insert(
                                '''INSERT INTO recommendations (user_id, content_type, content_id, reason, priority, is_completed)
                                   VALUES (?, ?, ?, ?, ?, 0)''',
                                (user_id, r_type, r_cid, r_reason, r_priority)
                            )

                except Exception as rec_err:
                    logger.error(f"Failed to persist recommendations: {rec_err}")

            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    def check_intervention_alerts(self, user_id, class_id):
        """Check if teacher intervention is needed"""
        try:
            metrics_cols = self._get_table_columns('student_metrics')
            if {'score_avg', 'pace_score', 'rating'}.issubset(metrics_cols):
                metrics = self.db.execute_one(
                    'SELECT score_avg, pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
                    (user_id, class_id)
                )
            else:
                metrics = self.db.execute_one(
                    'SELECT quiz_score as score_avg, participation_score as pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
                    (user_id, class_id)
                )
            
            alerts = []
            
            if not metrics:
                return alerts
            
            # Low performance alert
            if metrics['score_avg'] < 60:
                alerts.append({
                    'type': 'low_performance',
                    'message': f"Student scoring below 60% (current: {metrics['score_avg']:.1f}%)",
                    'severity': 'high'
                })
            
            # Declining pace alert
            if metrics['pace_score'] < 0.8:
                alerts.append({
                    'type': 'declining_pace',
                    'message': "Student's recent performance declining",
                    'severity': 'medium'
                })
            
            # Overall low rating alert
            if metrics['rating'] < 50:
                alerts.append({
                    'type': 'at_risk',
                    'message': "Student may be at risk of falling behind",
                    'severity': 'high'
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking intervention alerts: {e}")
            return []

    def get_student_context(self, user_id):
        """Retrieve context for AI personalization"""
        try:
            # Get weak topics from all classes
            enrolled_classes = self.db.execute_query(
                'SELECT class_id FROM enrollments WHERE student_id = ?',
                (user_id,)
            )
            
            all_gaps = []
            for enrollment in enrolled_classes:
                gaps = self.analyze_knowledge_gaps(user_id, enrollment['class_id'])
                all_gaps.extend(gaps)
            
            # Get recent activity
            recent_queries = self.db.execute_query(
                'SELECT prompt, created_at FROM ai_queries WHERE user_id = ? ORDER BY created_at DESC LIMIT 3',
                (user_id,)
            )
            
            # Get overall performance
            metrics_cols = self._get_table_columns('student_metrics')
            if 'score_avg' in metrics_cols:
                metrics = self.db.execute_query(
                    'SELECT score_avg, rating FROM student_metrics WHERE user_id = ?',
                    (user_id,)
                )
            else:
                metrics = self.db.execute_query(
                    'SELECT quiz_score as score_avg, rating FROM student_metrics WHERE user_id = ?',
                    (user_id,)
                )
            
            avg_performance = sum(m['score_avg'] for m in metrics) / len(metrics) if metrics else 0
            
            return {
                'weak_topics': [gap['question'] for gap in all_gaps[:5]],
                'recent_queries': [q['prompt'] for q in recent_queries],
                'performance_level': 'struggling' if avg_performance < 60 else 'average' if avg_performance < 80 else 'excellent',
                'engagement': 'high' if len(recent_queries) > 5 else 'medium' if len(recent_queries) > 2 else 'low'
            }
            
        except Exception as e:
            logger.error(f"Error getting student context: {e}")
            return {
                'weak_topics': [],
                'recent_queries': [],
                'performance_level': 'unknown',
                'engagement': 'unknown'
            }
