import os
import libsql

TURSO_URL = os.environ.get("TURSO_URL")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    number    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL UNIQUE,
    username  TEXT,
    language  TEXT,
    joined_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_users_number ON users(number);
"""

def _connect():
    """Создаёт синхронное подключение к Turso."""
    return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

def init_db():
    """Создаёт таблицу при старте сервера."""
    with _connect() as db:
        db.executescript(SCHEMA)
        db.commit()

def register_user(user_id: int, username: str | None, language: str | None):
    """Регистрирует пользователя. Если уже зарегистрирован — возвращает его данные."""
    with _connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO users(user_id, username, language) VALUES (?,?,?)",
            (user_id, username, language),
        )
        db.commit()

        cur = db.execute(
            "SELECT number, username, language, joined_at FROM users WHERE user_id=?",
            (user_id,),
        )
        row = cur.fetchone()

        cur = db.execute("SELECT changes()")
        changes = cur.fetchone()[0]

        return {
            "number": row[0],
            "username": row[1],
            "language": row[2],
            "joined_at": row[3],
            "is_new": changes == 1,
        }

def list_users(offset: int, limit: int):
    """Постраничный вывод пользователей."""
    with _connect() as db:
        cur = db.execute(
            "SELECT number, username, language, joined_at FROM users "
            "ORDER BY number ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cur.fetchall()

        cur = db.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "users": [
            {"number": r[0], "username": r[1], "language": r[2], "joined_at": r[3]}
            for r in rows
        ],
    }
