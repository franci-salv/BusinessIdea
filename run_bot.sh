#!/bin/bash
# Start Telegram Puzzle Bot

cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "📝 Create .env from .env.example and add your TELEGRAM_BOT_TOKEN"
    exit 1
fi

echo "🚀 Starting Telegram Puzzle Bot..."
python main.py
