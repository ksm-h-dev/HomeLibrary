import os

BOOKS_DIR = os.getenv("LIBRARY_BOOKS_DIR", "C:/Book/")
DATABASE_URL = os.getenv("LIBRARY_DB", "library.db")
SERVER_HOST = os.getenv("LIBRARY_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("LIBRARY_PORT", "8000"))

SUPPORTED_FORMATS = ["pdf", "djvu", "rar", "zip", "rtf"]
SUPPORTED_METADATA_EXT = ["txt", "html"]
COVER_EXTENSIONS = ["jpg", "jpeg", "png", "gif"]
