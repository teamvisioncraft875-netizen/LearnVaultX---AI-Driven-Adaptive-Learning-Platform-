"""
Quiz Generation Script for LearnVaultX
Generates 5 quizzes per class with analytics-ready structure
"""
import sqlite3
import json
from datetime import datetime

def generate_quizzes():
    conn = sqlite3.connect('learnvault.db')
    cursor = conn.cursor()
    
    # Get all classes with teacher info
    cursor.execute('SELECT id, title, teacher_id FROM classes')
    classes = cursor.fetchall()
    
    print(f"Found {len(classes)} classes")
    
    quiz_templates = {
        'Web Development': [
            {
                'title': 'Quiz 1 - HTML Fundamentals',
                'questions': [
                    {'q': 'What does HTML stand for?', 'opts': ['Hyper Text Markup Language', 'High Tech Modern Language', 'Home Tool Markup Language', 'Hyperlinks and Text Markup Language'], 'correct': 0},
                    {'q': 'Which HTML tag is used for the largest heading?', 'opts': ['<h6>', '<heading>', '<h1>', '<head>'], 'correct': 2},
                    {'q': 'What is the correct HTML element for inserting a line break?', 'opts': ['<break>', '<lb>', '<br>', '<newline>'], 'correct': 2},
                    {'q': 'Which attribute specifies a unique identifier for an HTML element?', 'opts': ['class', 'id', 'name', 'key'], 'correct': 1},
                    {'q': 'What is the correct HTML for creating a hyperlink?', 'opts': ['<a url="http://example.com">', '<a href="http://example.com">', '<link src="http://example.com">', '<hyperlink to="http://example.com">'], 'correct': 1},
                    {'q': 'Which HTML tag is used to define an internal style sheet?', 'opts': ['<css>', '<script>', '<style>', '<styles>'], 'correct': 2},
                    {'q': 'What is the correct HTML for making a text input field?', 'opts': ['<input type="text">', '<textfield>', '<input type="textfield">', '<textinput>'], 'correct': 0},
                    {'q': 'Which HTML attribute is used to define inline styles?', 'opts': ['class', 'style', 'styles', 'font'], 'correct': 1},
                    {'q': 'What is the correct HTML for inserting an image?', 'opts': ['<image src="image.jpg">', '<img href="image.jpg">', '<img src="image.jpg">', '<picture src="image.jpg">'], 'correct': 2},
                    {'q': 'Which doctype is correct for HTML5?', 'opts': ['<!DOCTYPE html>', '<!DOCTYPE HTML5>', '<DOCTYPE html>', '<!HTML5>'], 'correct': 0}
                ]
            },
            {
                'title': 'Quiz 2 - CSS Styling',
                'questions': [
                    {'q': 'What does CSS stand for?', 'opts': ['Creative Style Sheets', 'Cascading Style Sheets', 'Computer Style Sheets', 'Colorful Style Sheets'], 'correct': 1},
                    {'q': 'Which property is used to change the background color?', 'opts': ['color', 'bgcolor', 'background-color', 'bg-color'], 'correct': 2},
                    {'q': 'How do you select an element with id "demo"?', 'opts': ['.demo', '#demo', '*demo', 'demo'], 'correct': 1},
                    {'q': 'Which property is used to change the font?', 'opts': ['font-family', 'font-style', 'text-font', 'font'], 'correct': 0},
                    {'q': 'How do you make text bold in CSS?', 'opts': ['font-weight: bold', 'text-style: bold', 'font: bold', 'text-weight: bold'], 'correct': 0},
                    {'q': 'Which property is used to change text color?', 'opts': ['text-color', 'font-color', 'color', 'text'], 'correct': 2},
                    {'q': 'How do you add a border in CSS?', 'opts': ['border: 1px solid black', 'border-style: solid', 'border-width: 1px', 'outline: 1px'], 'correct': 0},
                    {'q': 'Which property controls the text size?', 'opts': ['text-size', 'font-size', 'text-style', 'font-weight'], 'correct': 1},
                    {'q': 'How do you center a block element?', 'opts': ['text-align: center', 'margin: auto', 'align: center', 'center: true'], 'correct': 1},
                    {'q': 'Which property is used for spacing between elements?', 'opts': ['padding', 'margin', 'spacing', 'gap'], 'correct': 1}
                ]
            },
            {
                'title': 'Quiz 3 - JavaScript Basics',
                'questions': [
                    {'q': 'Inside which HTML element do we put JavaScript?', 'opts': ['<js>', '<javascript>', '<script>', '<scripting>'], 'correct': 2},
                    {'q': 'How do you declare a variable in JavaScript?', 'opts': ['var x', 'variable x', 'v x', 'declare x'], 'correct': 0},
                    {'q': 'Which operator is used for assignment?', 'opts': ['==', '=', '===', ':='], 'correct': 1},
                    {'q': 'How do you write a comment in JavaScript?', 'opts': ['<!-- comment -->', '// comment', '/* comment', '# comment'], 'correct': 1},
                    {'q': 'What is the correct way to write an array?', 'opts': ['var colors = "red", "green"', 'var colors = (1:"red", 2:"green")', 'var colors = ["red", "green"]', 'var colors = {red, green}'], 'correct': 2},
                    {'q': 'How do you call a function named "myFunction"?', 'opts': ['call myFunction()', 'myFunction()', 'execute myFunction()', 'run myFunction()'], 'correct': 1},
                    {'q': 'Which event occurs when a user clicks on an element?', 'opts': ['onmouseclick', 'onclick', 'onpress', 'onmousedown'], 'correct': 1},
                    {'q': 'How do you write an IF statement?', 'opts': ['if x = 5', 'if (x == 5)', 'if x == 5 then', 'if x === 5 then'], 'correct': 1},
                    {'q': 'What is the correct way to write a JavaScript object?', 'opts': ['var obj = {name:"John", age:30}', 'var obj = (name:"John", age:30)', 'var obj = [name:"John", age:30]', 'var obj = name:"John", age:30'], 'correct': 0},
                    {'q': 'How do you round the number 7.25 to the nearest integer?', 'opts': ['Math.round(7.25)', 'Math.rnd(7.25)', 'round(7.25)', 'rnd(7.25)'], 'correct': 0}
                ]
            },
            {
                'title': 'Quiz 4 - Responsive Design',
                'questions': [
                    {'q': 'What does RWD stand for?', 'opts': ['Responsive Web Design', 'Reactive Web Design', 'Real Web Design', 'Ready Web Design'], 'correct': 0},
                    {'q': 'Which meta tag is used for responsive design?', 'opts': ['<meta name="responsive">', '<meta name="viewport">', '<meta name="mobile">', '<meta name="device">'], 'correct': 1},
                    {'q': 'What CSS unit is best for responsive design?', 'opts': ['px', 'pt', 'em or rem', 'cm'], 'correct': 2},
                    {'q': 'Which CSS feature is used for responsive layouts?', 'opts': ['tables', 'frames', 'media queries', 'divs'], 'correct': 2},
                    {'q': 'What is mobile-first design?', 'opts': ['Designing for mobile only', 'Starting design from mobile view', 'Mobile apps first', 'Testing on mobile first'], 'correct': 1},
                    {'q': 'Which property makes images responsive?', 'opts': ['width: 100%', 'max-width: 100%', 'responsive: true', 'auto-resize: true'], 'correct': 1},
                    {'q': 'What is a breakpoint in responsive design?', 'opts': ['A bug in code', 'A point where layout changes', 'A loading point', 'An error point'], 'correct': 1},
                    {'q': 'Which CSS layout is best for responsive design?', 'opts': ['float', 'table', 'flexbox or grid', 'inline'], 'correct': 2},
                    {'q': 'What does "min-width" in media query mean?', 'opts': ['Minimum screen width', 'Applies when width is at least this value', 'Maximum width', 'Fixed width'], 'correct': 1},
                    {'q': 'Which viewport unit represents 1% of viewport width?', 'opts': ['vw', 'vh', 'vmin', 'vmax'], 'correct': 0}
                ]
            },
            {
                'title': 'Quiz 5 - Web Performance',
                'questions': [
                    {'q': 'What does CDN stand for?', 'opts': ['Content Delivery Network', 'Central Data Network', 'Content Distribution Node', 'Central Delivery Network'], 'correct': 0},
                    {'q': 'Which technique reduces HTTP requests?', 'opts': ['Adding more images', 'CSS sprites', 'Inline styles', 'More JavaScript files'], 'correct': 1},
                    {'q': 'What is minification?', 'opts': ['Making files smaller by removing whitespace', 'Compressing images', 'Reducing server load', 'Minimizing code lines'], 'correct': 0},
                    {'q': 'Which image format is best for web performance?', 'opts': ['BMP', 'TIFF', 'WebP', 'RAW'], 'correct': 2},
                    {'q': 'What is lazy loading?', 'opts': ['Slow loading', 'Loading content as needed', 'Delayed loading', 'Background loading'], 'correct': 1},
                    {'q': 'Which tool measures web performance?', 'opts': ['Photoshop', 'Lighthouse', 'Illustrator', 'Dreamweaver'], 'correct': 1},
                    {'q': 'What is caching?', 'opts': ['Storing data for reuse', 'Deleting old files', 'Compressing files', 'Encrypting data'], 'correct': 0},
                    {'q': 'Which HTTP method is cacheable?', 'opts': ['POST', 'PUT', 'GET', 'DELETE'], 'correct': 2},
                    {'q': 'What is GZIP compression?', 'opts': ['Image compression', 'Text file compression', 'Video compression', 'Audio compression'], 'correct': 1},
                    {'q': 'Which metric measures time to interactive?', 'opts': ['FCP', 'TTI', 'LCP', 'CLS'], 'correct': 1}
                ]
            }
        ],
        'default': [
            {
                'title': 'Quiz 1 - Fundamentals',
                'questions': [
                    {'q': 'What is the primary goal of this course?', 'opts': ['Learn basics', 'Master advanced concepts', 'Build projects', 'All of the above'], 'correct': 3},
                    {'q': 'Which skill is most important?', 'opts': ['Memorization', 'Understanding', 'Speed', 'Copying'], 'correct': 1},
                    {'q': 'How often should you practice?', 'opts': ['Once a week', 'Daily', 'Monthly', 'Never'], 'correct': 1},
                    {'q': 'What is the best learning approach?', 'opts': ['Passive reading', 'Active practice', 'Watching only', 'Listening only'], 'correct': 1},
                    {'q': 'Which resource is most valuable?', 'opts': ['Documentation', 'Videos', 'Practice problems', 'All combined'], 'correct': 3},
                    {'q': 'What indicates mastery?', 'opts': ['Completing course', 'Teaching others', 'Getting certificate', 'Watching all videos'], 'correct': 1},
                    {'q': 'How do you handle errors?', 'opts': ['Ignore them', 'Learn from them', 'Give up', 'Skip them'], 'correct': 1},
                    {'q': 'What is the key to retention?', 'opts': ['Reading once', 'Spaced repetition', 'Cramming', 'Highlighting'], 'correct': 1},
                    {'q': 'Which mindset helps learning?', 'opts': ['Fixed', 'Growth', 'Negative', 'Passive'], 'correct': 1},
                    {'q': 'What should you do when stuck?', 'opts': ['Give up', 'Ask for help', 'Skip it', 'Guess'], 'correct': 1}
                ]
            },
            {
                'title': 'Quiz 2 - Core Concepts',
                'questions': [
                    {'q': 'What is the foundation of this subject?', 'opts': ['Theory', 'Practice', 'Both', 'Neither'], 'correct': 2},
                    {'q': 'Which approach yields best results?', 'opts': ['Passive learning', 'Active engagement', 'Memorization', 'Copying'], 'correct': 1},
                    {'q': 'How important is consistency?', 'opts': ['Not important', 'Somewhat important', 'Very important', 'Optional'], 'correct': 2},
                    {'q': 'What role does feedback play?', 'opts': ['None', 'Minor', 'Critical', 'Optional'], 'correct': 2},
                    {'q': 'Which skill develops over time?', 'opts': ['Instant mastery', 'Problem solving', 'Luck', 'Guessing'], 'correct': 1},
                    {'q': 'What is the value of mistakes?', 'opts': ['None', 'Learning opportunities', 'Failures', 'Setbacks'], 'correct': 1},
                    {'q': 'How do experts differ from beginners?', 'opts': ['Talent', 'Practice hours', 'Luck', 'Age'], 'correct': 1},
                    {'q': 'What builds confidence?', 'opts': ['Avoiding challenges', 'Overcoming challenges', 'Easy tasks', 'Luck'], 'correct': 1},
                    {'q': 'Which habit supports learning?', 'opts': ['Procrastination', 'Regular practice', 'Cramming', 'Multitasking'], 'correct': 1},
                    {'q': 'What is the role of curiosity?', 'opts': ['Distraction', 'Fuel for learning', 'Waste of time', 'Optional'], 'correct': 1}
                ]
            },
            {
                'title': 'Quiz 3 - Application',
                'questions': [
                    {'q': 'How do you apply knowledge?', 'opts': ['Just read', 'Practice problems', 'Watch videos', 'Listen only'], 'correct': 1},
                    {'q': 'What is the best project approach?', 'opts': ['Copy paste', 'Build from scratch', 'Skip projects', 'Use templates only'], 'correct': 1},
                    {'q': 'Which validates understanding?', 'opts': ['Reading', 'Teaching', 'Watching', 'Listening'], 'correct': 1},
                    {'q': 'How do you measure progress?', 'opts': ['Time spent', 'Problems solved', 'Videos watched', 'Pages read'], 'correct': 1},
                    {'q': 'What indicates deep learning?', 'opts': ['Memorization', 'Application', 'Repetition', 'Speed'], 'correct': 1},
                    {'q': 'Which skill transfers best?', 'opts': ['Specific facts', 'Problem-solving', 'Memorized formulas', 'Shortcuts'], 'correct': 1},
                    {'q': 'How do you tackle complex problems?', 'opts': ['Give up', 'Break into parts', 'Guess', 'Skip'], 'correct': 1},
                    {'q': 'What builds expertise?', 'opts': ['Reading', 'Deliberate practice', 'Luck', 'Talent'], 'correct': 1},
                    {'q': 'Which approach ensures retention?', 'opts': ['One-time study', 'Spaced review', 'Cramming', 'Skimming'], 'correct': 1},
                    {'q': 'What is the goal of practice?', 'opts': ['Completion', 'Mastery', 'Speed', 'Quantity'], 'correct': 1}
                ]
            },
            {
                'title': 'Quiz 4 - Advanced Topics',
                'questions': [
                    {'q': 'What distinguishes advanced learners?', 'opts': ['Speed', 'Depth of understanding', 'Memorization', 'Age'], 'correct': 1},
                    {'q': 'How do you approach new concepts?', 'opts': ['Skip them', 'Connect to known concepts', 'Memorize', 'Ignore'], 'correct': 1},
                    {'q': 'What is the value of synthesis?', 'opts': ['None', 'Combining ideas', 'Copying', 'Repeating'], 'correct': 1},
                    {'q': 'Which skill is most transferable?', 'opts': ['Facts', 'Critical thinking', 'Formulas', 'Definitions'], 'correct': 1},
                    {'q': 'How do you handle ambiguity?', 'opts': ['Avoid it', 'Embrace it', 'Ignore it', 'Fear it'], 'correct': 1},
                    {'q': 'What drives innovation?', 'opts': ['Repetition', 'Curiosity', 'Memorization', 'Following rules'], 'correct': 1},
                    {'q': 'Which approach builds mastery?', 'opts': ['Surface learning', 'Deep learning', 'Quick review', 'Skimming'], 'correct': 1},
                    {'q': 'What is the role of reflection?', 'opts': ['Waste of time', 'Critical for growth', 'Optional', 'Unnecessary'], 'correct': 1},
                    {'q': 'How do you evaluate solutions?', 'opts': ['Accept first answer', 'Analyze critically', 'Guess', 'Skip'], 'correct': 1},
                    {'q': 'What builds long-term success?', 'opts': ['Shortcuts', 'Consistent effort', 'Luck', 'Talent'], 'correct': 1}
                ]
            },
            {
                'title': 'Quiz 5 - Mastery Assessment',
                'questions': [
                    {'q': 'What defines mastery?', 'opts': ['Completion', 'Deep understanding', 'Speed', 'Memorization'], 'correct': 1},
                    {'q': 'How do you maintain skills?', 'opts': ['Never practice', 'Regular practice', 'One-time learning', 'Forget them'], 'correct': 1},
                    {'q': 'What is the best learning strategy?', 'opts': ['Passive', 'Active', 'Random', 'None'], 'correct': 1},
                    {'q': 'Which mindset supports growth?', 'opts': ['Fixed', 'Growth', 'Negative', 'Closed'], 'correct': 1},
                    {'q': 'How do you approach challenges?', 'opts': ['Avoid', 'Embrace', 'Fear', 'Ignore'], 'correct': 1},
                    {'q': 'What is the value of persistence?', 'opts': ['None', 'Everything', 'Little', 'Optional'], 'correct': 1},
                    {'q': 'Which habit ensures success?', 'opts': ['Procrastination', 'Consistency', 'Cramming', 'Avoiding work'], 'correct': 1},
                    {'q': 'How do you measure understanding?', 'opts': ['Time spent', 'Can explain to others', 'Pages read', 'Videos watched'], 'correct': 1},
                    {'q': 'What drives continuous improvement?', 'opts': ['Satisfaction', 'Curiosity', 'Complacency', 'Luck'], 'correct': 1},
                    {'q': 'Which approach builds expertise?', 'opts': ['Quick fixes', 'Deliberate practice', 'Shortcuts', 'Luck'], 'correct': 1}
                ]
            }
        ]
    }
    
    total_quizzes_created = 0
    
    for class_id, class_title, teacher_id in classes:
        print(f"\nProcessing Class {class_id}: {class_title} (Teacher {teacher_id})")
        
        # Check existing quizzes for this class
        cursor.execute('SELECT COUNT(*) FROM quizzes WHERE class_id = ?', (class_id,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count >= 5:
            print(f"  Already has {existing_count} quizzes, skipping...")
            continue
        
        # Determine quiz template based on class title
        if 'web' in class_title.lower() or 'html' in class_title.lower() or 'css' in class_title.lower() or 'javascript' in class_title.lower():
            templates = quiz_templates['Web Development']
        else:
            templates = quiz_templates['default']
        
        # Create 5 quizzes for this class
        for quiz_template in templates:
            # Insert quiz
            cursor.execute(
                'INSERT INTO quizzes (class_id, title, created_at) VALUES (?, ?, ?)',
                (class_id, quiz_template['title'], datetime.now().isoformat())
            )
            quiz_id = cursor.lastrowid
            
            # Insert questions
            for q_data in quiz_template['questions']:
                options_json = json.dumps(q_data['opts'])
                cursor.execute(
                    'INSERT INTO quiz_questions (quiz_id, question_text, options, correct_option_index) VALUES (?, ?, ?, ?)',
                    (quiz_id, q_data['q'], options_json, q_data['correct'])
                )
            
            total_quizzes_created += 1
            print(f"  Created: {quiz_template['title']} (Quiz ID: {quiz_id})")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"QUIZ GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total quizzes created: {total_quizzes_created}")
    print(f"All quizzes are analytics-ready with proper class_id linkage")
    print(f"Students can attempt all quizzes")
    print(f"Teacher analytics will work correctly")

if __name__ == '__main__':
    generate_quizzes()
