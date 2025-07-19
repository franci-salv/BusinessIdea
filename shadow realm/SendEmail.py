import requests
import json

# Load JSON file
with open("daily_quiz.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

# Build HTML email body
html = f"<h2>🧠 {quiz_data['title']} — {quiz_data['date']}</h2><ol>"
for q in quiz_data["questions"]:
    html += f"<li><p><strong>{q['question']}</strong></p><ul>"
    for option in q["options"]:
        html += f"<li>{option}</li>"
    html += "</ul></li>"
html += "</ol>"

# Your MailerLite Transactional API key
API_KEY = ""  # NEVER share publicly!

# Verified sender and recipients
SENDER_EMAIL = "francisalv@icloud.com"  # Must be verified in MailerLite
RECIPIENTS = [
    {"email": "francisalv@icloud.com"},
    {"email": "dodopower318@gmail.com"}
]

# Define headers and payload
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "email": {
        "from": {
            "email": SENDER_EMAIL,
            "name": "Daily Quiz"
        },
        "to": RECIPIENTS,
        "subject": f"{quiz_data['title']} — {quiz_data['date']}",
        "html": html
    }
}

# Correct endpoint for transactional email
url = "https://connect.mailerlite.com/api/email/send" 

# Send email
response = requests.post(url, headers=headers, json=payload)

# Output result
print("✅ Email sent!" if response.ok else f"❌ Error: {response.status_code}\n{response.text}")
