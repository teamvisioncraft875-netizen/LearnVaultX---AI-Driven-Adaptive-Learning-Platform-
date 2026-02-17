"""
AI Tutor Avatar Blueprint
Provides /ai_tutor page and supporting API endpoints.
Isolated module — does NOT modify any existing routes or templates.
"""

from flask import Blueprint, render_template, request, jsonify, session
import json
import logging
import time

logger = logging.getLogger(__name__)

ai_tutor_bp = Blueprint('ai_tutor', __name__)

# These will be injected by init_ai_tutor() called from app.py
_db = None
_adaptive = None
_kyknox = None
_learning_path_service = None


def init_ai_tutor(db, adaptive, kyknox, learning_path_service):
    """Initialize the blueprint with app services. Called once from app.py."""
    global _db, _adaptive, _kyknox, _learning_path_service
    _db = db
    _adaptive = adaptive
    _kyknox = kyknox
    _learning_path_service = learning_path_service


def _get_user_id():
    return session.get('user_id')


def _require_student():
    """Return user_id if student, else None."""
    if session.get('role') != 'student':
        return None
    return _get_user_id()


# ─── TUTOR PAGE ──────────────────────────────────────────────
@ai_tutor_bp.route('/ai_tutor')
def ai_tutor_page():
    """Render the AI Tutor Avatar page."""
    if 'user_id' not in session:
        from flask import redirect, url_for
        return redirect(url_for('login'))
    return render_template('ai_tutor.html')


# ─── LEARNING SUMMARY API ───────────────────────────────────
@ai_tutor_bp.route('/api/student/learning_summary')
def student_learning_summary():
    """Comprehensive student summary for the AI tutor page."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403

    try:
        # 1. Enrolled classes
        enrollments = _db.execute_query(
            '''SELECT c.id, c.title, c.description, u.name as teacher_name
               FROM enrollments e
               JOIN classes c ON e.class_id = c.id
               JOIN users u ON c.teacher_id = u.id
               WHERE e.student_id = ?''',
            (user_id,)
        )

        # 2. Per-class details
        classes_data = []
        all_weak_topics = []
        total_progress = 0
        next_recommended_module = None

        for cls in enrollments:
            class_id = cls['id']

            # Quiz submissions for this class
            submissions = _db.execute_query(
                '''SELECT qs.score, qs.total, qs.submitted_at, q.title as quiz_title
                   FROM quiz_submissions qs
                   JOIN quizzes q ON qs.quiz_id = q.id
                   WHERE qs.student_id = ? AND q.class_id = ?
                   ORDER BY qs.submitted_at DESC''',
                (user_id, class_id)
            )

            last_score = None
            if submissions:
                last = submissions[0]
                last_score = {
                    'quiz': last['quiz_title'],
                    'score': last['score'],
                    'total': last['total'],
                    'percentage': round((last['score'] / last['total']) * 100, 1) if last['total'] > 0 else 0,
                    'date': last['submitted_at']
                }

            # Module progress
            modules = []
            try:
                modules = _learning_path_service.get_subject_modules(class_id, user_id)
            except Exception:
                pass

            completed = sum(1 for m in modules if m.get('status') == 'COMPLETED')
            total_mods = len(modules)
            progress_pct = round((completed / total_mods) * 100) if total_mods > 0 else 0
            total_progress += progress_pct

            # Find next recommended module
            for m in modules:
                if m.get('status') in ('UNLOCKED', 'IN_PROGRESS'):
                    if not next_recommended_module:
                        next_recommended_module = {
                            'class': cls['title'],
                            'module_id': m['id'],
                            'module_title': m['title'],
                            'description': m.get('description', ''),
                            'status': m['status']
                        }
                    break

            # Knowledge gaps for this class
            try:
                gaps = _adaptive.analyze_knowledge_gaps(user_id, class_id)
                for g in gaps[:3]:
                    all_weak_topics.append({
                        'class': cls['title'],
                        'topic': g.get('question', g.get('quiz', 'Unknown'))[:80],
                        'severity': g.get('severity', 'medium')
                    })
            except Exception:
                pass

            classes_data.append({
                'id': class_id,
                'title': cls['title'],
                'teacher': cls['teacher_name'],
                'last_score': last_score,
                'modules_completed': completed,
                'modules_total': total_mods,
                'progress_pct': progress_pct
            })

        avg_progress = round(total_progress / len(classes_data)) if classes_data else 0

        # 3. Overall quiz stats
        overall_stats = _db.execute_one(
            '''SELECT COUNT(*) as total_attempts,
                      AVG(CAST(score AS FLOAT) / CASE WHEN total > 0 THEN total ELSE 1 END * 100) as avg_pct
               FROM quiz_submissions WHERE student_id = ?''',
            (user_id,)
        )

        return jsonify({
            'success': True,
            'data': {
                'classes': classes_data,
                'overall_progress': avg_progress,
                'total_attempts': overall_stats['total_attempts'] if overall_stats else 0,
                'average_score': round(overall_stats['avg_pct'] or 0, 1) if overall_stats else 0,
                'weak_topics': all_weak_topics[:5],
                'next_recommended_module': next_recommended_module
            }
        })

    except Exception as e:
        logger.exception('Error building learning summary')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── TUTOR RESPOND API ──────────────────────────────────────
@ai_tutor_bp.route('/api/tutor/respond', methods=['POST'])
def tutor_respond():
    """AI Tutor chat — sends student context + message to AI, returns structured response."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Message required'}), 400

    try:
        # 1. Build rich student context
        student_context = _build_tutor_context(user_id)

        # 1b. Load conversation memory for context
        chat_history = []
        try:
            chat_history = _db.execute_query(
                '''SELECT message, role, topic_tag, timestamp
                   FROM chat_memory WHERE student_id = ?
                   ORDER BY timestamp DESC LIMIT 20''',
                (user_id,)
            )
            chat_history.reverse()  # chronological order
        except Exception:
            pass

        # 2. Build system prompt for tutor mode (now includes memory)
        system_prompt = _build_tutor_system_prompt(student_context, chat_history)

        # 3. Call Groq API through KyKnoX (reuse existing infra)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        # Use KyKnoX's Groq client directly for richer control
        import requests as http_requests
        import os

        api_key = os.getenv('GROQ_API_KEY')
        ai_text = ""
        provider = "Fallback"

        if api_key:
            try:
                resp = http_requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1500
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    ai_text = resp.json()['choices'][0]['message']['content']
                    provider = "Groq"
                else:
                    logger.error(f"Groq API error {resp.status_code}: {resp.text[:200]}")
                    ai_text = _fallback_tutor_response(message, student_context)
            except Exception as api_err:
                logger.error(f"Groq API call failed: {api_err}")
                ai_text = _fallback_tutor_response(message, student_context)
        else:
            ai_text = _fallback_tutor_response(message, student_context)

        # 4. Determine emotion and gesture from response
        emotion, gesture = _detect_emotion_gesture(ai_text, student_context)

        # 5. Build recommended actions
        recommended_actions = _build_recommended_actions(student_context)

        # 6. Save to ai_tutor_sessions
        try:
            _db.execute_insert(
                '''INSERT INTO ai_tutor_sessions (user_id, message, response, emotion, gesture, recommended_actions)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, message[:500], ai_text[:5000], emotion, gesture, json.dumps(recommended_actions))
            )
        except Exception:
            pass  # Non-critical

        # 6b. Save to chat_memory for persistent recall
        try:
            topic = _detect_topic_tag(message)
            _db.execute_insert(
                'INSERT INTO chat_memory (student_id, message, role, topic_tag) VALUES (?, ?, ?, ?)',
                (user_id, message[:500], 'user', topic)
            )
            _db.execute_insert(
                'INSERT INTO chat_memory (student_id, message, role, topic_tag) VALUES (?, ?, ?, ?)',
                (user_id, ai_text[:2000], 'assistant', topic)
            )
        except Exception:
            pass  # Non-critical

        # 7. Return structured response
        return jsonify({
            'success': True,
            'text': ai_text,
            'emotion': emotion,
            'gesture': gesture,
            'audio_url': None,  # TTS not yet integrated
            'viseme_url': None,
            'recommended_actions': recommended_actions
        })

    except Exception as e:
        logger.exception('Error in tutor respond')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── MARK MODULE COMPLETE ───────────────────────────────────
@ai_tutor_bp.route('/api/student/mark_module_complete', methods=['POST'])
def mark_module_complete():
    """Allow manual module completion tracking."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403

    data = request.get_json(silent=True) or {}
    module_id = data.get('module_id')
    if not module_id:
        return jsonify({'success': False, 'error': 'module_id required'}), 400

    try:
        module_id = int(module_id)
        # Check module exists
        mod = _db.execute_one('SELECT id, class_id FROM learning_modules WHERE id = ?', (module_id,))
        if not mod:
            return jsonify({'success': False, 'error': 'Module not found'}), 404

        # Check enrollment
        enrollment = _db.execute_one(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (user_id, mod['class_id'])
        )
        if not enrollment:
            return jsonify({'success': False, 'error': 'Not enrolled'}), 403

        # Update or insert progress
        existing = _db.execute_one(
            'SELECT id, status FROM student_module_progress WHERE user_id = ? AND module_id = ?',
            (user_id, module_id)
        )

        if existing:
            _db.execute_update(
                "UPDATE student_module_progress SET status = 'COMPLETED', completion_percent = 100, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (existing['id'],)
            )
        else:
            _db.execute_insert(
                "INSERT INTO student_module_progress (user_id, module_id, status, completion_percent, quiz_score_avg, attempts_count) VALUES (?, ?, 'COMPLETED', 100, 0, 0)",
                (user_id, module_id)
            )

        # Unlock next module
        try:
            _learning_path_service._unlock_next_module(user_id, mod['class_id'], module_id)
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Module marked as complete'})

    except Exception as e:
        logger.exception('Error marking module complete')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── TUTOR CHAT HISTORY ─────────────────────────────────────
@ai_tutor_bp.route('/api/tutor/history')
def tutor_chat_history():
    """Get recent AI tutor chat history for the current student."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403

    try:
        history = _db.execute_query(
            '''SELECT message, response, emotion, gesture, recommended_actions, created_at
               FROM ai_tutor_sessions WHERE user_id = ?
               ORDER BY created_at DESC LIMIT 20''',
            (user_id,)
        )

        # Reverse to chronological order
        history.reverse()

        return jsonify({'success': True, 'history': history})
    except Exception as e:
        logger.exception('Error fetching tutor history')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── CLEAR CHAT MEMORY ─────────────────────────────────────
@ai_tutor_bp.route('/api/tutor/clear-memory', methods=['POST'])
def clear_chat_memory():
    """Delete all chat memory for the current student."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403
    try:
        _db.execute_update('DELETE FROM chat_memory WHERE student_id = ?', (user_id,))
        return jsonify({'success': True, 'message': 'Chat memory cleared'})
    except Exception as e:
        logger.exception('Error clearing chat memory')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── WEAK TOPICS SUMMARY ───────────────────────────────────
@ai_tutor_bp.route('/api/tutor/weak-summary')
def weak_topics_summary():
    """Return a structured summary of weak topics and conversation themes."""
    user_id = _require_student()
    if not user_id:
        return jsonify({'success': False, 'error': 'Student login required'}), 403
    try:
        context = _build_tutor_context(user_id)
        
        # Get recent conversation topics from chat_memory
        recent_topics = []
        try:
            topics = _db.execute_query(
                '''SELECT topic_tag, COUNT(*) as cnt
                   FROM chat_memory WHERE student_id = ? AND topic_tag != '' AND role = 'user'
                   GROUP BY topic_tag ORDER BY cnt DESC LIMIT 5''',
                (user_id,)
            )
            recent_topics = [t['topic_tag'] for t in topics]
        except Exception:
            pass

        return jsonify({
            'success': True,
            'data': {
                'weak_topics': context.get('weak_topics', []),
                'strong_topics': context.get('strong_topics', []),
                'recent_conversation_topics': recent_topics,
                'overall_performance': context.get('overall_performance', 'unknown'),
                'avg_score': context.get('avg_score', 0)
            }
        })
    except Exception as e:
        logger.exception('Error building weak summary')
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def _detect_topic_tag(message):
    """Auto-detect topic tag from a user message."""
    msg_lower = message.lower()
    topic_keywords = {
        'python': ['python', 'variable', 'loop', 'function', 'class', 'def ', 'import '],
        'java': ['java', 'public static', 'jvm', 'spring'],
        'sql': ['sql', 'query', 'database', 'select ', 'join ', 'table '],
        'math': ['math', 'algebra', 'equation', 'calculus', 'geometry', 'formula'],
        'science': ['physics', 'chemistry', 'biology', 'experiment'],
        'study': ['study', 'revise', 'revision', 'exam', 'test', 'prepare'],
        'quiz': ['quiz', 'score', 'result', 'attempt', 'answer'],
        'career': ['career', 'job', 'interview', 'resume', 'skill'],
        'help': ['help', 'explain', 'understand', 'confused', 'doubt'],
    }
    for tag, keywords in topic_keywords.items():
        if any(kw in msg_lower for kw in keywords):
            return tag
    return ''


def _build_tutor_context(user_id):
    """Build comprehensive student context for AI prompt."""
    context = {
        'weak_topics': [],
        'strong_topics': [],
        'classes': [],
        'recent_scores': [],
        'next_module': None,
        'overall_performance': 'unknown',
        'total_quizzes_taken': 0,
        'avg_score': 0
    }

    try:
        enrollments = _db.execute_query(
            'SELECT e.class_id, c.title FROM enrollments e JOIN classes c ON e.class_id = c.id WHERE e.student_id = ?',
            (user_id,)
        )

        context['classes'] = [{'id': e['class_id'], 'title': e['title']} for e in enrollments]

        all_weak = []
        all_strong = []

        for e in enrollments:
            cid = e['class_id']

            # Get per-topic performance using topic_tag
            topic_perf = _db.execute_query(
                '''SELECT qq.topic_tag,
                          COUNT(*) as total_q,
                          SUM(CASE WHEN CAST(
                              json_extract(qs.answers, '$.' || CAST(qq.id AS TEXT))
                          AS INTEGER) = qq.correct_option_index THEN 1 ELSE 0 END) as correct
                   FROM quiz_questions qq
                   JOIN quizzes q ON qq.quiz_id = q.id
                   JOIN quiz_submissions qs ON qs.quiz_id = q.id AND qs.student_id = ?
                   WHERE q.class_id = ? AND qq.topic_tag IS NOT NULL AND qq.topic_tag != 'general'
                   GROUP BY qq.topic_tag''',
                (user_id, cid)
            )

            for tp in topic_perf:
                pct = round((tp['correct'] / tp['total_q']) * 100) if tp['total_q'] > 0 else 0
                entry = {'topic': tp['topic_tag'], 'class': e['title'], 'accuracy': pct, 'attempts': tp['total_q']}
                if pct < 60:
                    all_weak.append(entry)
                elif pct >= 80:
                    all_strong.append(entry)

            # Get modules
            try:
                modules = _learning_path_service.get_subject_modules(cid, user_id)
                for m in modules:
                    if m.get('status') in ('UNLOCKED', 'IN_PROGRESS') and not context['next_module']:
                        context['next_module'] = {'title': m['title'], 'class': e['title']}
                        break
            except Exception:
                pass

        context['weak_topics'] = sorted(all_weak, key=lambda x: x['accuracy'])[:5]
        context['strong_topics'] = sorted(all_strong, key=lambda x: x['accuracy'], reverse=True)[:3]

        # Recent scores
        recent = _db.execute_query(
            '''SELECT qs.score, qs.total, q.title as quiz_title, qs.submitted_at
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE qs.student_id = ?
               ORDER BY qs.submitted_at DESC LIMIT 5''',
            (user_id,)
        )
        context['recent_scores'] = [
            {'quiz': r['quiz_title'], 'score': r['score'], 'total': r['total'],
             'pct': round((r['score'] / r['total']) * 100) if r['total'] > 0 else 0}
            for r in recent
        ]

        # Overall stats
        stats = _db.execute_one(
            'SELECT COUNT(*) as cnt, AVG(CAST(score AS FLOAT) / CASE WHEN total > 0 THEN total ELSE 1 END * 100) as avg FROM quiz_submissions WHERE student_id = ?',
            (user_id,)
        )
        if stats:
            context['total_quizzes_taken'] = stats['cnt']
            context['avg_score'] = round(stats['avg'] or 0, 1)

        if context['avg_score'] < 50:
            context['overall_performance'] = 'struggling'
        elif context['avg_score'] < 70:
            context['overall_performance'] = 'average'
        elif context['avg_score'] < 85:
            context['overall_performance'] = 'good'
        else:
            context['overall_performance'] = 'excellent'

    except Exception as e:
        logger.error(f"Error building tutor context: {e}")

    return context


def _build_tutor_system_prompt(context, chat_history=None):
    """Build the system prompt for the AI tutor with full student context + memory."""
    prompt_parts = [
        "You are KyKnoX, the AI Tutor Avatar for LearnVaultX — a personalized learning platform.",
        "You are speaking directly to a student. Be supportive, encouraging, and specific.",
        "Use Markdown formatting in your responses. Use bullet points, bold, and emojis for clarity.",
        "Always give actionable, personalized advice based on the student's data below.",
        "",
        "=== STUDENT DATA ===",
    ]

    # Classes
    if context['classes']:
        prompt_parts.append(f"Enrolled in: {', '.join(c['title'] for c in context['classes'])}")

    # Performance
    prompt_parts.append(f"Overall performance: {context['overall_performance']} (avg score: {context['avg_score']}%)")
    prompt_parts.append(f"Total quizzes taken: {context['total_quizzes_taken']}")

    # Recent scores
    if context['recent_scores']:
        prompt_parts.append("\nRecent quiz scores:")
        for s in context['recent_scores']:
            prompt_parts.append(f"  - {s['quiz']}: {s['score']}/{s['total']} ({s['pct']}%)")

    # Weak topics
    if context['weak_topics']:
        prompt_parts.append("\n⚠️ Weak topics (needs improvement):")
        for w in context['weak_topics']:
            prompt_parts.append(f"  - {w['topic']} in {w['class']}: {w['accuracy']}% accuracy ({w['attempts']} questions)")

    # Strong topics
    if context['strong_topics']:
        prompt_parts.append("\n✅ Strong topics:")
        for s in context['strong_topics']:
            prompt_parts.append(f"  - {s['topic']} in {s['class']}: {s['accuracy']}% accuracy")

    # Next module
    if context['next_module']:
        prompt_parts.append(f"\nNext recommended module: {context['next_module']['title']} ({context['next_module']['class']})")

    prompt_parts.extend([
        "",
        "=== INSTRUCTIONS ===",
        "1. When asked 'what to study next' → recommend the next module and relevant weak topics",
        "2. When asked about low scores → analyze which topics are weak and suggest revision plans",
        "3. When asked for practice → suggest specific quizzes in their enrolled classes",
        "4. When asked to explain a topic → give a clear, educational explanation",
        "5. Always be motivational and encouraging",
        "6. Keep responses concise but helpful (max 300 words)",
        "7. End with 1-2 specific action items the student can take right now",
        "8. If you see conversation history below, ref prior topics naturally (e.g. 'Last time you asked about X')",
    ])

    # Inject conversation memory
    if chat_history:
        prompt_parts.append("")
        prompt_parts.append("=== RECENT CONVERSATION HISTORY ===")
        for msg in chat_history[-10:]:
            role_label = 'Student' if msg['role'] == 'user' else 'KyKnoX'
            prompt_parts.append(f"{role_label}: {msg['message'][:200]}")

    return "\n".join(prompt_parts)


def _fallback_tutor_response(message, context):
    """Generate a meaningful response without API."""
    msg_lower = message.lower()

    # Personalized fallback based on context
    parts = ["🎓 **KyKnoX AI Tutor**\n"]

    if 'study next' in msg_lower or 'what should' in msg_lower or 'recommend' in msg_lower:
        if context['next_module']:
            parts.append(f"Based on your progress, I recommend focusing on **{context['next_module']['title']}** in {context['next_module']['class']}.")
        if context['weak_topics']:
            parts.append("\n📌 **Areas to strengthen:**")
            for w in context['weak_topics'][:3]:
                parts.append(f"- **{w['topic']}** ({w['class']}): {w['accuracy']}% accuracy")
            parts.append("\nTry revising these topics and then attempt the related quizzes.")
        elif context['classes']:
            parts.append(f"\nYou're enrolled in {len(context['classes'])} classes. Keep taking quizzes to track your progress!")
        else:
            parts.append("\nJoin a class to get started with personalized learning!")

    elif 'weak' in msg_lower or 'gap' in msg_lower or 'struggle' in msg_lower:
        if context['weak_topics']:
            parts.append("📊 **Your weak areas detected:**\n")
            for w in context['weak_topics'][:5]:
                parts.append(f"- **{w['topic']}** in {w['class']}: only {w['accuracy']}% accuracy")
            parts.append("\n💡 **Tip:** Focus on one weak topic at a time. Review the lecture material, then attempt the quiz again.")
        else:
            parts.append("✅ No significant weak areas detected! Keep up the great work and continue practicing.")

    elif 'score' in msg_lower or 'result' in msg_lower or 'performance' in msg_lower:
        parts.append(f"📈 **Your Performance Summary:**\n")
        parts.append(f"- Overall average: **{context['avg_score']}%**")
        parts.append(f"- Total quizzes taken: **{context['total_quizzes_taken']}**")
        if context['recent_scores']:
            parts.append("\n**Recent scores:**")
            for s in context['recent_scores'][:3]:
                emoji = "🟢" if s['pct'] >= 70 else "🟡" if s['pct'] >= 50 else "🔴"
                parts.append(f"- {emoji} {s['quiz']}: {s['pct']}%")

    elif 'practice' in msg_lower or 'quiz' in msg_lower:
        parts.append("📝 **Practice Recommendations:**\n")
        if context['weak_topics']:
            parts.append("Focus on quizzes related to your weak topics:")
            for w in context['weak_topics'][:3]:
                parts.append(f"- Practice **{w['topic']}** questions in {w['class']}")
        parts.append("\nGo to your class page and attempt the available quizzes!")

    elif 'revision' in msg_lower or 'plan' in msg_lower:
        parts.append("📋 **Your Personalized Study Plan:**\n")
        if context['weak_topics']:
            parts.append("**Priority 1 — Revise weak topics:**")
            for i, w in enumerate(context['weak_topics'][:3], 1):
                parts.append(f"{i}. Study **{w['topic']}** from {w['class']} materials")
        if context['next_module']:
            parts.append(f"\n**Priority 2 — Continue learning:**")
            parts.append(f"- Complete **{context['next_module']['title']}** in {context['next_module']['class']}")
        parts.append(f"\n**Priority 3 — Practice daily:**")
        parts.append("- Attempt at least 1 quiz per day for consistency")

    else:
        parts.append(f"I'm here to help you learn! Here's a quick overview:\n")
        parts.append(f"- 📊 Your average score: **{context['avg_score']}%**")
        parts.append(f"- 📚 Classes enrolled: **{len(context['classes'])}**")
        if context['next_module']:
            parts.append(f"- 🎯 Next module: **{context['next_module']['title']}**")
        parts.append("\n**Try asking me:**\n- \"What should I study next?\"\n- \"Explain my weak topics\"\n- \"Make a revision plan\"\n- \"Show my performance\"")

    return "\n".join(parts)


def _detect_emotion_gesture(ai_text, context):
    """Detect emotion and gesture from AI response and student context.
    
    Emotions: happy, serious, encouraging, confused, excited, neutral
    Gestures: idle, talk, nod, wave, think, celebrate, point, shrug
    """
    text_lower = ai_text.lower()

    # ── EMOTION DETECTION ──────────────────────────
    # Priority order: performance-based → keyword-based → neutral
    emotion = 'neutral'

    if context.get('overall_performance') == 'excellent':
        emotion = 'happy'
    elif context.get('overall_performance') == 'struggling':
        emotion = 'encouraging'
    
    # Keyword overrides (more specific signals)
    if any(w in text_lower for w in ['congratulations', 'amazing', 'perfect score', 'outstanding', 'incredible']):
        emotion = 'excited'
    elif any(w in text_lower for w in ['great job', 'well done', 'keep it up', 'fantastic', 'excellent work', 'nice work']):
        emotion = 'happy'
    elif any(w in text_lower for w in ['not sure', 'unclear', 'hard to say', 'depends on', 'it varies']):
        emotion = 'confused'
    elif any(w in text_lower for w in ['improve', 'weak', 'low score', 'revise', 'practice more', 'don\'t worry']):
        emotion = 'encouraging'
    elif any(w in text_lower for w in ['important', 'critical', 'must', 'carefully', 'pay attention']):
        emotion = 'serious'

    # ── GESTURE DETECTION ──────────────────────────
    gesture = 'idle'

    # Celebration gestures (achievements, milestones)
    if any(w in text_lower for w in ['congratulations', 'achieved', 'completed', 'milestone', 'perfect']):
        gesture = 'celebrate'
    # Wave gesture (greetings, welcomes)
    elif any(w in text_lower for w in ['hello', 'welcome', 'hi there', 'good morning', 'good evening', 'greetings']):
        gesture = 'wave'
    # Think gesture (analysis, consideration)
    elif any(w in text_lower for w in ['let me think', 'consider', 'interesting', 'analyzing', 'looking at your']):
        gesture = 'think'
    # Point gesture (specific recommendations)
    elif any(w in text_lower for w in ['focus on', 'start with', 'i recommend', 'you should try', 'take a look']):
        gesture = 'point'
    # Shrug gesture (uncertainty, options)
    elif any(w in text_lower for w in ['depends', 'either way', 'up to you', 'hard to say', 'not sure']):
        gesture = 'shrug'
    # Nod gesture (agreement, encouragement)
    elif any(w in text_lower for w in ['exactly', 'right', 'correct', 'yes', 'agree', 'good question']):
        gesture = 'nod'
    # Talk gesture (explanations, long answers)
    elif any(w in text_lower for w in ['explain', 'means', 'concept', 'understand', 'how', 'let me']):
        gesture = 'talk'

    return emotion, gesture


def _build_recommended_actions(context):
    """Build a list of concrete recommended actions."""
    actions = []

    if context['next_module']:
        actions.append(f"Study Module: {context['next_module']['title']}")

    for w in context['weak_topics'][:2]:
        actions.append(f"Revise: {w['topic']} ({w['class']})")

    if context['total_quizzes_taken'] < 5:
        actions.append("Take more quizzes to build your learning profile")

    if not actions:
        actions = [
            "Explore your enrolled classes",
            "Attempt a practice quiz",
            "Set a daily learning goal"
        ]

    return actions[:5]
