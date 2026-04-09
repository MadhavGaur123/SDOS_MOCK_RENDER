from pathlib import Path
import os


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
STORAGE_DIR = BACKEND_DIR / "storage"
UPLOAD_DIR = Path(os.getenv("HEALIN_UPLOAD_DIR", STORAGE_DIR / "documents")).resolve()
DOCUMENTS_PATH = Path(
    os.getenv("HEALIN_DOCUMENTS_JSON", STORAGE_DIR / "documents.json")
).resolve()
HOSPITALS_PATH = Path(
    os.getenv("HEALIN_HOSPITALS_JSON", STORAGE_DIR / "hospitals.json")
).resolve()
REFRESH_LOGS_PATH = Path(
    os.getenv("HEALIN_REFRESH_LOGS_JSON", STORAGE_DIR / "refresh_logs.json")
).resolve()
VECTOR_DB_DIR = Path(
    os.getenv("VECTOR_DB_DIR", BACKEND_DIR / "rag_pipeline" / "vectordb")
).resolve()

DATABASE_URL = (
    os.getenv("HEALIN_DB_URL")
    or os.getenv("DATABASE_URL")
    or os.getenv("DB_URL")
    or "postgresql://postgres:postgres@localhost:5432/HealIN_DB2"
)

LEGACY_DATABASE_URL = os.getenv("HEALIN_RAG_DB_URL") or os.getenv("PG_DSN") or DATABASE_URL
READ_SOURCE = os.getenv("HEALIN_READ_SOURCE", "json_first").strip().lower()
DB_CONNECT_TIMEOUT = int(os.getenv("HEALIN_DB_CONNECT_TIMEOUT", "1"))

ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("HEALIN_ALLOW_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
