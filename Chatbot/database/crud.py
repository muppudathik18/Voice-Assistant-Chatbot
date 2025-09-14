# database/crud.py
import sqlite3
from typing import List, Dict, Tuple
import os

# Import DB_FILE from config
from config import DB_FILE

# Global connection and cursor (managed carefully for thread-safety in FastAPI)
# For production, consider using a connection pool or dependency injection per request.
# For SQLite with check_same_thread=False, this is generally okay for simple apps.
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

def setup_db():
    """Creates tables and seeds initial data if they don't exist."""
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        work_start TEXT DEFAULT '09:00',
        work_end TEXT DEFAULT '17:00'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER,
        customer_name TEXT,
        start_time TEXT,
        duration_minutes INTEGER DEFAULT 30,
        type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(agent_id) REFERENCES agents(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

    seed_agents()

def seed_agents():
    """Seeds initial agent data if the agents table is empty."""
    cur.execute("SELECT COUNT(*) FROM agents")
    if cur.fetchone()[0] == 0:
        agents = [
            ("Sarah Johnson", "sales", "09:00", "17:00"),
            ("Mike Rodriguez", "sales", "09:00", "17:00"),
            ("Jennifer Chen", "sales", "10:00", "18:00"),
            ("Tom Wilson", "service", "08:00", "16:00"),
            ("Lisa Martinez", "service", "09:00", "17:00"),
            ("David Park", "service", "10:00", "18:00")
        ]
        cur.executemany("INSERT INTO agents (name, role, work_start, work_end) VALUES (?, ?, ?, ?)", agents)
        conn.commit()

def append_history(session_id: str, role: str, content: str):
    """Appends a message to the conversation history."""
    cur.execute("INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content))
    conn.commit()

def load_history(session_id: str, last_n: int = 10) -> List[Dict[str, str]]:
    """Loads the last N messages from conversation history."""
    cur.execute("""
    SELECT role, content FROM conversations
    WHERE session_id = ?
    ORDER BY id DESC LIMIT ?
    """, (session_id, last_n))
    rows = cur.fetchall()
    rows = list(reversed(rows))
    return [{"role": r, "content": c} for r, c in rows]

def get_agent_work_hours(agent_id: int) -> Tuple[str, str]:
    """Retrieves work hours for a given agent."""
    cur.execute("SELECT work_start, work_end FROM agents WHERE id = ?", (agent_id,))
    return cur.fetchone()

def get_agent_by_role(role: str) -> List[Tuple[int, str]]:
    """Retrieves agents by their role."""
    cur.execute("SELECT id, name FROM agents WHERE role = ?", (role,))
    return cur.fetchall()

def get_conflicting_appointments(agent_id: int, start_time: str, end_time: str) -> List[Tuple[str, int]]:
    """Checks for conflicting appointments for a given agent and time slot."""
    cur.execute("""
        SELECT start_time, duration_minutes FROM appointments
        WHERE agent_id = ?
        AND (
            (start_time <= ? AND ? < start_time + duration_minutes * 60) OR
            (? <= start_time AND start_time < ?)
        )
    """, (agent_id, start_time, start_time, end_time, end_time))
    return cur.fetchall()

def create_appointment(agent_id: int, customer_name: str, start_time: str, duration_minutes: int, appt_type: str):
    """Creates a new appointment record."""
    cur.execute("INSERT INTO appointments (agent_id, customer_name, start_time, duration_minutes, type) VALUES (?, ?, ?, ?, ?)",
                (agent_id, customer_name, start_time, duration_minutes, appt_type))
    conn.commit()

def get_upcoming_appointments(limit: int = 5) -> List[Tuple[str, str]]:
    """Retrieves a list of upcoming appointments."""
    cur.execute("SELECT a.start_time, ag.name FROM appointments a JOIN agents ag ON a.agent_id = ag.id ORDER BY a.start_time LIMIT ?", (limit,))
    return cur.fetchall()

# Initialize DB on module import
setup_db()