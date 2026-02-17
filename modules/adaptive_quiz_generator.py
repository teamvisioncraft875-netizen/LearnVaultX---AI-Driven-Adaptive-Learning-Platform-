"""
Adaptive Quiz Generator + Mistake Notes Generator
Uses KyKnoX AI to generate personalized quizzes and post-quiz mistake analysis.
"""
import json
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)


class AdaptiveQuizGenerator:
    """Generates adaptive quizzes and mistake notes using KyKnoX AI."""

    def __init__(self, db, kyknox, adaptive_engine=None):
        self.db = db
        self.kyknox = kyknox
        self.adaptive = adaptive_engine

    # ─── Difficulty Logic ───────────────────────────────────────────────

    def get_student_level(self, student_id, class_id):
        """Determine difficulty level based on student's quiz history."""
        # Check adaptive profile first
        profile = self.db.execute_one(
            'SELECT current_level, last_score FROM student_adaptive_profile WHERE student_id = ? AND class_id = ?',
            (student_id, class_id)
        )
        if profile:
            return profile['current_level']

        # Fallback: check last quiz submission in this class
        last_sub = self.db.execute_one(
            '''SELECT qs.score, qs.total FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE qs.student_id = ? AND q.class_id = ?
               ORDER BY qs.submitted_at DESC LIMIT 1''',
            (student_id, class_id)
        )
        if last_sub and last_sub['total'] > 0:
            score = last_sub['score']
            if score >= 9:
                return 'hard'
            elif score >= 6:
                return 'medium'
            else:
                return 'easy'

        return 'medium'  # Default for new students

    def _score_to_level(self, score):
        """Convert a score (out of 10) to difficulty level."""
        if score >= 9:
            return 'hard'
        elif score >= 6:
            return 'medium'
        else:
            return 'easy'

    def update_adaptive_profile(self, student_id, class_id, score, total=10):
        """Update student adaptive profile after quiz submission."""
        normalized = round((score / total) * 10) if total > 0 else 0
        new_level = self._score_to_level(normalized)

        # Get weak topics
        weak_topics = []
        if self.adaptive:
            try:
                gaps = self.adaptive.analyze_knowledge_gaps(student_id, class_id) or []
                weak_topics = [g.get('topic', g.get('quiz', '')) for g in gaps[:5] if isinstance(g, dict)]
            except Exception as e:
                logger.error(f"Failed to get weak topics: {e}")

        try:
            existing = self.db.execute_one(
                'SELECT id FROM student_adaptive_profile WHERE student_id = ? AND class_id = ?',
                (student_id, class_id)
            )
            if existing:
                self.db.execute_query(
                    '''UPDATE student_adaptive_profile
                       SET current_level = ?, weak_topics_json = ?, last_score = ?, updated_at = ?
                       WHERE student_id = ? AND class_id = ?''',
                    (new_level, json.dumps(weak_topics), score, datetime.now().isoformat(),
                     student_id, class_id),
                    fetch=False
                )
            else:
                self.db.execute_insert(
                    '''INSERT INTO student_adaptive_profile (student_id, class_id, current_level, weak_topics_json, last_score, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (student_id, class_id, new_level, json.dumps(weak_topics), score, datetime.now().isoformat())
                )
            logger.info(f"Updated adaptive profile: student={student_id}, class={class_id}, level={new_level}")
        except Exception as e:
            logger.error(f"Failed to update adaptive profile: {e}")

    # ─── Quiz Generation ────────────────────────────────────────────────

    def _get_weak_topics(self, student_id, class_id):
        """Retrieve weak topics for the student."""
        profile = self.db.execute_one(
            'SELECT weak_topics_json FROM student_adaptive_profile WHERE student_id = ? AND class_id = ?',
            (student_id, class_id)
        )
        if profile and profile.get('weak_topics_json'):
            try:
                return json.loads(profile['weak_topics_json'])
            except Exception:
                pass
        return []

    def generate_quiz(self, student_id, class_id, class_title):
        """Generate an AI-powered adaptive quiz and save it to the database."""
        level = self.get_student_level(student_id, class_id)
        weak_topics = self._get_weak_topics(student_id, class_id)

        prompt = self._build_quiz_prompt(class_title, level, weak_topics)

        try:
            response_text, provider = self.kyknox.generate_response(
                prompt, mode='expert', context=None, role='student'
            )
            questions = self._parse_quiz_response(response_text, level)
        except Exception as e:
            logger.error(f"AI quiz generation failed: {e}")
            questions = self._generate_fallback_questions(class_title, level)

        if not questions or len(questions) < 5:
            logger.warning("AI returned too few questions, using fallback")
            questions = self._generate_fallback_questions(class_title, level)

        # Save to database
        quiz_title = f"{class_title} - Adaptive Quiz ({level.title()})"
        quiz_id = self.db.execute_insert(
            "INSERT INTO quizzes (class_id, title, difficulty_level, generated_by) VALUES (?, ?, ?, ?)",
            (class_id, quiz_title, level, student_id)
        )

        for q in questions[:10]:
            self.db.execute_insert(
                '''INSERT INTO quiz_questions (quiz_id, question_text, options, correct_option_index, topic_tag, explanation, difficulty)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (quiz_id, q['question_text'], json.dumps(q['options']),
                 q['correct_option_index'], q.get('topic_tag', ''),
                 q.get('explanation', ''), q.get('difficulty', level))
            )

        logger.info(f"Generated adaptive quiz: id={quiz_id}, level={level}, questions={len(questions[:10])}")
        return {
            'quiz_id': quiz_id,
            'title': quiz_title,
            'difficulty': level,
            'question_count': len(questions[:10])
        }

    def _build_quiz_prompt(self, class_title, level, weak_topics):
        """Build the prompt for quiz generation."""
        difficulty_desc = {
            'easy': 'basic, beginner-friendly questions covering fundamental concepts. Use simple language.',
            'medium': 'intermediate questions that test understanding and application of concepts.',
            'hard': 'advanced, challenging questions that require deep understanding, analysis, and problem-solving.'
        }

        weak_section = ""
        if weak_topics:
            weak_section = f"\nFocus more on these weak areas: {', '.join(weak_topics[:5])}"

        return f"""Generate exactly 10 multiple-choice quiz questions for the subject: "{class_title}".

Difficulty: {level.upper()} - {difficulty_desc.get(level, difficulty_desc['medium'])}
{weak_section}

CRITICAL: Return ONLY a valid JSON array. No markdown, no code blocks, no extra text.

Each object in the array MUST have these exact keys:
- "question_text": string (the question)
- "options": array of exactly 4 strings (answer choices)
- "correct_option_index": integer 0-3 (index of correct answer)
- "explanation": string (why the correct answer is right)
- "topic_tag": string (topic this question covers)
- "difficulty": "{level}"

Example format:
[{{"question_text":"What is X?","options":["A","B","C","D"],"correct_option_index":0,"explanation":"A is correct because...","topic_tag":"basics","difficulty":"{level}"}}]

Return ONLY the JSON array, nothing else."""

    def _parse_quiz_response(self, response_text, level):
        """Parse the AI response into structured questions."""
        if not response_text:
            return []

        # Clean the response
        text = response_text.strip()

        # Remove markdown code blocks if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        # Find the JSON array
        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx == -1 or end_idx == -1:
            logger.error("No JSON array found in AI response")
            return []

        json_str = text[start_idx:end_idx + 1]

        try:
            questions = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return []

        # Validate and clean
        valid_questions = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            if not q.get('question_text') or not q.get('options'):
                continue
            if not isinstance(q['options'], list) or len(q['options']) != 4:
                continue

            correct_idx = q.get('correct_option_index', 0)
            try:
                correct_idx = int(correct_idx)
            except (TypeError, ValueError):
                correct_idx = 0
            if correct_idx < 0 or correct_idx > 3:
                correct_idx = 0

            valid_questions.append({
                'question_text': str(q['question_text']),
                'options': [str(o) for o in q['options'][:4]],
                'correct_option_index': correct_idx,
                'explanation': str(q.get('explanation', '')),
                'topic_tag': str(q.get('topic_tag', '')),
                'difficulty': level
            })

        return valid_questions

    def _generate_fallback_questions(self, class_title, level):
        """Generate fallback questions when AI fails."""
        templates = {
            'easy': [
                {"question_text": f"Which of the following is a key concept in {class_title}?",
                 "options": ["Fundamentals", "Advanced Theory", "Research Methods", "None of the above"],
                 "correct_option_index": 0, "explanation": f"Fundamentals are the building blocks of {class_title}.",
                 "topic_tag": "basics", "difficulty": "easy"},
            ],
            'medium': [
                {"question_text": f"In {class_title}, which approach is commonly used for problem solving?",
                 "options": ["Trial and error", "Systematic analysis", "Random guessing", "Ignoring the problem"],
                 "correct_option_index": 1, "explanation": "Systematic analysis is the standard approach.",
                 "topic_tag": "methodology", "difficulty": "medium"},
            ],
            'hard': [
                {"question_text": f"What is the most complex aspect of advanced {class_title}?",
                 "options": ["Basic definitions", "Optimization and scalability", "Simple syntax", "Memorization"],
                 "correct_option_index": 1, "explanation": "Optimization and scalability require deep understanding.",
                 "topic_tag": "advanced", "difficulty": "hard"},
            ]
        }
        base = templates.get(level, templates['medium'])
        # Repeat to fill 10 questions with variations
        questions = []
        for i in range(10):
            q = base[i % len(base)].copy()
            q['question_text'] = f"Q{i+1}: {q['question_text']}"
            questions.append(q)
        return questions

    # ─── Mistake Notes Generation ───────────────────────────────────────

    def generate_mistake_notes(self, student_id, quiz_id, class_id, wrong_questions):
        """Generate AI-powered mistake notes for wrong answers."""
        if not wrong_questions:
            return []

        prompt = self._build_mistake_prompt(wrong_questions)

        try:
            response_text, provider = self.kyknox.generate_response(
                prompt, mode='expert', context=None, role='student'
            )
            notes = self._parse_mistake_response(response_text)
        except Exception as e:
            logger.error(f"AI mistake notes failed: {e}")
            notes = self._generate_fallback_notes(wrong_questions)

        if not notes or len(notes) < len(wrong_questions):
            notes = self._generate_fallback_notes(wrong_questions)

        # Save to database
        saved_notes = []
        for i, note in enumerate(notes[:len(wrong_questions)]):
            wq = wrong_questions[i] if i < len(wrong_questions) else {}
            try:
                self.db.execute_insert(
                    '''INSERT INTO mistake_notes
                       (student_id, quiz_id, class_id, question_id, topic_tag,
                        mistake_summary, quick_fix, memory_trick, recommended_topic)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (student_id, quiz_id, class_id,
                     wq.get('question_id', 0), note.get('topic_tag', ''),
                     note.get('mistake_summary', ''), note.get('quick_fix', ''),
                     note.get('memory_trick', ''), note.get('recommended_topic', ''))
                )
            except Exception as e:
                logger.error(f"Failed to save mistake note: {e}")

            saved_notes.append({
                'question_text': wq.get('question_text', ''),
                'user_answer': wq.get('user_answer', ''),
                'correct_answer': wq.get('correct_answer', ''),
                'mistake_summary': note.get('mistake_summary', ''),
                'quick_fix': note.get('quick_fix', ''),
                'memory_trick': note.get('memory_trick', ''),
                'recommended_topic': note.get('recommended_topic', '')
            })

        logger.info(f"Generated {len(saved_notes)} mistake notes for quiz {quiz_id}")
        return saved_notes

    def _build_mistake_prompt(self, wrong_questions):
        """Build prompt for mistake notes generation."""
        mistakes_text = ""
        for i, wq in enumerate(wrong_questions[:10], 1):
            mistakes_text += f"""
{i}. Question: {wq.get('question_text', 'N/A')}
   Student answered: {wq.get('user_answer', 'N/A')}
   Correct answer: {wq.get('correct_answer', 'N/A')}
"""

        return f"""A student got these questions wrong on a quiz. For each question, generate a helpful study note.

{mistakes_text}

CRITICAL: Return ONLY a valid JSON array with exactly {len(wrong_questions[:10])} objects. No markdown, no code blocks.

Each object MUST have these exact keys:
- "mistake_summary": string (1-2 sentences explaining what the student got wrong and why)
- "quick_fix": string (a concise tip to fix this misunderstanding)
- "memory_trick": string (a memorable trick, mnemonic, or analogy to remember the correct concept)
- "recommended_topic": string (the specific topic area to review)
- "topic_tag": string (short tag for the topic)

Return ONLY the JSON array."""

    def _parse_mistake_response(self, response_text):
        """Parse AI response into mistake notes."""
        if not response_text:
            return []

        text = response_text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx == -1 or end_idx == -1:
            return []

        try:
            notes = json.loads(text[start_idx:end_idx + 1])
            return [n for n in notes if isinstance(n, dict) and n.get('mistake_summary')]
        except json.JSONDecodeError:
            return []

    def _generate_fallback_notes(self, wrong_questions):
        """Generate fallback notes when AI is unavailable."""
        notes = []
        for wq in wrong_questions:
            notes.append({
                'mistake_summary': f"You selected \"{wq.get('user_answer', '?')}\" but the correct answer was \"{wq.get('correct_answer', '?')}\".",
                'quick_fix': 'Review the core concept behind this question and practice similar problems.',
                'memory_trick': 'Try creating a flashcard with this question to reinforce your memory.',
                'recommended_topic': wq.get('topic_tag', 'General Review'),
                'topic_tag': wq.get('topic_tag', '')
            })
        return notes
