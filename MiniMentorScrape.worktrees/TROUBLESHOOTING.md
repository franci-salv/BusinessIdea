# Quick Troubleshooting Guide

## If Leaderboard Still Doesn't Work

### Check 1: Monitor the Bot Logs
Run the bot and watch for these error patterns:

```
✅ Good signs:
- "Leaderboard query returned 3 users for date 2026-06-09"
- User sees leaderboard message immediately

❌ Bad signs:
- "Telegram API error: Bad Request: message text is empty"
- "Database lock" errors
- "Error sending message" with no API response
```

### Check 2: Verify Database isn't Corrupted
If you're still seeing issues, the SQLite database might be corrupted:

```bash
# Run a database check
sqlite3 data/users.db "PRAGMA integrity_check;"

# If corrupted, backup and reset
cp data/users.db data/users.db.backup
rm data/users.db  # Bot will recreate it
```

### Check 3: Clear Message Queue
If the bot is stuck processing old messages, restart it:

1. Stop the bot (`Ctrl+C`)
2. Wait 30 seconds
3. Start it again

This clears the `processed_polls` and `poll_question_map` cache.

### Check 4: Test with a Single User
Have one user:
1. Click "Start Quiz"
2. Complete one question
3. Click "My Stats" (should work)
4. Click "Today's Leaderboard" (should work)

If it works with 1 user but fails with 3, it's a concurrency issue - the database timeout fix should help.

## Common Issues & Fixes

| Issue | Cause | Solution |
|-------|-------|----------|
| Leaderboard loads but no message | Message exceeds 4096 chars | Now auto-truncated |
| Hangs on leaderboard click | Database lock from concurrent access | Added 5s timeout |
| API error about empty message | send_message() failure not caught | Now logged explicitly |
| "No scores yet" when users completed quiz | Database query timing out | Added timeout parameter |
| User not appearing on leaderboard | quiz_date mismatch or incorrect INSERT | Check timestamps |

## Testing the Fix

### Scenario 1: Multiple Users Simultaneously
```python
# Have 3+ users click leaderboard at same time
# Expected: All get message within 2 seconds
# Should see in logs: "Leaderboard query returned 3 users for date..."
```

### Scenario 2: Large Leaderboard
```python
# Simulate 50 users with different scores
# Expected: Message shows top 3, truncates if needed
# Should see in logs: "Leaderboard message too long (4250 chars), truncating"
```

### Scenario 3: Stats View
```python
# Click "My Stats" right after completing quiz
# Expected: Shows correct count and percentage
# Should see no database lock errors
```

## Enabling Debug Logging

To see more detailed logs, change logging level in `main_bot.py` line 19:

```python
# FROM:
level=logging.INFO

# TO:
level=logging.DEBUG
```

This will show all database operations and API calls.
