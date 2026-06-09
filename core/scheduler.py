#!/usr/bin/env python3
"""
Scheduler for daily quiz delivery at 10:00 AM
Scrapes quiz at 9:55 AM, sends at 10:00 AM
"""

import os
import sqlite3
import logging
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")
SCRAPER_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "Scrape.py")

logger = logging.getLogger(__name__)

def scrape_daily_quiz():
    """Run the scraper to fetch today's quiz"""
    logger.info("📥 [SCHEDULER] Scraping daily quiz at 9:55 AM...")
    try:
        result = subprocess.run(
            ["python", SCRAPER_PATH],
            capture_output=True,
            timeout=30,
            cwd=os.path.dirname(SCRAPER_PATH)
        )
        if result.returncode == 0:
            logger.info("✅ [SCHEDULER] Quiz scraped successfully!")
        else:
            logger.error(f"[SCHEDULER] Scraper error: {result.stderr.decode()}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error running scraper: {e}")

def broadcast_daily_quiz():
    """Send daily quiz announcement + button to all subscribed users at 10:00 AM"""
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
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": user_id,
                "text": "🎉 Good morning! Today's puzzle is ready!\n\n📚 Press the button below to start:",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🚀 Start Quiz Now", "callback_data": "start_quiz"}]]
                }
            }, timeout=10)
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"[SCHEDULER] Error sending to user {user_id}: {e}")
    
    logger.info(f"✅ [SCHEDULER] Sent daily quiz to {len(users)} users")

def start_scheduler():
    """Start background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Scrape at 9:55 AM
    scheduler.add_job(
        scrape_daily_quiz,
        CronTrigger(hour=9, minute=55),
        id='scrape_quiz_955am',
        name='Scrape Quiz at 9:55 AM',
        replace_existing=True
    )
    
    # Send quiz at 10:00 AM
    scheduler.add_job(
        broadcast_daily_quiz,
        CronTrigger(hour=10, minute=0),
        id='daily_quiz_10am',
        name='Daily Quiz at 10:00 AM',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("📅 [SCHEDULER] Started - Daily scrape at 9:55 AM, send at 10:00 AM")
    
    return scheduler
