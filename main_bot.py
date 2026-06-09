#!/usr/bin/env python3
"""
Telegram Puzzle Bot - Daily Quiz with encouragement messages
Shows all 10 questions one at a time with feedback
"""

import os
import json
import sqlite3
import logging
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env file!")
    exit(1)

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


class UserDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
            # Migrate legacy schema from core/telegram_bot.py
            _add_column_if_missing(conn, "quiz_responses", "poll_id", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "answer_index", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "question_number", "INTEGER")
            _add_column_if_missing(conn, "quiz_responses", "answer_text", "TEXT")
            conn.commit()
    
    def add_user(self, user_id, username):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding user: {e}")
    
    def get_user_progress(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                cols = _table_columns(conn, "quiz_responses")
                if "question_number" in cols and "answer_text" in cols:
                    conn.execute(
                        "INSERT INTO quiz_responses "
                        "(user_id, quiz_date, question_number, answer_text, is_correct, poll_id, answer_index) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (user_id, quiz_date, question_num, answer, is_correct, poll_id, option_id)
                    )
                else:
                    conn.execute(
                        "INSERT INTO quiz_responses (user_id, quiz_date, poll_id, answer_index, is_correct) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (user_id, quiz_date, poll_id or 0, option_id or 0, is_correct)
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording answer: {e}")

def load_quiz():
    try:
        with open(QUIZ_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading quiz: {e}")
        return None

def send_message(chat_id, text):
    """Send a text message"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

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
    
    # Send the keyboard
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": "Choose an option:",
        "reply_markup": keyboard
    })

def handle_callback(query_id, chat_id, user_id, data):
    """Handle button clicks"""
    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loading..."})
    
    if data == "start_quiz":
        start_quiz(chat_id, user_id)
    elif data == "stats":
        show_stats(chat_id, user_id)
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
    
    today = datetime.now().strftime("%Y-%m-%d")
    progress, quiz_date = user_db.get_user_progress(user_id)
    
    # Reset if it's a new day
    if quiz_date != today:
        progress = 0
        user_db.set_user_progress(user_id, 0, today)
    
    if progress >= len(quiz["questions"]):
        send_message(chat_id, "🎉 You've completed today's quiz! Come back tomorrow for new questions.")
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
    
    # Prevent duplicate processing
    poll_key = f"{user_id}_{poll_id}"
    if poll_key in processed_polls:
        logger.info(f"⏭️ Poll already processed: {poll_key}")
        return
    
    processed_polls.add(poll_key)
    user_db.add_user(user_id, "")
    
    quiz = load_quiz()
    if not quiz:
        return
    
    progress, quiz_date = user_db.get_user_progress(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Reset if new day
    if quiz_date != today:
        progress = 0
        user_db.set_user_progress(user_id, 0, today)
    
    poll_key_map = (user_id, poll_id)
    if poll_key_map in poll_question_map:
        question_index = poll_question_map.pop(poll_key_map)
    else:
        question_index = progress
        logger.warning(
            f"Poll {poll_id} not tracked for user {user_id}, using DB progress {progress}"
        )
    
    if question_index >= len(quiz["questions"]):
        send_message(user_id, "🏆 All done! You already completed today's quiz!")
        return
    
    # Reject answers to polls from an earlier question in today's quiz
    if question_index < progress:
        logger.info(f"Ignoring stale poll answer: Q{question_index + 1} (progress is Q{progress + 1})")
        return
    
    q = quiz["questions"][question_index]
    correct_idx = q["options"].index(q["correct_answer"])
    was_correct = (option_id == correct_idx)
    
    if was_correct:
        import random
        msg = random.choice(ENCOURAGEMENTS)
        send_message(user_id, msg)
    else:
        import random
        msg = random.choice(WRONG_MESSAGES)
        correct_answer = q["correct_answer"]
        send_message(user_id, f"{msg}\n\n💡 The correct answer was: **{correct_answer}**")
    
    user_db.record_answer(
        user_id, today, question_index + 1, q["options"][option_id], was_correct,
        poll_id=poll_id, option_id=option_id
    )
    
    progress = question_index + 1
    user_db.set_user_progress(user_id, progress, today)
    
    time.sleep(0.5)
    
    total = len(quiz["questions"])
    if progress >= total:
        send_message(user_id, f"🏆 Awesome! You completed all {total} questions today! 🎉")
        return
    
    logger.info(f"➡️ Sending Q{progress + 1} to user {user_id}")
    send_next_question(user_id, user_id, quiz, progress)

def broadcast_daily_quiz():
    """Send quiz to all subscribed users"""
    logger.info("📢 Broadcasting daily quiz...")
    user_db_inst = UserDB(DB_PATH)
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
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
        with sqlite3.connect(DB_PATH) as conn:
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

def get_updates(offset=0):
    """Get updates from Telegram"""
    try:
        response = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
        return response.json().get("result", [])
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
            updates = get_updates(offset)
            
            for update in updates:
                offset = update["update_id"] + 1
                
                # Handle messages
                if "message" in update:
                    msg = update["message"]
                    if msg.get("text") == "/start":
                        user_id = msg["from"]["id"]
                        username = msg["from"].get("username", "user")
                        user_db.add_user(user_id, username)
                        handle_start(msg["chat"]["id"], user_id)
                
                # Handle button clicks
                elif "callback_query" in update:
                    query = update["callback_query"]
                    user_id = query["from"]["id"]
                    username = query["from"].get("username", "user")
                    user_db.add_user(user_id, username)
                    handle_callback(query["id"], query["message"]["chat"]["id"], user_id, query["data"])
                
                # Handle poll answers (auto-send next question)
                elif "poll_answer" in update:
                    poll_answer = update["poll_answer"]
                    user_id = poll_answer["user"]["id"]
                    poll_id = poll_answer["poll_id"]
                    option_id = poll_answer["option_ids"][0] if poll_answer.get("option_ids") else 0
                    logger.info(f"✅ User {user_id} answered option {option_id} in poll {poll_id}")
                    handle_poll_answer(user_id, poll_id, option_id)
    
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")

if __name__ == "__main__":
    main()
