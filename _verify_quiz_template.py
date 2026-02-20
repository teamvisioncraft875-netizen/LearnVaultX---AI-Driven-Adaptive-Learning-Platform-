from flask import Flask, render_template_string
import json

app = Flask(__name__)

template = """
<script>
    window.QUIZ_DATA = {
        questions: {{ questions|tojson if questions else '[]' }},
        quizType: '{{ quiz_type }}',
        exam: '{{ exam if exam is defined else "" }}',
        subject: '{{ subject if subject is defined else "" }}',
        timeLimit: {{ time_limit }},
        totalQuestions: {{ questions|length if questions else 0 }}
    };
</script>
"""

with app.app_context():
    # Mock data
    questions = [{'id': 1, 'text': 'Q1'}, {'id': 2, 'text': 'Q2'}]
    rendered = render_template_string(template, 
                                      questions=questions, 
                                      quiz_type='daily',
                                      exam='JEE',
                                      subject='Physics',
                                      time_limit=600)
    print("RENDERED OUTPUT:")
    print(rendered)
    
    # Check for valid JS syntax (simple check)
    if "timeLimit: 600" in rendered and "totalQuestions: 2" in rendered:
        print("\n✅ Verification PASSED: Valid JS structure detected.")
    else:
        print("\n❌ Verification FAILED: Invalid structure.")
