import os
import time
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request
import requests

# Always load .env relative to this file's directory, not the CWD
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from detector import find_secrets
from verifier import verify_aws_key, verify_telegram_token, verify_openai_key
from revoker import revoke_aws_key
from notifier import send_slack_alert
from github_reverter import delete_github_file, redact_github_file, restore_github_file
from telegram_notifier import send_telegram_alert, register_telegram_webhook, undo_store

app = Flask(__name__)

ADMIN_ACCESS_KEY = os.getenv("ADMIN_AWS_ACCESS_KEY")
ADMIN_SECRET_KEY = os.getenv("ADMIN_AWS_SECRET_KEY")
DEMO_LEAKED_SECRET_KEY = os.getenv("DEMO_LEAKED_SECRET_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
NGROK_URL = os.getenv("NGROK_URL")  # e.g. https://1234abcd.ngrok-free.app/


@app.route("/webhook", methods=["POST"])
def github_webhook():
    payload = request.json
    print("\n📥 Webhook received!")
    print(f"   Raw payload keys: {list(payload.keys()) if payload else 'EMPTY'}")

    if not payload or "repository" not in payload:
        print("   ⚠️  No 'repository' key in payload — ignoring.")
        return "No repo info", 400

    repo_name = payload["repository"]["full_name"]
    commits = payload.get("commits", [])
    print(f"   Repo: {repo_name}")
    print(f"   Commits in payload: {len(commits)}")

    if not commits:
        event = request.headers.get("X-GitHub-Event", "unknown")
        print(f"   ℹ️  No commits in payload (event type: '{event}'). Nothing to scan.")
        return "OK", 200

    for commit in commits:
        commit_id = commit["id"]
        added = commit.get("added", [])
        modified = commit.get("modified", [])
        changed_files = added + modified
        print(f"   Commit {commit_id[:7]}: +{len(added)} added, ~{len(modified)} modified → {changed_files}")

        if not changed_files:
            print("   ⚠️  No added/modified files in this commit — skipping.")
            continue

        for filename in changed_files:
            raw_url = f"https://raw.githubusercontent.com/{repo_name}/{commit_id}/{filename}"
            print(f"   Fetching: {raw_url}")
            file_content = None
            for attempt in range(1, 4):  # 3 attempts
                try:
                    response = requests.get(raw_url, timeout=15)
                    print(f"   HTTP {response.status_code} for {filename} (attempt {attempt})")
                    file_content = response.text
                    break
                except Exception as e:
                    print(f"   ⚠️  Attempt {attempt}/3 failed for {filename}: {e}")
                    if attempt < 3:
                        time.sleep(2)
            if file_content is None:
                print(f"   ❌ All attempts failed for {filename} — skipping.")
                continue

            secrets_found = find_secrets(file_content)
            print(f"   Secrets found in {filename}: {len(secrets_found)}")

            if not secrets_found:
                print(f"   ✅ No secrets detected in {filename}.")

            for secret in secrets_found:
                print(f"   🔍 Found: {secret['type']} -> {secret['value'][:8]}...")
                handle_secret(secret, repo_name, commit_id, filename)

    return "OK", 200


@app.route("/revert", methods=["GET"])
def revert_commit():
    repo = request.args.get("repo")
    path = request.args.get("path")

    if not repo or not path:
        return "Missing repo or path parameters", 400

    print(f"🔄 Revert requested for {path} in {repo}...")
    success, message = delete_github_file(repo, path, GITHUB_TOKEN)

    if success:
        send_slack_alert(f"✅ *SUCCESS:* Successfully deleted `{path}` from `{repo}` to fix the leak!")
        send_telegram_alert(f"✅ <b>SUCCESS:</b> Deleted <code>{path}</code> from <code>{repo}</code>!")
        return f"<h1>Success!</h1><p>{message}</p>", 200
    else:
        send_slack_alert(f"❌ *FAILED:* Could not delete `{path}` from `{repo}`. Error: {message}")
        return f"<h1>Failed</h1><p>{message}</p>", 500


@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    """Handles button click callbacks from Telegram inline keyboards."""
    data = request.json
    if not data:
        return "OK", 200

    callback_query = data.get("callback_query")
    if not callback_query:
        return "OK", 200

    callback_id = callback_query["id"]
    callback_data = callback_query.get("data", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    # Answer the callback to remove the loading spinner on Telegram
    answer_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    requests.post(answer_url, json={"callback_query_id": callback_id}, timeout=5)

    if callback_data == "keep":
        send_telegram_alert("✅ Understood! The redaction has been kept. The secret has been replaced safely in your repository.")
        return "OK", 200

    if callback_data.startswith("undo:"):
        undo_key = callback_data[5:]  # strip "undo:"
        stored = undo_store.get(undo_key)

        if not stored:
            send_telegram_alert("⚠️ Could not find the undo data. It may have expired or the server was restarted.")
            return "OK", 200

        repo, file_path, original_content = stored
        print(f"↩️ Undo requested for {file_path} in {repo}")
        success, message = restore_github_file(repo, file_path, original_content, GITHUB_TOKEN)

        if success:
            del undo_store[undo_key]
            send_telegram_alert(f"↩️ <b>Undo Successful!</b> <code>{file_path}</code> has been restored to its original content in <code>{repo}</code>.\n\n⚠️ <b>WARNING:</b> The original (possibly leaked) secret is now back in your code! Make sure you actually intended this.")
        else:
            send_telegram_alert(f"❌ <b>Undo Failed!</b> Could not restore <code>{file_path}</code>. Error: {message}")

    return "OK", 200


def handle_secret(secret, repo_name, commit_id, filename):
    secret_type = secret["type"]
    secret_val = secret["value"]

    print(f"🔒 Processing {secret_type} in {repo_name}/{filename}...")

    # 1. First, automatically redact the secret in the GitHub repository
    success, commit_sha, original_content, message = redact_github_file(
        repo_name, filename, secret_val, GITHUB_TOKEN
    )

    extra_info = ""
    # 2. Check if specific revocation / verification steps apply
    if secret_type == "AWS Access Key":
        is_live, identity = verify_aws_key(secret_val, DEMO_LEAKED_SECRET_KEY)
        if is_live:
            print("✅ AWS Key confirmed LIVE — revoking now via IAM...")
            revoked = revoke_aws_key(secret_val, ADMIN_ACCESS_KEY, ADMIN_SECRET_KEY)
            extra_info = "\n⚡ <b>AWS IAM Status:</b> Automatically deactivated!" if revoked else "\n⚠️ <b>AWS IAM Status:</b> Revocation failed, please revoke manually!"
        else:
            extra_info = "\nℹ️ <i>AWS Key was checked and is not active/live.</i>"

    elif secret_type == "Telegram Bot Token":
        is_live, bot_info = verify_telegram_token(secret_val)
        if is_live:
            bot_username = bot_info.get("username", "Unknown Bot")
            extra_info = f"\n⚠️ <b>ACTION REQUIRED:</b> Live Bot Token for <code>@{bot_username}</code>! Revoke via @BotFather."

    # 3. Send Notification via Telegram
    if success:
        tg_msg = (
            f"🚨 <b>Leaked {secret_type} Detected!</b>\n"
            f"📁 <b>Repo:</b> <code>{repo_name}</code>\n"
            f"📄 <b>File:</b> <code>{filename}</code>\n"
            f"🔢 <b>Commit:</b> <code>{commit_id[:7]}</code>\n\n"
            f"🛡️ <b>Action Taken:</b> The secret was automatically replaced with <code>ENTER_YOUR_API_KEY_HERE</code> on GitHub to prevent misuse."
            f"{extra_info}\n\n"
            f"❓ <i>Do you want to revert this change and restore your original file?</i>"
        )
        send_telegram_alert(
            tg_msg,
            repo=repo_name,
            file_path=filename,
            original_content=original_content
        )
        send_slack_alert(f"🚨 Auto-redacted {secret_type} in {repo_name}/{filename}!")
    else:
        print(f"❌ Auto-redaction failed: {message}")
        tg_msg = (
            f"🚨 <b>Leaked {secret_type} Detected!</b>\n"
            f"📁 <b>Repo:</b> <code>{repo_name}</code> | 📄 <code>{filename}</code>\n\n"
            f"⚠️ <b>Auto-redaction failed:</b> {message}\n"
            f"Please verify your <code>GITHUB_TOKEN</code> in <code>.env</code> has repo write permissions!"
            f"{extra_info}"
        )
        send_telegram_alert(tg_msg)
        send_slack_alert(f"⚠️ Leaked {secret_type} in {repo_name}/{filename} but auto-redact failed: {message}")


if __name__ == "__main__":
    # Auto-register Telegram webhook on startup if NGROK_URL is set
    if NGROK_URL:
        register_telegram_webhook(NGROK_URL)
    app.run(port=5000, debug=True)