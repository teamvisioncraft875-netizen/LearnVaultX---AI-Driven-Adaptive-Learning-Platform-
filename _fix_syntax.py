import re
import os

file_path = r"c:\Users\subha\Desktop\ProjectLVX1\templates\arena\arena_quiz.html"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace { { with {{
    new_content = re.sub(r'\{\s+\{', '{{', content)
    # Replace } } with }}
    new_content = re.sub(r'\}\s+\}', '}}', new_content)

    # Also fix ( ( if any
    new_content = re.sub(r'\(\s+\(', '((', new_content)
    new_content = re.sub(r'\)\s+\)', '))', new_content)

    if content != new_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("FIXED: Replaced syntax errors.")
    else:
        print("NO CHANGE: Syntax appeared correct.")

    # Verify
    if "{ {" in new_content:
        print("WARNING: { { still present!")
    if "{{ quiz_type" in new_content:
        print("VERIFIED: {{ quiz_type is present.")

except Exception as e:
    print(f"Error: {e}")
