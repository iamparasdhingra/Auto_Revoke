import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# In-memory store for pending undo actions: { callback_data_key: (repo, path, original_content) }
# In production, use a database or Redis instead.
undo_store = {}


def _html(text: str) -> str:
    """Escape special HTML characters so Telegram's HTML parser doesn't choke."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_telegram_alert(message, repo=None, file_path=None, original_content=None):
    """
    Sends a Telegram message. If repo/file_path/original_content are provided,
    attaches an [Undo Redaction] inline keyboard button.
    NOTE: message must use HTML tags (<b>, <code>, etc.) not Markdown.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("No Telegram bot configured — printing instead:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"   # HTML is safer than Markdown for paths/keys with special chars
    }

    # Attach an Undo button if we have the context to undo
    if repo and file_path and original_content is not None:
        # Store original content keyed by a simple unique key
        undo_key = f"{repo}|{file_path}"
        undo_store[undo_key] = (repo, file_path, original_content)

        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[
                {
                    "text": "↩️ Revert this change (Restore)",
                    "callback_data": f"undo:{undo_key}"
                },
                {
                    "text": "✅ Keep Safe (Don't Revert)",
                    "callback_data": "keep"
                }
            ]]
        })

    try:
        resp = requests.post(url, json=payload, timeout=5)
        result = resp.json()
        if not result.get("ok"):
            print(f"⚠️ Telegram sendMessage FAILED: {result}")
        else:
            print(f"✅ Telegram message sent (msg_id={result['result']['message_id']})")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")


def register_telegram_webhook(ngrok_url):
    """
    Registers our Flask server's /telegram_webhook endpoint with Telegram
    so we receive inline button click events.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    webhook_url = f"{ngrok_url.rstrip('/')}/telegram_webhook"
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    try:
        res = requests.post(url, json={"url": webhook_url}, timeout=5)
        print(f"✅ Telegram webhook registered: {res.json().get('description')}")
    except Exception as e:
        print(f"⚠️ Failed to register Telegram webhook: {e}")


if __name__ == "__main__":
    send_telegram_alert("🚨 Test message from Auto-Revoke Bot!")
