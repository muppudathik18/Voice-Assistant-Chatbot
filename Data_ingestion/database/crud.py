# data_ingestion_service/database/crud.py
import sqlite3
from typing import List, Dict
from datetime import datetime, UTC

# Import DB_FILE from config
from config import DB_FILE

# Global connection and cursor
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

def setup_db():
    """Creates tables for scraped pages if they don't exist."""
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scraped_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        raw_text TEXT,
        scraped_at TEXT
    )
    """)
    conn.commit()

def get_last_scraped_time(url: str) -> str | None:
    """Retrieves the last scraped timestamp for a given URL."""
    cur.execute("SELECT scraped_at FROM scraped_pages WHERE url = ? ORDER BY scraped_at DESC LIMIT 1", (url,))
    result = cur.fetchone()
    return result[0] if result else None

def save_scraped_page(url: str, raw_text: str):
    """Saves or updates a scraped page record."""
    cur.execute("INSERT OR REPLACE INTO scraped_pages (url, raw_text, scraped_at) VALUES (?, ?, ?)",
                (url, raw_text, datetime.now(UTC).isoformat()))
    conn.commit()

# Initialize DB on module import
setup_db()