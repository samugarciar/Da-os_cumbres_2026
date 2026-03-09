import httpx
import os
from dotenv import load_dotenv

load_dotenv()

SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN")
AUTH_CODE = os.getenv("KOMMO_AUTHORIZATION_CODE")

CLIENT_ID = os.getenv("KOMMO_CLEINT_ID")
CLIENT_SECRET = os.getenv("KOMMO_CLIENT_SECRET")

url = f"https://{SUBDOMAIN}.kommo.com/oauth2/access_token"

payload = {
    "grant_type": "authorization_code",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": AUTH_CODE,
    "redirect_uri": "https://example.com"
}

response = httpx.post(url, json=payload)

print("Status:", response.status_code)
print("Respuesta:", response.json())
