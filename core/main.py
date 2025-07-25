import subprocess
import os

# 🔧 Get current script's absolute directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("🔍 Scraping quiz...")
scrape_path = os.path.join(BASE_DIR, "Scrape.py")
subprocess.run(["python", scrape_path])

print("🚀 Triggering quiz...")
trigger_path = os.path.join(BASE_DIR, "triggerQuiz.py")
subprocess.run(["python", trigger_path])

print("✅ Daily quiz process complete.")
