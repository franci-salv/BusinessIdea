from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
import time

app = Flask(__name__)

quiz_data = {}

def load_quiz():
    global quiz_data
    print("📅 Loading new quiz data...")
    quiz_path = os.path.join(os.path.dirname(__file__), "..", "data", "daily_quiz.json")
    with open(quiz_path, "r", encoding="utf-8") as f:
        quiz_data = json.load(f)


# Load quiz initially
load_quiz()

# Scheduler to refresh every 24h
scheduler = BackgroundScheduler()
scheduler.add_job(func=load_quiz, trigger="interval", hours=24)
scheduler.start()

# Prevent scheduler from being killed with the app
import atexit
atexit.register(lambda: scheduler.shutdown())

user_progress = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    if os.getenv("TEST_MODE") == "1":
        print("⚠️ Skipping user response logic — TEST_MODE active")
        return "🛑 Response temporarily disabled", 200
    incoming_msg = request.form.get('Body').strip().upper()
    user_number = request.form.get('From')

    response = MessagingResponse()
    msg = response.message()

    if user_number not in user_progress:
        user_progress[user_number] = 0

    index = user_progress[user_number]

    if user_progress[user_number] >= 2:
        msg.body("🛑 You've already completed today's quiz! Come back tomorrow for new questions.")
        return str(response)

    valid_inputs = ["A", "B", "C", "D"]
    if incoming_msg not in valid_inputs:
        msg.body("🤖 I'm only programmed to understand answers A, B, C, or D.\nIf you've already completed the quiz, come back tomorrow!")
        return str(response)

    current_q = quiz_data["questions"][index]
    correct_letter = get_correct_letter(current_q)
    if incoming_msg == correct_letter:
        msg.body("✅ Correct!")
    else:
        msg.body(f"❌ Wrong! The correct answer was {correct_letter}) {current_q['correct_answer']}")

    index += 1
    if index < 2:
        user_progress[user_number] = index
        next_q = quiz_data["questions"][index]
        msg.body("\n" + format_question(next_q, index + 1))
    else:
        msg.body("\n🎉 Quiz complete! Thanks for playing!")

    return str(response)

def format_question(q, number):
    return (
        f"🧠 Q{number}: {q['question']}\n"
        f"A) {q['options'][0]}\n"
        f"B) {q['options'][1]}\n"
        f"C) {q['options'][2]}\n"
        f"D) {q['options'][3]}\n\n"
        "Reply with A, B, C or D!"
    )

def get_correct_letter(q):
    correct = q['correct_answer']
    index = q['options'].index(correct)
    return ["A", "B", "C", "D"][index]




@app.route("/refresh_quiz", methods=["POST"])
def refresh_quiz():
    if request.headers.get("X-API-Key") != os.getenv("REFRESH_KEY"):
        return "⛔ Unauthorized", 403

    load_quiz()
    print("✅ Quiz reloaded via webhook!")
    return "✅ Quiz reloaded", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
