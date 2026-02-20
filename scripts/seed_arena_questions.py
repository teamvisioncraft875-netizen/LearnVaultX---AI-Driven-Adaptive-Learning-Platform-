import sqlite3
import random
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'education.db')

def get_db():
    return sqlite3.connect(DB_PATH)

def seed_arena_questions():
    print(f"Connecting to {DB_PATH}...")
    conn = get_db()
    cursor = conn.cursor()

    # Check existing count
    cursor.execute("SELECT COUNT(*) FROM arena_question_bank")
    count = cursor.fetchone()[0]
    print(f"Current question count: {count}")
    
    if count >= 300:
        print("Sufficient questions exist. Skipping seed.")
        conn.close()
        return

    questions = []

    # ── PHYSICS GENERATOR ─────────────────────────────────────────────
    print("Generating Physics questions...")
    for _ in range(30):
        # Kinematics
        u = random.randint(0, 20)
        a = random.randint(1, 5)
        t = random.randint(2, 10)
        v = u + a * t
        s = u*t + 0.5*a*t**2
        
        # Velocity
        q_text = f"A particle starts with velocity {u} m/s and accelerates at {a} m/s² for {t} s. Final velocity is:"
        ans = f"{v} m/s"
        opts = [f"{v} m/s", f"{v+2} m/s", f"{v-2} m/s", f"{v*2} m/s"]
        random.shuffle(opts)
        questions.append(('JEE', 'Physics', 'Mechanics', 'Easy', q_text, *opts, ans, "v = u + at", 45))

        # Distance
        q_text = f"A car starts from {u} m/s and accelerates at {a} m/s² for {t} s. Distance covered is:"
        ans = f"{s:.1f} m"
        opts = [f"{s:.1f} m", f"{s+10:.1f} m", f"{s-5:.1f} m", f"{s*2:.1f} m"]
        random.shuffle(opts)
        questions.append(('JEE', 'Physics', 'Mechanics', 'Medium', q_text, *opts, ans, "s = ut + ½at²", 60))

    # Thermodynamics
    for _ in range(20):
        temp_c = random.randint(20, 100)
        temp_k = temp_c + 273
        q_text = f"Convert {temp_c}°C to Kelvin."
        ans = f"{temp_k} K"
        opts = [f"{temp_k} K", f"{temp_k-273} K", f"{temp_k+100} K", f"{temp_c} K"]
        random.shuffle(opts)
        questions.append(('JEE', 'Physics', 'Thermodynamics', 'Easy', q_text, *opts, ans, "K = °C + 273", 30))

    # ── MATH GENERATOR ────────────────────────────────────────────────
    print("Generating Math questions...")
    for _ in range(30):
        # Quadratic
        root1 = random.randint(1, 5)
        root2 = random.randint(1, 5)
        b = -(root1 + root2)
        c = root1 * root2
        q_text = f"The roots of equation x² {b:+}x {c:+} = 0 are:"
        ans = f"{root1}, {root2}"
        opts = [f"{root1}, {root2}", f"{-root1}, {-root2}", f"{root1}, {-root2}", f"{root1+1}, {root2+1}"]
        random.shuffle(opts)
        questions.append(('JEE', 'Mathematics', 'Algebra', 'Easy', q_text, *opts, ans, f"Apply quadratic formula or factoring: (x-{root1})(x-{root2})=0", 45))

        # Arithmetic Progression
        a = random.randint(1, 10)
        d = random.randint(2, 5)
        n = random.randint(5, 15)
        nth = a + (n-1)*d
        q_text = f"Find the {n}th term of AP: {a}, {a+d}, {a+2*d}..."
        ans = str(nth)
        opts = [str(nth), str(nth+d), str(nth-d), str(nth*2)]
        random.shuffle(opts)
        questions.append(('JEE', 'Mathematics', 'Algebra', 'Easy', q_text, *opts, ans, "an = a + (n-1)d", 45))

    # ── CHEMISTRY (Hardcoded but diverse) ─────────────────────────────
    print("Generating Chemistry questions...")
    chem_qs = [
        ("Atomic Structure", "Easy", "Which orbital is filled after 3p?", "4s", "3d", "4p", "3f", "4s", "Aufbau principle: 1s 2s 2p 3s 3p 4s 3d..."),
        ("Periodic Table", "Medium", "Which element has highest electron affinity?", "Chlorine", "Fluorine", "Oxygen", "Bromine", "Chlorine", "Chlorine has highest EA due to size/repulsion balance."),
        ("Bonding", "Easy", "Shape of water molecule is:", "Bent/V-shape", "Linear", "Tetrahedral", "Trigonal", "Bent/V-shape", "Due to 2 lone pairs on Oxygen."),
        ("Equilibrium", "Hard", "pH of 0.001 M HCl is:", "3", "2", "4", "1", "3", "pH = -log[H+] = -log(10^-3) = 3"),
        ("Organic", "Medium", "Hybridization of carbon in ethyne is:", "sp", "sp2", "sp3", "dsp2", "sp", "Triple bond carbons are sp hybridized."),
    ]
    for _ in range(5): # Duplicate with slight variation or just add few
        for topic, diff, q, o1, o2, o3, o4, ans, expl in chem_qs:
            opts = [o1, o2, o3, o4]
            random.shuffle(opts)
            questions.append(('JEE', 'Chemistry', topic, diff, q, *opts, ans, expl, 45))

    # ── BIOLOGY (NEET) ────────────────────────────────────────────────
    print("Generating Biology questions...")
    bio_qs = [
        ("Cell", "Powerhouse of cell is:", "Mitochondria", "Nucleus", "Ribosome", "Lysosome"),
        ("Genetics", "Mendel worked on which plant?", "Garden Pea", "Sweet Pea", "Rose", "Mango"),
        ("Physiology", "Heart of human has how many chambers?", "4", "3", "2", "5"),
        ("Diversity", "Which is an amphibian?", "Frog", "Lizard", "Fish", "Whale"),
        ("Reproduction", "Male gamete in humans is:", "Sperm", "Ovum", "Zygote", "Embryo"),
    ]
    for _ in range(6): # Multiply
        for topic, q, o1, o2, o3, o4 in bio_qs:
            opts = [o1, o2, o3, o4]
            random.shuffle(opts)
            questions.append(('NEET', 'Biology', topic, 'Easy', q, *opts, o1, "Basic biology fact.", 30))

    # ── GK / UPSC ─────────────────────────────────────────────────────
    print("Generating GK questions...")
    gk_qs = [
        ("History", "Who was first President of India?", "Dr. Rajendra Prasad", "Nehru", "Gandhi", "Ambedkar"),
        ("Geography", "Capital of Australia is:", "Canberra", "Sydney", "Melbourne", "Perth"),
        ("Polity", "Constitution of India was adopted in:", "1950", "1947", "1952", "1949"),
        ("Science", "Light year is unit of:", "Distance", "Time", "Light", "Intensity"),
        ("Economy", "Currency of Japan is:", "Yen", "Dollar", "Yuan", "Won"),
    ]
    for _ in range(6):
        for topic, q, o1, o2, o3, o4 in gk_qs:
            opts = [o1, o2, o3, o4]
            random.shuffle(opts)
            questions.append(('UPSC', 'GK', topic, 'Easy', q, *opts, o1, "General Knowledge fact.", 30))


    # Shuffle options mapping
    final_data = []
    for exam, subj, topic, diff, q, oa, ob, oc, od, ans, expl, time in questions:
        options = [oa, ob, oc, od]
        correct_letter = 'A'
        # Logic to find which shuffled option matches answer
        # But wait, I shuffled options in the list above but passed them as oa, ob...
        # So I need to find which one is 'ans'.
        if oa == ans: correct_letter = 'A'
        elif ob == ans: correct_letter = 'B'
        elif oc == ans: correct_letter = 'C'
        elif od == ans: correct_letter = 'D'
        
        final_data.append((exam, subj, topic, diff, q, oa, ob, oc, od, correct_letter, expl, time, 'SEED_SCRIPT'))

    # INSERT
    print(f"Inserting {len(final_data)} questions...")
    cursor.executemany('''
        INSERT INTO arena_question_bank (exam, subject, topic_tag, difficulty, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, estimated_time_seconds, source_tag)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', final_data)
    
    conn.commit()
    print("Seeding complete.")
    conn.close()

if __name__ == "__main__":
    seed_arena_questions()
