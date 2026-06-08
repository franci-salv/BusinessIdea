# 🚀 Deploy to Fly.io - Complete Guide

## Why Fly.io?

✅ **Generous free tier** - Includes 3 shared VMs + persistent storage  
✅ **Always on** - No sleep/wake cycles like other platforms  
✅ **Persistent storage** - Database saved between restarts  
✅ **Global deployment** - Pick your region (Amsterdam = `ams`)  
✅ **Simple cron/scheduler** - APScheduler runs reliably  
✅ **Great for this use case** - Designed for long-running apps  

---

## 📋 Prerequisites

1. **GitHub account** (repo with your bot code)
2. **Fly.io account** (free at https://fly.io)
3. **Fly CLI** installed on your laptop

---

## Step 1: Install Fly CLI

### Windows (PowerShell):
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### Mac/Linux:
```bash
curl -L https://fly.io/install.sh | sh
```

**Verify installation:**
```bash
flyctl version
```

---

## Step 2: Push to GitHub

Make sure your code is on GitHub:

```bash
git add .
git commit -m "Deploy Telegram bot to Fly.io"
git push origin main
```

**Files we added:**
- ✅ `Dockerfile` - Container setup
- ✅ `fly.toml` - Fly.io config
- ✅ `main.py` - Bot with scheduler
- ✅ `main_bot.py` - Bot logic
- ✅ `core/scheduler.py` - Daily trigger

---

## Step 3: Create Fly App

### Login to Fly:
```bash
flyctl auth login
```
(Opens browser, sign in with your email)

### Create app:
```bash
cd path/to/your/project
flyctl launch
```

This will ask:

```
? App Name (leave blank to use 'puzzle-bot'):
telegram-puzzle-bot

? Select region:
Amsterdam (ams)  ← Choose this

? Would you like to set up a Postgresql database now?
No

? Would you like to set up an upstash redis database now?
No

? Would you like to set up Upstash Redis now?
No
```

**Result:** Creates `fly.toml` (we already have it) ✅

---

## Step 4: Create Persistent Storage

Your bot needs to save user data. Create a volume:

```bash
flyctl volumes create puzzle_data --size 1 --region ams
```

Output:
```
        ID: vol_abc123def456
      Name: puzzle_data
       App: telegram-puzzle-bot
    Region: ams
      Size: 1 GB
   Created: 2025-06-08T21:30:00Z
```

✅ Done! Volume is ready.

---

## Step 5: Set Secret (Bot Token)

Your bot token should be private. Add it as a secret:

```bash
flyctl secrets set TELEGRAM_BOT_TOKEN=8725771063:AAH-X_YNfVEGFvmyGVqr2G5mOXxDcYZJ9OM
```

Verify:
```bash
flyctl secrets list
```

---

## Step 6: Deploy!

```bash
flyctl deploy
```

**What happens:**
1. Builds Docker image
2. Uploads to Fly.io
3. Starts your app
4. Mounts persistent storage
5. Bot starts polling ✅

**Watch logs:**
```bash
flyctl logs
```

You should see:
```
🚀 Starting Telegram Puzzle Bot with Daily Scheduler
📅 [SCHEDULER] Started - Daily quiz scheduled for 10:00 AM
🤖 Bot is polling... Press Ctrl+C to stop
```

---

## Step 7: Test Your Bot

1. Open Telegram
2. Find your bot
3. `/start` it
4. Click "Start Quiz"
5. Answer a question to test

✅ If it works, you're done!

---

## 🔄 Update Bot (After Making Changes)

Every time you update code:

```bash
git add .
git commit -m "Update bot features"
git push origin main
flyctl deploy
```

---

## 📊 Monitor Your App

### View logs:
```bash
flyctl logs -n 50
```

### Check status:
```bash
flyctl status
```

### View metrics:
```bash
flyctl metrics
```

### SSH into machine (if needed):
```bash
flyctl ssh console
```

---

## 🆘 Troubleshooting

### "Bot not receiving updates"
```bash
flyctl logs | grep "ERROR"
```
Common fixes:
- Check TELEGRAM_BOT_TOKEN is set: `flyctl secrets list`
- Check internet: `flyctl ssh console` → `curl https://api.telegram.org/botXXX/getMe`

### "Database not persisting"
Make sure volume is mounted:
```bash
flyctl volumes list
```

If missing:
```bash
flyctl volumes create puzzle_data --size 1 --region ams
```

### "Scheduler not running at 10:00 AM"
Check timezone in `fly.toml`:
```
[env]
  TZ = "Europe/Amsterdam"  # Change to your timezone
```

Then redeploy:
```bash
flyctl deploy
```

### App keeps restarting
Check logs for errors:
```bash
flyctl logs --follow
```

Most common: Missing dependencies
- Update `requirements.txt` if needed
- Run `pip freeze > requirements.txt` locally
- Redeploy: `flyctl deploy`

---

## 💰 Free Tier Limits

| Resource | Free Allowance |
|----------|---|
| VMs | 3 shared @ 0.25CPU |
| Memory | 3GB total |
| Storage | 3 x 1GB volumes |
| Data transfer | 160GB/month |
| Cost | **$0** |

✅ More than enough for your bot!

If you hit limits later, add a credit card. Fly.io is pay-as-you-go ($0 if you stay under free tier).

---

## 🎉 You're Done!

Your bot is now:
- ✅ Running 24/7 on Fly.io
- ✅ Sending puzzles daily at 10:00 AM
- ✅ Persisting user data
- ✅ Automatically restarting if it crashes
- ✅ Completely free

**No laptop required!** 🎊

---

## Quick Reference Commands

```bash
# Deploy
flyctl deploy

# View logs
flyctl logs --follow

# Set/update secret
flyctl secrets set TELEGRAM_BOT_TOKEN=xxx

# Check status
flyctl status

# SSH in
flyctl ssh console

# Scale up (if needed later)
flyctl scale vm shared-cpu-1x
```

---

## Next Steps

1. Run `flyctl launch` in your project folder
2. Run `flyctl volumes create puzzle_data --size 1 --region ams`
3. Run `flyctl secrets set TELEGRAM_BOT_TOKEN=your_token`
4. Run `flyctl deploy`
5. Check `flyctl logs`
6. Test your bot! 🎉
