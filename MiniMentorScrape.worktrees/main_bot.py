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
            # Migrate legacy schema from core/telegram_bot.py
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
        except sqlite3.OperationalError as e:
            logger.error(f"Database lock adding user {user_id}: {e}")
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
        except sqlite3.OperationalError as e:
            logger.error(f"Database lock getting progress for user {user_id}: {e}")
            return (0, None)
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
        except sqlite3.OperationalError as e:
            logger.error(f"Database lock setting progress for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error setting progress: {e}")
    
    def record_answer(self, user_id, quiz_date, question_num, answer, is_correct, poll_id=None, option_id=None):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
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
        except sqlite3.OperationalError as e:
            logger.error(f"Database lock recording answer for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error recording answer: {e}")
    
    def get_today_leaderboard(self, quiz_date):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.execute("""
                    SELECT
                      qr.user_id,
                      COALESCE(u.username, 'Player') AS username,
                      SUM(qr.is_correct) AS correct,
                      COUNT(*) AS answered
                    FROM quiz_responses qr
                    LEFT JOIN users u ON u.user_id = qr.user_id
                    WHERE qr.quiz_date = ?
                    GROUP BY qr.user_id
                    ORDER BY correct DESC, answered ASC, qr.user_id ASC
                """, (quiz_date,))
                results = cursor.fetchall()
                logger.info(f"Leaderboard query returned {len(results)} users for date {quiz_date}")
                return results
        except sqlite3.OperationalError as e:
            logger.error(f"Database operational error fetching leaderboard: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
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
        
        logger.info(f"Fetched and saved quiz: {quiz_title} ({len(output['questions'])} questions)")
    except Exception as e:
        logger.error(f"Error fetching quiz from API: {e}")

def send_message(chat_id, text):
    """Send a text message"""
    logger.info(f"📤 [SEND_MSG] Attempting to send {len(text)} char message to chat {chat_id}")
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        logger.info(f"📤 [SEND_MSG] Got HTTP {response.status_code} response")
        result = response.json()
        logger.info(f"📤 [SEND_MSG] API response: ok={result.get('ok')}, error_code={result.get('error_code')}")
        if not result.get("ok"):
            error_desc = result.get('description', 'Unknown error')
            logger.error(f"❌ [SEND_MSG] Telegram API error: {error_desc} | Message length: {len(text)}")
            return False
        logger.info(f"✅ [SEND_MSG] Message sent successfully")
        return True
    except Exception as e:
        logger.error(f"❌ [SEND_MSG] Exception: {e} | Message length: {len(text)}", exc_info=True)
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
    
    # Send the keyboard
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": "Choose an option:",
        "reply_markup": keyboard
    })

def handle_callback(query_id, chat_id, user_id, data):
    """Handle button clicks"""
    logger.info(f"🔘 [CALLBACK] User {user_id} clicked: {data}")
    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loading..."})
    
    if data == "start_quiz":
        logger.info(f"🔘 [CALLBACK] Starting quiz for user {user_id}")
        start_quiz(chat_id, user_id)
    elif data == "stats":
        logger.info(f"🔘 [CALLBACK] Showing stats for user {user_id}")
        show_stats(chat_id, user_id)
    elif data == "leaderboard":
        logger.info(f"🔘 [CALLBACK] Showing leaderboard for user {user_id}")
        show_leaderboard(chat_id, user_id)
    elif data == "unsubscribe":
        logger.info(f"🔘 [CALLBACK] Unsubscribing user {user_id}")
        user_db.add_user(user_id, "")
        send_message(chat_id, "✅ Unsubscribed! Use /start to resubscribe.")
    elif data.startswith("answer_"):
        logger.info(f"🔘 [CALLBACK] Handling answer for user {user_id}")
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
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            cursor = conn.execute("SELECT user_id FROM users WHERE subscribed = 1")
            users = [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        logger.error(f"Database lock fetching users for broadcast: {e}")
        return
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
    except sqlite3.OperationalError as e:
        logger.error(f"Database lock fetching stats for user {user_id}: {e}")
        correct, total = 0, 0
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
    """Show today's leaderboard with user rank"""
    try:
        logger.info(f"📊 [LEADERBOARD] User {user_id} requested leaderboard in chat {chat_id}")
        today = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"📊 [LEADERBOARD] Fetching leaderboard for date: {today}")
        leaderboard = user_db.get_today_leaderboard(today)
        logger.info(f"📊 [LEADERBOARD] Got {len(leaderboard)} users on leaderboard")
        
        if not leaderboard:
            logger.warning(f"📊 [LEADERBOARD] No scores found for {today}")
            result = send_message(chat_id, "🏆 **Today's Leaderboard**\n\nNo scores yet today. Be the first to take the quiz!")
            logger.info(f"📊 [LEADERBOARD] Sent empty leaderboard message: {result}")
            return
        
        quiz = load_quiz()
        quiz_title = quiz.get("title", "Daily Quiz") if quiz else "Daily Quiz"
        logger.info(f"📊 [LEADERBOARD] Quiz title: {quiz_title}")
        
        message = f"🏆 **Today's Leaderboard**\n{quiz_title} — {today}\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        top_count = min(3, len(leaderboard))
        logger.info(f"📊 [LEADERBOARD] Building top {top_count} entries")
        for idx in range(top_count):
            db_user_id, username, correct, answered = leaderboard[idx]
            medal = medals[idx] if idx < 3 else "  "
            display_name = f"@{username}" if username and username != "Player" else f"Player {db_user_id % 10000}"
            message += f"{medal} {display_name} — {correct}/10\n"
            logger.info(f"📊 [LEADERBOARD] Top {idx+1}: {display_name} = {correct}/10")
        
        user_rank = None
        user_score = None
        for idx, (db_user_id, username, correct, answered) in enumerate(leaderboard):
            if db_user_id == user_id:
                user_rank = idx + 1
                user_score = correct
                logger.info(f"📊 [LEADERBOARD] User {user_id} is rank {user_rank} with {correct} correct")
                break
        
        total_players = len(leaderboard)
        message += f"\n**You: {user_score or 0}/10** — Rank #{user_rank or '—'} of {total_players}"
        
        if user_rank is None:
            message += "\nStart the quiz to join today's board!"
            logger.info(f"📊 [LEADERBOARD] User {user_id} not on leaderboard yet")
        
        logger.info(f"📊 [LEADERBOARD] Final message length: {len(message)} chars")
        
        # Check message length to avoid Telegram's 4096 character limit
        if len(message) > 4000:
            logger.warning(f"⚠️ [LEADERBOARD] Message too long ({len(message)} chars), truncating")
            message = message[:3900] + "\n\n...*Leaderboard truncated*"
            logger.info(f"📊 [LEADERBOARD] Truncated to {len(message)} chars")
        
        logger.info(f"📊 [LEADERBOARD] Sending message to chat {chat_id}")
        result = send_message(chat_id, message)
        logger.info(f"📊 [LEADERBOARD] send_message returned: {result}")
        
        if not result:
            logger.error(f"❌ [LEADERBOARD] Failed to send message! Message was: {message[:200]}...")
        
    except Exception as e:
        logger.error(f"❌ [LEADERBOARD] CRITICAL ERROR: {e}", exc_info=True)
        send_message(chat_id, f"❌ Error loading leaderboard: {str(e)[:100]}")

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
