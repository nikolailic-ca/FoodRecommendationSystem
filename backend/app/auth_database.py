from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"

DATABASE_DIR.mkdir(exist_ok=True)

DB_FILE = DATABASE_DIR / "app.db"


def get_connection():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row

    # Omogućava foreign key constraints u SQLite-u
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database():

    connection = get_connection()

    # =========================
    # USERS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # USER RATINGS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            recipe_id INTEGER NOT NULL,

            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, recipe_id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()