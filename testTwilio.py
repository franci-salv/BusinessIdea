import subprocess
import requests
import time
from twilio.rest import Client
import pyperclip

# === CONFIG ===
NGROK_PATH = r"C:\path\to\ngrok.exe"  # ← YOUR path
TWILIO_SID = "AC4824518f33e5c5947ea93c97a9eaa74f"  # ← YOUR Twilio SID
TWILIO_TOKEN = "405b98b9d0f64ea003841c70f3b716ec"  # ← YOUR Twilio Auth Token
PHONE_SID = ""  # ← Your sandbox phone SID

def start_ngrok():
    return subprocess.Popen([NGROK_PATH, "http", "5000"])

def get_ngrok_url():
    time.sleep(2)
    tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()
    for tunnel in tunnels["tunnels"]:
        if tunnel["proto"] == "https":
            return tunnel["public_url"]
    return None

def update_twilio_webhook(account_sid, auth_token, phone_number_sid, new_url):
    client = Client(account_sid, auth_token)
    client.incoming_phone_numbers(phone_number_sid).update(
        sms_url=new_url
    )
    print(f"✅ Twilio webhook updated to: {new_url}")

# === RUN ===
print("🚀 Starting ngrok...")
ngrok_process = start_ngrok()

url = get_ngrok_url()
if url:
    print("🌍 ngrok URL:", url)
    update_twilio_webhook(TWILIO_SID, TWILIO_TOKEN, PHONE_SID, f"{url}/whatsapp")
else:
    print("❌ Couldn't get ngrok URL")

pyperclip.copy(f"{url}/whatsapp")
print("📋 ngrok URL copied to clipboard!")
