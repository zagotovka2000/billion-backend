from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from app import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте сервера создаём таблицу
    await db.init_db()
    yield

app = FastAPI(default_response_class=ORJSONResponse, lifespan=lifespan)

# CORS — чтобы фронтенд с GitHub Pages мог обращаться к API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для продакшена лучше указать конкретный домен
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class RegisterIn(BaseModel):
    user_id: int
    username: str | None = None
    language: str | None = None

@app.get("/health")
async def health():
    """Health-чек для UptimeRobot."""
    return {"status": "ok"}

@app.post("/register")
async def register(payload: RegisterIn):
    """Регистрирует пользователя из Telegram Mini App."""
    if payload.user_id <= 0:
        raise HTTPException(400, "invalid user_id")
    return await db.register_user(
        payload.user_id,
        (payload.username or "").lstrip("@")[:64] or None,
        (payload.language or "")[:8] or None,
    )

@app.get("/users")
async def users(
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=2000),
):
    """Возвращает список зарегистрированных пользователей."""
    return await db.list_users(offset, limit)
