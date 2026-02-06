import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AdaptiveEngine:
    def __init__(self, db_manager):
        self.db = db_manager

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
            
            # Update or insert metrics
            existing = self.db.execute_one(
                'SELECT user_id FROM student_metrics WHERE user_id = ? AND class_id = ?',
                (user_id, class_id)
            )
            
            if existing:
                self.db.execute_update('''
                    UPDATE student_metrics 
                    SET score_avg = ?, avg_time = ?, pace_score = ?, rating = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND class_id = ?
                ''', (score_avg, avg_time, pace_score, rating, user_id, class_id))
            else:
                self.db.execute_insert('''
                    INSERT INTO student_metrics (user_id, class_id, score_avg, avg_time, pace_score, rating)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, class_id, score_avg, avg_time, pace_score, rating))
                
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
                    answers = json.loads(gap['answers'])
                    question_id = str(gap['question_id'])
                    
                    if question_id in answers:
                        if answers[question_id] != gap['correct_option_index']:
                            weak_topics.append({
                                'quiz': gap['quiz_title'],
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
            metrics = self.db.execute_one(
                'SELECT score_avg, pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
                (user_id, class_id)
            )
            
            recommendations = []
            
            if not metrics:
                # New student - recommend starting materials
                lectures = self.db.execute_query(
                    'SELECT id, filename FROM lectures WHERE class_id = ? ORDER BY uploaded_at ASC LIMIT 3',
                    (class_id,)
                )
                for lec in lectures:
                    recommendations.append({
                        'type': 'lecture',
                        'content_id': lec['id'],
                        'title': lec['filename'],
                        'reason': 'Start with foundational materials',
                        'priority': 100
                    })
            else:
                # Struggling student - recommend review materials
                if metrics['score_avg'] < 70:
                    lectures = self.db.execute_query(
                        'SELECT id, filename FROM lectures WHERE class_id = ? ORDER BY uploaded_at ASC LIMIT 5',
                        (class_id,)
                    )
                    for lec in lectures:
                        recommendations.append({
                            'type': 'lecture',
                            'content_id': lec['id'],
                            'title': lec['filename'],
                            'reason': 'Review foundational concepts',
                            'priority': 90
                        })
                
                # Recommend practice quizzes
                quizzes = self.db.execute_query(
                    'SELECT id, title FROM quizzes WHERE class_id = ? LIMIT 3',
                    (class_id,)
                )
                for quiz in quizzes:
                    recommendations.append({
                        'type': 'quiz',
                        'content_id': quiz['id'],
                        'title': quiz['title'],
                        'reason': 'Practice makes perfect',
                        'priority': 80
                    })
            
            return recommendations[:5]
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    def check_intervention_alerts(self, user_id, class_id):
        """Check if teacher intervention is needed"""
        try:
            metrics = self.db.execute_one(
                'SELECT score_avg, pace_score, rating FROM student_metrics WHERE user_id = ? AND class_id = ?',
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
            metrics = self.db.execute_query(
                'SELECT score_avg, rating FROM student_metrics WHERE user_id = ?',
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
