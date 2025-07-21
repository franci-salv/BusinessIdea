import sys
import os
os.environ["TEST_MODE"] = "1"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.triggerQuiz import send_quiz_message

send_quiz_message("+393773753088", "Test message from Twilio to WhatsApp",   refresh_url ="https://8433d29d882d.ngrok-free.app/refresh_quiz")
