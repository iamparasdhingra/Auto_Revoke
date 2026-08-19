import boto3
import requests
from botocore.exceptions import ClientError


def verify_aws_key(access_key, secret_key):
    """
    Try using the leaked key pair to make a harmless API call.
    If it succeeds, the key is live and dangerous.
    """
    try:
        client = boto3.client(
            "sts",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        identity = client.get_caller_identity()
        return True, identity
    except ClientError as e:
        print(f"Verification failed (key likely invalid): {e}")
        return False, None
    except Exception as e:
        print(f"Unexpected error during verification: {e}")
        return False, None


def verify_telegram_token(token):
    """
    Try using the leaked token to call the getMe endpoint.
    If it succeeds, the token is live.
    """
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data.get("result", {})
        return False, None
    except Exception as e:
        print(f"Unexpected error during Telegram verification: {e}")
        return False, None


def verify_openai_key(api_key):
    """
    Test an OpenAI API key against the models endpoint.
    If it succeeds (200), the key is live.
    """
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"Unexpected error during OpenAI verification: {e}")
        return False
