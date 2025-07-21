import subprocess

print("🔍 Scraping quiz...")
subprocess.run(["python", "Scrape.py"])

print("🚀 Triggering quiz...")
subprocess.run(["python", "triggerQuiz.py"])

print("✅ Daily quiz process complete.")
