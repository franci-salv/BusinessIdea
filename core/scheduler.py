#!/usr/bin/env python3
"""
Scheduler for daily quiz delivery at 10:00 AM
Runs with the main bot in separate thread
"""

import os
import sqlite3
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")

logger = logging.getLogger(__name__)

def broadcast_daily_quiz():
    """Send 'quiz time' message to all subscribed users"""
    logger.info("📢 [SCHEDULER] Broadcasting daily quiz at 10:00 AM...")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT user_id FROM users WHERE subscribed = 1")
            users = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"[SCHEDULER] Error fetching users: {e}")
        return
    
    logger.info(f"[SCHEDULER] Found {len(users)} subscribed users")
    
    for user_id in users:
        try:
            # Send wake-up message
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": user_id,
                "text": "🎉 Good morning! Today's puzzle is ready! 📚",
            }, timeout=10)
            
            time.sleep(0.2)
            
            # Send quiz button
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": user_id,
                "text": "Ready?",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "📚 Start Quiz", "callback_data": "start_quiz"}]]
                }
            }, timeout=10)
            
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"[SCHEDULER] Error sending to user {user_id}: {e}")
    
    logger.info(f"✅ [SCHEDULER] Sent daily quiz to {len(users)} users")

def start_scheduler():
    """Start background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule daily at 10:00 AM (adjust timezone as needed)
    scheduler.add_job(
        broadcast_daily_quiz,
        CronTrigger(hour=10, minute=0),
        id='daily_quiz_10am',
        name='Daily Quiz at 10:00 AM',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("📅 [SCHEDULER] Started - Daily quiz scheduled for 10:00 AM")
    
    return scheduler
