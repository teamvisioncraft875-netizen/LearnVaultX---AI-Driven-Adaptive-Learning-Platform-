"""
Database seeding script for LearnVaultX
Creates test users, classes, lectures, quizzes for demonstration
"""
import sqlite3
import hashlib
from datetime import datetime, timedelta

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_database(db_path='learnvault.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🌱 Seeding LearnVaultX database...")
    
    # Create test users
    print("Creating users...")
    users = [
        ('Alice Johnson', 'student@test.com', hash_password('password123'), 'student'),
        ('Bob Smith', 'student2@test.com', hash_password('password123'), 'student'),
        ('Dr. Sarah Williams', 'teacher@test.com', hash_password('password123'), 'teacher'),
        ('Prof. John Davis', 'teacher2@test.com', hash_password('password123'), 'teacher'),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
        users
    )
    
    # Get user IDs
    cursor.execute("SELECT id, role FROM users")
    user_ids = cursor.fetchall()
    student_ids = [uid for uid, role in user_ids if role == 'student']
    teacher_ids = [uid for uid, role in user_ids if role == 'teacher']
    
    # Create classes
    print("Creating classes...")
    classes = [
        ('Introduction to Python Programming', 'Learn Python from scratch with hands-on projects', teacher_ids[0]),
        ('Data Structures & Algorithms', 'Master fundamental CS concepts and problem-solving', teacher_ids[0]),
        ('Web Development Fundamentals', 'Build modern websites with HTML, CSS, and JavaScript', teacher_ids[1]),
        ('Machine Learning Basics', 'Introduction to ML algorithms and applications', teacher_ids[1]),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO classes (title, description, teacher_id) VALUES (?, ?, ?)',
        classes
    )
    
    # Get class IDs
    cursor.execute("SELECT id FROM classes")
    class_ids = [row[0] for row in cursor.fetchall()]
    
    # Enroll students in classes
    print("Enrolling students...")
    enrollments = []
    for student_id in student_ids:
        for class_id in class_ids[:2]:  # Enroll in first 2 classes
            enrollments.append((student_id, class_id))
    
    cursor.executemany(
        'INSERT OR IGNORE INTO enrollments (student_id, class_id) VALUES (?, ?)',
        enrollments
    )
    
    # Create sample lectures  
    print("Creating lectures...")
    lectures = [
        (class_ids[0], 'python_basics.pdf', 'static/uploads/python_basics.pdf', 1024000),
        (class_ids[0], 'variables_and_types.pdf', 'static/uploads/variables_and_types.pdf', 512000),
        (class_ids[1], 'arrays_and_lists.pdf', 'static/uploads/arrays_and_lists.pdf', 768000),
        (class_ids[1], 'sorting_algorithms.pdf', 'static/uploads/sorting_algorithms.pdf', 1536000),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO lectures (class_id, filename, filepath, file_size) VALUES (?, ?, ?, ?)',
        lectures
    )
    
    # Create quizzes
    print("Creating quizzes...")
    quizzes = [
        (class_ids[0], 'Python Basics Quiz', 'Test your understanding of Python fundamentals'),
        (class_ids[1], 'Arrays and Lists Quiz', 'Check your knowledge of data structures'),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO quizzes (class_id, title, description) VALUES (?, ?, ?)',
        quizzes
    )
    
    # Get quiz IDs
    cursor.execute("SELECT id FROM quizzes")
    quiz_ids = [row[0] for row in cursor.fetchall()]
    
    # Create quiz questions
    print("Creating quiz questions...")
    questions = [
        # Quiz 1 questions
        (quiz_ids[0], 'What is the correct way to create a variable in Python?', 
         '["x = 5", "var x = 5", "int x = 5", "declare x = 5"]', 0, 'Python uses simple assignment without type declarations'),
        (quiz_ids[0], 'Which of the following is a mutable data type?',
         '["tuple", "string", "list", "int"]', 2, 'Lists can be modified after creation'),
        (quiz_ids[0], 'What does the len() function do?',
         '["Returns the length of an object", "Converts to lowercase", "Loops through items", "None of these"]', 0, 'len() returns the number of items'),
        # Quiz 2 questions
        (quiz_ids[1], 'What is the time complexity of accessing an element in an array?',
         '["O(1)", "O(n)", "O(log n)", "O(n^2)"]', 0, 'Array access is constant time'),
        (quiz_ids[1], 'Which operation is NOT efficient on an array?',
         '["Access by index", "Insert at beginning", "Access last element", "Random access"]', 1, 'Inserting at beginning requires shifting all elements'),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO quiz_questions (quiz_id, question_text, options, correct_option_index, explanation) VALUES (?, ?, ?, ?, ?)',
        questions
    )
    
    # Create some quiz submissions
    print("Creating quiz submissions...")
    submissions = [
        (quiz_ids[0], student_ids[0], 2, 3, '{"1": 0, "2": 2, "3": 1}', 180),
        (quiz_ids[0], student_ids[1], 3, 3, '{"1": 0, "2": 2, "3": 0}', 240),
        (quiz_ids[1], student_ids[0], 1, 2, '{"4": 0, "5": 2}', 120),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO quiz_submissions (quiz_id, student_id, score, total, answers, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)',
        submissions
    )
    
    # Create AI query history
    print("Creating AI query history...")
    queries = [
        (student_ids[0], 'How do I create a list in Python?', 'You can create a list using square brackets: my_list = [1, 2, 3]', 'Groq', 'expert'),
        (student_ids[0], 'What is the difference between a list and a tuple?', 'Lists are mutable (can be changed) while tuples are immutable (cannot be changed after creation)', 'Groq', 'expert'),
        (student_ids[1], 'Can you help me understand loops?', 'What specific aspect of loops are you finding challenging? Can you show me an example?', 'Groq', 'socratic'),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO ai_queries (user_id, prompt, response, provider, mode) VALUES (?, ?, ?, ?, ?)',
        queries
    )
    
    # Create student metrics
    print("Creating student metrics...")
    metrics = [
        (student_ids[0], class_ids[0], 66.7, 180, 1.0, 66.7),
        (student_ids[0], class_ids[1], 50.0, 120, 0.75, 45.0),
        (student_ids[1], class_ids[0], 100.0, 240, 1.5, 115.0),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO student_metrics (user_id, class_id, score_avg, avg_time, pace_score, rating) VALUES (?, ?, ?, ?, ?, ?)',
        metrics
    )
    
    conn.commit()
    conn.close()
    
    print("✅ Database seeded successfully!")
    print("\nTest Accounts:")
    print("Student: student@test.com / password123")
    print("Student 2: student2@test.com / password123")
    print("Teacher: teacher@test.com / password123")
    print("Teacher 2: teacher2@test.com / password123")

if __name__ == '__main__':
    seed_database()
