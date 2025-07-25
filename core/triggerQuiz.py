from twilio.rest import Client
import json
import os
import requests
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), "..", "env", ".env.dev")
load_dotenv(dotenv_path=env_path)

account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
refresh_key = os.getenv("REFRESH_KEY")
refresh_url = "https://user-ui-quiz.onrender.com/refresh_quiz"

client = Client(account_sid, auth_token)

def format_question_text():
    quiz_path = os.path.join(os.path.dirname(__file__), "..", "data", "daily_quiz.json")
    with open(quiz_path, "r", encoding="utf-8") as f:
        quiz_data = json.load(f)

    q = quiz_data["questions"][0]
    print('Message formatting SUCCESS')
    return (
        f"🧠 {quiz_data['title']} — {quiz_data['date']}\n\n"
        f"{q['question']}\n"
        f"A) {q['options'][0]}\n"
        f"B) {q['options'][1]}\n"
        f"C) {q['options'][2]}\n"
        f"D) {q['options'][3]}\n\n"
        "Reply with A, B, C or D!"
    )

def synchronise_quiz_data():
    try:
        response = requests.post(
            refresh_url,
            headers={"X-API-Key": refresh_key}
        )
        print("📨 Sent refresh signal to Flask app")
        print("Response:", response.status_code, response.text)
    except Exception as e:
        print("⚠️ Failed to refresh Flask app:", e)

def send_quiz_message(to_number: str, message_override=None):
    if message_override:
        print("📦 Using message override for testing")
        question_text = message_override
    else:
        question_text = format_question_text()
    
    print(f"📨 Sending quiz to {to_number}...")
    client.messages.create(
        body=question_text,
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{to_number}'
    )

    synchronise_quiz_data()

if __name__ == "__main__":
    # Replace with real user list later
    user_numbers = ["+393773753088"]
    for num in user_numbers:
        send_quiz_message(num)
