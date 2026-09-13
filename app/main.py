from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from app import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

app = FastAPI(default_response_class=ORJSONResponse, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class RegisterIn(BaseModel):
    user_id: int
    username: str | None = None
    language: str | None = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register")
def register(payload: RegisterIn):
    if payload.user_id <= 0:
        raise HTTPException(400, "invalid user_id")
    return db.register_user(
        payload.user_id,
        (payload.username or "").lstrip("@")[:64] or None,
        (payload.language or "")[:8] or None,
    )

@app.get("/users")
def users(
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=2000),
):
    return db.list_users(offset, limit)
