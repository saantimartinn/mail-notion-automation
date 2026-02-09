import email
import html
import imaplib
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from flask import Flask
from google.auth import default
from google.cloud import secretmanager
from notion_client import Client

from gcs_helpers import guardar_en_gcs, leer_de_gcs

app = Flask(__name__)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# -----------------------------
# Env config (cloud-run friendly)
# -----------------------------
SECRET_NAME = os.environ.get("GCP_SECRET_NAME")
if not SECRET_NAME:
    raise RuntimeError("Missing environment variable: GCP_SECRET_NAME")

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "mi-bucket-automatizaciones")

LOG_OBJECT_NAME = os.environ.get("LOG_OBJECT_NAME", "log_email_notion.txt")
LAST_UID_OBJECT_NAME = os.environ.get("LAST_UID_OBJECT_NAME", "last_IMAPemail_id.txt")

IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")

# -----------------------------
# Load config from Secret Manager (ADC)
# -----------------------------
credentials, _ = default()
sm_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
response = sm_client.access_secret_version(request={"name": SECRET_NAME})
claves_json = response.payload.data.decode("UTF-8")
config = json.loads(claves_json)

# --- CONFIG (from secret JSON) ---
NOTION_TOKEN = config["notion"]["token"]
DATABASE_ID = config["notion"]["database_id"]
REMITENTE = config["config"]["remitente"]
EMAIL_USER = config["gmail"]["email"]
EMAIL_PASS = config["gmail"]["app_password"]

notion = Client(auth=NOTION_TOKEN)


# -----------------------------
# Helpers (GCS state)
# -----------------------------
def guardar_ultimo_uid(uid: bytes) -> None:
    if DRY_RUN:
        logger.info("[DRY_RUN] Guardar último UID: %s", uid.decode(errors="ignore"))
        return
    guardar_en_gcs(LAST_UID_OBJECT_NAME, uid.decode(), bucket_name=GCS_BUCKET_NAME)


def cargar_ultimo_uid() -> Optional[bytes]:
    contenido = leer_de_gcs(LAST_UID_OBJECT_NAME, bucket_name=GCS_BUCKET_NAME)
    return contenido.strip().encode() if contenido else None


def registrar_log(
    uid_final: Optional[bytes],
    nuevos_uids: List[bytes],
    ignorados: List[str],
    errores: List[str],
    nombres_creados: List[str],
) -> None:
    log = f"Ejecucion: {datetime.now().isoformat()}\n"
    log += f"Nuevos correos detectados: {len(nuevos_uids)}\n"
    log += f"UIDs procesados: {[u.decode(errors='ignore') for u in nuevos_uids]}\n"
    log += f"Remitentes ignorados: {ignorados}\n"
    log += f"Errores: {errores}\n"
    log += f"Paginas creadas en Notion: {nombres_creados}\n"
    log += f"Ultimo UID guardado: {uid_final.decode(errors='ignore') if uid_final else 'Ninguno'}\n"

    if DRY_RUN:
        logger.info("[DRY_RUN] Log:\n%s", log)
        return

    guardar_en_gcs(LOG_OBJECT_NAME, log, bucket_name=GCS_BUCKET_NAME)


# -----------------------------
# Notion helpers
# -----------------------------
def extraer_datos(texto: str, fecha_recepcion: str) -> Dict[str, str]:
    texto = re.sub(r"\r?\n", "\n", texto)
    campos = {
        "Nombre": "",
        "Correo electrónico": "",
        "Telefono": "",
        "Servicio": "",
        "Mensaje": "",
        "Contact_date": fecha_recepcion,
    }

    patrones = {
        "Nombre": r"Nombre:\s*(.*?)\s*Correo electrónico:",
        "Correo electrónico": r"Correo electrónico:\s*(.*?)\s*Tel[eé]fono:",
        "Telefono": r"Tel[eé]fono:\s*(.*?)\s*Servicio:",
        "Servicio": r"Servicio:\s*(.*?)\s*Mensaje:",
        "Mensaje": r"Mensaje:\s*(.*?)(?=\s*---|$)",
    }

    for campo, patron in patrones.items():
        m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        if m:
            campos[campo] = m.group(1).strip()

    return campos


def añadir_a_notion(datos: Dict[str, str], uid: str) -> Optional[str]:
    # Evitar duplicados por UID
    resultados = notion.databases.query(
        database_id=DATABASE_ID,
        filter={"property": "Email UID", "rich_text": {"equals": str(uid)}},
    )
    if resultados.get("results"):
        logger.info("Correo UID %s ya procesado en Notion. Saltando.", uid)
        return None

    if DRY_RUN:
        logger.info("[DRY_RUN] Crear página en Notion (UID=%s, Nombre=%s)", uid, datos.get("Nombre"))
        return datos.get("Nombre") or "Sin nombre"

    resp = notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Nombre": {"title": [{"text": {"content": datos.get("Nombre") or "Sin nombre"}}]},
            "Email": {"email": datos.get("Correo electrónico") or None},
            "Phone": {"phone_number": datos.get("Telefono") or None},
            "Carpeta Creada": {"checkbox": False},
            "comentario": {"rich_text": [{"text": {"content": datos.get("Mensaje") or ""}}]},
            "Contact date": {"date": {"start": datos.get("Contact_date")}},
            "Email UID": {"rich_text": [{"text": {"content": str(uid)}}]},
        },
    )
    logger.info("Página creada en Notion: %s", resp.get("url"))
    return datos.get("Nombre") or "Sin nombre"


# -----------------------------
# Email parsing
# -----------------------------
def _extraer_cuerpo(msg: email.message.Message) -> str:
    cuerpo = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                cuerpo = part.get_payload(decode=True).decode(errors="ignore")
                break
            if content_type == "text/html" and not cuerpo:
                html_content = part.get_payload(decode=True).decode(errors="ignore")
                cuerpo = re.sub(r"<[^>]+>", "", html.unescape(html_content))
    else:
        payload = msg.get_payload(decode=True).decode(errors="ignore")
        if msg.get_content_type() == "text/plain":
            cuerpo = payload
        else:
            cuerpo = re.sub(r"<[^>]+>", "", html.unescape(payload))

    return cuerpo


def process_emails() -> Tuple[int, List[str], List[str]]:
    logger.info("Iniciando process_emails()")
    ignorados: List[str] = []
    errores: List[str] = []
    nombres_creados: List[str] = []

    last_uid = cargar_ultimo_uid()
    logger.info("Último UID cargado: %s", last_uid.decode(errors="ignore") if last_uid else None)

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    if last_uid:
        criteria = f"(UID {int(last_uid.decode()) + 1}:*)"
    else:
        criteria = "ALL"

    logger.info("Criterio IMAP: %s", criteria)

    status, data = mail.uid("search", None, criteria)
    nuevos = (data[0] or b"").split()

    logger.info("Nuevos UIDs encontrados: %s", [u.decode(errors="ignore") for u in nuevos])

    if not nuevos:
        logger.info("No hay correos nuevos.")
        mail.logout()
        return 0, ignorados, errores

    for uid in nuevos:
        res, msg_data = mail.uid("fetch", uid, "(BODY.PEEK[])")
        if res != "OK":
            errores.append(f"Error al obtener UID {uid.decode(errors='ignore')}")
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        remitente = msg.get("From", "")

        if REMITENTE.lower() not in remitente.lower():
            ignorados.append(remitente)
            logger.info("Ignorado por remitente: %s", remitente)
            continue

        cuerpo = _extraer_cuerpo(msg)

        # Filtros básicos anti-spam (los mismos que ya tenías)
        if re.search(r"\bSEO\b", cuerpo, re.IGNORECASE):
            logger.info("Correo ignorado por contener 'SEO'.")
            continue
        if re.search(r"Se ha suscrito a la newsletter", cuerpo, re.IGNORECASE):
            logger.info("Correo ignorado por suscripción a newsletter.")
            continue

        datos = extraer_datos(cuerpo, datetime.now().date().isoformat())
        logger.info("Datos extraídos (UID=%s): %s", uid.decode(errors="ignore"), datos)

        nombre_pagina = añadir_a_notion(datos, uid.decode(errors="ignore"))
        if nombre_pagina:
            nombres_creados.append(nombre_pagina)

    # Guardar el UID más reciente (solo si hubo nuevos)
    try:
        max_uid = max(nuevos, key=lambda x: int(x))
        guardar_ultimo_uid(max_uid)
        registrar_log(max_uid, nuevos, ignorados, errores, nombres_creados)
    except Exception as exc:
        logger.exception("Error guardando estado/log: %s", exc)
        errores.append(str(exc))

    mail.logout()
    return len(nuevos), ignorados, errores


@app.route("/", methods=["POST"])
def trigger():
    process_emails()
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
