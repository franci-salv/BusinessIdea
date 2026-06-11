#!/usr/bin/env python3
"""
Main entry point with bot + daily scheduler
Runs bot in main thread, scheduler in background
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging ONCE here - all modules share this config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env file!")
    sys.exit(1)

def main():
    """Start bot with scheduler"""
    logger.info("🚀 Starting Telegram Puzzle Bot with Daily Scheduler")

    # Start scheduler in background thread
    logger.info("⏰ Starting scheduler...")
    from core.scheduler import start_scheduler
    scheduler = start_scheduler()

    logger.info("🤖 Starting bot polling...")
    logger.info("=" * 50)
    logger.info("✅ Bot is LIVE")
    logger.info("📅 Daily puzzles will be sent at 10:00 AM")
    logger.info("=" * 50)

    # Import and run bot
    from main_bot import main as bot_main

    try:
        bot_main()
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        scheduler.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    main()
