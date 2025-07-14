from twilio.rest import Client
import json

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

account_sid = 'AC4824518f33e5c5947ea93c97a9eaa74f'
auth_token = '405b98b9d0f64ea003841c70f3b716ec'
client = Client(account_sid, auth_token)

client.messages.create(
    body=question_text,
    from_='whatsapp:+14155238886',
    to='whatsapp:+393773753088'
)
