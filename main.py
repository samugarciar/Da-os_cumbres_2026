from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from services.kommo_client import get_lead, agregar_nota_al_lead

from services.kommo_client import get_lead
from ia.gemini import determinar_responsable_con_gemini

load_dotenv()

app = FastAPI()


# 🧠 Extraer campo personalizado
def get_custom_field_value(lead: dict, field_name: str) -> str | None:
    for field in lead.get("custom_fields_values", []):
        if field.get("field_name") == field_name:
            values = field.get("values", [])
            if values:
                return values[0].get("value")
    return None


# 📦 Clasificación por reglas
def clasificar_por_reglas(descripcion: str | None) -> dict:
    if not descripcion:
        return {
            "categoria": "desconocido",
            "urgencia": "baja",
            "sugerencia_responsable": "revisar"
        }

    texto = descripcion.lower()

    if any(p in texto for p in ["gas", "olor a gas", "fuga de gas", "válvula", "medidor"]):
        return {
            "categoria": "gas",
            "urgencia": "alta",
            "sugerencia_responsable": "propietario"
        }

    if any(p in texto for p in [
        "agua", "fuga", "gotera", "humedad", "filtración",
        "ducha", "sanitario", "wc", "lavamanos",
        "tubería", "presión", "yeso"
    ]):
        return {
            "categoria": "agua",
            "urgencia": "media",
            "sugerencia_responsable": "propietario"
        }

    if any(p in texto for p in [
        "puerta", "ventana", "vidrio", "cerradura",
        "pared", "techo", "piso", "baldosa"
    ]):
        return {
            "categoria": "estructura",
            "urgencia": "baja",
            "sugerencia_responsable": "revisar"
        }

    return {
        "categoria": "otro",
        "urgencia": "baja",
        "sugerencia_responsable": "revisar"
    }


@app.post("/kommo/reporte-danos")
async def reporte_danos(request: Request):

    # 🔥 SOLUCIÓN CORRECTA: leer el body UNA sola vez
    content_type = request.headers.get("content-type", "")
    print("📬 Content-Type:", content_type)

    if "application/json" in content_type:
        body = await request.json()
        print("📦 JSON recibido:", body)
    else:
        form = await request.form()
        body = dict(form)
        print("📦 FORM recibido:", body)

    if not body:
        return JSONResponse(
            content={"status": "empty body"},
            status_code=200
        )

    # 🔎 Extraer lead_id dependiendo del formato
    lead_id = None

    # Caso JSON tipo leads.add
    if isinstance(body, dict) and "leads" in body:
        try:
            lead_id = body["leads"]["add"][0]["id"]
        except Exception:
            pass

    # Caso form-data típico de Kommo
    if not lead_id and "leads[add][0][id]" in body:
        lead_id = body["leads[add][0][id]"]

    if not lead_id:
        print("❌ No se pudo extraer lead_id")
        return JSONResponse(
            content={"status": "lead_id not found"},
            status_code=200
        )

    lead_id = int(lead_id)
    print(f"🎯 Lead ID detectado: {lead_id}")

    # 🔥 Obtener lead desde Kommo
    lead = await get_lead(lead_id)

    # 👤 Obtener contacto principal del lead
    contact_id = None

    if "_embedded" in lead and "contacts" in lead["_embedded"]:
        contactos = lead["_embedded"]["contacts"]
        if contactos:
            contact_id = contactos[0]["id"]

    print("👤 Contact ID detectado:", contact_id)

    if not lead:
        return JSONResponse(
            content={"status": "lead not found"},
            status_code=200
        )

    descripcion_dano = get_custom_field_value(
        lead,
        "Descripción del daño"
    )

    clasificacion_reglas = clasificar_por_reglas(descripcion_dano)

    # ⚖️ Si reglas determinan propietario, no usar Gemini
    if clasificacion_reglas["sugerencia_responsable"] == "propietario":
        resultado_final = {
            "responsable_preliminar": "propietario",
            "mensaje_operativo": (
                "De manera preliminar, el daño sería asumido por el propietario. "
                "Por favor enviar evidencia audiovisual (foto o video) para validación técnica. "
                "Se iniciará la gestión correspondiente."
            )
        }
    else:
        resultado_final = await determinar_responsable_con_gemini(
            descripcion_dano,
            clasificacion_reglas
        )

    # 📨 Construir mensaje
    mensaje_chat = (
        "🤖 Evaluación automática del sistema\n\n"
        f"🔎 Responsable preliminar: {resultado_final.get('responsable_preliminar')}\n\n"
        f"{resultado_final.get('mensaje_operativo')}"
    )

    # 📤 Enviar nota al lead
    await agregar_nota_al_lead(lead_id, mensaje_chat)

    return {
        "status": "ok",
        "lead_id": lead_id,
        "descripcion_dano": descripcion_dano,
        "evaluacion_responsable": resultado_final
    }