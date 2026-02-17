
import logging
from modules.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class BadgeService:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_quiz_badges(self, user_id, quiz_id, score, total):
        """Check and award badges for quiz performance"""
        awarded = []
        
        # Perfect Score Badge
        if score == total and total > 0:
            badge = self._award_badge(user_id, 'perfect_score', 'Perfect Score', 'Got 100% on a quiz!', '🏆')
            if badge: awarded.append(badge)

        # First Quiz Badge
        count = self.db.execute_one('SELECT COUNT(*) as count FROM quiz_submissions WHERE student_id = ?', (user_id,))['count']
        if count == 1:
             badge = self._award_badge(user_id, 'first_quiz', 'First Steps', 'Completed your first quiz!', '🚀')
             if badge: awarded.append(badge)

        return awarded

    def check_module_completion(self, user_id, class_id):
        """Check if all quizzes in a class are completed and award badge"""
        try:
            # Get total quizzes for class
            total_quizzes = self.db.execute_one(
                'SELECT COUNT(*) as count FROM quizzes WHERE class_id = ?', 
                (class_id,)
            )['count']
            
            if total_quizzes == 0:
                return None

            # Get unique quizzes attempted by student
            attempted_quizzes = self.db.execute_one(
                'SELECT COUNT(DISTINCT quiz_id) as count FROM quiz_submissions qs JOIN quizzes q ON qs.quiz_id = q.id WHERE qs.student_id = ? AND q.class_id = ?',
                (user_id, class_id)
            )['count']

            if attempted_quizzes >= total_quizzes:
                return self._award_badge(
                    user_id, 
                    f'course_complete_{class_id}', 
                    'Course Completed', 
                    'Completed all quizzes in the course!', 
                    '🎓'
                )
        except Exception as e:
            logger.error(f"Error check_module_completion: {e}")
        return None

    def _award_badge(self, user_id, code, title, description, icon):
        try:
            # Check if already awarded
            existing = self.db.execute_one('SELECT id FROM user_badges WHERE user_id = ? AND badge_code = ?', (user_id, code))
            if existing:
                return None

            self.db.execute_insert(
                'INSERT INTO user_badges (user_id, badge_code, title, description, icon) VALUES (?, ?, ?, ?, ?)',
                (user_id, code, title, description, icon)
            )
            logger.info(f"Badge awarded to user {user_id}: {title}")
            return {'title': title, 'description': description, 'icon': icon}
        except Exception as e:
            logger.error(f"Error awarding badge {code}: {e}")
            return None
