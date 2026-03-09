import os
import json
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

# ====== CONFIG ======

KOMMO_SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN")
KOMMO_CLIENT_ID = os.getenv("KOMMO_CLIENT_ID")
KOMMO_CLIENT_SECRET = os.getenv("KOMMO_CLIENT_SECRET")

KOMMO_OAUTH_URL = f"https://{KOMMO_SUBDOMAIN}.kommo.com/oauth2/access_token"

TOKENS_FILE = "data/tokens.json"


# ====== PERSISTENCIA ======

def ensure_tokens_file():
    """Crea el archivo de tokens si no existe."""
    if not os.path.exists(TOKENS_FILE):
        os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
        with open(TOKENS_FILE, "w") as f:
            json.dump({
                "access_token": "",
                "refresh_token": os.getenv("KOMMO_REFRESH_TOKEN"),  # solo inicial
                "expires_at": 0
            }, f)


def load_tokens():
    ensure_tokens_file()
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)


def save_tokens(access_token, refresh_token, expires_in):
    expires_at = time.time() + expires_in - 60  # margen de seguridad

    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at
    }

    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=4)


def token_is_valid(tokens):
    return time.time() < tokens["expires_at"]


# ====== REFRESH ======

async def refresh_access_token():
    tokens = load_tokens()

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": KOMMO_CLIENT_ID,
        "client_secret": KOMMO_CLIENT_SECRET,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(KOMMO_OAUTH_URL, json=payload)

    if response.status_code != 200:
        print("❌ Error renovando token:", response.text)
        raise Exception("No se pudo renovar el token")

    data = response.json()

    save_tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"]
    )

    print("✅ Token renovado correctamente")


# ====== TOKEN PRINCIPAL ======

async def get_access_token():
    tokens = load_tokens()

    if token_is_valid(tokens) and tokens["access_token"]:
        return tokens["access_token"]

    print("🔄 Token expirado o inexistente, renovando...")
    await refresh_access_token()

    tokens = load_tokens()
    return tokens["access_token"]