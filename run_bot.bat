@echo off
setlocal enabledelayexpand

if not exist ".env" (
    echo.
    echo ❌ .env file not found!
    echo 📝 Create .env from .env.example and add your TELEGRAM_BOT_TOKEN
    echo.
    pause
    exit /b 1
)

echo 🚀 Starting Telegram Puzzle Bot...
python main.py
pause
