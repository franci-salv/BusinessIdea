import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0"
}

# STEP 1: Get today's quiz ID from the list
quiz_list_url = "https://quizoftheday.co.uk/api/quizzes"
res = requests.get(quiz_list_url, headers=headers)
quiz_list = res.json()

# Get the first (most recent) quiz
latest_quiz = quiz_list["quizzes"][0]
quiz_id = latest_quiz["id"]
quiz_title = latest_quiz["name"]
quiz_date = latest_quiz["quizDate"]

# STEP 2: Use that ID to fetch the full quiz
quiz_url = f"https://quizoftheday.co.uk/api/quiz/{quiz_id}"
res = requests.get(quiz_url, headers=headers)
quiz_data = res.json()["quiz"]

# STEP 3: Extract clean questions
output = {
    "title": quiz_title,
    "date": quiz_date,
    "questions": []
}

for q in quiz_data["questions"]:
    question_text = q["text"]
    options = [a["text"] for a in q["answers"]]
    correct_answer = next(a["text"] for a in q["answers"] if a["correct"])
    
    output["questions"].append({
        "question": question_text,
        "options": options,
        "correct_answer": correct_answer
    })

# STEP 4: Save as JSON
import os
output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "daily_quiz.json")

if os.getenv("RENDER"):
    output_path = "/app/data/daily_quiz.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"OK: Fetched quiz - {quiz_title} ({quiz_date}) with {len(output['questions'])} questions.")
print(f"Saved to: {output_path}")




