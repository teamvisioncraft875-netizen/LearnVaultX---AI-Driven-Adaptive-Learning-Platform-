"""
Skill Tree Engine — Generates topic-based skill trees per class and tracks student progress.
Integrates with KyKnoX AI for intelligent topic generation based on class subject.
"""
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Default skill trees by common subjects (fallback when AI is unavailable)
DEFAULT_TREES = {
    'python': [
        {'title': 'Variables & Data Types', 'icon': '📦', 'desc': 'Learn to store and manipulate data'},
        {'title': 'Conditionals', 'icon': '🔀', 'desc': 'Make decisions with if/else'},
        {'title': 'Loops', 'icon': '🔄', 'desc': 'Repeat actions with for/while'},
        {'title': 'Functions', 'icon': '⚙️', 'desc': 'Create reusable blocks of code'},
        {'title': 'Data Structures', 'icon': '📊', 'desc': 'Lists, dicts, sets, tuples'},
        {'title': 'OOP', 'icon': '🏗️', 'desc': 'Classes, objects, inheritance'},
        {'title': 'File Handling', 'icon': '📁', 'desc': 'Read and write files'},
        {'title': 'Error Handling', 'icon': '🛡️', 'desc': 'Try/except/finally patterns'},
    ],
    'java': [
        {'title': 'Syntax & Variables', 'icon': '📦', 'desc': 'Java basics and data types'},
        {'title': 'Control Flow', 'icon': '🔀', 'desc': 'If/else, switch statements'},
        {'title': 'Loops & Arrays', 'icon': '🔄', 'desc': 'For, while, arrays'},
        {'title': 'Methods', 'icon': '⚙️', 'desc': 'Define and call methods'},
        {'title': 'OOP Fundamentals', 'icon': '🏗️', 'desc': 'Classes, objects, constructors'},
        {'title': 'Inheritance & Polymorphism', 'icon': '🧬', 'desc': 'Extend and override'},
        {'title': 'Collections', 'icon': '📊', 'desc': 'ArrayList, HashMap, Set'},
        {'title': 'Exception Handling', 'icon': '🛡️', 'desc': 'Try/catch/throw/throws'},
    ],
    'mathematics': [
        {'title': 'Number Systems', 'icon': '🔢', 'desc': 'Natural, integer, rational numbers'},
        {'title': 'Algebra Basics', 'icon': '📐', 'desc': 'Expressions and equations'},
        {'title': 'Linear Equations', 'icon': '📈', 'desc': 'Solve and graph linear equations'},
        {'title': 'Quadratic Equations', 'icon': '📉', 'desc': 'Factoring, formula, graphing'},
        {'title': 'Geometry', 'icon': '📏', 'desc': 'Shapes, area, volume'},
        {'title': 'Trigonometry', 'icon': '📐', 'desc': 'Sin, cos, tan and applications'},
        {'title': 'Statistics', 'icon': '📊', 'desc': 'Mean, median, mode, probability'},
        {'title': 'Calculus Intro', 'icon': '∫', 'desc': 'Limits, derivatives basics'},
    ],
    'default': [
        {'title': 'Introduction', 'icon': '📖', 'desc': 'Fundamentals and basics'},
        {'title': 'Core Concepts', 'icon': '🧠', 'desc': 'Essential theories and principles'},
        {'title': 'Intermediate Topics', 'icon': '📊', 'desc': 'Building on the basics'},
        {'title': 'Advanced Concepts', 'icon': '🔬', 'desc': 'Deep dive into the subject'},
        {'title': 'Practical Application', 'icon': '🛠️', 'desc': 'Hands-on exercises'},
        {'title': 'Problem Solving', 'icon': '🧩', 'desc': 'Complex challenges'},
        {'title': 'Review & Mastery', 'icon': '🏆', 'desc': 'Final assessment preparation'},
    ],
}


class SkillTreeEngine:
    """Manages skill tree generation, retrieval, and progress tracking."""

    def __init__(self, db, kyknox=None):
        self.db = db
        self.kyknox = kyknox

    # ─── GENERATE SKILL TREE ──────────────────────────────────
    def generate_skill_tree(self, class_id):
        """Generate a skill tree for a class using AI or fallback."""
        # Check if tree already exists
        existing = self.db.execute_query(
            'SELECT id FROM skill_tree_nodes WHERE class_id = ?', (class_id,)
        )
        if existing:
            logger.info(f"Skill tree already exists for class {class_id} ({len(existing)} nodes)")
            return existing

        # Get class info
        cls = self.db.execute_one('SELECT title, description FROM classes WHERE id = ?', (class_id,))
        if not cls:
            logger.error(f"Class {class_id} not found")
            return []

        class_title = cls['title']
        nodes = []

        # Try AI generation
        if self.kyknox:
            try:
                nodes = self._ai_generate_nodes(class_title, cls.get('description', ''))
            except Exception as e:
                logger.error(f"AI skill tree generation failed: {e}")

        # Fallback to defaults
        if not nodes:
            nodes = self._fallback_nodes(class_title)

        # Save to DB
        saved_nodes = []
        prev_node_id = None
        for i, node in enumerate(nodes):
            node_id = self.db.execute_insert(
                '''INSERT INTO skill_tree_nodes (class_id, title, description, position_order, prerequisite_node_id, icon)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (class_id, node['title'], node.get('desc', ''), i + 1, prev_node_id, node.get('icon', '📘'))
            )
            saved_nodes.append({'id': node_id, 'title': node['title'], 'position_order': i + 1})
            prev_node_id = node_id

        logger.info(f"Generated {len(saved_nodes)} skill tree nodes for class {class_id} ({class_title})")
        return saved_nodes

    def _ai_generate_nodes(self, class_title, class_desc):
        """Use KyKnoX AI to generate skill tree topics."""
        prompt = f"""Generate a learning skill tree for the subject: "{class_title}"
{f'Description: {class_desc}' if class_desc else ''}

Return EXACTLY a JSON array of 6-8 topic objects in progressive order (easy → hard).
Each object must have: "title" (short topic name), "icon" (single emoji), "desc" (one-line description).

Example format:
[
  {{"title": "Variables", "icon": "📦", "desc": "Store and manipulate data"}},
  {{"title": "Loops", "icon": "🔄", "desc": "Repeat actions efficiently"}}
]

Return ONLY the JSON array, no other text."""

        response, provider = self.kyknox.generate_response(prompt, mode='expert')

        # Extract JSON from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            nodes = json.loads(json_match.group())
            if isinstance(nodes, list) and len(nodes) >= 4:
                # Validate each node
                valid = []
                for n in nodes[:8]:
                    if isinstance(n, dict) and 'title' in n:
                        valid.append({
                            'title': n['title'][:50],
                            'icon': n.get('icon', '📘')[:4],
                            'desc': n.get('desc', '')[:100]
                        })
                if len(valid) >= 4:
                    return valid

        logger.warning("AI response didn't contain valid skill tree JSON, using fallback")
        return []

    def _fallback_nodes(self, class_title):
        """Get default nodes based on class title keyword matching."""
        title_lower = class_title.lower()
        for keyword, nodes in DEFAULT_TREES.items():
            if keyword != 'default' and keyword in title_lower:
                return nodes
        return DEFAULT_TREES['default']

    # ─── GET SKILL TREE WITH PROGRESS ─────────────────────────
    def get_skill_tree(self, class_id, student_id):
        """Return the full skill tree with per-student progress."""
        nodes = self.db.execute_query(
            '''SELECT id, title, description, position_order, prerequisite_node_id, icon
               FROM skill_tree_nodes WHERE class_id = ?
               ORDER BY position_order''',
            (class_id,)
        )

        if not nodes:
            return []

        # Get student progress
        progress = self.db.execute_query(
            '''SELECT node_id, status, score, unlocked_at, completed_at
               FROM student_skill_progress WHERE student_id = ?
               AND node_id IN (SELECT id FROM skill_tree_nodes WHERE class_id = ?)''',
            (student_id, class_id)
        )
        progress_map = {p['node_id']: p for p in progress}

        # Build tree with status
        result = []
        for node in nodes:
            nid = node['id']
            prog = progress_map.get(nid)

            if prog:
                status = prog['status']
                score = prog['score']
            elif node['prerequisite_node_id'] is None:
                # First node is always unlocked
                status = 'unlocked'
                score = 0
                self._ensure_progress_row(student_id, nid, 'unlocked')
            else:
                status = 'locked'
                score = 0

            result.append({
                'id': nid,
                'title': node['title'],
                'description': node['description'],
                'icon': node['icon'],
                'position': node['position_order'],
                'prerequisite_id': node['prerequisite_node_id'],
                'status': status,
                'score': round(score, 1)
            })

        return result

    def _ensure_progress_row(self, student_id, node_id, status):
        """Create a progress row if it doesn't exist."""
        existing = self.db.execute_one(
            'SELECT id FROM student_skill_progress WHERE student_id = ? AND node_id = ?',
            (student_id, node_id)
        )
        if not existing:
            self.db.execute_insert(
                '''INSERT INTO student_skill_progress (student_id, node_id, status, unlocked_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)''',
                (student_id, node_id, status)
            )

    # ─── UPDATE PROGRESS AFTER QUIZ ──────────────────────────
    def update_progress_after_quiz(self, student_id, quiz_id, class_id, score, total):
        """Update skill tree progress based on quiz results."""
        try:
            percentage = (score / total * 100) if total > 0 else 0

            # Get or generate the skill tree
            nodes = self.db.execute_query(
                'SELECT id, title, position_order, prerequisite_node_id FROM skill_tree_nodes WHERE class_id = ? ORDER BY position_order',
                (class_id,)
            )

            if not nodes:
                # Auto-generate tree on first quiz
                self.generate_skill_tree(class_id)
                nodes = self.db.execute_query(
                    'SELECT id, title, position_order, prerequisite_node_id FROM skill_tree_nodes WHERE class_id = ? ORDER BY position_order',
                    (class_id,)
                )

            if not nodes:
                return

            # Try to match quiz topic_tags to skill tree nodes
            quiz_topics = self.db.execute_query(
                'SELECT DISTINCT topic_tag FROM quiz_questions WHERE quiz_id = ? AND topic_tag IS NOT NULL AND topic_tag != ""',
                (quiz_id,)
            )
            topic_tags = [t['topic_tag'].lower() for t in quiz_topics]

            # Find matching node based on topic_tag similarity
            matched_node = None
            for node in nodes:
                node_title_lower = node['title'].lower()
                for tag in topic_tags:
                    if tag in node_title_lower or node_title_lower in tag:
                        matched_node = node
                        break
                if matched_node:
                    break

            # If no direct match, use the first unlocked/uncompleted node
            if not matched_node:
                for node in nodes:
                    prog = self.db.execute_one(
                        'SELECT status FROM student_skill_progress WHERE student_id = ? AND node_id = ?',
                        (student_id, node['id'])
                    )
                    if not prog or prog['status'] in ('unlocked', 'weak'):
                        matched_node = node
                        break

            if not matched_node:
                # All done or no match — update last node
                matched_node = nodes[-1]

            # Determine status based on score
            if percentage >= 70:
                new_status = 'completed'
            elif percentage >= 40:
                new_status = 'weak'
            else:
                new_status = 'unlocked'  # Keep unlocked, not enough to progress

            # Update or insert progress
            existing = self.db.execute_one(
                'SELECT id, status, score FROM student_skill_progress WHERE student_id = ? AND node_id = ?',
                (student_id, matched_node['id'])
            )

            if existing:
                # Only upgrade status (don't downgrade completed → weak)
                current = existing['status']
                if current == 'completed' and new_status != 'completed':
                    pass  # Don't downgrade
                else:
                    self.db.execute_update(
                        '''UPDATE student_skill_progress
                           SET status = ?, score = ?, completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                           WHERE id = ?''',
                        (new_status, percentage, new_status, existing['id'])
                    )
            else:
                self.db.execute_insert(
                    '''INSERT INTO student_skill_progress (student_id, node_id, status, score, unlocked_at, completed_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END)''',
                    (student_id, matched_node['id'], new_status, percentage, new_status)
                )

            # Auto-unlock next node if current is completed
            if new_status == 'completed':
                self._unlock_next_node(student_id, class_id, matched_node['id'])

            logger.info(f"Skill tree updated: student={student_id}, node={matched_node['title']}, status={new_status}, score={percentage:.0f}%")

        except Exception as e:
            logger.error(f"Error updating skill tree progress: {e}")

    def _unlock_next_node(self, student_id, class_id, completed_node_id):
        """Unlock the next node in the tree after completing a prerequisite."""
        next_nodes = self.db.execute_query(
            'SELECT id FROM skill_tree_nodes WHERE class_id = ? AND prerequisite_node_id = ?',
            (class_id, completed_node_id)
        )
        for node in next_nodes:
            existing = self.db.execute_one(
                'SELECT id, status FROM student_skill_progress WHERE student_id = ? AND node_id = ?',
                (student_id, node['id'])
            )
            if existing:
                if existing['status'] == 'locked':
                    self.db.execute_update(
                        "UPDATE student_skill_progress SET status = 'unlocked', unlocked_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (existing['id'],)
                    )
            else:
                self.db.execute_insert(
                    "INSERT INTO student_skill_progress (student_id, node_id, status, unlocked_at) VALUES (?, ?, 'unlocked', CURRENT_TIMESTAMP)",
                    (student_id, node['id'])
                )
