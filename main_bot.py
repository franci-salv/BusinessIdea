#!/usr/bin/env python3
"""
Telegram Puzzle Bot - Daily Quiz with encouragement messages
Shows all 10 questions one at a time with feedback
"""

import os
import json
import sqlite3
import logging
import sys
import time
import random
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env file!")
    sys.exit(1)

QUIZ_PATH = os.path.join(os.path.dirname(__file__), "data", "daily_quiz.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "users.db")

if os.getenv("RENDER"):
    QUIZ_PATH = "/app/data/daily_quiz.json"
    DB_PATH = "/app/data/users.db"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Ensure data directory exists
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

# Track processed polls to avoid duplicates
processed_polls = set()
# Map (user_id, poll_id) -> question index for the poll that was sent
poll_question_map = {}

ENCOURAGEMENTS = [
    "🎉 Fantastic! You got it!",
    "⭐ Brilliant answer!",
    "🚀 You're on fire!",
    "💪 Nice work!",
    "🎯 Perfect!",
    "🏆 Awesome job!",
    "✨ Excellent!",
    "🌟 Keep going!",
    "🎊 Great thinking!",
    "👏 Well done!"
]

WRONG_MESSAGES = [
    "❌ Not quite. Try again next time!",
    "❌ That wasn't it. Better luck next!",
    "❌ Close, but not quite!",
    "❌ Not this time. Keep learning!",
    "❌ That's incorrect. No worries!"
]

def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column_if_missing(conn, table, column, definition):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _get_quiz_id(quiz):
    """Get a stable identifier for a quiz (title + date combo)."""
    return quiz.get("date", "unknown")


class UserDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    subscribed BOOLEAN DEFAULT 1,
                    quiz_progress INTEGER DEFAULT 0,
                    today_quiz_date TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            _add_column_if_missing(conn, "users", "quiz_progress", "INTEGER DEFAULT 0")
            _add_column_if_missing(conn, "users", "today_quiz_date", "TEXT")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS quiz_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    quiz_date TEXT,
                    question_number INTEGER,
                    answer_text TEXT,
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _add_column_if_missing(conn, "quiz_responses", "poll_id", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "answer_index", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "question_number", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "answer_text", "TEXT")
            conn.commit()

    def add_user(self, user_id, username):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding user: {e}")

    def get_user_progress(self, user_id):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.execute(
                    "SELECT quiz_progress, today_quiz_date FROM users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result if result else (0, None)
        except Exception as e:
            logger.error(f"Error getting progress: {e}")
            return (0, None)

    def set_user_progress(self, user_id, progress, quiz_date):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    """INSERT INTO users (user_id, quiz_progress, today_quiz_date)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                       quiz_progress = excluded.quiz_progress,
                       today_quiz_date = excluded.today_quiz_date""",
                    (user_id, progress, quiz_date)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error setting progress: {e}")

    def record_answer(self, user_id, quiz_date, question_num, answer, is_correct, poll_id=None, option_id=None):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    "INSERT INTO quiz_responses "
                    "(user_id, quiz_date, question_number, answer_text, is_correct, poll_id, answer_index) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, quiz_date, question_num, answer, is_correct, poll_id, option_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording answer: {e}")

    def get_today_leaderboard(self, quiz_date):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.execute("""
                    SELECT
                      qr.user_id,
                      COALESCE(u.username, 'Player') AS username,
                      CAST(SUM(qr.is_correct) AS INTEGER) AS correct,
                      COUNT(*) AS answered
                    FROM quiz_responses qr
                    LEFT JOIN users u ON u.user_id = qr.user_id
                    WHERE qr.quiz_date = ?
                    GROUP BY qr.user_id
                    ORDER BY correct DESC, answered ASC, qr.user_id ASC
                """, (quiz_date,))
                results = cursor.fetchall()
                logger.info(f"Leaderboard query for '{quiz_date}': {len(results)} user(s)")
                return results
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}", exc_info=True)
            return []


def load_quiz():
    try:
        if not os.path.exists(QUIZ_PATH):
            logger.warning(f"Quiz file not found at: {QUIZ_PATH}. Fetching fresh quiz...")
            fetch_and_save_quiz()

        if not os.path.exists(QUIZ_PATH):
            logger.error(f"Failed to fetch quiz. File still missing at: {QUIZ_PATH}")
            return None

        with open(QUIZ_PATH, 'r', encoding='utf-8') as f:
            quiz = json.load(f)
            if not quiz.get("questions"):
                logger.error("Quiz file is empty or has no questions")
                return None
            logger.info(f"Loaded quiz: {quiz['title']} ({len(quiz['questions'])} questions)")
            return quiz
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in quiz file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading quiz from {QUIZ_PATH}: {e}")
        return None


def fetch_and_save_quiz():
    """Fetch quiz from API and save locally"""
    try:
        logger.info("Fetching quiz from API...")
        headers = {"User-Agent": "Mozilla/5.0"}

        quiz_list_url = "https://quizoftheday.co.uk/api/quizzes"
        res = requests.get(quiz_list_url, headers=headers, timeout=10)
        quiz_list = res.json()

        latest_quiz = quiz_list["quizzes"][0]
        quiz_id = latest_quiz["id"]
        quiz_title = latest_quiz["name"]
        quiz_date = latest_quiz["quizDate"]

        quiz_url = f"https://quizoftheday.co.uk/api/quiz/{quiz_id}"
        res = requests.get(quiz_url, headers=headers, timeout=10)
        quiz_data = res.json()["quiz"]

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

        os.makedirs(os.path.dirname(QUIZ_PATH), exist_ok=True)
        with open(QUIZ_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Fetched and saved quiz: {quiz_title} ({quiz_date}) - {len(output['questions'])} questions")
    except Exception as e:
        logger.error(f"❌ Error fetching quiz from API: {e}", exc_info=True)


def send_message(chat_id, text):
    """Send a text message via Telegram API"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        result = response.json()
        if not result.get("ok"):
            error_desc = result.get('description', 'Unknown error')
            logger.error(f"Telegram API error: {error_desc} (chat={chat_id}, len={len(text)})")
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        return False


def send_poll(chat_id, question, options, correct_option_id):
    """Send a poll. Returns Telegram poll id on success."""
    data = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "is_anonymous": False,
        "explanation": f"✅ The correct answer is: **{options[correct_option_id]}**"
    }
    try:
        response = requests.post(f"{API_URL}/sendPoll", json=data, timeout=10)
        result = response.json()
        if result.get("ok"):
            return result["result"]["poll"]["id"]
        logger.error(f"sendPoll failed: {result}")
    except Exception as e:
        logger.error(f"Error sending poll: {e}")
    return None


def handle_start(chat_id, user_id):
    """Handle /start command"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "📚 Start Quiz", "callback_data": "start_quiz"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "🏆 Today's Leaderboard", "callback_data": "leaderboard"}],
            [{"text": "🛑 Unsubscribe", "callback_data": "unsubscribe"}]
        ]
    }

    send_message(
        chat_id,
        "🎉 Welcome to **Daily Puzzle Master**!\n\n"
        "Get 10 fresh questions every day at 10:00 AM ⏰\n\n"
        "Answer them one by one and earn encouragement! 🌟\n\n"
        "*What would you like to do?*"
    )

    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": "Choose an option:",
        "reply_markup": keyboard
    })


def handle_callback(query_id, chat_id, user_id, data):
    """Handle button clicks"""
    logger.info(f"[CALLBACK] user={user_id} data={data}")
    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loading..."})

    if data == "start_quiz":
        start_quiz(chat_id, user_id)
    elif data == "stats":
        show_stats(chat_id, user_id)
    elif data == "leaderboard":
        show_leaderboard(chat_id, user_id)
    elif data == "unsubscribe":
        user_db.add_user(user_id, "")
        send_message(chat_id, "✅ Unsubscribed! Use /start to resubscribe.")
    elif data.startswith("answer_"):
        handle_answer(chat_id, user_id, data)


def start_quiz(chat_id, user_id):
    """Start or resume quiz"""
    user_db.add_user(user_id, "")
    quiz = load_quiz()
    if not quiz or not quiz.get("questions"):
        send_message(chat_id, "❌ No quiz available today. Try again later!")
        return

    quiz_id = _get_quiz_id(quiz)
    progress, stored_quiz_id = user_db.get_user_progress(user_id)

    if stored_quiz_id != quiz_id:
        logger.info(f"[QUIZ] New quiz for user {user_id}: '{stored_quiz_id}' -> '{quiz_id}'")
        progress = 0
        user_db.set_user_progress(user_id, 0, quiz_id)

    if progress >= len(quiz["questions"]):
        send_message(chat_id, "🎉 You've completed today's quiz! Come back when the next quiz is available.")
        return

    total = len(quiz["questions"])
    send_message(chat_id, f"📚 **{quiz.get('title', 'Daily Quiz')}**\n\nQuestion {progress + 1}/{total}")
    send_next_question(chat_id, user_id, quiz, progress)


def send_next_question(chat_id, user_id, quiz, question_index):
    """Send the next question"""
    if question_index >= len(quiz["questions"]):
        send_message(chat_id, "🏆 All done! You completed today's quiz!")
        return

    q = quiz["questions"][question_index]
    options = q["options"]
    correct_idx = options.index(q["correct_answer"])

    poll_id = send_poll(
        chat_id,
        f"Q{question_index + 1}: {q['question']}",
        options,
        correct_idx
    )
    if poll_id is not None:
        poll_question_map[(user_id, poll_id)] = question_index


def handle_poll_answer(user_id, poll_id, option_id):
    """Handle poll answer and send next question"""
    global processed_polls

    poll_key = f"{user_id}_{poll_id}"
    if poll_key in processed_polls:
        return

    processed_polls.add(poll_key)
    user_db.add_user(user_id, "")

    quiz = load_quiz()
    if not quiz:
        return

    quiz_id = _get_quiz_id(quiz)
    progress, stored_quiz_id = user_db.get_user_progress(user_id)

    if stored_quiz_id != quiz_id:
        progress = 0
        user_db.set_user_progress(user_id, 0, quiz_id)

    poll_key_map = (user_id, poll_id)
    if poll_key_map in poll_question_map:
        question_index = poll_question_map.pop(poll_key_map)
    else:
        question_index = progress
        logger.warning(f"Poll {poll_id} not tracked for user {user_id}, using DB progress {progress}")

    if question_index >= len(quiz["questions"]):
        send_message(user_id, "🏆 All done! You already completed this quiz!")
        return

    if question_index < progress:
        return

    q = quiz["questions"][question_index]
    correct_idx = q["options"].index(q["correct_answer"])
    was_correct = (option_id == correct_idx)

    if was_correct:
        send_message(user_id, random.choice(ENCOURAGEMENTS))
    else:
        correct_answer = q["correct_answer"]
        send_message(user_id, f"{random.choice(WRONG_MESSAGES)}\n\n💡 The correct answer was: **{correct_answer}**")

    user_db.record_answer(
        user_id, quiz_id, question_index + 1, q["options"][option_id], was_correct,
        poll_id=poll_id, option_id=option_id
    )

    progress = question_index + 1
    user_db.set_user_progress(user_id, progress, quiz_id)

    time.sleep(0.5)

    total = len(quiz["questions"])
    if progress >= total:
        send_message(user_id, f"🏆 Awesome! You completed all {total} questions! 🎉")
        return

    send_next_question(user_id, user_id, quiz, progress)


def broadcast_daily_quiz():
    """Send quiz to all subscribed users"""
    logger.info("📢 Broadcasting daily quiz...")
    try:
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            cursor = conn.execute("SELECT user_id FROM users WHERE subscribed = 1")
            users = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return

    for user_id in users:
        try:
            send_message(user_id, "🎉 Good morning! Today's puzzle is here! Use /start to begin.")
            time.sleep(0.3)
            start_quiz(user_id, user_id)
        except Exception as e:
            logger.error(f"Error sending to user {user_id}: {e}")
        time.sleep(0.5)

    logger.info(f"✅ Sent to {len(users)} users")


def show_stats(chat_id, user_id):
    """Show user statistics"""
    try:
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM quiz_responses WHERE user_id = ? AND is_correct = 1",
                (user_id,)
            )
            correct = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM quiz_responses WHERE user_id = ?",
                (user_id,)
            )
            total = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        correct, total = 0, 0

    wrong = total - correct
    percentage = int((correct / total * 100)) if total > 0 else 0
    send_message(
        chat_id,
        f"📊 **Your Stats**\n\n✅ Correct: {correct}\n❌ Wrong: {wrong}\n📝 Answered: {total}\n📈 Accuracy: {percentage}%"
    )


def show_leaderboard(chat_id, user_id):
    """Show leaderboard for current quiz"""
    try:
        quiz = load_quiz()
        if not quiz:
            send_message(chat_id, "❌ Could not load quiz. Try again later.")
            return

        quiz_id = _get_quiz_id(quiz)
        logger.info(f"[LEADERBOARD] user={user_id} quiz_id='{quiz_id}'")

        leaderboard = user_db.get_today_leaderboard(quiz_id)

        if not leaderboard:
            send_message(chat_id, "🏆 **Today's Leaderboard**\n\nNo scores yet. Be the first to complete the quiz!")
            return

        quiz_title = quiz.get("title", "Daily Quiz")
        total_q = len(quiz.get("questions", []))

        message = f"🏆 **{quiz_title}**\n{quiz_id}\n\n"

        medals = ["🥇", "🥈", "🥉"]
        top_count = min(3, len(leaderboard))

        for idx in range(top_count):
            try:
                row = leaderboard[idx]
                db_user_id = row[0]
                username = row[1]
                correct = int(row[2]) if row[2] is not None else 0
                medal = medals[idx]
                display_name = f"@{username}" if username and username != "Player" else f"Player {db_user_id % 10000}"
                message += f"{medal} {display_name} — {correct}/{total_q}\n"
            except Exception as e:
                logger.error(f"Error processing leaderboard row {idx}: {e}", exc_info=True)
                continue

        user_rank = None
        user_score = None
        for idx, row in enumerate(leaderboard):
            if row[0] == user_id:
                user_rank = idx + 1
                user_score = int(row[2]) if row[2] is not None else 0
                break

        total_players = len(leaderboard)
        message += f"\n**You: {user_score or 0}/{total_q}** — Rank #{user_rank or '—'} of {total_players}"

        if user_rank is None:
            message += "\nStart the quiz to join the leaderboard!"

        if len(message) > 4000:
            message = message[:3900] + "\n\n...*Leaderboard truncated*"

        result = send_message(chat_id, message)
        if not result:
            logger.error(f"[LEADERBOARD] Failed to send to chat {chat_id}")

    except Exception as e:
        logger.error(f"[LEADERBOARD] ERROR: {e}", exc_info=True)
        send_message(chat_id, "❌ Error loading leaderboard. Please try again.")


def get_updates(offset=0):
    """Get updates from Telegram"""
    try:
        response = requests.get(
            f"{API_URL}/getUpdates",
            params={"offset": offset, "timeout": 10},
            timeout=15
        )
        result = response.json()
        return result.get("result", [])
    except requests.exceptions.Timeout:
        return []
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []


def main():
    """Start the bot"""
    global user_db
    user_db = UserDB(DB_PATH)
    logger.info("✅ Database initialized")
    logger.info("🤖 Bot is polling... Press Ctrl+C to stop")

    offset = 0

    try:
        while True:
            try:
                updates = get_updates(offset)

                for update in updates:
                    try:
                        offset = update["update_id"] + 1

                        if "message" in update:
                            msg = update["message"]
                            logger.info(f"[UPDATE] message from {msg['from'].get('id')}: {msg.get('text', '')[:50]}")
                            if msg.get("text") == "/start":
                                user_id = msg["from"]["id"]
                                username = msg["from"].get("username", "user")
                                user_db.add_user(user_id, username)
                                handle_start(msg["chat"]["id"], user_id)
                            elif msg.get("text") == "/scrape":
                                chat_id = msg["chat"]["id"]
                                send_message(chat_id, "⏳ Fetching today's quiz...")
                                fetch_and_save_quiz()
                                quiz = load_quiz()
                                if quiz:
                                    send_message(chat_id, f"✅ Got it! **{quiz['title']}** ({quiz.get('date', '?')}) — {len(quiz['questions'])} questions")
                                else:
                                    send_message(chat_id, "❌ Failed to fetch quiz. Check logs.")

                        elif "callback_query" in update:
                            query = update["callback_query"]
                            user_id = query["from"]["id"]
                            username = query["from"].get("username", "user")
                            logger.info(f"[UPDATE] callback from {user_id}: {query.get('data')}")
                            user_db.add_user(user_id, username)
                            handle_callback(query["id"], query["message"]["chat"]["id"], user_id, query["data"])

                        elif "poll_answer" in update:
                            poll_answer = update["poll_answer"]
                            user_id = poll_answer["user"]["id"]
                            poll_id = poll_answer["poll_id"]
                            option_id = poll_answer["option_ids"][0] if poll_answer.get("option_ids") else 0
                            logger.info(f"[UPDATE] poll_answer from {user_id}: poll={poll_id} option={option_id}")
                            handle_poll_answer(user_id, poll_id, option_id)

                    except Exception as e:
                        logger.error(f"Error processing update: {e}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Polling loop error: {e}", exc_info=True)
                time.sleep(5)

    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")


if __name__ == "__main__":
    main()
