from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import json

app = Flask(__name__)

# Load quiz
with open("daily_quiz.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

# Keep track of each user's question index
user_progress = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.form.get('Body').strip().upper()
    user_number = request.form.get('From')

    response = MessagingResponse()
    msg = response.message()

    # If new user, start at Q0
    if user_number not in user_progress:
        user_progress[user_number] = 0

    index = user_progress[user_number]
    current_q = quiz_data["questions"][index]

    # Check if answer is correct
    correct_letter = get_correct_letter(current_q)
    if incoming_msg == correct_letter:
        msg.body("✅ Correct!")
    else:
        msg.body(f"❌ Wrong! The correct answer was {correct_letter}) {current_q['correct_answer']}")

    # Move to next question
    index += 1
    if index < len(quiz_data["questions"]):
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
    app.run(port=5000)
