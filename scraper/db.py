import sqlite3
import os
from typing import Optional, List, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "leads.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            email TEXT,
            website TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            project_name TEXT,
            project_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)
    conn.commit()
    conn.close()


def company_exists(company_name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM companies WHERE name = ?", (company_name,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def add_company(
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    address: Optional[str] = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO companies (name, phone, email, website, address)
            VALUES (?, ?, ?, ?, ?)
        """,
            (name, phone, email, website, address),
        )
        company_id = cursor.lastrowid
        conn.commit()
        return company_id
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM companies WHERE name = ?", (name,))
        result = cursor.fetchone()
        conn.close()
        return result["id"] if result else -1


def add_project(company_id: int, project_name: Optional[str], project_url: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO projects (company_id, project_name, project_url)
        VALUES (?, ?, ?)
    """,
        (company_id, project_name, project_url),
    )
    conn.commit()
    conn.close()


def get_all_companies() -> List[Tuple]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone, email, website, address FROM companies")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_company_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM companies")
    result = cursor.fetchone()
    conn.close()
    return result["count"] if result else 0


def get_project_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM projects")
    result = cursor.fetchone()
    conn.close()
    return result["count"] if result else 0


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
