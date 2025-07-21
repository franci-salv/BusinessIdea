import subprocess
import requests
import time
import pyperclip

# === CONFIG ===
NGROK_PATH = r"ngrok.exe"  # ← YOUR ngrok path

def start_ngrok():
    return subprocess.Popen([NGROK_PATH, "http", "5000"])

def get_ngrok_url():
    time.sleep(2)
    tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()
    for tunnel in tunnels["tunnels"]:
        if tunnel["proto"] == "https":
            return tunnel["public_url"]
    return None

# === RUN ===
print("🚀 Starting ngrok...")
ngrok_process = start_ngrok()

url = get_ngrok_url()
if url:
    full_url = f"{url}/whatsapp"
    pyperclip.copy(full_url)
    print("🌍 ngrok URL:", full_url)
    print("📋 Copied to clipboard — paste into Twilio Sandbox webhook field:")
    print("🔗 https://www.twilio.com/console/sms/whatsapp/sandbox")
else:
    print("❌ Couldn't get ngrok URL")
