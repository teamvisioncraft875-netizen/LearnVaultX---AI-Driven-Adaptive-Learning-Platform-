import logging
import json
import random
from datetime import date

logger = logging.getLogger(__name__)


class MicroLearningManager:
    def __init__(self, db_manager, adaptive_engine, kyknox=None):
        self.db = db_manager
        self.adaptive = adaptive_engine
        self.kyknox = kyknox

    def get_daily_tasks(self, student_id, class_id, class_title='General'):
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
        return self._generate_new_tasks(student_id, class_id, today, class_title)

    def _generate_new_tasks(self, student_id, class_id, date_str, class_title='General'):
        """Generate a new set of tasks based on weak topics"""
        logger.info(f"Generating micro-tasks for student {student_id}, class {class_id}")

        # 1. Get weak topics
        weak_topics = self.adaptive.analyze_knowledge_gaps(student_id, class_id)

        # Pick a topic (prioritize weak, else general)
        if weak_topics:
            primary_topic = weak_topics[0]['quiz']  # Assuming 'quiz' field holds topic/quiz title
        else:
            primary_topic = "General Revision"

        # Count previous attempts to vary content
        attempt_count = self.db.execute_one(
            'SELECT COUNT(*) as cnt FROM micro_tasks WHERE student_id = ? AND class_id = ?',
            (student_id, class_id)
        )
        attempt_num = (attempt_count['cnt'] if attempt_count else 0) + 1

        # 2. Create micro_task record
        task_id = self.db.execute_insert(
            'INSERT INTO micro_tasks (student_id, class_id, task_date, topic_tag, status) VALUES (?, ?, ?, ?, ?)',
            (student_id, class_id, date_str, primary_topic, 'PENDING')
        )

        # 3. Generate Content (AI-powered or fallback)
        self._generate_flashcards(task_id, primary_topic, class_title, attempt_num)
        self._generate_coding(task_id, primary_topic, class_title, attempt_num)
        self._generate_quiz_booster(task_id, primary_topic, class_title, attempt_num)

        return self._fetch_full_task_details(task_id)

    # ─── AI Flashcard Generation ────────────────────────────────────────

    def _generate_flashcards(self, task_id, topic, class_title='General', attempt_num=1):
        """Generate flashcards using AI, with topic-aware fallbacks"""
        cards = None

        if self.kyknox:
            try:
                cards = self._ai_generate_flashcards(topic, class_title, attempt_num)
            except Exception as e:
                logger.error(f"AI flashcard generation failed: {e}")

        if not cards or len(cards) < 3:
            cards = self._fallback_flashcards(topic, class_title, attempt_num)

        for front, back in cards[:3]:
            self.db.execute_insert(
                'INSERT INTO ml_flashcards (task_id, front, back, topic) VALUES (?, ?, ?, ?)',
                (task_id, front, back, topic)
            )

    def _ai_generate_flashcards(self, topic, class_title, attempt_num):
        """Use KyKnoX AI to generate flashcards"""
        prompt = f"""Generate exactly 3 study flashcards for the subject "{class_title}", focusing on the topic "{topic}".
This is attempt #{attempt_num}, so generate completely fresh and unique questions different from basic/obvious ones.

CRITICAL: Return ONLY a valid JSON array. No markdown, no code blocks, no extra text.

Each object MUST have:
- "front": string (the question or concept to test)
- "back": string (the answer or explanation, 1-2 sentences)

Example format:
[{{"front":"What is Newton's Third Law?","back":"For every action, there is an equal and opposite reaction."}}]

Make the questions specific to {class_title} and academically accurate.
Return ONLY the JSON array."""

        response_text, provider = self.kyknox.generate_response(
            prompt, mode='expert', context=None, role='student'
        )

        return self._parse_flashcard_response(response_text)

    def _parse_flashcard_response(self, response_text):
        """Parse AI response into flashcard tuples"""
        if not response_text:
            return []

        text = response_text.strip()
        # Remove markdown code blocks
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx == -1 or end_idx == -1:
            return []

        try:
            items = json.loads(text[start_idx:end_idx + 1])
            cards = []
            for item in items:
                if isinstance(item, dict) and item.get('front') and item.get('back'):
                    cards.append((str(item['front']), str(item['back'])))
            return cards
        except json.JSONDecodeError:
            return []

    def _fallback_flashcards(self, topic, class_title, attempt_num):
        """Topic-aware fallback flashcards when AI is unavailable"""
        # Varied fallback pools based on attempt number for diversity
        pools = [
            [
                (f"What is the core principle behind {topic} in {class_title}?",
                 f"The core principle involves understanding the fundamental rules and relationships that govern {topic}."),
                (f"Name two real-world applications of {topic}.",
                 f"{topic} is applied in engineering, technology, and scientific research to solve practical problems."),
                (f"What is the most common mistake students make when studying {topic}?",
                 f"Students often confuse related concepts or skip foundational steps needed to understand {topic}.")
            ],
            [
                (f"How does {topic} connect to other areas in {class_title}?",
                 f"{topic} builds on foundational concepts and connects to advanced topics throughout {class_title}."),
                (f"Explain the key formula or rule in {topic}.",
                 f"The key rules in {topic} define how quantities relate and are used to solve problems step by step."),
                (f"Why is {topic} important for exams?",
                 f"{topic} is frequently tested because it demonstrates a student's understanding of core {class_title} concepts.")
            ],
            [
                (f"What are the sub-topics within {topic}?",
                 f"{topic} has several sub-areas that each cover specific aspects of the broader concept."),
                (f"How would you explain {topic} to a beginner?",
                 f"Start with the basic definitions, then show how simple examples illustrate the key ideas of {topic}."),
                (f"What prerequisite knowledge is needed for {topic}?",
                 f"Understanding basic {class_title} fundamentals is essential before diving deep into {topic}.")
            ]
        ]
        pool_index = (attempt_num - 1) % len(pools)
        return pools[pool_index]

    # ─── AI Coding Challenge Generation ─────────────────────────────────

    def _generate_coding(self, task_id, topic, class_title='General', attempt_num=1):
        """Generate a coding challenge using AI"""
        coding = None

        if self.kyknox:
            try:
                coding = self._ai_generate_coding(topic, class_title, attempt_num)
            except Exception as e:
                logger.error(f"AI coding generation failed: {e}")

        if not coding:
            coding = self._fallback_coding(topic, class_title, attempt_num)

        self.db.execute_insert(
            '''INSERT INTO ml_coding (task_id, prompt, starter_code, solution_code, topic, test_case) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (task_id, coding['prompt'], coding['starter_code'],
             coding['solution_code'], topic, coding['test_case'])
        )

    def _ai_generate_coding(self, topic, class_title, attempt_num):
        """Use KyKnoX AI to generate a coding challenge"""
        prompt = f"""Generate 1 coding challenge related to the subject "{class_title}", topic "{topic}".
This is attempt #{attempt_num}, so make it unique and different from basic examples.

CRITICAL: Return ONLY a valid JSON object. No markdown, no code blocks, no extra text.

The object MUST have these exact keys:
- "prompt": string (the challenge description, 1-2 sentences)
- "starter_code": string (Python starter code with function signature and comments)
- "solution_code": string (complete working Python solution)
- "test_case": string (a simple assert or comparison to verify the solution)

Make it relevant to {class_title} concepts.
Return ONLY the JSON object."""

        response_text, provider = self.kyknox.generate_response(
            prompt, mode='expert', context=None, role='student'
        )

        return self._parse_coding_response(response_text)

    def _parse_coding_response(self, response_text):
        """Parse AI coding challenge response"""
        if not response_text:
            return None

        text = response_text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx == -1 or end_idx == -1:
            return None

        try:
            obj = json.loads(text[start_idx:end_idx + 1])
            if obj.get('prompt') and obj.get('starter_code'):
                return {
                    'prompt': str(obj['prompt']),
                    'starter_code': str(obj.get('starter_code', 'def solve():\n    pass')),
                    'solution_code': str(obj.get('solution_code', 'def solve():\n    pass')),
                    'test_case': str(obj.get('test_case', 'True'))
                }
        except json.JSONDecodeError:
            pass
        return None

    def _fallback_coding(self, topic, class_title, attempt_num):
        """Topic-aware fallback coding challenge"""
        challenges = [
            {
                'prompt': f"Write a function that takes a concept from {topic} and returns a brief definition as a string.",
                'starter_code': f"def define_concept(concept_name):\n    # Return a definition for the given {topic} concept\n    pass",
                'solution_code': f"def define_concept(concept_name):\n    return f'{{concept_name}} is a key concept in {topic}'",
                'test_case': "define_concept('test') is not None"
            },
            {
                'prompt': f"Write a function that calculates a score percentage given correct and total answers for a {class_title} quiz.",
                'starter_code': "def calculate_score(correct, total):\n    # Return the percentage score\n    pass",
                'solution_code': "def calculate_score(correct, total):\n    if total == 0:\n        return 0\n    return round((correct / total) * 100, 1)",
                'test_case': "calculate_score(8, 10) == 80.0"
            },
            {
                'prompt': f"Write a function that categorizes a {class_title} score into 'Excellent', 'Good', 'Average', or 'Needs Improvement'.",
                'starter_code': "def categorize_score(percentage):\n    # Return category based on percentage\n    pass",
                'solution_code': "def categorize_score(percentage):\n    if percentage >= 90:\n        return 'Excellent'\n    elif percentage >= 70:\n        return 'Good'\n    elif percentage >= 50:\n        return 'Average'\n    return 'Needs Improvement'",
                'test_case': "categorize_score(85) == 'Good'"
            }
        ]
        return challenges[(attempt_num - 1) % len(challenges)]

    # ─── AI Quiz Booster Generation ─────────────────────────────────────

    def _generate_quiz_booster(self, task_id, topic, class_title='General', attempt_num=1):
        """Generate a quiz booster question using AI"""
        quiz = None

        if self.kyknox:
            try:
                quiz = self._ai_generate_quiz(topic, class_title, attempt_num)
            except Exception as e:
                logger.error(f"AI quiz booster generation failed: {e}")

        if not quiz:
            quiz = self._fallback_quiz(topic, class_title, attempt_num)

        self.db.execute_insert(
            '''INSERT INTO ml_quiz_booster (task_id, question, options, correct_answer, topic) 
               VALUES (?, ?, ?, ?, ?)''',
            (task_id, quiz['question'], json.dumps(quiz['options']),
             quiz['correct_answer'], topic)
        )

    def _ai_generate_quiz(self, topic, class_title, attempt_num):
        """Use KyKnoX AI to generate a quiz question"""
        prompt = f"""Generate exactly 1 multiple-choice question for the subject "{class_title}", topic "{topic}".
This is attempt #{attempt_num}, so make it unique and different from common/basic questions.

CRITICAL: Return ONLY a valid JSON object. No markdown, no code blocks, no extra text.

The object MUST have:
- "question": string (the question text)
- "options": array of exactly 4 strings (answer choices)
- "correct_answer": string (the correct option, must match one of the options exactly)

Make the question specific, academically accurate, and relevant to {class_title}.
Return ONLY the JSON object."""

        response_text, provider = self.kyknox.generate_response(
            prompt, mode='expert', context=None, role='student'
        )

        return self._parse_quiz_response(response_text)

    def _parse_quiz_response(self, response_text):
        """Parse AI quiz response"""
        if not response_text:
            return None

        text = response_text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx == -1 or end_idx == -1:
            return None

        try:
            obj = json.loads(text[start_idx:end_idx + 1])
            if (obj.get('question') and obj.get('options') and
                    isinstance(obj['options'], list) and len(obj['options']) == 4 and
                    obj.get('correct_answer')):
                return {
                    'question': str(obj['question']),
                    'options': [str(o) for o in obj['options'][:4]],
                    'correct_answer': str(obj['correct_answer'])
                }
        except json.JSONDecodeError:
            pass
        return None

    def _fallback_quiz(self, topic, class_title, attempt_num):
        """Topic-aware fallback quiz question"""
        questions = [
            {
                'question': f"In {class_title}, which approach best describes the study of {topic}?",
                'options': ["Theoretical framework and principles", "Random experimentation only",
                            "Memorization without understanding", "Ignoring foundational concepts"],
                'correct_answer': "Theoretical framework and principles"
            },
            {
                'question': f"What is the primary goal when mastering {topic} in {class_title}?",
                'options': ["Understanding concepts deeply and applying them", "Memorizing all formulas",
                            "Skipping difficult sections", "Only studying for exams"],
                'correct_answer': "Understanding concepts deeply and applying them"
            },
            {
                'question': f"Which skill is most important for excelling in {topic}?",
                'options': ["Problem-solving and analytical thinking", "Pure memorization",
                            "Speed reading textbooks", "Avoiding practice problems"],
                'correct_answer': "Problem-solving and analytical thinking"
            }
        ]
        return questions[(attempt_num - 1) % len(questions)]

    # ─── Task Details & Completion ──────────────────────────────────────

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

    def refresh_tasks(self, student_id, class_id, class_title='General'):
        """Delete today's tasks and regenerate fresh content"""
        today = date.today().isoformat()

        existing_task = self.db.execute_one(
            'SELECT id FROM micro_tasks WHERE student_id = ? AND class_id = ? AND task_date = ?',
            (student_id, class_id, today)
        )

        if existing_task:
            task_id = existing_task['id']
            # Delete related content
            self.db.execute_update('DELETE FROM ml_flashcards WHERE task_id = ?', (task_id,))
            self.db.execute_update('DELETE FROM ml_coding WHERE task_id = ?', (task_id,))
            self.db.execute_update('DELETE FROM ml_quiz_booster WHERE task_id = ?', (task_id,))
            self.db.execute_update('DELETE FROM micro_tasks WHERE id = ?', (task_id,))

        # Generate fresh tasks
        return self._generate_new_tasks(student_id, class_id, today, class_title)
