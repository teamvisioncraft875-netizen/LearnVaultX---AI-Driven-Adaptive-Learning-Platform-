import logging
import json
import random
from datetime import date

logger = logging.getLogger(__name__)

class MicroLearningManager:
    def __init__(self, db_manager, adaptive_engine):
        self.db = db_manager
        self.adaptive = adaptive_engine

    def get_daily_tasks(self, student_id, class_id):
        """Get or generate daily micro-learning tasks for a student"""
        today = date.today().isoformat()
        
        # Check if tasks exist for today
        existing_task = self.db.execute_one(
            'SELECT * FROM micro_tasks WHERE student_id = ? AND class_id = ? AND task_date = ?',
            (student_id, class_id, today)
        )
        
        if existing_task:
            return self._fetch_full_task_details(existing_task['id'])
        
        # Generate new tasks
        return self._generate_new_tasks(student_id, class_id, today)

    def _generate_new_tasks(self, student_id, class_id, date_str):
        """Generate a new set of tasks based on weak topics"""
        logger.info(f"Generating micro-tasks for student {student_id}, class {class_id}")
        
        # 1. Get weak topics
        weak_topics = self.adaptive.analyze_knowledge_gaps(student_id, class_id)
        
        # Pick a topic (prioritize weak, else general)
        if weak_topics:
            primary_topic = weak_topics[0]['quiz'] # Assuming 'quiz' field holds topic/quiz title
        else:
            primary_topic = "General Revision"

        # 2. Create micro_task record
        task_id = self.db.execute_insert(
            'INSERT INTO micro_tasks (student_id, class_id, task_date, topic_tag, status) VALUES (?, ?, ?, ?, ?)',
            (student_id, class_id, date_str, primary_topic, 'PENDING')
        )

        # 3. Generate Content (Mocking content generation for now, ideally calls LLM)
        self._generate_flashcards(task_id, primary_topic)
        self._generate_coding(task_id, primary_topic)
        self._generate_quiz_booster(task_id, primary_topic)

        return self._fetch_full_task_details(task_id)

    def _generate_flashcards(self, task_id, topic):
        # Mock Content - Real implementation would use LLM
        cards = [
            ("What is a variable?", "A storage location paired with an associated symbolic name."),
            ("Explain 'int' data type.", "Integer type, stores whole numbers."),
            ("What is a loop?", "A sequence of instructions repeated until a condition is reached.")
        ]
        
        for front, back in cards:
            self.db.execute_insert(
                'INSERT INTO ml_flashcards (task_id, front, back, topic) VALUES (?, ?, ?, ?)',
                (task_id, f"{topic}: {front}", back, topic)
            )

    def _generate_coding(self, task_id, topic):
        self.db.execute_insert(
            '''INSERT INTO ml_coding (task_id, prompt, starter_code, solution_code, topic, test_case) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (task_id, 
             f"Write a function to print 'Hello {topic}'", 
             "def say_hello():\n    # Your code here\n    pass", 
             "def say_hello():\n    print('Hello World')", 
             topic, 
             "say_hello() == 'Hello World'")
        )

    def _generate_quiz_booster(self, task_id, topic):
        self.db.execute_insert(
            '''INSERT INTO ml_quiz_booster (task_id, question, options, correct_answer, topic) 
               VALUES (?, ?, ?, ?, ?)''',
            (task_id, 
             f"What is the main concept of {topic}?", 
             json.dumps(["Abstraction", "Iteration", "Compilation", "None"]), 
             "Iteration", 
             topic)
        )

    def _fetch_full_task_details(self, task_id):
        """Fetch all related items for a task"""
        task = self.db.execute_one('SELECT * FROM micro_tasks WHERE id = ?', (task_id,))
        if not task:
            return None
            
        flashcards = self.db.execute_query('SELECT * FROM ml_flashcards WHERE task_id = ?', (task_id,))
        coding = self.db.execute_query('SELECT * FROM ml_coding WHERE task_id = ?', (task_id,))
        quiz = self.db.execute_query('SELECT * FROM ml_quiz_booster WHERE task_id = ?', (task_id,))
        
        # Calculate completion
        total_items = len(flashcards) + len(coding) + len(quiz)
        completed_items = sum(1 for x in flashcards if x['is_completed']) + \
                          sum(1 for x in coding if x['is_completed']) + \
                          sum(1 for x in quiz if x['is_completed'])
        
        return {
            'meta': dict(task),
            'flashcards': [dict(x) for x in flashcards],
            'coding': [dict(x) for x in coding],
            'quiz': [dict(x) for x in quiz],
            'stats': {
                'total': total_items,
                'completed': completed_items,
                'percent': int((completed_items / total_items * 100) if total_items > 0 else 0)
            }
        }

    def mark_completed(self, item_type, item_id, task_id):
        """Mark a specific item as completed and update overall progress"""
        table_map = {
            'flashcard': 'ml_flashcards',
            'coding': 'ml_coding',
            'quiz': 'ml_quiz_booster'
        }
        
        table = table_map.get(item_type)
        if not table:
            return False
            
        # Update Item
        self.db.execute_update(f'UPDATE {table} SET is_completed = 1 WHERE id = ?', (item_id,))
        
        # Update Main Task Progress
        details = self._fetch_full_task_details(task_id)
        if details:
            progress = details['stats']['percent']
            status = 'COMPLETED' if progress == 100 else 'PENDING'
            self.db.execute_update(
                'UPDATE micro_tasks SET progress = ?, status = ? WHERE id = ?',
                (progress, status, task_id)
            )
            return True
        return False
