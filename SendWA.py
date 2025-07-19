from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import json
import os




app = Flask(__name__)

# Load quiz
def load_quiz():
    with open("daily_quiz.json", "r", encoding="utf-8") as f:
        return json.load(f)
quiz_data = load_quiz()

# Keep track of each user's question index
user_progress = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    quiz_data = load_quiz()

    incoming_msg = request.form.get('Body').strip().upper()
    user_number = request.form.get('From')

    response = MessagingResponse()
    msg = response.message()

    # If new user, start at Q0
    if user_number not in user_progress:
        user_progress[user_number] = 0

    index = user_progress[user_number]
    current_q = quiz_data["questions"][index]

# Input validation
    valid_inputs = ["A", "B", "C", "D"]

# Check if user already finished the quiz
    if user_number in user_progress and user_progress[user_number] >= 2:
        msg.body("🛑 You've already completed today's quiz! Come back tomorrow for new questions.")
        return str(response)

# If input is not A–D, warn user
    if incoming_msg not in valid_inputs:
        msg.body("🤖 I'm only programmed to understand answers A, B, C, or D.\nIf you're in the middle of the quiz, make sure to reply with one of those options.\nIf you've already completed the quiz, come back tomorrow!")
        return str(response)

# Continue with answer checking
    correct_letter = get_correct_letter(current_q)
    if incoming_msg == correct_letter:
        msg.body("✅ Correct!")
    else:
        msg.body(f"❌ Wrong! The correct answer was {correct_letter}) {current_q['correct_answer']}")


    # Move to next question
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

