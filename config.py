import os

DATABASE_URL = os.getenv("LIBRARY_DB", "library.db")
SERVER_HOST = os.getenv("LIBRARY_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("LIBRARY_PORT", "8000"))

DEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", "H:/Book")
SHOW_WELCOME = os.getenv("LIBRARY_SHOW_WELCOME", "true")

SUPPORTED_FORMATS = ["pdf", "djvu", "rar", "zip", "rtf", "7z"]
SUPPORTED_METADATA_EXT = ["txt", "json"]
COVER_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"]

AUDIT_ENABLED = os.getenv("LIBRARY_AUDIT_ENABLED", "false").lower() == "true"  # Updated by setup
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")