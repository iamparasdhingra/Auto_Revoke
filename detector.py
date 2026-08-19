import re

# Regex patterns for common API key formats
PATTERNS = {
    "AWS Access Key": r"(?i)\b(AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
    # AWS Secret Key intentionally omitted — the 40-char base64 pattern is too generic and causes false positives
    "OpenAI API Key": r"(?i)\b(?:sk-[a-zA-Z0-9]{48}|sk-proj-[a-zA-Z0-9_-]{48})\b",
    "Stripe Test Key": r"sk_test_[0-9a-zA-Z]{24,}",
    "Stripe Live Key": r"sk_live_[0-9a-zA-Z]{24,}",
    "GitHub Token": r"(?i)\b(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}\b",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z-]{10,}",
    "Telegram Bot Token": r"[0-9]{8,10}:[a-zA-Z0-9_-]{35}",
    "Database URL (Postgres)": r"(?i)postgres(?:ql)?://[^:]+:[^@]+@[^/]+/[^ \n]+",
    "Database URL (MySQL)": r"(?i)mysql://[^:]+:[^@]+@[^/]+/[^ \n]+",
    "Database URL (MongoDB)": r"(?i)mongodb(?:\+srv)?://[^:]+:[^@]+@[^/]+(?:/[^ \n]+)?",
    "Database URL (Redis)": r"(?i)redis(?:s)?://(?:[^:]+:[^@]+@)?[^/]+(?:/[^ \n]+)?",
    "SSH Private Key": r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----[\s\S]+?-----END (?:RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----",
    "JWT Token": r"\b(ey[a-zA-Z0-9_-]{15,}\.ey[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,})\b",
    "Twilio API Key": r"SK[0-9a-fA-F]{32}",
    "Mailgun API Key": r"key-[0-9a-zA-Z]{32}",
    "SendGrid API Key": r"SG\.[0-9a-zA-Z_-]{22}\.[0-9a-zA-Z_-]{43}",
    "Google API Key": r"AIza[0-9A-Za-z_-]{35}",
    "Firebase URL": r"[a-z0-9.-]+\.firebaseio\.com",
    "Stripe Webhook Secret": r"whsec_[0-9a-zA-Z]{24,}",
    "Discord Bot Token": r"[MNO][a-zA-Z0-9_-]{23,27}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27}",
    "Discord Webhook": r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[a-zA-Z0-9_-]+",
    "Generic API Key / Secret": r"(?i)(?:api_key|apikey|api_secret|apisecret|secret_key|secretkey|access_token|accesstoken|auth_token|authtoken|client_secret|clientsecret|password|pwd)[\s:=]+['\"]([a-zA-Z0-9\-_+/=]{16,})['\"]"
}


def find_secrets(text):
    """Scan a block of text and return any detected secrets."""
    found = []
    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            # If the pattern has a specific capturing group for the key value (e.g., Generic Secret), extract group 1; otherwise full match
            if label == "Generic API Key / Secret" and match.lastindex:
                val = match.group(1)
            else:
                val = match.group(0)
            
            # Avoid duplicate detections
            if not any(f["value"] == val for f in found):
                found.append({"type": label, "value": val})
    return found


if __name__ == "__main__":
    # Quick manual test
    sample_code = '''
    aws_key = "AKIAABCD1234EFGH5678"
    stripe_key = "sk_test_51H8xK2eZvKYlo2C0nJ8abcdefghijklmno"
    github_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz01"
    '''
    results = find_secrets(sample_code)
    print("Detected secrets:")
    for r in results:
        print(f"  - {r['type']}: {r['value']}")