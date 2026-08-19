import os
import requests
from dotenv import load_dotenv

load_dotenv()


def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("No Slack webhook configured — printing instead:")
        print(message)
        return

    payload = {"text": message}
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")


if __name__ == "__main__":
    send_slack_alert("🚨 Test message from Auto-Revoke Bot!")
