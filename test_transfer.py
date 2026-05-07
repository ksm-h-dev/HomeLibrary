import sqlite3
from app.database import transfer_source as db_transfer
import asyncio

# Using sync sqlite for this test
conn = sqlite3.connect('library.db')
c = conn.cursor()

# Get source info
c.execute("SELECT id, name, path FROM sources WHERE id = 43")
source = c.fetchone()
print(f"Source to transfer: {source}")

# Check files in C:\Book
import os
book_dir = r'C:\Book'
if os.path.exists(book_dir):
    files_count = sum(len(f) for _, f, _ in os.walk(book_dir))
    print(f"Files in {book_dir}: {files_count}")

conn.close()