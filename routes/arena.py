"""
Exam Arena (KyKnoX Exam Engine) Blueprint
Isolated module for competitive exam preparation with adaptive AI.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, date
import json, logging, random, os, requests as http_requests
import sqlite3

logger = logging.getLogger(__name__)
arena_bp = Blueprint('arena', __name__)

# ─── EXAM → SUBJECT MAPPING (Single Source of Truth) ────────
EXAM_SUBJECT_MAP = {
    'JEE':  ['Physics', 'Chemistry', 'Mathematics'],
    'NEET': ['Physics', 'Chemistry', 'Biology'],
    'OJEE': ['Physics', 'Chemistry', 'Mathematics', 'Biology', 'Logical Reasoning'],
    'UPSC': ['General Studies', 'Indian Polity', 'Indian History', 'Geography', 'Economy', 'Environment', 'Current Affairs'],
}

_db = None
_kyknox = None

def init_arena(db, kyknox):
    global _db, _kyknox
    _db = db
    _kyknox = kyknox

def _require_student():
    """Return student user_id, or 'NO_AUTH'/'WRONG_ROLE' string."""
    if 'user_id' not in session:
        return 'NO_AUTH'
    if session.get('role') != 'student':
        return 'WRONG_ROLE'
    return session['user_id']

def _guard_arena():
    """Check arena access. Returns (uid, error_response) tuple."""
    uid = _require_student()
    if uid == 'NO_AUTH':
        return None, redirect(url_for('login', next=request.path))
    if uid == 'WRONG_ROLE':
        flash('Exam Arena is available only for students.', 'warning')
        return None, redirect(url_for('teacher_dashboard'))
    return uid, None

# ─── QUESTION SEED DATA (Truncated for brevity, full content is in Step 219 if needed) ───
SEED_QUESTIONS = {
    'JEE': {
        'Physics': {
            'Mechanics': [
                ("A block of mass 5 kg is placed on a frictionless inclined plane of angle 30°. What is the acceleration of the block?", "4.9 m/s²", "9.8 m/s²", "2.45 m/s²", "7.35 m/s²", "A", "On a frictionless incline, a = g sin θ = 9.8 × sin 30° = 9.8 × 0.5 = 4.9 m/s²", 60),
                ("A projectile is launched at 60° with initial velocity 20 m/s. What is the maximum height?", "15.3 m", "20.4 m", "10.2 m", "5.1 m", "A", "H = u²sin²θ/(2g) = 400×0.75/19.6 ≈ 15.3 m", 90),
                ("Two masses 3 kg and 5 kg are connected by a string over a pulley. Find the acceleration.", "2.45 m/s²", "4.9 m/s²", "1.225 m/s²", "3.675 m/s²", "A", "a = (m₂-m₁)g/(m₁+m₂) = 2×9.8/8 = 2.45 m/s²", 75),
                ("A car moves in a circle of radius 50 m at 20 m/s. What is the centripetal acceleration?", "8 m/s²", "4 m/s²", "10 m/s²", "2 m/s²", "A", "a = v²/r = 400/50 = 8 m/s²", 60),
                ("What is the work done by a force of 10 N moving an object 5 m at 60° to the displacement?", "25 J", "50 J", "43.3 J", "8.66 J", "A", "W = Fd cos θ = 10×5×cos60° = 50×0.5 = 25 J", 60),
            ],
            'Thermodynamics': [
                ("An ideal gas at 300K is compressed isothermally to half its volume. The work done on the gas (n=1 mol) is:", "1728 J", "2078 J", "862 J", "3456 J", "A", "W = nRT ln(V₁/V₂) = 1×8.314×300×ln(2) ≈ 1728 J", 90),
                ("The efficiency of a Carnot engine operating between 500K and 300K is:", "40%", "60%", "50%", "30%", "A", "η = 1 - T_cold/T_hot = 1 - 300/500 = 0.4 = 40%", 60),
                ("For an adiabatic process, if γ=1.4 and volume is halved, the temperature ratio T₂/T₁ is:", "1.32", "2.0", "1.4", "0.76", "A", "T₂/T₁ = (V₁/V₂)^(γ-1) = 2^0.4 ≈ 1.32", 90),
                ("The internal energy of an ideal monoatomic gas at temperature T for n moles is:", "3nRT/2", "5nRT/2", "nRT", "nRT/2", "A", "U = (f/2)nRT = (3/2)nRT for monoatomic gas", 45),
                ("In a free expansion of an ideal gas:", "ΔU = 0, W = 0, Q = 0", "ΔU > 0, W = 0", "ΔU = 0, W > 0", "ΔU < 0, Q > 0", "A", "Free expansion: no external pressure, W=0; ideal gas: ΔU depends only on T, which doesn't change, so ΔU=0 and Q=0", 75),
            ],
            'Electrostatics': [
                ("Two charges +2μC and -2μC are 10 cm apart. The electric field at the midpoint is:", "14.4 × 10⁶ N/C", "7.2 × 10⁶ N/C", "0 N/C", "28.8 × 10⁶ N/C", "A", "Fields add at midpoint of dipole: E = 2kq/r² = 2×9×10⁹×2×10⁻⁶/(0.05)² ≈ 14.4×10⁶ N/C", 90),
                ("A capacitor of 10 μF is charged to 100V. The energy stored is:", "0.05 J", "0.5 J", "0.1 J", "1 J", "A", "E = ½CV² = 0.5×10×10⁻⁶×10000 = 0.05 J", 60),
                ("Gauss's law is most useful for finding electric field when the charge distribution has:", "High symmetry", "Random distribution", "Point charges only", "Uniform density only", "A", "Gauss's law is most useful with symmetric charge distributions (spherical, cylindrical, planar)", 45),
                ("The electric potential at a distance r from a point charge q is:", "kq/r", "kq/r²", "kq²/r", "kqr", "A", "V = kq/r is the electric potential due to a point charge", 30),
                ("If the distance between two charges is doubled, the force becomes:", "F/4", "F/2", "2F", "4F", "A", "By Coulomb's law, F ∝ 1/r², so doubling r gives F/4", 30),
            ],
        },
        'Chemistry': {
            'Atomic Structure': [
                ("The maximum number of electrons in a shell with principal quantum number n=3 is:", "18", "8", "32", "9", "A", "Max electrons = 2n² = 2(3)² = 18", 30),
                ("The shape of a d-orbital is:", "Cloverleaf", "Spherical", "Dumbbell", "Linear", "A", "d-orbitals have a cloverleaf (four-lobed) shape", 30),
                ("Which quantum number determines the shape of an orbital?", "Azimuthal (l)", "Principal (n)", "Magnetic (mₗ)", "Spin (mₛ)", "A", "The azimuthal quantum number l determines the shape", 45),
                ("The de Broglie wavelength of an electron accelerated through 100V is approximately:", "0.123 nm", "1.23 nm", "0.0123 nm", "12.3 nm", "A", "λ = 1.226/√V nm = 1.226/10 ≈ 0.123 nm", 75),
                ("Heisenberg's uncertainty principle states:", "Δx·Δp ≥ ℏ/2", "ΔE·Δt = 0", "Δx·Δv = 0", "Δp = mΔv exactly", "A", "The uncertainty principle: Δx·Δp ≥ ℏ/2", 45),
            ],
            'Chemical Bonding': [
                ("The bond angle in methane (CH₄) is:", "109.5°", "120°", "90°", "180°", "A", "CH₄ has tetrahedral geometry with bond angle 109.5°", 30),
                ("Which molecule has the highest dipole moment?", "HF", "HCl", "HBr", "HI", "A", "HF has the highest dipole moment due to highest electronegativity difference", 45),
                ("The hybridization of carbon in ethylene (C₂H₄) is:", "sp²", "sp³", "sp", "sp³d", "A", "Double bond means sp² hybridization with one unhybridized p orbital for π bond", 45),
                ("How many sigma and pi bonds are in acetylene (C₂H₂)?", "3σ, 2π", "2σ, 3π", "5σ, 0π", "2σ, 2π", "A", "C≡C has 1σ+2π, each C-H has 1σ: total 3σ + 2π", 60),
                ("The VSEPR shape of SF₆ is:", "Octahedral", "Tetrahedral", "Trigonal bipyramidal", "Square planar", "A", "6 bonding pairs around S → octahedral geometry", 45),
            ],
        },
    },
    'NEET': {
        'Biology': {
            'Cell Biology': [
                ("The powerhouse of the cell is:", "Mitochondria", "Nucleus", "Ribosome", "Golgi apparatus", "A", "Mitochondria produce ATP through oxidative phosphorylation", 30),
                ("Which organelle is involved in protein synthesis?", "Ribosome", "Lysosome", "Peroxisome", "Vacuole", "A", "Ribosomes translate mRNA into proteins", 30),
                ("The fluid mosaic model of cell membrane was proposed by:", "Singer and Nicolson", "Watson and Crick", "Schleiden and Schwann", "Robert Hooke", "A", "Singer and Nicolson proposed the fluid mosaic model in 1972", 45),
                ("Rough endoplasmic reticulum has ribosomes on its surface for:", "Protein synthesis and secretion", "Lipid synthesis", "Detoxification", "DNA replication", "A", "RER synthesizes proteins destined for secretion or membrane insertion", 45),
                ("The cell organelle involved in autophagy is:", "Lysosome", "Ribosome", "Mitochondria", "Golgi body", "A", "Lysosomes contain hydrolytic enzymes that digest worn-out organelles (autophagy)", 45),
            ],
        },
        'Physics': {
             'Optics': [
                ("The phenomenon of splitting of white light into colors is:", "Dispersion", "Diffraction", "Interference", "Polarization", "A", "Dispersion occurs because different wavelengths refract at different angles", 30),
                ("The focal length of a convex lens is 20 cm. Its power is:", "+5 D", "-5 D", "+20 D", "+0.2 D", "A", "P = 1/f(m) = 1/0.20 = +5 D", 30),
                ("Total internal reflection occurs when light travels from:", "Denser to rarer medium", "Rarer to denser medium", "Same medium", "Vacuum to glass", "A", "TIR occurs when light goes from denser to rarer medium at angle > critical angle", 45),
                ("In Young's double slit experiment, fringe width is proportional to:", "Wavelength", "Slit width", "1/slit separation", "Both A and C", "D", "β = λD/d, proportional to both wavelength and inversely to slit separation", 60),
                ("A concave mirror of focal length 15 cm forms a real image at 30 cm. Object distance is:", "30 cm", "15 cm", "10 cm", "45 cm", "A", "1/f = 1/v + 1/u → 1/15 = 1/30 + 1/u → u = 30 cm", 60),
            ],
        },
    }
}

def _get_difficulty_pool():
    return ['Easy', 'Medium', 'Hard']

def _generate_fallback_questions(exam, subject):
    """Generate basic fallback questions when no seed data exists."""
    topics = {
        'Physics': ['Mechanics', 'Thermodynamics', 'Electrostatics', 'Optics', 'Waves'],
        'Chemistry': ['Atomic Structure', 'Chemical Bonding', 'Organic Chemistry', 'Thermochemistry', 'Equilibrium'],
        'Mathematics': ['Calculus', 'Algebra', 'Coordinate Geometry', 'Trigonometry', 'Probability'],
        'Biology': ['Cell Biology', 'Genetics', 'Human Physiology', 'Ecology', 'Evolution'],
        'Logical Reasoning': ['Analogies', 'Series Completion', 'Blood Relations', 'Coding-Decoding', 'Syllogisms'],
        'General Studies': ['Indian History', 'Indian Polity', 'Geography', 'Economy', 'Science & Technology'],
        'Indian Polity': ['Constitution', 'Parliament', 'Judiciary', 'Fundamental Rights', 'Panchayati Raj'],
        'Indian History': ['Ancient India', 'Medieval India', 'Modern India', 'Freedom Movement', 'Post-Independence'],
        'Geography': ['Physical Geography', 'Indian Geography', 'World Geography', 'Climatology', 'Oceanography'],
        'Economy': ['GDP & Growth', 'Inflation & Monetary Policy', 'Fiscal Policy & Budget', 'Banking & RBI', 'International Trade'],
        'Environment': ['Biodiversity', 'Climate Change', 'Pollution', 'Environmental Laws', 'Sustainable Development'],
        'Current Affairs': ['National Events', 'International Relations', 'Science & Tech', 'Sports & Awards', 'Government Schemes'],
    }
    topic_list = topics.get(subject, ['General'])
    for topic in topic_list:
        for diff in _get_difficulty_pool():
            for i in range(3):
                _db.execute_insert(
                    '''INSERT INTO arena_question_bank
                       (exam, subject, topic_tag, difficulty, question_text,
                        option_a, option_b, option_c, option_d, correct_option,
                        explanation, estimated_time_seconds, source_tag)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (exam, subject, topic, diff,
                     f"[{exam}] {subject} - {topic} ({diff}) Practice Question {i+1}: This is a demonstration question. Which option is correct?",
                     "Option A (Correct)", "Option B", "Option C", "Option D",
                     "A", f"This is a placeholder for {topic}. Real questions will be generated by AI.",
                     60, 'FALLBACK')
                )

def _seed_questions_if_needed(exam, subject):
    """Seed questions for an exam+subject combo if the bank is empty."""
    count = _db.execute_one(
        'SELECT COUNT(*) as cnt FROM arena_question_bank WHERE exam=? AND subject=?',
        (exam, subject)
    )
    if count and count['cnt'] >= 10:
        return

    logger.info(f"[ARENA] Seeding questions for {exam}/{subject}")
    exam_data = SEED_QUESTIONS.get(exam, {}).get(subject, {})

    for topic_tag, questions in exam_data.items():
        for diff in _get_difficulty_pool():
            for q in questions:
                try:
                    _db.execute_insert(
                        '''INSERT INTO arena_question_bank
                           (exam, subject, topic_tag, difficulty, question_text,
                            option_a, option_b, option_c, option_d, correct_option,
                            explanation, estimated_time_seconds, source_tag)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (exam, subject, topic_tag, diff, q[0],
                         q[1], q[2], q[3], q[4], q[5], q[6], q[7], 'SEED')
                    )
                except Exception:
                    pass

    # Always ensure at least some fallback questions exist if seeding was empty or partial
    _generate_fallback_questions(exam, subject)


def _ensure_rank_status(student_id):
    """Ensure rank status row exists for student."""
    row = _db.execute_one('SELECT id FROM arena_rank_status WHERE student_id=?', (student_id,))
    if not row:
        _db.execute_insert(
            'INSERT INTO arena_rank_status (student_id, rank_name, xp_total, streak_days, readiness_score) VALUES (?,?,?,?,?)',
            (student_id, 'Bronze', 0, 0, 0)
        )


def _calculate_rank(xp, accuracy, streak):
    score = xp * 0.5 + accuracy * 3 + streak * 10
    if score >= 800:
        return 'Diamond'
    elif score >= 500:
        return 'Platinum'
    elif score >= 300:
        return 'Gold'
    elif score >= 150:
        return 'Silver'
    return 'Bronze'


def _compute_readiness(student_id, exam, subject):
    """Compute readiness score: accuracy(50%) + difficulty(25%) + speed(15%) + attempt_penalty(10%)."""
    attempts = _db.execute_query(
        "SELECT * FROM arena_attempts WHERE student_id=? AND exam=? AND subject=? AND status='completed' ORDER BY created_at DESC LIMIT 10",
        (student_id, exam, subject)
    )
    if not attempts:
        return 0.0

    # Accuracy component (50%) — recent attempts weighted higher via exponential decay
    weighted_acc = 0
    weight_sum = 0
    for i, a in enumerate(attempts):
        weight = 1.0 / (1 + i * 0.3)  # Most recent = weight 1.0, second = 0.77, third = 0.63...
        acc = (a['score'] / a['total_questions'] * 100) if a['total_questions'] > 0 else 0
        weighted_acc += acc * weight
        weight_sum += weight
    accuracy_component = (weighted_acc / weight_sum if weight_sum > 0 else 0) * 0.50

    # Difficulty component (25%) — harder questions solved = higher readiness
    diff_map = {'Easy': 30, 'Medium': 60, 'Hard': 90, 'Extreme': 100}
    diff_scores = [diff_map.get(a.get('difficulty_end') or a.get('difficulty_start', 'Medium'), 50) for a in attempts]
    difficulty_component = (sum(diff_scores) / len(diff_scores)) * 0.25 if diff_scores else 50 * 0.25

    # Speed consistency component (15%) — stable speed is better than erratic
    avg_times = [a['avg_time_per_question'] for a in attempts if a['avg_time_per_question'] and a['avg_time_per_question'] > 0]
    if avg_times:
        avg_speed = sum(avg_times) / len(avg_times)
        speed_score = max(0, min(100, (90 - avg_speed) / 90 * 100))
        # Bonus for consistency (low std dev)
        if len(avg_times) > 1:
            mean = avg_speed
            variance = sum((t - mean) ** 2 for t in avg_times) / len(avg_times)
            std_dev = variance ** 0.5
            consistency_bonus = max(0, min(20, 20 - std_dev))  # Lower std = higher bonus
            speed_score = min(100, speed_score + consistency_bonus)
        speed_component = speed_score * 0.15
    else:
        speed_component = 50 * 0.15

    # Attempt penalty component (10%) — repeated failures reduce score
    total_attempts = len(attempts)
    failed_attempts = sum(1 for a in attempts if (a['accuracy_percent'] or 0) < 40)
    failure_ratio = failed_attempts / total_attempts if total_attempts > 0 else 0
    attempt_penalty_component = max(0, (1 - failure_ratio) * 100) * 0.10

    readiness = accuracy_component + difficulty_component + speed_component + attempt_penalty_component
    return round(min(100, max(0, readiness)), 1)


def _pick_adaptive_difficulty(student_id, exam, subject):
    """Choose next difficulty based on trend of last 3 attempts, not just the latest one."""
    recent = _db.execute_query(
        "SELECT accuracy_percent, avg_time_per_question, difficulty_end FROM arena_attempts WHERE student_id=? AND exam=? AND subject=? AND status='completed' ORDER BY created_at DESC LIMIT 3",
        (student_id, exam, subject)
    )
    if not recent:
        return 'Medium'

    # Weighted average: most recent attempt counts more
    weights = [0.5, 0.3, 0.2][:len(recent)]
    weight_sum = sum(weights)
    avg_acc = sum((r['accuracy_percent'] or 0) * w for r, w in zip(recent, weights)) / weight_sum
    avg_speed = sum((r['avg_time_per_question'] or 60) * w for r, w in zip(recent, weights)) / weight_sum

    # Count consecutive failures for revision mode detection
    consecutive_fails = 0
    for r in recent:
        if (r['accuracy_percent'] or 0) < 40:
            consecutive_fails += 1
        else:
            break

    logger.info(f"[ARENA-ADAPT] uid={student_id} avg_acc={avg_acc:.1f}% avg_speed={avg_speed:.1f}s consecutive_fails={consecutive_fails}")

    # Revision mode trigger: multiple consecutive failures
    if consecutive_fails >= 2:
        return 'Easy'  # Force easy + revision will be triggered in submit

    if avg_acc >= 85 and avg_speed < 40:
        return 'Hard'
    elif avg_acc >= 70 and avg_speed < 50:
        return 'Hard' if recent[0].get('difficulty_end') == 'Medium' else 'Medium'
    elif avg_acc >= 50 and avg_speed < 70:
        return 'Medium'
    elif avg_acc < 40 or avg_speed > 90:
        return 'Easy'
    return 'Medium'


# ─── POST-SUBMISSION ANALYTICS ENGINE ────────────────────────

def _update_topic_mastery(uid, exam, subject, wrong_answers, correct_answers):
    """Update per-topic mastery scores based on quiz results."""
    topic_stats = {}  # topic -> {correct: int, total: int}

    for ans in correct_answers:
        topic = ans.get('topic_tag', 'General')
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0}
        topic_stats[topic]['correct'] += 1
        topic_stats[topic]['total'] += 1

    for ans in wrong_answers:
        topic = ans.get('topic_tag', 'General')
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0}
        topic_stats[topic]['total'] += 1

    for topic, stats in topic_stats.items():
        if not topic:
            continue
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0

        # Blend with existing mastery (70% new, 30% old)
        existing = _db.execute_one(
            'SELECT mastery_score FROM arena_topic_mastery WHERE student_id=? AND exam=? AND subject=? AND topic_tag=?',
            (uid, exam, subject, topic)
        )
        if existing:
            blended = accuracy * 0.7 + existing['mastery_score'] * 0.3
        else:
            blended = accuracy

        weak_flag = 1 if blended < 50 else 0

        # Upsert
        try:
            _db.execute_insert(
                '''INSERT INTO arena_topic_mastery (student_id, exam, subject, topic_tag, mastery_score, weak_flag, updated_at)
                   VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                (uid, exam, subject, topic, round(blended, 1), weak_flag)
            )
        except Exception:
            _db.execute_update(
                '''UPDATE arena_topic_mastery SET mastery_score=?, weak_flag=?, updated_at=CURRENT_TIMESTAMP
                   WHERE student_id=? AND exam=? AND subject=? AND topic_tag=?''',
                (round(blended, 1), weak_flag, uid, exam, subject, topic)
            )

    logger.info(f"[ARENA-MASTERY] Updated topic mastery for uid={uid}: {list(topic_stats.keys())}")


def _generate_ai_notes(uid, attempt_id, wrong_answers):
    """Generate AI revision notes for each wrong answer's topic."""
    topics_covered = set()

    for ans in wrong_answers:
        topic = ans.get('topic_tag', 'General')
        if topic in topics_covered:
            continue
        topics_covered.add(topic)

        q_text = ans.get('question_text', 'Unknown question')
        correct = ans.get('correct_option', '?')
        explanation = ans.get('explanation', 'No explanation available')

        mistake_summary = f"Missed a question on {topic}: {q_text[:100]}..."
        quick_fix = f"The correct answer was '{correct}'. {explanation}"
        memory_trick = _generate_memory_trick(topic, explanation)

        try:
            _db.execute_insert(
                '''INSERT INTO arena_ai_notes (student_id, attempt_id, topic_tag, mistake_summary, quick_fix, memory_trick)
                   VALUES (?,?,?,?,?,?)''',
                (uid, attempt_id, topic, mistake_summary, quick_fix, memory_trick)
            )
        except Exception as e:
            logger.error(f"[ARENA-AI-NOTES] Failed to insert note for topic={topic}: {e}")

    logger.info(f"[ARENA-AI-NOTES] Generated {len(topics_covered)} AI notes for attempt_id={attempt_id}")


def _generate_memory_trick(topic, explanation):
    """Generate a memory trick based on the topic and explanation."""
    tricks = {
        'Mechanics': 'Remember: F=ma is the foundation. Mass stays, force and acceleration are proportional!',
        'Thermodynamics': 'Think of heat as water flowing downhill — from hot to cold, never backward without work.',
        'Electrostatics': 'Like charges repel, unlike attract. Force drops with square of distance (inverse square law).',
        'Optics': 'Mirror mirror on the wall: concave converges, convex diverges. Lenses do the opposite!',
        'Atomic Structure': 'Remember: n (principal) = size, l (azimuthal) = shape, m = orientation, s = spin.',
        'Chemical Bonding': 'Sigma bonds are strong head-on overlaps. Pi bonds are weaker sideways overlaps.',
        'Cell Biology': 'Mitochondria = powerhouse, Ribosome = protein factory, Lysosome = recycling center.',
        'Genetics': 'DNA → RNA → Protein. Central dogma never changes!',
        'Calculus': 'Derivative = slope of tangent, Integral = area under curve. They are inverses!',
        'Algebra': 'Quadratic formula: x = (-b ± √(b²-4ac)) / 2a. Never forget the ±!',
    }
    return tricks.get(topic, f"Focus on understanding the core concept: {explanation[:80]}...")


def _generate_revision_plan(uid, attempt_id, exam, subject):
    """Generate a comprehensive revision plan after poor performance or 3rd attempt."""
    # Get wrong answers from this attempt
    wrong = _db.execute_query(
        '''SELECT aa.*, qb.topic_tag, qb.question_text, qb.explanation, qb.correct_option
           FROM arena_attempt_answers aa
           JOIN arena_question_bank qb ON aa.question_id = qb.id
           WHERE aa.attempt_id=? AND aa.is_correct=0''',
        (attempt_id,)
    )

    if not wrong:
        return  # No wrong answers = no revision needed

    # Get current readiness
    readiness_before = _compute_readiness(uid, exam, subject)

    # Build mistake summary
    topic_mistakes = {}
    for w in wrong:
        t = w.get('topic_tag', 'General')
        if t not in topic_mistakes:
            topic_mistakes[t] = []
        topic_mistakes[t].append({
            'question': w.get('question_text', ''),
            'correct': w.get('correct_option', ''),
            'explanation': w.get('explanation', '')
        })

    mistake_summary = ''
    for topic, mistakes in topic_mistakes.items():
        mistake_summary += f"\n### {topic} ({len(mistakes)} mistake{'s' if len(mistakes) > 1 else ''})\n"
        for m in mistakes[:3]:  # Max 3 per topic
            mistake_summary += f"- Q: {m['question'][:80]}... → Correct: {m['correct']}\n"

    # Build revision notes
    revision_notes = ''
    for topic, mistakes in topic_mistakes.items():
        revision_notes += f"\n## {topic}\n"
        for m in mistakes[:2]:
            revision_notes += f"**Key concept:** {m['explanation'][:150]}\n\n"
        trick = _generate_memory_trick(topic, mistakes[0]['explanation'])
        revision_notes += f"💡 **Memory Trick:** {trick}\n"

    # Practice questions: pick 3 from weak topics
    weak_tags = list(topic_mistakes.keys())
    practice_q = []
    if weak_tags:
        placeholders = ','.join('?' for _ in weak_tags)
        practice_rows = _db.execute_query(
            f'''SELECT id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic_tag
                FROM arena_question_bank WHERE exam=? AND subject=? AND topic_tag IN ({placeholders})
                AND id NOT IN (SELECT question_id FROM arena_attempt_answers WHERE attempt_id=?)
                ORDER BY RANDOM() LIMIT 3''',
            (exam, subject, *weak_tags, attempt_id)
        )
        for pq in practice_rows:
            practice_q.append({
                'question': pq['question_text'],
                'options': {'A': pq['option_a'], 'B': pq['option_b'], 'C': pq['option_c'], 'D': pq['option_d']},
                'correct': pq['correct_option'],
                'explanation': pq['explanation'],
                'topic': pq['topic_tag']
            })

    topic_suggestions = [{'topic': t, 'mistake_count': len(m), 'priority': 'HIGH' if len(m) >= 2 else 'MEDIUM'}
                         for t, m in topic_mistakes.items()]

    try:
        _db.execute_insert(
            '''INSERT INTO arena_revision_plans
               (student_id, attempt_id, exam, subject, mistake_summary, revision_notes,
                practice_questions, topic_suggestions, readiness_before)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (uid, attempt_id, exam, subject, mistake_summary, revision_notes,
             json.dumps(practice_q), json.dumps(topic_suggestions), readiness_before)
        )
        logger.info(f"[ARENA-REVISION] Generated revision plan for uid={uid} attempt={attempt_id}")
    except Exception as e:
        logger.error(f"[ARENA-REVISION] Failed to insert revision plan: {e}")


# ─── GAMIFICATION CONSTANTS ──────────────────────────────────

LEVEL_THRESHOLDS = [0, 200, 500, 1000, 2000, 3500, 5500, 8000, 11000, 15000, 20000]

ACHIEVEMENTS = {
    'FIRST_BLOOD': {'title': 'First Blood', 'desc': 'Complete your first quiz', 'icon': '⚔️'},
    'SPEED_DEMON': {'title': 'Speed Demon', 'desc': 'Complete a quiz with avg time < 10s', 'icon': '⚡'},
    'PERFECT_10': {'title': 'Perfect 10', 'desc': 'Score 10/10 in a quiz', 'icon': '🎯'},
    'STREAK_MASTER': {'title': 'Streak Master', 'desc': 'Reach a 7-day streak', 'icon': '🔥'},
    'BOSS_SLAYER': {'title': 'Boss Slayer', 'desc': 'Win a Boss Fight', 'icon': '👹'},
    'SCHOLAR': {'title': 'Scholar', 'desc': 'Reach Level 5', 'icon': '🎓'},
    'LEGEND': {'title': 'Legend', 'desc': 'Reach Diamond Rank', 'icon': '💎'},
}

def _get_level(xp):
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp < threshold:
            return i
    return len(LEVEL_THRESHOLDS) + int((xp - LEVEL_THRESHOLDS[-1]) / 5000)

def _get_next_level_xp(level):
    if level < len(LEVEL_THRESHOLDS):
        return LEVEL_THRESHOLDS[level]
    return LEVEL_THRESHOLDS[-1] + (level - len(LEVEL_THRESHOLDS) + 1) * 5000

def _check_achievements(uid, attempt_data=None):
    newly_unlocked = []
    
    # Get current stats
    rank_row = _db.execute_one('SELECT * FROM arena_rank_status WHERE student_id=?', (uid,))
    profile = _db.execute_one('SELECT * FROM arena_profiles WHERE student_id=?', (uid,))
    existing_badges = _db.execute_query('SELECT achievement_code FROM arena_achievements WHERE student_id=?', (uid,))
    owned_codes = {b['achievement_code'] for b in existing_badges}
    
    def _unlock(code):
        if code not in owned_codes:
            meta = ACHIEVEMENTS[code]
            _db.execute_insert(
                'INSERT INTO arena_achievements (student_id, achievement_code, title, description, icon) VALUES (?,?,?,?,?)',
                (uid, code, meta['title'], meta['desc'], meta['icon'])
            )
            # Award generic XP for achievement
            _award_xp(uid, 100, 'achievement', f"Unlocked: {meta['title']}")
            newly_unlocked.append(meta)
            owned_codes.add(code)

    # 1. First Blood
    total_attempts = _db.execute_one('SELECT COUNT(*) as cnt FROM arena_attempts WHERE student_id=?', (uid,))['cnt']
    if total_attempts >= 1:
        _unlock('FIRST_BLOOD')

    # 2. Scholar (Level 5)
    level = _get_level(rank_row['xp_total']) if rank_row else 1
    if level >= 5:
        _unlock('SCHOLAR')

    # 3. Legend (Diamond Rank)
    if rank_row and rank_row['rank_name'] == 'Diamond':
        _unlock('LEGEND')

    # 4. Streak Master
    if rank_row and rank_row['streak_days'] >= 7:
        _unlock('STREAK_MASTER')

    # Attempt-specific checks
    if attempt_data:
        # 5. Perfect 10
        if attempt_data['score'] == attempt_data['total_questions'] and attempt_data['total_questions'] >= 10:
            _unlock('PERFECT_10')
        
        # 6. Speed Demon
        if attempt_data['avg_time'] < 10 and attempt_data['total_questions'] >= 5:
            _unlock('SPEED_DEMON')

        # 7. Boss Slayer
        if attempt_data['attempt_type'] == 'boss_fight' and attempt_data['score'] >= 10:
             _unlock('BOSS_SLAYER')

    return newly_unlocked

def _award_xp(uid, amount, source, desc=''):
    _db.execute_insert(
        'INSERT INTO arena_xp_log (student_id, amount, source, description) VALUES (?,?,?,?)',
        (uid, amount, source, desc)
    )
    if source == 'achievement':
         _db.execute_update(
            'UPDATE arena_rank_status SET xp_total = xp_total + ? WHERE student_id=?',
            (amount, uid)
        )

# ─── CORE MISSION MAP LOGIC ─────────────────────────────────

def _get_mission_map(uid):
    """Generate the mission map status. GUARANTEED TO RETURN LIST."""
    
    # 1. Define Core Nodes (Always exist)
    missions = [
        {'id': 'daily_challenge', 'title': 'Daily Challenge', 'type': 'daily', 'x': 10, 'y': 50, 'icon': '📅'},
        {'id': 'adaptive_mock', 'title': 'Adaptive Mock', 'type': 'mock', 'x': 30, 'y': 20, 'icon': '🧠'},
        {'id': 'weakness_fix', 'title': 'Weakness Fix', 'type': 'weakness', 'x': 50, 'y': 50, 'icon': '🔧'},
        {'id': 'speed_run', 'title': 'Speed Run', 'type': 'speed', 'x': 70, 'y': 80, 'icon': '⚡'},
        {'id': 'boss_fight', 'title': 'Boss Fight', 'type': 'boss', 'x': 90, 'y': 50, 'icon': '👹'},
    ]
    
    # 2. Get Unlock Prereqs
    mock_count = 0
    try:
        res = _db.execute_one("SELECT COUNT(*) as cnt FROM arena_attempts WHERE student_id=? AND attempt_type='mock'", (uid,))
        if res: mock_count = res['cnt']
    except Exception as e:
        logger.error(f"Error checking mock count: {e}")

    today = date.today().isoformat()
    daily_done = False
    try:
        res = _db.execute_one("SELECT id FROM arena_attempts WHERE student_id=? AND attempt_type='daily' AND DATE(created_at)=?", (uid, today))
        if res: daily_done = True
    except: pass
    
    # 3. Build Map List
    map_data = []
    
    for m in missions:
        status = 'locked'
        stars = 0
        
        # Dynamic Unlock Logic
        if m['id'] == 'daily_challenge':
            status = 'completed' if daily_done else 'unlocked'
        elif m['id'] == 'adaptive_mock':
             status = 'unlocked' # Always open
        elif m['id'] == 'weakness_fix':
             if mock_count >= 1: status = 'unlocked'
        elif m['id'] == 'speed_run':
             if mock_count >= 2: status = 'unlocked'
        elif m['id'] == 'boss_fight':
             if mock_count >= 3: status = 'unlocked'

        map_data.append({
            **m,
            'status': status,
            'stars': stars,
            'level_req': 1 # simplifying
        })
        
    return map_data

# ─── ROUTES ──────────────────────────────────────────────────

@arena_bp.route('/arena')
def arena_dashboard():
    uid, err = _guard_arena()
    if err: return err
        
    # Default State
    profile = None
    rank = None
    level = 1
    next_xp = 100
    progress_percent = 0
    daily_done = False
    readiness = 0
    strongest = 'None'
    weakest = 'None'
    mock_attempts_used = 0
    mission_map = []
    achievements = []

    error_msg = None
    try:
        # 1. Ensure Dependencies
        _ensure_rank_status(uid)

        # 2. Load Core Data
        profile = _db.execute_one('SELECT * FROM arena_profiles WHERE student_id=?', (uid,))
        if not profile:
            # Auto-create profile if missing
            _db.execute_insert(
                'INSERT INTO arena_profiles (student_id, exam, subject, mode, preferred_difficulty) VALUES (?,?,?,?,?)',
                (uid, 'JEE', 'Physics', 'Practice', 'Auto')
            )
            profile = {'exam': 'JEE', 'subject': 'Physics', 'mode': 'Practice', 'preferred_difficulty': 'Auto'}
        
        rank = _db.execute_one('SELECT * FROM arena_rank_status WHERE student_id=?', (uid,))

        # 3. Load Readiness & Stats
        exam = profile.get('exam', 'JEE')
        subject = profile.get('subject', 'Physics')
        
        readiness = _compute_readiness(uid, exam, subject)
        
        # Update readiness
        _db.execute_update(
            'UPDATE arena_rank_status SET readiness_score=?, updated_at=CURRENT_TIMESTAMP WHERE student_id=?',
            (readiness, uid)
        )

        # Topic Mastery
        mastery = _db.execute_query(
            'SELECT topic_tag, mastery_score FROM arena_topic_mastery WHERE student_id=? AND exam=? AND subject=? ORDER BY mastery_score DESC',
            (uid, exam, subject)
        )
        if mastery:
            strongest = mastery[0]['topic_tag']
            weakest = mastery[-1]['topic_tag']

        # Mock Count
        mock_count = _db.execute_one(
            "SELECT COUNT(*) as cnt FROM arena_attempts WHERE student_id=? AND attempt_type='mock' AND exam=? AND subject=?",
            (uid, exam, subject)
        )
        mock_attempts_used = mock_count['cnt'] if mock_count else 0
        
        # Daily Done?
        today = date.today().isoformat()
        daily_done_row = _db.execute_one(
            "SELECT id FROM arena_attempts WHERE student_id=? AND attempt_type='daily' AND DATE(created_at)=?",
            (uid, today)
        )
        daily_done = bool(daily_done_row)

        # 4. Generate Mission Map
        mission_map = _get_mission_map(uid)
        
        # 5. UX Gamification
        if rank:
            level = _get_level(rank['xp_total'])
            next_xp = _get_next_level_xp(level)
            if next_xp > 0:
                progress_percent = min(100, (rank['xp_total'] / next_xp) * 100)
            else:
                progress_percent = 100
        
        achievements = _db.execute_query('SELECT * FROM arena_achievements WHERE student_id=? ORDER BY unlocked_at DESC LIMIT 5', (uid,))
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        logger.error(f"Arena Dashboard Error: {e}")
        # Even on error, we try to pass defaults

    return render_template('arena/arena_dashboard.html',
        profile=profile,
        rank=rank,
        level=level,
        next_xp=next_xp,
        progress_percent=int(progress_percent),
        daily_done=daily_done,
        readiness=readiness,
        strongest=strongest,
        weakest=weakest,
        mock_attempts_used=mock_attempts_used,
        mock_attempts_max=3,
        mission_map=mission_map,
        achievements=achievements,
        error_msg=error_msg
    )


@arena_bp.route('/arena/set_exam_profile', methods=['POST'])
def set_exam_profile():
    uid = _require_student()
    if not uid:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json(silent=True) or {}
    exam = data.get('exam', 'JEE')
    subject = data.get('subject', 'Physics')
    mode = data.get('mode', 'Practice')
    difficulty = data.get('preferred_difficulty', 'Auto')

    # ── VALIDATE exam + subject against EXAM_SUBJECT_MAP ──
    if exam not in EXAM_SUBJECT_MAP:
        return jsonify({'success': False, 'error': f'Invalid exam: {exam}. Valid: {list(EXAM_SUBJECT_MAP.keys())}'}), 400
    valid_subjects = EXAM_SUBJECT_MAP[exam]
    if subject not in valid_subjects:
        return jsonify({'success': False, 'error': f'Invalid subject "{subject}" for {exam}. Valid: {valid_subjects}'}), 400

    existing = _db.execute_one('SELECT id FROM arena_profiles WHERE student_id=?', (uid,))
    if existing:
        _db.execute_update(
            'UPDATE arena_profiles SET exam=?, subject=?, mode=?, preferred_difficulty=?, updated_at=CURRENT_TIMESTAMP WHERE student_id=?',
            (exam, subject, mode, difficulty, uid)
        )
    else:
        _db.execute_insert(
            'INSERT INTO arena_profiles (student_id, exam, subject, mode, preferred_difficulty) VALUES (?,?,?,?,?)',
            (uid, exam, subject, mode, difficulty)
        )

    _seed_questions_if_needed(exam, subject)
    return jsonify({'success': True, 'message': 'Profile saved'})


@arena_bp.route('/arena/api/exam_subjects')
def api_exam_subjects():
    """Return EXAM_SUBJECT_MAP for frontend dynamic dropdown."""
    return jsonify({'success': True, 'data': EXAM_SUBJECT_MAP})


@arena_bp.route('/arena/start/daily', methods=['POST'])
def start_daily_challenge():
    uid, err = _guard_arena()
    if err: return jsonify({'error': str(err)}), 401

    today = date.today().isoformat()
    daily_done = _db.execute_one(
        "SELECT id FROM arena_attempts WHERE student_id=? AND attempt_type='daily' AND DATE(created_at)=?",
        (uid, today)
    )
    if daily_done:
        return jsonify({'success': False, 'error': 'Daily completed!'}), 400

    profile = _db.execute_one('SELECT * FROM arena_profiles WHERE student_id=?', (uid,))
    exam = profile['exam'] if profile else 'JEE'
    subject = profile['subject'] if profile else 'Physics'

    _seed_questions_if_needed(exam, subject)
    difficulty = _pick_adaptive_difficulty(uid, exam, subject)

    # Adaptive daily: 4 from weak topics + 6 at adaptive difficulty
    final_ids = []

    weak_topics = _db.execute_query(
        'SELECT topic_tag FROM arena_topic_mastery WHERE student_id=? AND exam=? AND subject=? AND weak_flag=1',
        (uid, exam, subject)
    )
    if weak_topics:
        tags = [w['topic_tag'] for w in weak_topics]
        placeholders = ','.join('?' for _ in tags)
        weak_q = _db.execute_query(
            f'SELECT id FROM arena_question_bank WHERE exam=? AND subject=? AND topic_tag IN ({placeholders}) ORDER BY RANDOM() LIMIT 4',
            (exam, subject, *tags)
        )
        final_ids.extend([q['id'] for q in weak_q])

    needed = 10 - len(final_ids)
    if needed > 0:
        diff_q = _db.execute_query(
            'SELECT id FROM arena_question_bank WHERE exam=? AND subject=? AND difficulty=? ORDER BY RANDOM() LIMIT ?',
            (exam, subject, difficulty, needed)
        )
        final_ids.extend([q['id'] for q in diff_q])

    # Fallback to fill remaining
    if len(final_ids) < 10:
        needed = 10 - len(final_ids)
        extra = _db.execute_query('SELECT id FROM arena_question_bank WHERE exam=? AND subject=? ORDER BY RANDOM() LIMIT ?', (exam, subject, needed))
        final_ids.extend([e['id'] for e in extra])

    attempt_id = _db.execute_insert(
        '''INSERT INTO arena_attempts 
           (student_id, exam, subject, attempt_type, difficulty_start, status, questions_json, total_questions)
           VALUES (?,?,?,?,?,?,?,?)''',
        (uid, exam, subject, 'daily', difficulty, 'ongoing', json.dumps(final_ids), len(final_ids))
    )
    logger.info(f"[ARENA-DAILY] Started adaptive daily for uid={uid} difficulty={difficulty} weak_topics={len(weak_topics) if weak_topics else 0}")

    return jsonify({'success': True, 'redirect': url_for('arena.arena_session_view', session_id=attempt_id)})


@arena_bp.route('/arena/start/mock', methods=['POST'])
def start_mock_test():
    uid, err = _guard_arena()
    if err: return jsonify({'error': str(err)}), 401

    profile = _db.execute_one('SELECT * FROM arena_profiles WHERE student_id=?', (uid,))
    exam = profile['exam'] if profile else 'JEE'
    subject = profile['subject'] if profile else 'Physics'
    
    # Check limit — 3 max per exam+subject
    mock_count = _db.execute_one(
        "SELECT COUNT(*) as cnt FROM arena_attempts WHERE student_id=? AND attempt_type='mock' AND exam=? AND subject=?",
        (uid, exam, subject)
    )
    if mock_count and mock_count['cnt'] >= 3:
        # Attempts exhausted → return revision plan if exists
        last_attempt = _db.execute_one(
            "SELECT id FROM arena_attempts WHERE student_id=? AND attempt_type='mock' AND exam=? AND subject=? ORDER BY created_at DESC LIMIT 1",
            (uid, exam, subject)
        )
        revision = None
        if last_attempt:
            revision = _db.execute_one(
                'SELECT id FROM arena_revision_plans WHERE student_id=? AND attempt_id=?',
                (uid, last_attempt['id'])
            )
        if revision:
            return jsonify({
                'success': False,
                'error': 'All 3 attempts used. Review your AI Coaching Revision Plan before retrying.',
                'revision_redirect': url_for('arena.session_result', session_id=last_attempt['id'])
            }), 400
        else:
            return jsonify({'success': False, 'error': 'All 3 mock attempts exhausted for this exam/subject. Switch to a different subject or try Daily Challenge.'}), 400

    _seed_questions_if_needed(exam, subject)
    difficulty = _pick_adaptive_difficulty(uid, exam, subject)
    logger.info(f"[ARENA-MOCK] Starting mock for uid={uid} exam={exam} subject={subject} difficulty={difficulty}")

    # Adaptive question selection: 5 weak topic + 5 at adaptive difficulty
    weak_topics = _db.execute_query(
        'SELECT topic_tag FROM arena_topic_mastery WHERE student_id=? AND exam=? AND subject=? AND weak_flag=1',
        (uid, exam, subject)
    )
    
    final_ids = []
    
    if weak_topics:
        tags = [w['topic_tag'] for w in weak_topics]
        placeholders = ','.join('?' for _ in tags)
        weak_q = _db.execute_query(
            f'SELECT id FROM arena_question_bank WHERE exam=? AND subject=? AND topic_tag IN ({placeholders}) ORDER BY RANDOM() LIMIT 5',
            (exam, subject, *tags)
        )
        final_ids.extend([q['id'] for q in weak_q])

    needed = 10 - len(final_ids)
    if needed > 0:
        diff_q = _db.execute_query(
            'SELECT id FROM arena_question_bank WHERE exam=? AND subject=? AND difficulty=? ORDER BY RANDOM() LIMIT ?',
            (exam, subject, difficulty, needed)
        )
        final_ids.extend([q['id'] for q in diff_q])
    
    # Fallback to fill remaining
    if len(final_ids) < 10:
         needed = 10 - len(final_ids)
         extra = _db.execute_query('SELECT id FROM arena_question_bank WHERE exam=? AND subject=? ORDER BY RANDOM() LIMIT ?', (exam, subject, needed))
         final_ids.extend([e['id'] for e in extra])

    attempt_id = _db.execute_insert(
        '''INSERT INTO arena_attempts 
           (student_id, exam, subject, attempt_type, difficulty_start, status, questions_json, total_questions)
           VALUES (?,?,?,?,?,?,?,?)''',
        (uid, exam, subject, 'mock', difficulty, 'ongoing', json.dumps(final_ids), len(final_ids))
    )

    return jsonify({'success': True, 'redirect': url_for('arena.arena_session_view', session_id=attempt_id)})


@arena_bp.route('/arena/session/<int:session_id>')
def arena_session_view(session_id):
    uid, err = _guard_arena()
    if err: return err
    
    attempt = _db.execute_one('SELECT * FROM arena_attempts WHERE id=? AND student_id=?', (session_id, uid))
    if not attempt:
        flash('Invalid session.', 'error')
        return redirect(url_for('arena.arena_dashboard'))
        
    if attempt['status'] == 'completed':
        return redirect(url_for('arena.session_result', session_id=session_id))
        
    # Load questions
    try:
        q_ids = json.loads(attempt['questions_json'])
    except:
        q_ids = []
        
    questions = []
    if q_ids:
        placeholders = ','.join('?' for _ in q_ids)
        questions_objs = _db.execute_query(
            f"SELECT id, question_text, option_a, option_b, option_c, option_d, difficulty, topic_tag FROM arena_question_bank WHERE id IN ({placeholders})",
            q_ids
        )
        q_map = {q['id']: q for q in questions_objs}
        raw_questions = [q_map[mid] for mid in q_ids if mid in q_map]
        # Filter out any questions with missing required fields to prevent blank cards
        questions = [
            q for q in raw_questions
            if q.get('question_text') and q.get('option_a') and q.get('option_b')
            and q.get('option_c') and q.get('option_d')
        ]
        if not questions:
            # If all questions got filtered (edge case), fall back to all to avoid empty session
            questions = raw_questions

        
    time_limit = 600 if attempt['attempt_type'] == 'daily' else 900
    
    return render_template('arena/arena_session.html',
        session=attempt,
        questions=questions,
        time_limit=time_limit,
        current_index=attempt.get('current_q_index', 0)
    )

@arena_bp.route('/arena/leaderboard')
def leaderboard_view_legacy(): # Renamed to avoid confusion, but kept routing
    # This was the old one returning JSON. Merged below.
    return jsonify({'error': 'Deprecated. Use /api/leaderboard'})

@arena_bp.route('/arena/api/leaderboard', methods=['GET'])
def leaderboard_api():
    uid, err = _guard_arena()
    # Allowing public/unauthed access for preview? No, keep it safe
    if err: return jsonify({'success': False, 'error': 'Login required'}), 401
    
    # Simple top 10
    leaders = _db.execute_query('''
        SELECT u.name as name, r.rank_name, r.xp_total as xp, r.level, a.icon as badge_icon, r.readiness_score as readiness
        FROM arena_rank_status r
        JOIN users u ON r.student_id = u.id
        LEFT JOIN arena_achievements a ON a.student_id = r.student_id AND a.unlocked_at = (
            SELECT MAX(unlocked_at) FROM arena_achievements WHERE student_id = r.student_id
        )
        ORDER BY r.xp_total DESC
        LIMIT 10
    ''')
    
    # Frontend JS expects a list, or wrapped in success. 
    # Current JS: response.leaders array
    return jsonify({'success': True, 'leaders': leaders})


@arena_bp.route('/arena/submit_attempt', methods=['POST'])
def submit_attempt():
    import traceback
    try:
        uid = _require_student()
        if uid in ('NO_AUTH', 'WRONG_ROLE'):
            return jsonify({'success': False, 'error': 'Login required'}), 401

        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        answers = data.get('answers', [])
        
        if not session_id or not answers:
            return jsonify({'success': False, 'error': 'Missing session ID or answers'}), 400

        attempt = _db.execute_one(
            "SELECT * FROM arena_attempts WHERE id=? AND student_id=? AND status='ongoing'",
            (session_id, uid)
        )
        if not attempt:
            check_done = _db.execute_one("SELECT * FROM arena_attempts WHERE id=? AND student_id=? AND status='completed'", (session_id, uid))
            if check_done:
                 return jsonify({'success': True, 'redirect': url_for('arena.session_result', session_id=session_id)})
            return jsonify({'success': False, 'error': 'Invalid session'}), 400

        exam = attempt['exam']
        subject = attempt['subject']

        # ── Score calculation ──
        score = 0
        total = len(answers)
        wrong_answers = []   # For adaptive engine
        correct_answers = [] # For adaptive engine
        
        # Calculate Time Taken
        created_at_str = attempt['created_at']
        if created_at_str:
            try:
                if '.' in created_at_str:
                    created_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    created_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                duration_seconds = (datetime.now() - created_dt).total_seconds()
            except:
                duration_seconds = 600
        else:
            duration_seconds = 600

        avg_time = duration_seconds / total if total > 0 else 0
        
        for ans in answers:
            qid = ans.get('question_id')
            selected = ans.get('selected_option')
            
            q = _db.execute_one('SELECT * FROM arena_question_bank WHERE id=?', (qid,))
            is_correct = 0
            if q:
                if q['correct_option'] == selected:
                    score += 1
                    is_correct = 1
                    correct_answers.append(q)
                else:
                    wrong_answers.append(q)
                
                _db.execute_insert(
                    '''INSERT INTO arena_attempt_answers 
                       (attempt_id, question_id, selected_option, is_correct, 
                        question_text, option_a, option_b, option_c, option_d, correct_option, explanation) 
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (session_id, qid, selected, is_correct,
                     q['question_text'], q['option_a'], q['option_b'], q['option_c'], q['option_d'], q['correct_option'], q['explanation'])
                )
            else:
                 _db.execute_insert(
                    'INSERT INTO arena_attempt_answers (attempt_id, question_id, selected_option, is_correct) VALUES (?,?,?,?)',
                    (session_id, qid, selected, 0)
                )
        
        # ── Finalize attempt ──
        xp_earned = score * 10 + 50
        accuracy = (score/total*100 if total else 0)
        
        # Determine difficulty_end based on adaptive engine
        difficulty_end = _pick_adaptive_difficulty(uid, exam, subject)
        
        _db.execute_update(
            '''UPDATE arena_attempts 
               SET score=?, status='completed', xp_earned=?, accuracy_percent=?, 
                   avg_time_per_question=?, time_taken_total=?, difficulty_end=?,
                   updated_at=CURRENT_TIMESTAMP 
               WHERE id=?''',
            (score, xp_earned, accuracy, avg_time, int(duration_seconds), difficulty_end, session_id)
        )
        logger.info(f"[ARENA-SUBMIT] uid={uid} score={score}/{total} accuracy={accuracy:.1f}% difficulty_end={difficulty_end}")
        
        # ── Award XP ──
        _award_xp(uid, xp_earned, 'quiz', f"Completed {attempt['attempt_type']} quiz")
        
        # ── Update Rank (XP + streak + rank_name recalculation) ──
        _db.execute_update(
            'UPDATE arena_rank_status SET xp_total = xp_total + ?, streak_days = streak_days + 1 WHERE student_id=?',
            (xp_earned, uid)
        )
        rank_row = _db.execute_one('SELECT * FROM arena_rank_status WHERE student_id=?', (uid,))
        if rank_row:
            new_rank = _calculate_rank(rank_row['xp_total'], accuracy, rank_row['streak_days'])
            _db.execute_update(
                'UPDATE arena_rank_status SET rank_name=?, updated_at=CURRENT_TIMESTAMP WHERE student_id=?',
                (new_rank, uid)
            )
        
        # ── Update Topic Mastery ──
        try:
            _update_topic_mastery(uid, exam, subject, wrong_answers, correct_answers)
        except Exception as e:
            logger.error(f"[ARENA-SUBMIT] Topic mastery update failed: {e}")

        # ── Update Readiness Score ──
        try:
            readiness = _compute_readiness(uid, exam, subject)
            _db.execute_update(
                'UPDATE arena_rank_status SET readiness_score=?, updated_at=CURRENT_TIMESTAMP WHERE student_id=?',
                (readiness, uid)
            )
            logger.info(f"[ARENA-SUBMIT] Readiness updated to {readiness} for uid={uid}")
        except Exception as e:
            logger.error(f"[ARENA-SUBMIT] Readiness update failed: {e}")

        # ── Generate AI Revision Notes (for wrong answers) ──
        try:
            if wrong_answers:
                _generate_ai_notes(uid, session_id, wrong_answers)
        except Exception as e:
            logger.error(f"[ARENA-SUBMIT] AI notes generation failed: {e}")

        # ── Generate Revision Plan (on 3rd mock attempt OR accuracy < 40%) ──
        try:
            mock_count = _db.execute_one(
                "SELECT COUNT(*) as cnt FROM arena_attempts WHERE student_id=? AND attempt_type='mock' AND exam=? AND subject=? AND status='completed'",
                (uid, exam, subject)
            )
            is_3rd_attempt = mock_count and mock_count['cnt'] >= 3
            is_low_score = accuracy < 40

            if (is_3rd_attempt or is_low_score) and wrong_answers:
                _generate_revision_plan(uid, session_id, exam, subject)
                logger.info(f"[ARENA-SUBMIT] Revision plan triggered (3rd_attempt={is_3rd_attempt}, low_score={is_low_score})")
        except Exception as e:
            logger.error(f"[ARENA-SUBMIT] Revision plan generation failed: {e}")

        # ── Check Achievements ──
        _check_achievements(uid, {'score': score, 'total_questions': total, 'avg_time': avg_time, 'attempt_type': attempt['attempt_type']})

        return jsonify({'success': True, 'redirect': url_for('arena.session_result', session_id=session_id)})
    
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Submit attempt error: {e}")
        return jsonify({'success': False, 'error': f"Internal Error: {str(e)}"}), 500

@arena_bp.route('/arena/review/<int:session_id>')
def review_attempt(session_id):
    uid, err = _guard_arena()
    if err: return err
    
    attempt = _db.execute_one('SELECT * FROM arena_attempts WHERE id=? AND student_id=?', (session_id, uid))
    if not attempt or attempt['status'] != 'completed':
        flash('Invalid verification request.', 'error')
        return redirect(url_for('arena.arena_dashboard'))
        
    # Fetch answers with snapshot data
    answers = _db.execute_query('''
        SELECT * FROM arena_attempt_answers 
        WHERE attempt_id=? 
        ORDER BY id ASC
    ''', (session_id,))
    
    return render_template('arena/arena_review.html', attempt=attempt, answers=answers)

@arena_bp.route('/arena/progress')
def progress_view():
    uid, err = _guard_arena()
    if err: return err

    profile = _db.execute_one('SELECT * FROM arena_profiles WHERE student_id=?', (uid,))
    try:
        exam = profile['exam'] if profile else 'JEE'
    except (KeyError, IndexError, TypeError):
        exam = 'JEE'
    try:
        subject_pref = profile['subject'] if profile else 'Physics'
    except (KeyError, IndexError, TypeError):
        subject_pref = 'Physics'

    # ── Fetch ALL completed attempts (most recent first for table) ──
    all_attempts = _db.execute_query('''
        SELECT id, exam, subject, score, total_questions, accuracy_percent,
               avg_time_per_question, created_at, attempt_type
        FROM arena_attempts
        WHERE student_id=? AND status='completed'
        ORDER BY created_at DESC
    ''', (uid,))

    # ── Summary Stats ──
    total_attempts = len(all_attempts)
    avg_score = 0
    avg_accuracy = 0
    avg_speed = 0
    readiness = 0

    if total_attempts > 0:
        avg_score = round(sum(a['accuracy_percent'] or 0 for a in all_attempts) / total_attempts, 1)
        avg_accuracy = avg_score  # same metric
        valid_speeds = [a['avg_time_per_question'] for a in all_attempts if a['avg_time_per_question'] and a['avg_time_per_question'] > 0]
        avg_speed = round(sum(valid_speeds) / len(valid_speeds), 1) if valid_speeds else 0
        readiness = _compute_readiness(uid, exam, subject_pref)

    # ── Subject Strength / Weakness ──
    strongest_subject = 'N/A'
    weakest_subject = 'N/A'
    improvement_tip = 'Start taking quizzes to see your strengths and weaknesses.'

    subject_stats = {}
    for a in all_attempts:
        try:
            subj = a['subject'] or 'Unknown'
        except (KeyError, IndexError, TypeError):
            subj = 'Unknown'
        if subj not in subject_stats:
            subject_stats[subj] = {'total_acc': 0, 'count': 0}
        subject_stats[subj]['total_acc'] += (a['accuracy_percent'] or 0)
        subject_stats[subj]['count'] += 1

    if subject_stats:
        sorted_subjects = sorted(subject_stats.items(), key=lambda x: x[1]['total_acc'] / x[1]['count'], reverse=True)
        strongest_subject = sorted_subjects[0][0]
        weakest_subject = sorted_subjects[-1][0]
        weak_avg = round(sorted_subjects[-1][1]['total_acc'] / sorted_subjects[-1][1]['count'], 1)
        improvement_tip = f'Focus more on {weakest_subject} (avg {weak_avg}%). Try targeted practice in weak topics.'

    # Also check topic mastery if available
    mastery = _db.execute_query(
        'SELECT topic_tag, mastery_score FROM arena_topic_mastery WHERE student_id=? ORDER BY mastery_score DESC',
        (uid,)
    )
    if mastery and len(mastery) >= 2:
        strongest_subject = mastery[0]['topic_tag']
        weakest_subject = mastery[-1]['topic_tag']
        improvement_tip = f'Your weakest area is {weakest_subject}. Practice more in this topic to improve overall score.'

    # ── Chart Data: last 7 attempts (chronological order) ──
    last_7 = list(reversed(all_attempts[:7]))  # oldest first for chart
    chart_labels = []
    chart_scores = []
    chart_speeds = []

    for h in last_7:
        try:
            dt = datetime.strptime(h['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            chart_labels.append(dt.strftime('%b %d'))
        except Exception:
            chart_labels.append('N/A')
        chart_scores.append(round(h['accuracy_percent'] or 0, 1))
        chart_speeds.append(round(h['avg_time_per_question'] or 0, 1))

    return render_template('arena/arena_progress.html',
        history=all_attempts,
        total_attempts=total_attempts,
        avg_score=avg_score,
        avg_speed=avg_speed,
        readiness=round(readiness, 1),
        strongest_subject=strongest_subject,
        weakest_subject=weakest_subject,
        improvement_tip=improvement_tip,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        chart_speeds=chart_speeds,
        exam=exam,
        subject=subject_pref
    )

@arena_bp.route('/arena/result/<int:session_id>')
def session_result(session_id):
    uid, err = _guard_arena()
    if err: return err
    
    attempt = _db.execute_one('SELECT * FROM arena_attempts WHERE id=? AND student_id=?', (session_id, uid))
    if not attempt or attempt['status'] != 'completed':
        return redirect(url_for('arena.arena_dashboard'))
        
    rank = _db.execute_one('SELECT * FROM arena_rank_status WHERE student_id=?', (uid,))
    
    # Fetch AI Notes
    ai_notes = _db.execute_query('SELECT * FROM arena_ai_notes WHERE attempt_id=?', (session_id,))

    return render_template('arena/arena_result.html', attempt=attempt, rank=rank, ai_notes=ai_notes)
