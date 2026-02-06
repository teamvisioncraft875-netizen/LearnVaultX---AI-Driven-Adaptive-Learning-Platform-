"""
Demo Data Generator for LearnVaultX Analytics
Generates realistic fake data for student and teacher analytics
"""

import random
from datetime import datetime, timedelta


class DemoDataGenerator:
    """Generate realistic demo analytics data"""
    
    def __init__(self, db):
        self.db = db
        
    def generate_student_analytics(self, user_id):
        """Generate complete analytics for a student"""
        
        # Get student's classes
        classes = self.db.execute_query(
            'SELECT id, name FROM classes WHERE id IN (SELECT class_id FROM class_enrollments WHERE student_id = ?)',
            (user_id,)
        )
        
        if not classes:
            classes = [{'id': 1, 'name': 'Demo Class'}]
        
        # Generate quiz attempts (5 per class)
        quiz_attempts = []
        for cls in classes:
            for i in range(5):
                quiz_attempts.append(self._generate_quiz_attempt(cls['id'], cls['name'], i))
        
        # Sort by date (most recent first)
        quiz_attempts.sort(key=lambda x: x['submitted_at'], reverse=True)
        
        # Calculate overall stats
        total_quizzes = len(quiz_attempts)
        avg_score = sum(q['score_percent'] for q in quiz_attempts) / total_quizzes if total_quizzes > 0 else 0
        total_correct = sum(q['correct_answers'] for q in quiz_attempts)
        total_questions = sum(q['total_questions'] for q in quiz_attempts)
        accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
        
        # Generate weekly trend (last 7 days)
        weekly_trend = self._generate_weekly_trend()
        
        # Generate topic breakdown
        topic_breakdown = self._generate_topic_breakdown()
        
        # Calculate progress
        overall_progress = min(95, avg_score + random.randint(-5, 10))
        
        return {
            'user_id': user_id,
            'overall_progress': round(overall_progress, 1),
            'avg_score': round(avg_score, 1),
            'total_quizzes': total_quizzes,
            'accuracy': round(accuracy, 1),
            'streak_days': random.randint(3, 15),
            'quiz_attempts': quiz_attempts,
            'weekly_trend': weekly_trend,
            'topic_breakdown': topic_breakdown,
            'strong_topics': self._get_strong_topics(topic_breakdown),
            'weak_topics': self._get_weak_topics(topic_breakdown)
        }
    
    def _generate_quiz_attempt(self, class_id, class_name, index):
        """Generate a single quiz attempt"""
        difficulties = ['Easy', 'Medium', 'Hard']
        difficulty = random.choice(difficulties)
        
        # Adjust score based on difficulty
        if difficulty == 'Easy':
            base_score = random.randint(70, 100)
        elif difficulty == 'Medium':
            base_score = random.randint(50, 90)
        else:  # Hard
            base_score = random.randint(30, 80)
        
        total_questions = random.choice([10, 15, 20])
        correct_answers = int(total_questions * base_score / 100)
        wrong_answers = total_questions - correct_answers
        score_percent = round((correct_answers / total_questions) * 100, 1)
        
        # Generate realistic past dates
        days_ago = random.randint(1, 30)
        submitted_at = datetime.now() - timedelta(days=days_ago)
        
        quiz_titles = [
            f"{class_name} - Chapter {index + 1} Quiz",
            f"{class_name} - Unit Test {index + 1}",
            f"{class_name} - Practice Quiz {index + 1}",
            f"{class_name} - Assessment {index + 1}",
            f"{class_name} - Review Quiz {index + 1}"
        ]
        
        return {
            'quiz_id': 100 + index,
            'class_id': class_id,
            'class_name': class_name,
            'quiz_title': random.choice(quiz_titles),
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'score_percent': score_percent,
            'time_taken_minutes': random.randint(5, 30),
            'submitted_at': submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
            'difficulty': difficulty
        }
    
    def _generate_weekly_trend(self):
        """Generate weekly score trend data"""
        trend = []
        base_score = random.randint(60, 80)
        
        for i in range(7):
            date = datetime.now() - timedelta(days=6-i)
            score = base_score + random.randint(-10, 15)
            score = max(0, min(100, score))  # Clamp between 0-100
            
            trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%a'),
                'score': round(score, 1)
            })
            
            base_score = score  # Trend continues from previous
        
        return trend
    
    def _generate_topic_breakdown(self):
        """Generate topic performance breakdown"""
        topics = [
            'Mathematics', 'Science', 'History', 'English', 
            'Computer Science', 'Physics', 'Chemistry', 'Biology'
        ]
        
        breakdown = {}
        for topic in random.sample(topics, 5):
            breakdown[topic] = {
                'score': round(random.uniform(50, 95), 1),
                'attempts': random.randint(2, 8),
                'accuracy': round(random.uniform(60, 98), 1)
            }
        
        return breakdown
    
    def _get_strong_topics(self, topic_breakdown):
        """Get top 3 strong topics"""
        sorted_topics = sorted(
            topic_breakdown.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        return [{'topic': t[0], 'score': t[1]['score']} for t in sorted_topics[:3]]
    
    def _get_weak_topics(self, topic_breakdown):
        """Get top 3 weak topics"""
        sorted_topics = sorted(
            topic_breakdown.items(),
            key=lambda x: x[1]['score']
        )
        return [{'topic': t[0], 'score': t[1]['score']} for t in sorted_topics[:3]]
    
    def generate_teacher_analytics(self, teacher_id):
        """Generate analytics for teacher's classes"""
        
        # Get teacher's classes
        classes = self.db.execute_query(
            'SELECT id, name FROM classes WHERE teacher_id = ?',
            (teacher_id,)
        )
        
        if not classes:
            classes = [{'id': 1, 'name': 'Demo Class'}]
        
        analytics = []
        
        for cls in classes:
            # Get enrolled students count
            enrollments = self.db.execute_query(
                'SELECT COUNT(*) as count FROM class_enrollments WHERE class_id = ?',
                (cls['id'],)
            )
            total_students = enrollments[0]['count'] if enrollments else random.randint(15, 40)
            
            # Generate class stats
            class_stats = {
                'class_id': cls['id'],
                'class_name': cls['name'],
                'total_students': total_students,
                'active_students_today': random.randint(int(total_students * 0.3), int(total_students * 0.7)),
                'avg_class_score': round(random.uniform(65, 85), 1),
                'quiz_completion_rate': round(random.uniform(70, 95), 1),
                'most_difficult_quiz': self._get_most_difficult_quiz(),
                'most_failed_topic': random.choice(['Algebra', 'Calculus', 'Organic Chemistry', 'Quantum Physics']),
                'top_students': self._generate_top_students(5),
                'performance_distribution': self._generate_performance_distribution(),
                'participation_trend': self._generate_participation_trend(),
                'completion_stats': self._generate_completion_stats()
            }
            
            analytics.append(class_stats)
        
        return {
            'teacher_id': teacher_id,
            'total_classes': len(classes),
            'class_analytics': analytics
        }
    
    def _get_most_difficult_quiz(self):
        """Get the most difficult quiz"""
        quiz_names = [
            'Advanced Calculus Final',
            'Quantum Mechanics Midterm',
            'Organic Chemistry Lab Test',
            'Advanced Physics Quiz',
            'Complex Analysis Assessment'
        ]
        return {
            'title': random.choice(quiz_names),
            'avg_score': round(random.uniform(45, 65), 1),
            'attempts': random.randint(20, 50)
        }
    
    def _generate_top_students(self, count):
        """Generate top students leaderboard"""
        first_names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Avery', 'Quinn']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
        
        students = []
        for i in range(count):
            students.append({
                'rank': i + 1,
                'name': f"{random.choice(first_names)} {random.choice(last_names)}",
                'avg_score': round(random.uniform(85, 98), 1),
                'quizzes_completed': random.randint(10, 25)
            })
        
        # Sort by score
        students.sort(key=lambda x: x['avg_score'], reverse=True)
        
        # Update ranks
        for i, student in enumerate(students):
            student['rank'] = i + 1
        
        return students
    
    def _generate_performance_distribution(self):
        """Generate score distribution data"""
        total = 100
        distribution = {
            '0-20%': random.randint(0, 5),
            '20-40%': random.randint(5, 15),
            '40-60%': random.randint(15, 25),
            '60-80%': random.randint(25, 35),
            '80-100%': 0
        }
        
        # Calculate remaining for 80-100%
        distribution['80-100%'] = total - sum(distribution.values())
        
        return distribution
    
    def _generate_participation_trend(self):
        """Generate participation trend over last 7 days"""
        trend = []
        base_participation = random.randint(50, 70)
        
        for i in range(7):
            date = datetime.now() - timedelta(days=6-i)
            participation = base_participation + random.randint(-10, 15)
            participation = max(30, min(100, participation))
            
            trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%a'),
                'participation_percent': round(participation, 1)
            })
            
            base_participation = participation
        
        return trend
    
    def _generate_completion_stats(self):
        """Generate quiz completion statistics"""
        total_quizzes = random.randint(10, 20)
        completed = random.randint(int(total_quizzes * 0.7), total_quizzes)
        
        return {
            'total_quizzes': total_quizzes,
            'completed': completed,
            'pending': total_quizzes - completed,
            'completion_rate': round((completed / total_quizzes) * 100, 1)
        }
