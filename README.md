# 🎯 Telegram Puzzle Bot

A free, open-source daily puzzle bot for Telegram! Get a new quiz every day with interactive polls.

## ✨ Features

- ✅ **Free to operate** (no API costs, unlike Twilio)
- ✅ **Interactive polls** - Users vote on multiple choice questions
- ✅ **Automatic daily delivery** - Sends puzzles at scheduled time
- ✅ **User management** - /start to subscribe, /stop to unsubscribe
- ✅ **Answer validation** - Telegram shows if answer was correct in poll
- ✅ **SQLite persistence** - Tracks subscribed users
- ✅ **Easy setup** - Just one token needed

## 🚀 Quick Start

### Step 1: Get Your Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Click `/start` then `/newbot`
3. Name your bot (e.g., "Quiz Master Bot")
4. Choose a username ending with `_bot` (e.g., `quiz_master_bot`)
5. **Copy the token** you receive (e.g., `123456:ABC-DEF1234...`)

### Step 2: Setup Environment

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your token:
   ```
   TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
   SCHEDULE_HOUR=8
   SCHEDULE_MINUTE=0
   ```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Bot

**On Windows:**
```bash
run_bot.bat
```

**On Mac/Linux:**
```bash
bash run_bot.sh
```

Or directly:
```bash
python core/telegram_bot.py
```

### Step 5: Start Using It

1. Find your bot on Telegram
2. Click `/start` to subscribe
3. Click "Get Today's Quiz" to test
4. Bot will send daily puzzles at your scheduled time (default: 8:00 AM)

## 🎮 User Commands

| Command | Description |
|---------|-------------|
| `/start` | Subscribe to daily puzzles |
| `/stop` | Unsubscribe from daily puzzles |
| Inline buttons | Get quiz, manage preferences |

## ⚙️ Configuration

Edit `.env` to customize:

```
TELEGRAM_BOT_TOKEN=your_token_here
SCHEDULE_HOUR=8          # 24-hour format (0-23)
SCHEDULE_MINUTE=0        # 0-59
TEST_MODE=0              # Set to 1 to skip broadcasting
```

## 📊 Data

- **Users**: Stored in `data/users.db` (SQLite)
- **Quizzes**: Loaded from `data/daily_quiz.json`
- **Responses**: Tracked per user in `users.db`

## 🔄 How It Works

1. **Scraper** (`Scrape.py`) - Fetches daily quiz from quizoftheday.co.uk
2. **Bot** (`telegram_bot.py`) - Loads quiz and sends Telegram polls
3. **Scheduler** (`scheduler.py`) - Runs daily delivery at set time
4. **Database** (`users.db`) - Tracks subscriptions and answers

## 🌐 Deploy to Cloud (Optional)

For 24/7 running (currently runs locally):
- **Replit**: Free hosting, built-in scheduler
- **Railway.app**: $5/month minimal
- **Render**: $7/month
- **Digital Ocean Droplet**: $6/month

## 📝 Roadmap

- [ ] Leaderboards (top scorers)
- [ ] Difficulty levels
- [ ] Category selection
- [ ] Weekly summaries
- [ ] Share to groups

## 📜 License

MIT - Free to use and modify

---

**Questions?** Check the code in `core/telegram_bot.py` - it's well commented!
