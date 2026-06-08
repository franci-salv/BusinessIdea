# Telegram Puzzle Bot - Deployment Guide

## 🚀 Deploy to Render.com (Recommended - Free)

Render is perfect for this bot. It's free, reliable, and has built-in cron scheduling.

### Step 1: Prepare Your Repository

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add Telegram puzzle bot with daily scheduler"
   git push origin main
   ```

2. **Create `.gitignore` (if not exists)**:
   ```
   .env
   data/users.db
   __pycache__/
   *.pyc
   env/
   ```

### Step 2: Create Render Service

1. Go to **https://render.com** and sign up (free)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Fill in:
   - **Name**: `puzzle-bot` (or any name)
   - **Environment**: `Python 3.11`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Free Plan**: ✅ Select this

5. Click **"Create Web Service"**

### Step 3: Add Environment Variables

1. In Render dashboard, go to **Settings** → **Environment**
2. Add:
   ```
   TELEGRAM_BOT_TOKEN=8725771063:AAH-X_YNfVEGFvmyGVqr2G5mOXxDcYZJ9OM
   ```
3. Click **"Save"**

### Step 4: Enable Persistent Disk (Optional)

To keep user database between restarts:

1. Go to **Disks** tab
2. Click **"Add Disk"**
3. Set size to **1 GB** (free option)
4. Mount path: `/app/data`
5. Click **"Add"**

6. Update `main_bot.py` to use persistent path:
   ```python
   DB_PATH = "/app/data/users.db"  # On Render
   ```

### Step 5: Test Deployment

1. Your bot will deploy automatically ✅
2. Check **Logs** tab to see if it started
3. Open Telegram, find your bot, /start
4. Click "Start Quiz" to test

### ✅ Done! Your bot now runs 24/7 on Render

---

## 📅 Why Your Cron Job Failed Before

Common cron issues you likely had:

1. **Timezone mismatch** - Cron runs in UTC, not your local time
   - **FIX**: Use `TZ=Europe/Amsterdam` or specify timezone in code
   
2. **Cron couldn't find Python path** - `python` not in PATH
   - **FIX**: Use `/usr/bin/python3` absolute path
   
3. **Script output not logged** - Errors happened silently
   - **FIX**: Add `>> /var/log/my_cron.log 2>&1` to cron
   
4. **Database locked** - SQLite file being read by another process
   - **FIX**: Use connection pooling (our new code does this)
   
5. **Environment variables not loaded** - Cron doesn't load .bashrc/.env
   - **FIX**: Source .env explicitly in cron script

### Example of GOOD cron job:
```bash
# Run daily at 10:00 AM Amsterdam time
0 10 * * * cd /home/user/puzzle-bot && /usr/bin/python3 core/Scrape.py && /usr/bin/python3 trigger_send.py >> /var/log/puzzle_cron.log 2>&1
```

---

## 🔄 Alternative: Deploy to Railway.app ($7/month)

1. Go to **https://railway.app**
2. Create account
3. Deploy from GitHub
4. Add `TELEGRAM_BOT_TOKEN` in Variables
5. That's it! Runs forever

---

## 📦 What Happens After Deploy

✅ Bot starts polling immediately
✅ Every day at 10:00 AM, all subscribed users get "Good morning!" message
✅ Users click "Start Quiz" to get questions
✅ Questions sent one-at-a-time with encouragement
✅ User progress tracked in database
✅ All automatic - you don't touch your laptop!

---

## 🆘 Debugging

If bot doesn't start:

1. Check **Logs** in Render dashboard
2. Look for `✅ Database initialized` and `🤖 Bot is polling`
3. Common errors:
   - `TELEGRAM_BOT_TOKEN not set` → Add to Environment Variables
   - `ModuleNotFoundError` → Check requirements.txt
   - `Connection timeout` → Check internet/Telegram API

---

## 💰 Cost Comparison

| Platform | Free Tier | Cost |
|----------|-----------|------|
| **Render** | Yes (generous) | Free |
| **Railway** | Limited | $5+/month |
| **Replit** | Yes | Free or paid |
| **PythonAnywhere** | Partial | $5+/month |

✅ **Render is best for this**
