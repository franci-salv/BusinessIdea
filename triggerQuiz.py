from twilio.rest import Client
import json
from dotenv import load_dotenv
import os

# Absolute path to your env file
env_path = os.path.join(os.path.dirname(__file__), "secret.env")
load_dotenv(dotenv_path=env_path)

# Debug prints
print("SID loaded:", os.getenv("TWILIO_ACCOUNT_SID")[:6] if os.getenv("TWILIO_ACCOUNT_SID") else "❌ MISSING")
print("Token loaded:", "✅" if os.getenv("TWILIO_AUTH_TOKEN") else "❌ MISSING")

print("Script is running from:", os.getcwd())
print("Expecting .env at:", env_path)

with open("secret.env", "r") as f:
    print("ENV FILE CONTENTS:")
    print(f.read())


account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# Load quiz
with open("daily_quiz.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

q = quiz_data["questions"][0]
question_text = (
    f"🧠 {quiz_data['title']} — {quiz_data['date']}\n\n"
    f"{q['question']}\n"
    f"A) {q['options'][0]}\n"
    f"B) {q['options'][1]}\n"
    f"C) {q['options'][2]}\n"
    f"D) {q['options'][3]}\n\n"
    "Reply with A, B, C or D!"
)

client = Client(account_sid, auth_token)

client.messages.create(
    body=question_text,
    from_='whatsapp:+14155238886',
    to='whatsapp:+393773753088'
)
