import httpx
import os
from services.kommo_auth import get_access_token, refresh_access_token

KOMMO_SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN")
KOMMO_BASE_URL = f"https://{KOMMO_SUBDOMAIN}.kommo.com/api/v4"


async def request_with_retry(method: str, endpoint: str, retry: bool = True, **kwargs):
    """
    Cliente HTTP resiliente para Kommo.
    Maneja automáticamente expiración de token.
    """

    url = f"{KOMMO_BASE_URL}{endpoint}"
    access_token = await get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.request(method, url, headers=headers, **kwargs)

    # 🔁 Si token expiró, intentar refresh automático
    if response.status_code == 401 and retry:
        print("⚠️ Token vencido. Forzando refresh y reintentando...")

        await refresh_access_token()

        # Reintento una sola vez
        access_token = await get_access_token()

        headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, url, headers=headers, **kwargs)

    return response


# ====== FUNCIONES ESPECÍFICAS ======

async def get_lead(lead_id: int):
    endpoint = f"/leads/{lead_id}?with=custom_fields_values,contacts"

    response = await request_with_retry("GET", endpoint)

    print("Status:", response.status_code)
    print("Raw response:", response.text)

    if response.status_code != 200:
        return None

    return response.json()


# ====== ENVIAR NOTA AL LEAD ======

async def agregar_nota_al_lead(lead_id: int, mensaje: str):

    endpoint = f"/leads/{lead_id}/notes"

    payload = [
        {
            "note_type": "common",
            "params": {
                "text": mensaje
            }
        }
    ]

    response = await request_with_retry(
        "POST",
        endpoint,
        json=payload
    )

    print("📤 Nota enviada - Status:", response.status_code)
    print("📤 Respuesta Kommo:", response.text)

    if response.status_code not in [200, 201]:
        print("❌ Error enviando nota")

    return response.status_code