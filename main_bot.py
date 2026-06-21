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
import re
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
# Users currently being asked to enter their 3-letter arcade name
pending_arcade_name = set()

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

MENU_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "📚 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "📊 My Stats", "callback_data": "stats"}],
        [{"text": "🏆 Leaderboard", "callback_data": "leaderboard"}],
        [{"text": "✏️ Change My Tag", "callback_data": "change_tag"}],
        [{"text": "🛑 Unsubscribe", "callback_data": "unsubscribe"}]
    ]
}


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
            _add_column_if_missing(conn, "users", "arcade_name", "TEXT")

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

    def get_arcade_name(self, user_id):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.execute(
                    "SELECT arcade_name FROM users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
        except Exception as e:
            logger.error(f"Error getting arcade name: {e}")
            return None

    def set_arcade_name(self, user_id, arcade_name):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    "UPDATE users SET arcade_name = ? WHERE user_id = ?",
                    (arcade_name.upper(), user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting arcade name: {e}")
            return False

    def is_arcade_name_taken(self, arcade_name, exclude_user_id=None):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                if exclude_user_id:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM users WHERE arcade_name = ? AND user_id != ?",
                        (arcade_name.upper(), exclude_user_id)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM users WHERE arcade_name = ?",
                        (arcade_name.upper(),)
                    )
                return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"Error checking arcade name: {e}")
            return False

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
                      COALESCE(u.arcade_name, '???') AS display_name,
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


def _escape_html(text):
    """Escape HTML special characters in user-generated content."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    """Send a text message via Telegram API"""
    data = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = reply_markup
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


def send_post_quiz_buttons(chat_id):
    """Send action buttons after quiz completion."""
    keyboard = {
        "inline_keyboard": [
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "🏆 Leaderboard", "callback_data": "leaderboard"}],
            [{"text": "📚 Start Quiz", "callback_data": "start_quiz"}]
        ]
    }
    send_message(chat_id, "What would you like to do next?", reply_markup=keyboard)


def send_poll(chat_id, question, options, correct_option_id):
    """Send a poll. Returns Telegram poll id on success."""
    data = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "is_anonymous": False,
        "explanation": f"✅ The correct answer is: {options[correct_option_id]}"
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


def prompt_arcade_name(chat_id, user_id, is_change=False):
    """Ask the user to enter a 3-letter arcade tag."""
    pending_arcade_name.add(user_id)
    if is_change:
        current = user_db.get_arcade_name(user_id)
        msg = (
            f"✏️ Your current tag is <b>{_escape_html(current or '???')}</b>\n\n"
            "Enter a new <b>3-letter tag</b> for the leaderboard:"
        )
    else:
        msg = (
            "🕹️ <b>Welcome, player!</b>\n\n"
            "Before you start, pick a <b>3-letter tag</b> for the leaderboard.\n"
            "Just like the old arcade days!\n\n"
            "Type your 3 letters now (e.g. <b>ACE</b>, <b>MAX</b>, <b>ZAP</b>):"
        )
    send_message(chat_id, msg)


def handle_arcade_name_input(chat_id, user_id, text):
    """Validate and save the user's 3-letter arcade name."""
    name = text.strip().upper()

    if len(name) != 3 or not re.match(r'^[A-Z0-9]{3}$', name):
        send_message(
            chat_id,
            "⚠️ Your tag must be exactly <b>3 letters or numbers</b> (A-Z, 0-9).\n"
            "Try again:"
        )
        return

    if user_db.is_arcade_name_taken(name, exclude_user_id=user_id):
        send_message(
            chat_id,
            f"⚠️ <b>{_escape_html(name)}</b> is already taken! Pick another one:"
        )
        return

    pending_arcade_name.discard(user_id)
    user_db.set_arcade_name(user_id, name)
    send_message(
        chat_id,
        f"✅ Your leaderboard tag is now <b>{_escape_html(name)}</b>! 🕹️"
    )
    show_main_menu(chat_id)


def show_main_menu(chat_id):
    """Show the main menu with action buttons."""
    send_message(chat_id, "What would you like to do?", reply_markup=MENU_KEYBOARD)


def handle_start(chat_id, user_id, username):
    """Handle /start command"""
    user_db.add_user(user_id, username)

    send_message(
        chat_id,
        "🎉 Welcome to <b>Daily Puzzle Master</b>!\n\n"
        "Get 10 fresh questions every day at 10:00 AM ⏰\n\n"
        "Answer them one by one and earn encouragement! 🌟"
    )

    arcade_name = user_db.get_arcade_name(user_id)
    if not arcade_name:
        prompt_arcade_name(chat_id, user_id, is_change=False)
    else:
        show_main_menu(chat_id)


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
    elif data == "change_tag":
        prompt_arcade_name(chat_id, user_id, is_change=True)
    elif data == "unsubscribe":
        user_db.add_user(user_id, "")
        send_message(chat_id, "✅ Unsubscribed! Use /start to resubscribe.")
    elif data.startswith("answer_"):
        handle_answer(chat_id, user_id, data)


def start_quiz(chat_id, user_id):
    """Start or resume quiz"""
    user_db.add_user(user_id, "")

    arcade_name = user_db.get_arcade_name(user_id)
    if not arcade_name:
        prompt_arcade_name(chat_id, user_id, is_change=False)
        return

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
        send_message(chat_id, "🎉 You've already completed this quiz! Come back when the next one drops.")
        send_post_quiz_buttons(chat_id)
        return

    total = len(quiz["questions"])
    title = _escape_html(quiz.get('title', 'Daily Quiz'))
    send_message(chat_id, f"📚 <b>{title}</b>\n\nQuestion {progress + 1}/{total}")
    send_next_question(chat_id, user_id, quiz, progress)


def send_next_question(chat_id, user_id, quiz, question_index):
    """Send the next question"""
    if question_index >= len(quiz["questions"]):
        send_message(chat_id, "🏆 All done! You completed today's quiz!")
        send_post_quiz_buttons(chat_id)
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
        send_post_quiz_buttons(user_id)
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
        send_message(user_id, f"{random.choice(WRONG_MESSAGES)}\n\n💡 The correct answer was: <b>{_escape_html(correct_answer)}</b>")

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
        send_post_quiz_buttons(user_id)
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

    arcade_name = user_db.get_arcade_name(user_id) or "???"
    wrong = total - correct
    percentage = int((correct / total * 100)) if total > 0 else 0
    send_message(
        chat_id,
        f"📊 <b>Stats for {_escape_html(arcade_name)}</b>\n\n"
        f"✅ Correct: {correct}\n"
        f"❌ Wrong: {wrong}\n"
        f"📝 Answered: {total}\n"
        f"📈 Accuracy: {percentage}%"
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
            send_message(chat_id, "🏆 <b>Today's Leaderboard</b>\n\nNo scores yet. Be the first to complete the quiz!")
            return

        quiz_title = _escape_html(quiz.get("title", "Daily Quiz"))
        total_q = len(quiz.get("questions", []))

        message = f"🕹️ <b>{quiz_title}</b>\n📅 {_escape_html(quiz_id)}\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for idx, row in enumerate(leaderboard):
            try:
                db_user_id = row[0]
                arcade_tag = row[1] or "???"
                correct = int(row[2]) if row[2] is not None else 0
                rank_label = medals[idx] if idx < 3 else f"#{idx + 1}"
                display = _escape_html(arcade_tag)
                message += f"{rank_label} {display} — {correct}/{total_q}\n"
            except Exception as e:
                logger.error(f"Error processing leaderboard row {idx}: {e}", exc_info=True)
                continue

        user_rank = None
        user_score = None
        user_tag = user_db.get_arcade_name(user_id) or "???"
        for idx, row in enumerate(leaderboard):
            if row[0] == user_id:
                user_rank = idx + 1
                user_score = int(row[2]) if row[2] is not None else 0
                break

        total_players = len(leaderboard)
        message += (
            f"\n<b>You ({_escape_html(user_tag)}): "
            f"{user_score or 0}/{total_q}</b> — "
            f"Rank #{user_rank or '—'} of {total_players}"
        )

        if user_rank is None:
            message += "\nStart the quiz to join the leaderboard!"

        if len(message) > 4000:
            message = message[:3900] + "\n\n...<i>Leaderboard truncated</i>"

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
                            user_id = msg["from"]["id"]
                            chat_id = msg["chat"]["id"]
                            text = msg.get("text", "")
                            logger.info(f"[UPDATE] message from {user_id}: {text[:50]}")

                            if text == "/start":
                                username = msg["from"].get("username", "user")
                                handle_start(chat_id, user_id, username)
                            elif text == "/scrape":
                                send_message(chat_id, "⏳ Fetching today's quiz...")
                                fetch_and_save_quiz()
                                quiz = load_quiz()
                                if quiz:
                                    send_message(chat_id, f"✅ Got it! <b>{_escape_html(quiz['title'])}</b> ({_escape_html(quiz.get('date', '?'))}) — {len(quiz['questions'])} questions")
                                else:
                                    send_message(chat_id, "❌ Failed to fetch quiz. Check logs.")
                            elif user_id in pending_arcade_name:
                                handle_arcade_name_input(chat_id, user_id, text)

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
