import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, PollHandler
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
QUIZ_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "daily_quiz.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")

# Ensure data directory exists
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

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
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quiz_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    quiz_date TEXT,
                    poll_id INTEGER,
                    answer_index INTEGER,
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
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
    
    def get_subscribed_users(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT user_id FROM users WHERE subscribed = 1")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            return []
    
    def unsubscribe_user(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE users SET subscribed = 0 WHERE user_id = ?", (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error unsubscribing user: {e}")
    
    def resubscribe_user(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE users SET subscribed = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error resubscribing user: {e}")

def load_quiz():
    try:
        with open(QUIZ_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading quiz: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db.add_user(user.id, user.username or user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("📚 Get Today's Quiz", callback_data="get_quiz")],
        [InlineKeyboardButton("🛑 Unsubscribe from Daily Puzzles", callback_data="unsubscribe")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎉 Welcome to **Puzzle Master Bot**!\n\n"
        f"You'll receive a new daily puzzle each morning.\n\n"
        f"React to polls with your answer, and I'll reveal the correct answer after the poll ends.\n\n"
        f"*What would you like to do?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db.unsubscribe_user(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Resubscribe", callback_data="resubscribe")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "😢 You've been unsubscribed from daily puzzles.\n"
        "You can resubscribe anytime!",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_quiz":
        await send_quiz_poll(query, context)
    elif query.data == "unsubscribe":
        user_db.unsubscribe_user(query.from_user.id)
        await query.edit_message_text("✅ Unsubscribed! Use /start to resubscribe.")
    elif query.data == "resubscribe":
        user_db.resubscribe_user(query.from_user.id)
        await query.edit_message_text("✅ Resubscribed! You'll get tomorrow's puzzle.")

async def send_quiz_poll(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    quiz = load_quiz()
    if not quiz or not quiz.get("questions"):
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text("❌ No quiz available today. Try again later!")
        else:
            await update_or_query.edit_message_text("❌ No quiz available today. Try again later!")
        return
    
    questions = quiz["questions"]
    
    for idx, q in enumerate(questions[:2]):
        options = q["options"]
        correct_idx = options.index(q["correct_answer"])
        
        if hasattr(update_or_query, 'message'):
            poll_msg = await update_or_query.message.reply_poll(
                question=f"Q{idx + 1}: {q['question']}",
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_idx,
                is_anonymous=False,
                explanation=f"✅ The correct answer is: **{q['correct_answer']}**"
            )
        else:
            await update_or_query.edit_message_text(f"📚 Starting quiz: {quiz['title']}")
            poll_msg = await context.bot.send_poll(
                chat_id=update_or_query.from_user.id,
                question=f"Q{idx + 1}: {q['question']}",
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_idx,
                is_anonymous=False,
                explanation=f"✅ The correct answer is: **{q['correct_answer']}**"
            )

async def send_daily_quiz(context: ContextTypes.DEFAULT_TYPE):
    logger.info("📤 Sending daily quiz to all users...")
    users = user_db.get_subscribed_users()
    
    if not users:
        logger.info("No subscribed users found.")
        return
    
    quiz = load_quiz()
    if not quiz or not quiz.get("questions"):
        logger.error("No quiz available to send.")
        return
    
    questions = quiz["questions"]
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Good morning! Here's today's puzzle!\n\n📅 {quiz.get('title', 'Daily Quiz')}"
            )
            
            for idx, q in enumerate(questions[:2]):
                options = q["options"]
                correct_idx = options.index(q["correct_answer"])
                
                await context.bot.send_poll(
                    chat_id=user_id,
                    question=f"Q{idx + 1}: {q['question']}",
                    options=options,
                    type=Poll.QUIZ,
                    correct_option_id=correct_idx,
                    is_anonymous=False,
                    explanation=f"✅ The correct answer is: **{q['correct_answer']}**"
                )
        except Exception as e:
            logger.error(f"Error sending quiz to user {user_id}: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def run_bot():
    global user_db
    user_db = UserDB(DB_PATH)
    
    if not BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not found in .env file!")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Telegram bot is running...")
    application.run_polling()

if __name__ == "__main__":
    run_bot()
