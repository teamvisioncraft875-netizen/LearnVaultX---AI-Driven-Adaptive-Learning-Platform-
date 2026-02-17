"""
LeaderboardEngine — Computes and maintains class leaderboards.
Composite score = 60% avg_score + 25% quiz_completion_ratio + 15% efficiency.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LeaderboardEngine:
    def __init__(self, db):
        self.db = db

    # ─── PUBLIC API ───────────────────────────────────────────

    def recalculate_class(self, class_id):
        """Recalculate leaderboard for an entire class. Called after quiz submission."""
        try:
            # Get all students enrolled in this class
            students = self.db.execute_query(
                'SELECT student_id FROM enrollments WHERE class_id = ?',
                (class_id,)
            )
            if not students:
                return

            # Total quizzes in class
            total_quizzes = self.db.execute_one(
                'SELECT COUNT(*) as cnt FROM quizzes WHERE class_id = ?',
                (class_id,)
            )['cnt'] or 1

            entries = []
            for s in students:
                sid = s['student_id']
                stats = self.db.execute_one(
                    '''SELECT COUNT(*) as quizzes_done,
                              COALESCE(SUM(score), 0) as total_correct,
                              COALESCE(SUM(total), 0) as total_questions,
                              COALESCE(AVG(CAST(score AS FLOAT) / NULLIF(total, 0) * 100), 0) as avg_score
                       FROM quiz_submissions qs
                       JOIN quizzes q ON qs.quiz_id = q.id
                       WHERE qs.student_id = ? AND q.class_id = ?''',
                    (sid, class_id)
                )

                avg_score = round(stats['avg_score'], 1) if stats['avg_score'] else 0
                quizzes_done = stats['quizzes_done'] or 0
                total_correct = stats['total_correct'] or 0
                total_questions = stats['total_questions'] or 0

                # Quiz completion ratio (0-100)
                completion_ratio = min(100, (quizzes_done / total_quizzes) * 100)

                # Efficiency = correct/total * 100 (accuracy across all attempts)
                efficiency = (total_correct / total_questions * 100) if total_questions > 0 else 0

                # Composite: 60% avg + 25% completion + 15% efficiency
                composite = round(0.60 * avg_score + 0.25 * completion_ratio + 0.15 * efficiency, 2)

                entries.append({
                    'student_id': sid,
                    'avg_score': avg_score,
                    'quizzes_completed': quizzes_done,
                    'total_correct': total_correct,
                    'total_questions': total_questions,
                    'efficiency': round(efficiency, 1),
                    'composite': composite
                })

            # Sort by composite descending
            entries.sort(key=lambda x: x['composite'], reverse=True)

            # Upsert each entry with rank
            for rank, e in enumerate(entries, 1):
                self.db.execute_insert(
                    '''INSERT INTO leaderboard_scores
                       (student_id, class_id, avg_score, quizzes_completed, total_correct,
                        total_questions, efficiency_score, composite_score, rank_position, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(student_id, class_id) DO UPDATE SET
                        avg_score = excluded.avg_score,
                        quizzes_completed = excluded.quizzes_completed,
                        total_correct = excluded.total_correct,
                        total_questions = excluded.total_questions,
                        efficiency_score = excluded.efficiency_score,
                        composite_score = excluded.composite_score,
                        rank_position = excluded.rank_position,
                        updated_at = CURRENT_TIMESTAMP''',
                    (e['student_id'], class_id, e['avg_score'], e['quizzes_completed'],
                     e['total_correct'], e['total_questions'], e['efficiency'],
                     e['composite'], rank)
                )

            logger.info(f"Leaderboard recalculated for class {class_id}: {len(entries)} students")

        except Exception as ex:
            logger.error(f"Leaderboard recalculation failed for class {class_id}: {ex}")

    def get_class_leaderboard(self, class_id, limit=10):
        """Get top N students for a class leaderboard."""
        try:
            rows = self.db.execute_query(
                '''SELECT lb.*, u.name, u.email
                   FROM leaderboard_scores lb
                   JOIN users u ON lb.student_id = u.id
                   WHERE lb.class_id = ? AND lb.quizzes_completed > 0
                   ORDER BY lb.composite_score DESC
                   LIMIT ?''',
                (class_id, limit)
            )

            result = []
            for i, r in enumerate(rows, 1):
                result.append({
                    'rank': i,
                    'name': r['name'] or 'Student',
                    'email': self._mask_email(r['email'] or ''),
                    'avg_score': r['avg_score'],
                    'quizzes_completed': r['quizzes_completed'],
                    'efficiency': r['efficiency_score'],
                    'composite_score': r['composite_score'],
                    'badge': self._get_badge(i)
                })

            return result

        except Exception as ex:
            logger.error(f"Error fetching class leaderboard: {ex}")
            return []

    def get_global_leaderboard(self, limit=10):
        """Get top students across all classes (for teacher analytics)."""
        try:
            rows = self.db.execute_query(
                '''SELECT u.name, u.email,
                          COUNT(DISTINCT qs.quiz_id) as quizzes_completed,
                          COALESCE(AVG(CAST(qs.score AS FLOAT) / NULLIF(qs.total, 0) * 100), 0) as avg_score,
                          COALESCE(SUM(qs.score), 0) as total_correct,
                          COALESCE(SUM(qs.total), 0) as total_questions
                   FROM quiz_submissions qs
                   JOIN users u ON qs.student_id = u.id
                   GROUP BY qs.student_id
                   HAVING quizzes_completed > 0
                   ORDER BY avg_score DESC
                   LIMIT ?''',
                (limit,)
            )

            result = []
            for i, r in enumerate(rows, 1):
                efficiency = (r['total_correct'] / r['total_questions'] * 100) if r['total_questions'] > 0 else 0
                result.append({
                    'rank': i,
                    'name': r['name'] or 'Student',
                    'email': self._mask_email(r['email'] or ''),
                    'avg_score': round(r['avg_score'], 1),
                    'quizzes_completed': r['quizzes_completed'],
                    'efficiency': round(efficiency, 1),
                    'badge': self._get_badge(i)
                })

            return result

        except Exception as ex:
            logger.error(f"Error fetching global leaderboard: {ex}")
            return []

    # ─── HELPERS ──────────────────────────────────────────────

    @staticmethod
    def _mask_email(email):
        """Mask email for privacy: j***@gmail.com"""
        if not email or '@' not in email:
            return '***@***'
        local, domain = email.split('@', 1)
        if len(local) <= 1:
            masked = '*'
        else:
            masked = local[0] + '***'
        return f"{masked}@{domain}"

    @staticmethod
    def _get_badge(rank):
        """Return badge emoji for top 3."""
        badges = {1: '🥇', 2: '🥈', 3: '🥉'}
        return badges.get(rank, '')
