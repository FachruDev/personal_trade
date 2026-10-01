from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json

import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException

from .settings import settings

CREATE_AUDIT_TABLE = "CREATE TABLE IF NOT EXISTS bot_audit_events (id BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    async with app.state.database.acquire() as connection:
        await connection.execute(CREATE_AUDIT_TABLE)
    yield
    await app.state.redis.aclose()
    await app.state.database.close()


app = FastAPI(title="Trading Bot Control API", version="0.1.0", lifespan=lifespan)


async def record_event(event_type: str, payload: dict) -> None:
    async with app.state.database.acquire() as connection:
        await connection.execute("INSERT INTO bot_audit_events (event_type, payload) VALUES ($1, $2::jsonb)", event_type, json.dumps(payload))


async def freqtrade_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        f"{settings.freqtrade_api_url}/api/v1/token/login",
        auth=(settings.freqtrade_api_username, settings.freqtrade_api_password),
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@app.get("/health")
async def health() -> dict:
    await app.state.database.fetchval("SELECT 1")
    await app.state.redis.ping()
    return {"status": "ok", "timestamp": datetime.now(timezone.utc)}


@app.get("/v1/bot/status")
async def bot_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.freqtrade_api_url}/api/v1/status", headers=await freqtrade_headers(client))
            response.raise_for_status()
            return {"mode": "dry_run", "freqtrade": response.json()}
    except httpx.HTTPError as exc:
        return {"mode": "dry_run", "freqtrade": "unavailable", "detail": str(exc)}


@app.get("/v1/decisions")
async def decisions(limit: int = 50) -> list[dict]:
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch("SELECT id, event_type, payload, created_at FROM bot_audit_events ORDER BY id DESC LIMIT $1", min(max(limit, 1), 100))
    return [dict(row) for row in rows]


@app.post("/v1/bot/stop")
async def stop_bot(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(f"{settings.freqtrade_api_url}/api/v1/stop", headers=await freqtrade_headers(client))
        response.raise_for_status()
    await app.state.redis.set("trading:kill-switch", "enabled")
    await record_event("bot_stop_requested", {"source": "local_api"})
    return {"status": "stop_requested"}
