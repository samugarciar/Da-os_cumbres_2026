import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"


async def determinar_responsable_con_gemini(
    descripcion: str,
    clasificacion_reglas: dict
) -> dict:

    if not descripcion:
        return {
            "responsable_preliminar": "revisar",
            "mensaje_operativo": (
                "No se recibió descripción suficiente del daño. "
                "Por favor enviar evidencia audiovisual (foto o video). "
                "Se iniciará la gestión correspondiente."
            )
        }

    prompt = f"""
Actúa como administrador de propiedad horizontal en Colombia.

Daño reportado:
{descripcion}

Clasificación base:
Categoría: {clasificacion_reglas.get("categoria")}
Urgencia: {clasificacion_reglas.get("urgencia")}

Determina quién asumiría preliminarmente el daño.

El valor debe ser EXACTAMENTE uno de estos:
- propietario
- inquilino
- revisar

IMPORTANTE:
- Respuesta breve y operativa.
- No expliques normas legales.
- Máximo 3 líneas.
- Indica claramente quién asumiría el daño, y que esta es una respuesta preliminar que requiere igualmente estudio por parte de nuestros asesores.
- Solicita evidencia audiovisual (foto o video).
- Indica que se iniciará la gestión correspondiente.
- No uses markdown.

Responde EXCLUSIVAMENTE en JSON válido:

{{
  "responsable_preliminar": "",
  "mensaje_operativo": ""
}}
"""

    url = (
        f"https://generativelanguage.googleapis.com/v1/models/"
        f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2200
        }
    }

    text_response = None

    try:
        print("🚀 Enviando request a Gemini...")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True
        ) as client:

            response = await client.post(url, json=payload)

        print("✅ Respuesta recibida de Gemini")

        if response.status_code != 200:
            print("❌ Error HTTP Gemini:", response.status_code)
            return {
                "error": "gemini_http_error",
                "status_code": response.status_code,
                "raw": response.text
            }

        data = response.json()

        if "candidates" not in data:
            return {
                "error": "no_candidates_in_response",
                "raw": data
            }

        text_response = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        print("📨 Texto crudo Gemini:", text_response)

        # Limpieza si devuelve markdown
        if text_response.startswith("```"):
            text_response = (
                text_response
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        # Extraer JSON válido
        start = text_response.find("{")
        end = text_response.rfind("}") + 1

        if start != -1 and end != -1:
            clean_json = text_response[start:end]
            parsed = json.loads(clean_json)

            if "responsable_preliminar" in parsed:
                parsed["responsable_preliminar"] = (
                    parsed["responsable_preliminar"]
                    .strip()
                    .lower()
                )

            valores_validos = ["propietario", "inquilino", "revisar"]

            if (
                "responsable_preliminar" in parsed
                and "mensaje_operativo" in parsed
                and parsed["responsable_preliminar"] in valores_validos
            ):
                return parsed

        return {
            "error": "invalid_json_from_gemini",
            "raw_response": text_response
        }

    except httpx.RequestError as e:
        print("🌐 Error de conexión con Gemini:", str(e))
        return {
            "error": "connection_error",
            "detail": str(e)
        }

    except json.JSONDecodeError:
        print("⚠️ Error decodificando JSON de Gemini")
        return {
            "error": "json_decode_error",
            "raw_response": text_response
        }

    except Exception as e:
        print("🔥 Excepción inesperada en Gemini:", str(e))
        return {
            "error": "gemini_exception",
            "detail": str(e)
        }