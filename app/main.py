# app/main.py
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

from app.db import get_client
from app.score import calc_score

app = FastAPI(default_response_class=ORJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class RegisterUser(BaseModel):
    user_id: int
    username: str
    invited_by: int | None = None



async def _update_chain_score(client, start_user_id: int, delta: int, now: int):
    """
    Идёт наверх по цепочке приглашений (до 3 уровней)
    и меняет счётчики у предков.

    delta = +1 при регистрации, -1 при удалении.
    """
    field_by_depth = {
        1: "personal_count",
        2: "level2_count",
        3: "level3_count",
    }

    rows = await client.execute(
        """
        WITH RECURSIVE up(id, depth) AS (
          SELECT CAST(invited_by AS INTEGER), 1
          FROM users WHERE user_id = ?
          UNION ALL
          SELECT CAST(u.invited_by AS INTEGER), up.depth + 1
          FROM users u JOIN up ON u.user_id = up.id
          WHERE up.depth < 3 AND u.invited_by IS NOT NULL
        )
        SELECT id, depth FROM up WHERE id IS NOT NULL
        """,
        [start_user_id],
    )

    for row in rows.rows:
        ancestor_id = row[0]
        depth = row[1]
        field = field_by_depth[depth]

        anc = await client.execute(
            "SELECT personal_count, level2_count, level3_count FROM users WHERE user_id = ?",
            [ancestor_id],
        )
        if not anc.rows:
            continue

        l1, l2, l3 = anc.rows[0]
        new_l1 = max(0, l1 + (delta if field == "personal_count" else 0))
        new_l2 = max(0, l2 + (delta if field == "level2_count" else 0))
        new_l3 = max(0, l3 + (delta if field == "level3_count" else 0))
        new_score = calc_score(new_l1, new_l2, new_l3)

        await client.execute(
            f"""
            UPDATE users
            SET {field} = MAX(0, {field} + ?),
                score = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            [delta, new_score, now, ancestor_id],
        )



@app.get("/")
async def root():
    return {"status": "ok", "service": "billion-milestone-api"}


@app.post("/users/register")
async def register_user(payload: RegisterUser):
    """
    Регистрирует нового юзера.
    Если указан invited_by — обновляет счётчики у предков (до 3 уровней).
    """
    now = int(time.time())
    client = await get_client()

    async with client:
        existing = await client.execute(
            "SELECT user_id FROM users WHERE user_id = ?", [payload.user_id]
        )
        if existing.rows:
            raise HTTPException(409, "User already exists")

        # Если пригласитель указан — проверяем, что он существует
        if payload.invited_by is not None:
            inviter = await client.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                [payload.invited_by],
            )
            if not inviter.rows:
                raise HTTPException(404, "Inviter not found")

  
        await client.execute(
            """
            INSERT INTO users
              (user_id, username, invited_by,
               personal_count, level2_count, level3_count,
               score, joined_at, updated_at)
            VALUES (?, ?, ?, 0, 0, 0, 0, ?, ?)
            """,
            [
                payload.user_id,
                payload.username,
                str(payload.invited_by) if payload.invited_by is not None else None,
                now,
                now,
            ],
        )

        # счётчики у предков
        if payload.invited_by is not None:
            await _update_chain_score(client, payload.invited_by, +1, now)

        return {"ok": True, "user_id": payload.user_id}


@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    """Удаляет юзера и откатывает счётчики у предков."""
    now = int(time.time())
    client = await get_client()

    async with client:
        row = await client.execute(
            "SELECT invited_by FROM users WHERE user_id = ?", [user_id]
        )
        if not row.rows:
            raise HTTPException(404, "User not found")

        invited_by_raw = row.rows[0][0]
        invited_by = int(invited_by_raw) if invited_by_raw is not None else None

        if invited_by is not None:
            await _update_chain_score(client, invited_by, -1, now)

        await client.execute("DELETE FROM users WHERE user_id = ?", [user_id])

        return {"ok": True, "deleted": user_id}


@app.get("/leaderboard")
async def leaderboard(
    cursor_score: float | None = None,
    cursor_uid: int | None = None,
    limit: int = 50,
):
    """
    Топ юзеров с keyset-пагинацией.
    Курсор = (score, user_id) последней отданной строки.
    """
    limit = min(limit, 200)
    client = await get_client()

    async with client:
        if cursor_score is None:
            result = await client.execute(
                """
                SELECT user_id, username, score
                FROM users
                WHERE score > 0
                ORDER BY score DESC, user_id ASC
                LIMIT ?
                """,
                [limit + 1],
            )
        else:
            result = await client.execute(
                """
                SELECT user_id, username, score
                FROM users
                WHERE score > 0
                  AND ((score < ?) OR (score = ? AND user_id > ?))
                ORDER BY score DESC, user_id ASC
                LIMIT ?
                """,
                [cursor_score, cursor_score, cursor_uid, limit + 1],
            )

        rows = result.rows
        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = {"score": last[2], "uid": last[0]}

        return {
            "rows": [
                {"user_id": r[0], "username": r[1], "score": r[2]}
                for r in rows
            ],
            "nextCursor": next_cursor,
            "hasMore": has_more,
        }


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Возвращает данные одного юзера."""
    client = await get_client()
    async with client:
        result = await client.execute(
            """
            SELECT user_id, username, invited_by,
                   personal_count, level2_count, level3_count,
                   score, joined_at
            FROM users WHERE user_id = ?
            """,
            [user_id],
        )
        if not result.rows:
            raise HTTPException(404, "User not found")

        r = result.rows[0]
        invited_by_raw = r[2]

        return {
            "user_id": r[0],
            "username": r[1],
            "invited_by": int(invited_by_raw) if invited_by_raw is not None else None,
            "personal_count": r[3],
            "level2_count": r[4],
            "level3_count": r[5],
            "score": r[6],
            "joined_at": r[7],
        }
