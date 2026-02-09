import logging
import os
import shutil
import tempfile
from typing import Optional

from google.auth import default
from google.cloud import storage

logger = logging.getLogger(__name__)

DEFAULT_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "mi-bucket-automatizaciones")

_credentials, _ = default()
_storage_client = storage.Client(credentials=_credentials)


def guardar_en_gcs(nombre_archivo: str, contenido: str, bucket_name: str = DEFAULT_BUCKET_NAME) -> None:
    """Guarda un string en un objeto dentro de GCS."""
    bucket = _storage_client.bucket(bucket_name)
    blob = bucket.blob(nombre_archivo)
    blob.upload_from_string(contenido)
    logger.info("Archivo guardado en GCS: %s (bucket=%s)", nombre_archivo, bucket_name)


def leer_de_gcs(nombre_archivo: str, bucket_name: str = DEFAULT_BUCKET_NAME) -> Optional[str]:
    """Lee un objeto de GCS y devuelve su contenido como string. Devuelve None si no existe."""
    bucket = _storage_client.bucket(bucket_name)
    blob = bucket.blob(nombre_archivo)
    if not blob.exists():
        return None
    return blob.download_as_text()


def descargar_archivo_a_tmp(ruta_gcs: str, credentials) -> str:
    """
    Descarga un archivo de GCS a un archivo temporal local y devuelve la ruta.
    Acepta rutas tipo 'gs://' o 'gcs://'.
    """
    ruta = ruta_gcs.replace("gs://", "").replace("gcs://", "")
    bucket_name, blob_name = ruta.split("/", 1)

    client = storage.Client(credentials=credentials, project=credentials.project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if not blob.exists():
        raise FileNotFoundError(f"No se encontró {blob_name} en GCS")

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, os.path.basename(blob_name))
    blob.download_to_filename(tmp_path)
    return tmp_path


def limpiar_tmp(tmp_path: str) -> None:
    """Elimina la carpeta temporal donde se descargó el archivo."""
    tmp_dir = os.path.dirname(tmp_path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
