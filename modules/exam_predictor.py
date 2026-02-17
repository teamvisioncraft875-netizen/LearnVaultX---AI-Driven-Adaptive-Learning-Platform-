"""
ExamPredictor — AI-powered exam score prediction engine.
Uses quiz history, weak topics, and score trends to predict student performance.
"""
import json
import logging
import math
from datetime import datetime

logger = logging.getLogger(__name__)


class ExamPredictor:
    def __init__(self, db):
        self.db = db

    # ─── PUBLIC API ───────────────────────────────────────────

    def generate_prediction(self, student_id):
        """Generate a new exam prediction for the student and store it."""
        try:
            # 1. Get all quiz submissions
            submissions = self.db.execute_query(
                '''SELECT qs.score, qs.total, qs.submitted_at,
                          q.title as quiz_title, q.class_id, c.title as class_name
                   FROM quiz_submissions qs
                   JOIN quizzes q ON qs.quiz_id = q.id
                   JOIN classes c ON q.class_id = c.id
                   WHERE qs.student_id = ?
                   ORDER BY qs.submitted_at ASC''',
                (student_id,)
            )

            if not submissions or len(submissions) == 0:
                return self._empty_prediction(student_id)

            # 2. Calculate scores list
            scores = []
            for s in submissions:
                pct = round((s['score'] / s['total']) * 100, 1) if s['total'] > 0 else 0
                scores.append({
                    'score': pct,
                    'quiz_title': s['quiz_title'],
                    'class_name': s['class_name'],
                    'class_id': s['class_id'],
                    'submitted_at': s['submitted_at']
                })

            # 3. Weighted average (recent quizzes count more)
            predicted_score = self._weighted_average(scores)

            # 4. Trend analysis
            trend = self._calculate_trend([s['score'] for s in scores])

            # 5. Apply trend bonus/penalty
            if trend == 'improving':
                predicted_score = min(100, predicted_score + 3)
            elif trend == 'declining':
                predicted_score = max(0, predicted_score - 3)

            predicted_score = round(predicted_score, 1)

            # 6. CGPA chance (8+ = 80%+ scoring equivalent)
            cgpa_chance = self._calculate_cgpa_chance(predicted_score, scores)

            # 7. Weak topics
            weak_topics = self._identify_weak_topics(student_id)

            # 8. Suggestions
            suggestions = self._generate_suggestions(weak_topics, predicted_score, trend, scores)

            # 9. Save prediction
            prediction = {
                'student_id': student_id,
                'predicted_score': predicted_score,
                'cgpa_chance': cgpa_chance,
                'weak_topics': weak_topics,
                'suggestions': suggestions,
                'trend_direction': trend,
                'quiz_count_used': len(submissions)
            }

            self.db.execute_insert(
                '''INSERT INTO exam_predictions
                   (student_id, predicted_score, cgpa_chance, weak_topics, suggestions, trend_direction, quiz_count_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (student_id, predicted_score, cgpa_chance,
                 json.dumps(weak_topics), json.dumps(suggestions),
                 trend, len(submissions))
            )

            return prediction

        except Exception as e:
            logger.error(f"Prediction generation failed for student {student_id}: {e}")
            return self._empty_prediction(student_id)

    def get_latest_prediction(self, student_id):
        """Get the most recent prediction for a student."""
        try:
            row = self.db.execute_one(
                '''SELECT * FROM exam_predictions
                   WHERE student_id = ?
                   ORDER BY created_at DESC LIMIT 1''',
                (student_id,)
            )
            if not row:
                # Auto-generate if none exists
                return self.generate_prediction(student_id)

            return {
                'student_id': student_id,
                'predicted_score': row['predicted_score'],
                'cgpa_chance': row['cgpa_chance'],
                'weak_topics': json.loads(row['weak_topics']) if isinstance(row['weak_topics'], str) else row['weak_topics'],
                'suggestions': json.loads(row['suggestions']) if isinstance(row['suggestions'], str) else row['suggestions'],
                'trend_direction': row['trend_direction'],
                'quiz_count_used': row['quiz_count_used'],
                'created_at': row['created_at']
            }
        except Exception as e:
            logger.error(f"Error fetching latest prediction: {e}")
            return self._empty_prediction(student_id)

    # ─── CORE ALGORITHMS ──────────────────────────────────────

    def _weighted_average(self, scores):
        """Compute exponentially weighted average — recent quizzes matter more."""
        if not scores:
            return 0

        n = len(scores)
        total_weight = 0
        weighted_sum = 0

        for i, s in enumerate(scores):
            # Exponential weight: later quizzes get higher weight
            weight = math.exp(0.3 * (i - n + 1))  # ranges from ~0.05 for oldest to 1.0 for newest
            weighted_sum += s['score'] * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0

    def _calculate_trend(self, scores):
        """Analyze the last 5 scores to determine trend direction."""
        if len(scores) < 2:
            return 'stable'

        recent = scores[-5:]  # Last 5
        n = len(recent)

        # Simple linear regression slope
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n

        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 'stable'

        slope = numerator / denominator

        if slope > 2:
            return 'improving'
        elif slope < -2:
            return 'declining'
        return 'stable'

    def _calculate_cgpa_chance(self, predicted_score, scores):
        """Calculate probability of achieving 8+ CGPA (mapped to 80%+ exam score)."""
        if not scores:
            return 0

        # Base chance from predicted score
        if predicted_score >= 90:
            base_chance = 92
        elif predicted_score >= 80:
            base_chance = 75
        elif predicted_score >= 70:
            base_chance = 50
        elif predicted_score >= 60:
            base_chance = 30
        elif predicted_score >= 50:
            base_chance = 15
        else:
            base_chance = 5

        # Consistency bonus: low variance = more predictable = higher chance
        score_values = [s['score'] for s in scores]
        if len(score_values) >= 3:
            mean = sum(score_values) / len(score_values)
            variance = sum((x - mean) ** 2 for x in score_values) / len(score_values)
            std_dev = math.sqrt(variance)

            if std_dev < 5:
                base_chance = min(100, base_chance + 5)  # Very consistent
            elif std_dev > 20:
                base_chance = max(0, base_chance - 8)  # Very inconsistent

        # Count of high scores bonus
        high_score_ratio = sum(1 for s in scores if s['score'] >= 80) / len(scores)
        if high_score_ratio > 0.6:
            base_chance = min(100, base_chance + 5)

        return round(min(100, max(0, base_chance)), 1)

    def _identify_weak_topics(self, student_id):
        """Identify topics where the student scores below 60%."""
        try:
            topic_data = self.db.execute_query(
                '''SELECT q.title as topic, c.title as class_name,
                          AVG(CAST(qs.score AS FLOAT) / NULLIF(qs.total, 0) * 100) as avg_score,
                          COUNT(*) as attempts
                   FROM quiz_submissions qs
                   JOIN quizzes q ON qs.quiz_id = q.id
                   JOIN classes c ON q.class_id = c.id
                   WHERE qs.student_id = ?
                   GROUP BY q.title
                   ORDER BY avg_score ASC''',
                (student_id,)
            )

            weak = []
            for t in topic_data:
                if t['avg_score'] < 60:
                    weak.append({
                        'topic': t['topic'],
                        'class': t['class_name'],
                        'avg_score': round(t['avg_score'], 1),
                        'attempts': t['attempts']
                    })

            return weak[:5]  # Top 5 weakest
        except Exception as e:
            logger.error(f"Weak topic identification failed: {e}")
            return []

    def _generate_suggestions(self, weak_topics, predicted_score, trend, scores):
        """Generate actionable improvement suggestions."""
        suggestions = []

        # Score-based suggestions
        if predicted_score < 50:
            suggestions.append({
                'icon': '🚨',
                'text': 'Focus on fundamentals — review lecture notes before attempting quizzes',
                'priority': 'high'
            })
        elif predicted_score < 70:
            suggestions.append({
                'icon': '📖',
                'text': 'Practice more quizzes to strengthen medium-difficulty topics',
                'priority': 'medium'
            })
        else:
            suggestions.append({
                'icon': '🎯',
                'text': 'You\'re on track! Focus on mastering advanced topics for an edge',
                'priority': 'low'
            })

        # Trend-based
        if trend == 'declining':
            suggestions.append({
                'icon': '⚠️',
                'text': 'Your recent scores are dropping — revisit recent topics and take breaks to avoid burnout',
                'priority': 'high'
            })
        elif trend == 'improving':
            suggestions.append({
                'icon': '🔥',
                'text': 'Great momentum! Keep your current study rhythm going',
                'priority': 'low'
            })

        # Weak topic suggestions
        if weak_topics:
            topic_names = ', '.join(t['topic'] for t in weak_topics[:3])
            suggestions.append({
                'icon': '📚',
                'text': f'Prioritize revising: {topic_names}',
                'priority': 'high'
            })

        # Consistency suggestion
        if len(scores) >= 3:
            score_vals = [s['score'] for s in scores[-5:]]
            mean = sum(score_vals) / len(score_vals)
            variance = sum((x - mean) ** 2 for x in score_vals) / len(score_vals)
            if math.sqrt(variance) > 15:
                suggestions.append({
                    'icon': '📊',
                    'text': 'Your scores vary a lot — aim for consistent daily study sessions',
                    'priority': 'medium'
                })

        # Volume suggestion
        if len(scores) < 5:
            suggestions.append({
                'icon': '📝',
                'text': 'Take more quizzes to improve prediction accuracy',
                'priority': 'medium'
            })

        return suggestions[:5]

    def _empty_prediction(self, student_id):
        """Return a default prediction when no data is available."""
        return {
            'student_id': student_id,
            'predicted_score': 0,
            'cgpa_chance': 0,
            'weak_topics': [],
            'suggestions': [{
                'icon': '📝',
                'text': 'Complete your first quiz to get a prediction!',
                'priority': 'medium'
            }],
            'trend_direction': 'stable',
            'quiz_count_used': 0,
            'created_at': None
        }
