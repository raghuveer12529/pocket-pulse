import json
from typing import Any

DEFAULT_CATEGORIES = [
    ("Food",          ["zomato", "swiggy", "restaurant", "lunch", "dinner", "breakfast", "cafe"]),
    ("Transport",     ["uber", "ola", "auto", "petrol", "fuel", "metro", "bus"]),
    ("Shopping",      ["amazon", "flipkart", "mall", "clothes"]),
    ("Health",        ["pharmacy", "doctor", "hospital", "medicine"]),
    ("Bills",         ["electricity", "wifi", "internet", "rent", "water"]),
    ("Entertainment", ["netflix", "movie", "spotify", "hotstar"]),
    ("Other",         []),
]

async def create_tables(db: Any) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            currency  TEXT NOT NULL DEFAULT 'INR',
            timezone  TEXT NOT NULL DEFAULT 'Asia/Kolkata'
        );
        CREATE TABLE IF NOT EXISTS categories (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE NOT NULL,
            keywords TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            amount     REAL NOT NULL,
            category   TEXT NOT NULL,
            note       TEXT,
            date       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budgets (
            user_id       INTEGER NOT NULL,
            category      TEXT NOT NULL,
            monthly_limit REAL NOT NULL,
            PRIMARY KEY (user_id, category)
        );
        CREATE TABLE IF NOT EXISTS recurring (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            amount       REAL NOT NULL,
            note         TEXT NOT NULL,
            category     TEXT NOT NULL,
            day_of_month INTEGER NOT NULL,
            created_at   TEXT NOT NULL
        );
    """)
    for name, keywords in DEFAULT_CATEGORIES:
        await db.execute(
            "INSERT OR IGNORE INTO categories (name, keywords) VALUES (?, ?)",
            (name, json.dumps(keywords)),
        )
    await db.commit()
