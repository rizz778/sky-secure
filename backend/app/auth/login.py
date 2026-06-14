import base64
import hashlib
import hmac
import os
import secrets
import time
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

ZOHO_ACCOUNTS_BASE_URL = os.getenv("ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.com")
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")
DEFAULT_ZOHO_SCOPES = ",".join(
    [
        "ZohoProjects.portals.READ",
        "ZohoProjects.projects.READ",
        "ZohoProjects.tasks.READ",
    ]
)
ZOHO_SCOPES = os.getenv("ZOHO_SCOPES", DEFAULT_ZOHO_SCOPES)
STATE_TTL_SECONDS = 600


def missing_zoho_settings() -> list[str]:
    required_settings = {
        "ZOHO_CLIENT_ID": ZOHO_CLIENT_ID,
        "ZOHO_CLIENT_SECRET": ZOHO_CLIENT_SECRET,
        "ZOHO_REDIRECT_URI": ZOHO_REDIRECT_URI,
    }
    return [name for name, value in required_settings.items() if not value]


def build_authorization_url(state: str) -> str:
    query = urlencode(
        {
            "scope": ZOHO_SCOPES,
            "client_id": ZOHO_CLIENT_ID,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": ZOHO_REDIRECT_URI,
            "state": state,
            "prompt": "consent",
        }
    )
    return f"{ZOHO_ACCOUNTS_BASE_URL}/oauth/v2/auth?{query}"


def create_oauth_state() -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    message = f"{issued_at}.{nonce}"
    signature = _sign_state(message)
    return f"{message}.{signature}"


def verify_oauth_state(state: str) -> bool:
    try:
        issued_at, nonce, signature = state.split(".", 2)
        issued_at_seconds = int(issued_at)
    except (ValueError, AttributeError):
        return False

    if time.time() - issued_at_seconds > STATE_TTL_SECONDS:
        return False

    expected_signature = _sign_state(f"{issued_at}.{nonce}")
    return hmac.compare_digest(signature, expected_signature)


def token_url(accounts_base_url: str | None = None) -> str:
    base_url = accounts_base_url or ZOHO_ACCOUNTS_BASE_URL
    return f"{base_url}/oauth/v2/token"


def _sign_state(message: str) -> str:
    secret = ZOHO_CLIENT_SECRET or ""
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")
