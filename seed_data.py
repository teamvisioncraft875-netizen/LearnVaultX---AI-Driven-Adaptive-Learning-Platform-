"""
Seed the database with test data for demonstration
"""
import sqlite3
import hashlib
from datetime import datetime

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def seed_database():
    """Populate database with test data"""
    conn = sqlite3.connect('learnvaultx.db')
    c = conn.cursor()
    
    print("🌱 Seeding database with test data...")
    
    # Check if students already have classes
    c.execute('SELECT COUNT(*) FROM classes WHERE teacher_id = 2')
    existing_classes = c.fetchone()[0]
    
    if existing_classes > 0:
        print(f"✅ Database already has {existing_classes} class(es). Skipping seed.")
        conn.close()
        return
    
    try:
        # Create sample classes for teacher
        classes_data = [
            ('Introduction to Python Programming', 'Learn Python from scratch - variables, loops, functions, and OOP', 2),
            ('Web Development with Flask', 'Build modern web applications using Flask framework', 2),
            ('Data Structures and Algorithms', 'Master fundamental CS concepts and problem-solving techniques', 2),
        ]
        
        class_ids = []
        for title, desc, teacher_id in classes_data:
            c.execute('INSERT INTO classes (title, description, teacher_id) VALUES (?, ?, ?)',
                     (title, desc, teacher_id))
            class_ids.append(c.lastrowid)
            print(f"  ✓ Created class: {title}")
        
        # Enroll student in first two classes
        for class_id in class_ids[:2]:
            c.execute('INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)',
                     (1, class_id))
            print(f"  ✓ Enrolled student in class ID {class_id}")
        
        # Add sample lectures to first class
        lectures_data = [
            (class_ids[0], 'python_basics.pdf', 'static/uploads/python_basics.pdf', 2048000),
            (class_ids[0], 'python_functions.pdf', 'static/uploads/python_functions.pdf', 1536000),
        ]
        
        for class_id, filename, filepath, filesize in lectures_data:
            c.execute('INSERT INTO lectures (class_id, filename, filepath, file_size) VALUES (?, ?, ?, ?)',
                     (class_id, filename, filepath, filesize))
            print(f"  ✓ Added lecture: {filename}")
        
        # Add sample quiz to first class
        c.execute('''INSERT INTO quizzes (class_id, title, description) 
                     VALUES (?, ?, ?)''',
                  (class_ids[0], 'Python Basics Quiz', 'Test your understanding of Python fundamentals'))
        quiz_id = c.lastrowid
        print(f"  ✓ Created quiz: Python Basics Quiz")
        
        # Add quiz questions
        questions = [
            {
                'quiz_id': quiz_id,
                'question_text': 'What is the correct way to declare a variable in Python?',
                'options': '["x = 5", "var x = 5", "let x = 5", "int x = 5"]',
                'correct_option_index': 0,
                'explanation': 'In Python, variables are declared by simply assigning a value'
            },
            {
                'quiz_id': quiz_id,
                'question_text': 'Which data type is used for text in Python?',
                'options': '["string", "text", "char", "varchar"]',
                'correct_option_index': 0,
                'explanation': 'Python uses the str (string) data type for text'
            },
            {
                'quiz_id': quiz_id,
                'question_text': 'What does the print() function do?',
                'options': '["Outputs text to console", "Saves to file", "Creates a variable", "None of these"]',
                'correct option_index': 0,
                'explanation': 'print() outputs text or data to the console/terminal'
            }
        ]
        
        for q in questions:
            c.execute('''INSERT INTO quiz_questions 
                        (quiz_id, question_text, options, correct_option_index, explanation)
                        VALUES (?, ?, ?, ?, ?)''',
                     (q['quiz_id'], q['question_text'], q['options'], 
                      q['correct_option_index'], q['explanation']))
        
        print(f"  ✓ Added {len(questions)} quiz questions")
        
        # Add student metrics for enrolled classes
        c.execute('''INSERT INTO student_metrics 
                     (user_id, class_id, rating, quizzes_taken, avg_score, engagement_level)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (1, class_ids[0], 75, 0, 0, 0.7))
        print("  ✓ Added student metrics")
        
        # Add some AI recommendations
        recommendations = [
            'Practice Python list comprehensions with coding exercises',
            'Review Python function parameters and return values',
            'Complete additional practice on loops and conditionals'
        ]
        
        for rec_text in recommendations:
            c.execute('''INSERT INTO recommendations 
                        (user_id, class_id, recommendation, priority, reason)
                        VALUES (?, ?, ?, ?, ?)''',
                     (1, class_ids[0], rec_text, 5, 'Based on quiz performance analysis'))
        
        print(f"  ✓ Added {len(recommendations)} AI recommendations")
        
        conn.commit()
        print("\n✅ Database seeded successfully!")
        print(f"\n📊 Summary:")
        print(f"   - {len(classes_data)} classes created")
        print(f"   - 2 enrollments created")
        print(f"   - {len(lectures_data)} lectures added")
        print(f"   - 1 quiz with {len(questions)} questions")
        print(f"   - {len(recommendations)} AI recommendations")
        
    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    seed_database()
