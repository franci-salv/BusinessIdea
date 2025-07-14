import json

# Load JSON file
with open("quiz_template.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

# Convert to simple HTML
html = f"<h2>🧠 {quiz_data['title']} — {quiz_data['date']}</h2><ol>"

for q in quiz_data["questions"]:
    html += f"<li><p><strong>{q['question']}</strong></p><ul>"
    for option in q["options"]:
        html += f"<li>{option}</li>"
    html += "</ul></li>"

html += "</ol>"


