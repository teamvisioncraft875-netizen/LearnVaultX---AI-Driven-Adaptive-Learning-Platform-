import logging
import json

logger = logging.getLogger(__name__)

class LearningPathService:
    def __init__(self, db_manager, adaptive_engine=None):
        self.db = db_manager
        self.adaptive = adaptive_engine

    def get_subject_modules(self, class_id, user_id):
        """
        Get all modules for a subject (class), including their locked/unlocked status 
        and progress for a specific student.
        """
        try:
            # Fetch all modules for the class
            modules = self.db.execute_query(
                "SELECT * FROM learning_modules WHERE class_id = ? ORDER BY order_index ASC", 
                (class_id,)
            )
            
            if not modules:
                return []

            # Fetch student progress for these modules
            progress_records = self.db.execute_query(
                "SELECT * FROM student_module_progress WHERE user_id = ? AND module_id IN (SELECT id FROM learning_modules WHERE class_id = ?)",
                (user_id, class_id)
            )
            
            # Map progress by module_id
            progress_map = {row['module_id']: row for row in progress_records}
            
            # Fetch Knowledge Gaps
            gaps = []
            gap_quiz_ids = set()
            if self.adaptive:
                try:
                    gaps = self.adaptive.analyze_knowledge_gaps(user_id, class_id)
                    gap_quiz_ids = {gap['quiz_id'] for gap in gaps if 'quiz_id' in gap}
                except Exception as e:
                    logger.error(f"Error fetching gaps in learning path: {e}")

            result = []
            previous_module_completed = True # Module 1 is always unlocked potentially, or strict logic
            
            for index, mod in enumerate(modules):
                mod_id = mod['id']
                prog = progress_map.get(mod_id)
                
                # Determine status
                if prog:
                    status = prog['status']
                    completion = prog['completion_percent']
                    score = prog['quiz_score_avg']
                else:
                    # If no record exists yet
                    if index == 0:
                        status = 'UNLOCKED' # First module is always unlocked
                    elif previous_module_completed: 
                         # If previous was completed, unlocked
                         status = 'LOCKED'
                    else:
                        status = 'LOCKED'
                    completion = 0
                    score = 0
                
                if index == 0 and not prog:
                    status = 'UNLOCKED'
                
                # Fetch linked quiz
                quiz_row = self.db.execute_one("SELECT id FROM quizzes WHERE module_id = ? LIMIT 1", (mod_id,))
                quiz_id = quiz_row['id'] if quiz_row else None

                # Check for gaps
                needs_revision = False
                revision_reason = ""
                if quiz_id and quiz_id in gap_quiz_ids:
                    needs_revision = True
                    revision_reason = "Weak Topic Detected"

                mod_data = {
                    'id': mod['id'],
                    'title': mod['title'],
                    'description': mod['description'],
                    'order_index': mod['order_index'],
                    'status': status,
                    'completion_percent': completion,
                    'last_score': score,
                    'is_locked': status == 'LOCKED',
                    'quiz_id': quiz_id,
                    'needs_revision': needs_revision,
                    'revision_reason': revision_reason
                }
                
                result.append(mod_data)
                
                if status == 'COMPLETED':
                    previous_module_completed = True
                else:
                    previous_module_completed = False
            
            return result

        except Exception as e:
            logger.error(f"Error fetching learning path: {e}")
            return []

    def get_next_recommended_action(self, class_id, user_id):
        """
        Identify the next unfinished module and return a CTA.
        """
        modules = self.get_subject_modules(class_id, user_id)
        for mod in modules:
            if mod['status'] == 'IN_PROGRESS' or mod['status'] == 'UNLOCKED':
                return {
                    'module_id': mod['id'],
                    'title': mod['title'],
                    'message': f"Complete {mod['title']} to unlock the next module.",
                    'action': 'Start Quiz' # simplified
                }
        
        return None

    def update_module_progress(self, user_id, class_id, quiz_score, quiz_id):
        """
        Update progress when a quiz is submitted.
        If score >= 70%, mark module as COMPLETED and UNLOCK next module.
        """
        try:
            # Find which module this quiz belongs to
            quiz = self.db.execute_one("SELECT module_id FROM quizzes WHERE id = ?", (quiz_id,))
            if not quiz or not quiz['module_id']:
                logger.warning(f"Quiz {quiz_id} not linked to any module.")
                return

            module_id = quiz['module_id']
            
            # Check existing progress
            progress = self.db.execute_one(
                "SELECT * FROM student_module_progress WHERE user_id = ? AND module_id = ?",
                (user_id, module_id)
            )
            
            # Determine new status
            passed = quiz_score >= 70
            new_status = 'COMPLETED' if passed else 'IN_PROGRESS'
            completion_percent = 100 if passed else max(quiz_score, progress['completion_percent'] if progress else 0) # Simple logic: score = completion for now
            
            if progress:
                attempts = progress['attempts_count'] + 1
                # Only update status if it's an improvement (don't lock if already completed?)
                # Actually, in LMS, once completed, it stays completed usually.
                current_status = progress['status']
                if current_status == 'COMPLETED':
                    new_status = 'COMPLETED' 
                
                self.db.execute_update(
                    """
                    UPDATE student_module_progress 
                    SET completion_percent = ?, quiz_score_avg = ?, status = ?, attempts_count = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (completion_percent, quiz_score, new_status, attempts, progress['id'])
                )
            else:
                self.db.execute_insert(
                    """
                    INSERT INTO student_module_progress (user_id, module_id, status, completion_percent, quiz_score_avg, attempts_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, module_id, new_status, completion_percent, quiz_score, 1)
                )

            # Unlock NEXT module if passed
            if new_status == 'COMPLETED':
                self._unlock_next_module(user_id, class_id, module_id)

        except Exception as e:
            logger.error(f"Error updating module progress: {e}")

    def _unlock_next_module(self, user_id, class_id, current_module_id):
        """
        Find the next module in order and set its status to UNLOCKED if it doesn't exist or is LOCKED.
        """
        try:
            current_mod = self.db.execute_one("SELECT order_index FROM learning_modules WHERE id = ?", (current_module_id,))
            if not current_mod: 
                return

            next_order = current_mod['order_index'] + 1
            next_mod = self.db.execute_one(
                "SELECT id FROM learning_modules WHERE class_id = ? AND order_index = ?", 
                (class_id, next_order)
            )
            
            if next_mod:
                # Check if record exists
                next_progress = self.db.execute_one(
                    "SELECT id, status FROM student_module_progress WHERE user_id = ? AND module_id = ?",
                    (user_id, next_mod['id'])
                )
                
                if next_progress:
                    if next_progress['status'] == 'LOCKED':
                        self.db.execute_update(
                            "UPDATE student_module_progress SET status = 'UNLOCKED' WHERE id = ?",
                            (next_progress['id'],)
                        )
                else:
                    # Create new UNLOCKED record
                    self.db.execute_insert(
                        """
                        INSERT INTO student_module_progress (user_id, module_id, status, completion_percent) 
                        VALUES (?, ?, 'UNLOCKED', 0)
                        """,
                        (user_id, next_mod['id'])
                    )
                logger.info(f"Unlocked module {next_mod['id']} for user {user_id}")

        except Exception as e:
            logger.error(f"Error unlocking next module: {e}")
