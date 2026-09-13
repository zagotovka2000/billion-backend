import os
import libsql

# Читаем из переменных окружения Render
TURSO_URL = os.environ.get("TURSO_URL")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN")

# Схема таблицы
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

async def init_db():
    """Создаёт таблицу при старте сервера."""
    async with libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def register_user(user_id: int, username: str | None, language: str | None):
    """Регистрирует пользователя. Если уже зарегистрирован — возвращает его данные."""
    async with libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN) as db:
        # INSERT OR IGNORE — если user_id уже есть, ничего не делаем
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, username, language) VALUES (?,?,?)",
            (user_id, username, language),
        )
        await db.commit()

        # Читаем данные пользователя
        cur = await db.execute(
            "SELECT number, username, language, joined_at FROM users WHERE user_id=?",
            (user_id,),
        )
        row = await cur.fetchone()

        # Проверяем, был ли это новый пользователь
        cur = await db.execute("SELECT changes()")
        changes = (await cur.fetchone())[0]

        return {
            "number": row[0],
            "username": row[1],
            "language": row[2],
            "joined_at": row[3],
            "is_new": changes == 1,
        }

async def list_users(offset: int, limit: int):
    """Постраничный вывод пользователей."""
    async with libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN) as db:
        cur = await db.execute(
            "SELECT number, username, language, joined_at FROM users "
            "ORDER BY number ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cur.fetchall()

        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "users": [
            {"number": r[0], "username": r[1], "language": r[2], "joined_at": r[3]}
            for r in rows
        ],
    }
