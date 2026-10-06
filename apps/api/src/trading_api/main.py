from __future__ import annotations

from contextlib import asynccontextmanager, suppress
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from statistics import fmean

import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import Body, FastAPI, Header, HTTPException

from .settings import settings
from .market_context import fetch_global_market_context
from .macro_context import fetch_macro_context
from .ai_shadow import PROMPT_VERSION, ShadowAnalysisRequest, analyze_with_gemini, analyze_with_openai_compatible
from .news import NewsHeadline, fetch_crypto_headlines
from .binance_market import WATCHED_SYMBOLS, fetch_market_connectivity, fetch_orderbook_context
from .context_fusion import recommend_context_risk
from .research import experiment_catalog

CREATE_AUDIT_TABLE = "CREATE TABLE IF NOT EXISTS bot_audit_events (id BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
CREATE_CONTEXT_TABLE = "CREATE TABLE IF NOT EXISTS market_context_snapshots (id BIGSERIAL PRIMARY KEY, source TEXT NOT NULL, context_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
CREATE_AI_TABLE = "CREATE TABLE IF NOT EXISTS ai_shadow_assessments (id BIGSERIAL PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, request JSONB NOT NULL, assessment JSONB NOT NULL, observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
CREATE_NEWS_TABLE = "CREATE TABLE IF NOT EXISTS news_headlines (id BIGSERIAL PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, published_at TIMESTAMPTZ NULL, collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (url))"
GLOBAL_CONTEXT_PROVIDER_ERRORS = (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    async with app.state.database.acquire() as connection:
        await connection.execute(CREATE_AUDIT_TABLE)
        await connection.execute(CREATE_CONTEXT_TABLE)
        await connection.execute(CREATE_AI_TABLE)
        await connection.execute(CREATE_NEWS_TABLE)
    app.state.global_shadow_refresh_task = None
    app.state.orderbook_shadow_refresh_task = None
    app.state.paper_run_heartbeat_task = None
    if settings.global_shadow_refresh_seconds > 0:
        app.state.global_shadow_refresh_task = asyncio.create_task(global_shadow_refresh_loop())
    if settings.orderbook_shadow_refresh_seconds > 0:
        app.state.orderbook_shadow_refresh_task = asyncio.create_task(orderbook_shadow_refresh_loop())
    if settings.trading_environment == "paper" and settings.paper_run_heartbeat_seconds > 0:
        app.state.paper_run_heartbeat_task = asyncio.create_task(paper_run_heartbeat_loop())
    yield
    for task in (app.state.global_shadow_refresh_task, app.state.orderbook_shadow_refresh_task, app.state.paper_run_heartbeat_task):
        if task is None:
            continue
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await app.state.redis.aclose()
    await app.state.database.close()


app = FastAPI(title="Trading Bot Control API", version="0.1.0", lifespan=lifespan)


async def record_event(event_type: str, payload: dict) -> None:
    async with app.state.database.acquire() as connection:
        await connection.execute("INSERT INTO bot_audit_events (event_type, payload) VALUES ($1, $2::jsonb)", event_type, json.dumps(payload))


def normalize_audit_event(row: dict) -> dict:
    """Convert PostgreSQL JSON fields into a stable response shape."""
    payload = row.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"raw": payload}
    return {**row, "payload": payload if isinstance(payload, dict) else {"raw": payload}}


def context_stale_after_seconds(source: str, context_type: str) -> int:
    """Set a conservative display/analysis freshness window for shadow inputs."""
    if source == "coingecko" and context_type == "global":
        return max(settings.global_shadow_refresh_seconds * 2, 1_800)
    if source == "binance" and context_type == "orderbook":
        return max(settings.orderbook_shadow_refresh_seconds * 2, 900)
    if source == "fred" and context_type == "macro":
        # Macro series update slowly, but a manually refreshed snapshot should
        # not be presented as current indefinitely.
        return 72 * 3_600
    if source == "ai" and context_type == "assessment":
        return max(settings.ai_shadow_min_interval_seconds * 4, 3_600)
    return 24 * 3_600


def context_availability(observed_at: datetime, stale_after_seconds: int, now: datetime | None = None) -> tuple[str, int]:
    """Return freshness separately from collection success; stale data stays auditable."""
    reference = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age_seconds = max(int((reference - observed_at).total_seconds()), 0)
    return ("available" if age_seconds <= stale_after_seconds else "stale", age_seconds)


def summarize_decision_events(events: list[dict]) -> dict:
    """Summarize auditable reasons for non-entry without changing execution."""
    event_counts = Counter(event["event_type"] for event in events)
    hold_reasons: Counter[str] = Counter()
    latest_by_pair: dict[str, dict] = {}
    for event in events:
        payload = event.get("payload", {})
        if event["event_type"] == "hold":
            reasons = payload.get("failed_conditions", [])
            if isinstance(reasons, list):
                hold_reasons.update(str(reason) for reason in reasons)
        pair = payload.get("pair")
        if isinstance(pair, str) and pair not in latest_by_pair:
            latest_by_pair[pair] = {
                "event_type": event["event_type"],
                "created_at": event["created_at"],
                "regime": payload.get("regime"),
                "rsi": payload.get("rsi"),
                "adx_4h": payload.get("adx_4h"),
                "failed_conditions": payload.get("failed_conditions", []),
            }
    return {
        "events_observed": len(events),
        "event_counts": dict(event_counts),
        "hold_reasons": [{"reason": reason, "count": count} for reason, count in hold_reasons.most_common()],
        "latest_by_pair": latest_by_pair,
    }


async def refresh_global_context_from_provider() -> dict:
    try:
        context = await fetch_global_market_context(settings.coingecko_base_url, settings.coingecko_api_key or None)
    except GLOBAL_CONTEXT_PROVIDER_ERRORS as exc:
        await record_event("market_context_refresh_failed", {"source": "coingecko", "detail": str(exc)})
        raise
    payload = context.as_dict()
    await store_context("coingecko", "global", payload, context.observed_at)
    await record_event("market_context_refreshed", {"source": "coingecko", **payload})
    return payload


async def global_shadow_refresh_loop() -> None:
    latest = await latest_global_context()
    last_observed_at = latest["observed_at"] if latest else None
    delay = next_shadow_refresh_delay(
        last_observed_at,
        settings.global_shadow_refresh_seconds,
        datetime.now(timezone.utc),
    )
    if delay:
        await asyncio.sleep(delay)
    while True:
        try:
            await refresh_global_context_from_provider()
        except Exception:
            # Provider data is advisory only. A failure is audited and must not
            # interrupt API health, bot lifecycle, or order execution.
            pass
        await asyncio.sleep(settings.global_shadow_refresh_seconds)


async def refresh_orderbook_context_from_provider() -> dict:
    try:
        context = await fetch_orderbook_context(settings.binance_public_base_url)
    except GLOBAL_CONTEXT_PROVIDER_ERRORS as exc:
        await record_event("orderbook_context_refresh_failed", {"source": "binance", "detail": str(exc)})
        raise
    payload = context.as_dict()
    await store_context("binance", "orderbook", payload, context.observed_at)
    await record_event("orderbook_context_refreshed", {"source": "binance", **payload})
    return payload


def next_shadow_refresh_delay(last_observed_at: datetime | None, interval_seconds: int, now: datetime) -> float:
    if last_observed_at is None:
        return 0.0
    elapsed = max((now - last_observed_at).total_seconds(), 0.0)
    return max(interval_seconds - elapsed, 0.0)


async def orderbook_shadow_refresh_loop() -> None:
    latest = await latest_context("binance", "orderbook")
    last_observed_at = latest["observed_at"] if latest else None
    delay = next_shadow_refresh_delay(
        last_observed_at,
        settings.orderbook_shadow_refresh_seconds,
        datetime.now(timezone.utc),
    )
    if delay:
        await asyncio.sleep(delay)
    while True:
        try:
            await refresh_orderbook_context_from_provider()
        except Exception:
            # Microstructure data is research telemetry only. Its provider must
            # never affect service health, bot lifecycle, or execution.
            pass
        await asyncio.sleep(settings.orderbook_shadow_refresh_seconds)


def paper_strategy_source_sha256() -> str:
    """Hash the mounted strategy source so an unlabelled source edit resets evidence."""
    try:
        return hashlib.sha256(Path(settings.paper_strategy_source_file).read_bytes()).hexdigest()
    except OSError:
        return "source_unavailable"


def configured_paper_run_identity() -> tuple[str, str, str, str]:
    return (
        settings.freqtrade_strategy,
        settings.freqtrade_profile_config,
        settings.paper_run_revision,
        paper_strategy_source_sha256(),
    )


def paper_run_heartbeat_payload() -> dict[str, str]:
    strategy, profile, revision, source_sha256 = configured_paper_run_identity()
    return {
        "source": "api",
        "mode": "paper",
        "strategy": strategy,
        "profile": profile,
        "revision": revision,
        "source_sha256": source_sha256,
    }


async def latest_paper_run_heartbeat() -> dict | None:
    async with app.state.database.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT created_at, payload FROM bot_audit_events WHERE event_type = 'paper_run_heartbeat' ORDER BY created_at DESC LIMIT 1"
        )
    return dict(row) if row is not None else None


async def paper_run_heartbeat_loop() -> None:
    last_heartbeat = await latest_paper_run_heartbeat()
    last_observed_at = last_heartbeat["created_at"] if last_heartbeat else None
    identity_changed = last_heartbeat is not None and paper_run_identity(last_heartbeat.get("payload")) != configured_paper_run_identity()
    delay = next_shadow_refresh_delay(
        last_observed_at,
        settings.paper_run_heartbeat_seconds,
        datetime.now(timezone.utc),
    )
    if identity_changed:
        delay = 0.0
    if delay:
        await asyncio.sleep(delay)
    while True:
        try:
            bot = await bot_status()
            if bot["freqtrade"] != "unavailable":
                await record_event("paper_run_heartbeat", paper_run_heartbeat_payload())
        except Exception:
            # A missing heartbeat is deliberately left as evidence of an
            # interruption. It must never affect execution.
            pass
        await asyncio.sleep(settings.paper_run_heartbeat_seconds)


async def latest_global_context() -> dict | None:
    async with app.state.database.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT payload, observed_at FROM market_context_snapshots WHERE source = 'coingecko' AND context_type = 'global' ORDER BY id DESC LIMIT 1"
        )
    if row is None:
        return None
    payload = row["payload"]
    stale_after_seconds = context_stale_after_seconds("coingecko", "global")
    status, age_seconds = context_availability(row["observed_at"], stale_after_seconds)
    return {
        "status": status,
        "observed_at": row["observed_at"],
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "context": json.loads(payload) if isinstance(payload, str) else payload,
    }


async def latest_context(source: str, context_type: str) -> dict | None:
    async with app.state.database.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT payload, observed_at FROM market_context_snapshots WHERE source = $1 AND context_type = $2 ORDER BY id DESC LIMIT 1",
            source,
            context_type,
        )
    if row is None:
        return None
    payload = row["payload"]
    stale_after_seconds = context_stale_after_seconds(source, context_type)
    status, age_seconds = context_availability(row["observed_at"], stale_after_seconds)
    return {
        "status": status,
        "observed_at": row["observed_at"],
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "context": json.loads(payload) if isinstance(payload, str) else payload,
    }


def orderbook_collection_projection(
    observations: int,
    minimum_observations: int,
    last_observed_at: datetime | None,
    refresh_seconds: int,
) -> dict[str, int | datetime | None]:
    """Describe remaining collection work without treating partial data as evidence."""
    remaining_observations = max(minimum_observations - observations, 0)
    estimated_ready_at = (
        last_observed_at + timedelta(seconds=remaining_observations * refresh_seconds)
        if last_observed_at is not None and remaining_observations
        else last_observed_at if observations >= minimum_observations else None
    )
    return {
        "remaining_observations": remaining_observations,
        "estimated_ready_at": estimated_ready_at,
    }

def orderbook_coverage_status(observations: int, coverage_ratio: float | None) -> str:
    if observations == 0:
        return "not_collected"
    if observations < settings.orderbook_shadow_min_observations:
        return "collecting"
    if coverage_ratio is not None and coverage_ratio < 0.95:
        return "insufficient_coverage"
    return "ready_for_research"


async def orderbook_coverage() -> dict:
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(
            "SELECT date_bin(($1::int * INTERVAL '1 second'), observed_at, TIMESTAMPTZ '2000-01-01') AS bucket, "
            "MIN(observed_at) AS observed_at "
            "FROM market_context_snapshots WHERE source = 'binance' AND context_type = 'orderbook' "
            "GROUP BY bucket ORDER BY bucket ASC",
            settings.orderbook_shadow_refresh_seconds,
        )
    segment = latest_continuous_orderbook_segment(
        [(row["bucket"], row["observed_at"]) for row in rows],
        settings.orderbook_shadow_continuity_gap_seconds,
    )
    observations = len(segment)
    first_observed_at = segment[0][1] if segment else None
    last_observed_at = segment[-1][1] if segment else None
    coverage_ratio: float | None = None
    if observations and first_observed_at and last_observed_at:
        elapsed_seconds = max((last_observed_at - first_observed_at).total_seconds(), 0)
        expected = int(elapsed_seconds // settings.orderbook_shadow_refresh_seconds) + 1
        coverage_ratio = min(observations / expected, 1.0) if expected else 1.0
    projection = orderbook_collection_projection(
        observations,
        settings.orderbook_shadow_min_observations,
        last_observed_at,
        settings.orderbook_shadow_refresh_seconds,
    )
    return {
        "status": orderbook_coverage_status(observations, coverage_ratio),
        "observations": observations,
        "minimum_observations": settings.orderbook_shadow_min_observations,
        "coverage_ratio": coverage_ratio,
        "first_observed_at": first_observed_at,
        "last_observed_at": last_observed_at,
        "remaining_observations": projection["remaining_observations"],
        "estimated_ready_at": projection["estimated_ready_at"],
        "continuity_gap_seconds": settings.orderbook_shadow_continuity_gap_seconds,
    }


def latest_continuous_orderbook_segment(
    observations: list[tuple[datetime, datetime]], max_gap_seconds: int
) -> list[tuple[datetime, datetime]]:
    """Keep raw history but evaluate only the series after the last outage."""
    segment: list[tuple[datetime, datetime]] = []
    previous_bucket: datetime | None = None
    for bucket, observed_at in observations:
        if previous_bucket is not None and (bucket - previous_bucket).total_seconds() > max_gap_seconds:
            segment = []
        segment.append((bucket, observed_at))
        previous_bucket = bucket
    return segment


def summarize_forward_returns(samples: list[tuple[float, float]]) -> dict[str, dict[str, float | int | None]]:
    buckets = {
        "bid_heavy": [future_return for imbalance, future_return in samples if imbalance >= 0.1],
        "neutral": [future_return for imbalance, future_return in samples if -0.1 < imbalance < 0.1],
        "ask_heavy": [future_return for imbalance, future_return in samples if imbalance <= -0.1],
    }
    summary: dict[str, dict[str, float | int | None]] = {}
    for name, returns in buckets.items():
        summary[name] = {
            "samples": len(returns),
            "mean_return_bps": fmean(returns) * 10_000 if returns else None,
            "positive_rate": sum(value > 0 for value in returns) / len(returns) if returns else None,
        }
    return summary


async def orderbook_forward_returns(pair: str, horizon_minutes: int) -> list[tuple[float, float]]:
    query = """
        WITH snapshots AS (
            SELECT observed_at,
                (payload->'pairs'->$1->>'mid_price')::double precision AS mid_price,
                (payload->'pairs'->$1->>'imbalance')::double precision AS imbalance
            FROM market_context_snapshots
            WHERE source = 'binance' AND context_type = 'orderbook'
        )
        SELECT current.imbalance, (future.mid_price / current.mid_price) - 1 AS forward_return
        FROM snapshots AS current
        JOIN LATERAL (
            SELECT mid_price
            FROM snapshots
            WHERE observed_at >= current.observed_at + ($2::int * INTERVAL '1 minute')
              AND observed_at <= current.observed_at + (($2::int + 10) * INTERVAL '1 minute')
              AND mid_price > 0
            ORDER BY observed_at ASC
            LIMIT 1
        ) AS future ON TRUE
        WHERE current.mid_price > 0 AND current.imbalance IS NOT NULL
        ORDER BY current.observed_at ASC
    """
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(query, pair, horizon_minutes)
    return [(float(row["imbalance"]), float(row["forward_return"])) for row in rows]


async def latest_ai_assessment() -> dict | None:
    async with app.state.database.acquire() as connection:
        row = await connection.fetchrow("SELECT assessment, observed_at FROM ai_shadow_assessments ORDER BY id DESC LIMIT 1")
    if row is None:
        return None
    assessment = row["assessment"]
    stale_after_seconds = context_stale_after_seconds("ai", "assessment")
    status, age_seconds = context_availability(row["observed_at"], stale_after_seconds)
    return {
        "status": status,
        "observed_at": row["observed_at"],
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "assessment": json.loads(assessment) if isinstance(assessment, str) else assessment,
    }


async def store_context(source: str, context_type: str, payload: dict, observed_at: datetime) -> None:
    async with app.state.database.acquire() as connection:
        await connection.execute(
            "INSERT INTO market_context_snapshots (source, context_type, payload, observed_at) VALUES ($1, $2, $3::jsonb, $4)",
            source,
            context_type,
            json.dumps(payload),
            observed_at,
        )
    await app.state.redis.set(f"market-context:{context_type}", json.dumps(payload), ex=900)


async def store_headlines(headlines: list[NewsHeadline]) -> int:
    if not headlines:
        return 0
    rows = [(headline.source, headline.title, headline.url, headline.published_at) for headline in headlines if headline.url]
    if not rows:
        return 0
    stored = 0
    async with app.state.database.acquire() as connection:
        for row in rows:
            result = await connection.execute(
                "INSERT INTO news_headlines (source, title, url, published_at) VALUES ($1, $2, $3, $4) ON CONFLICT (url) DO NOTHING",
                *row,
            )
            if result.endswith("1"):
                stored += 1
    return stored


async def run_ai_shadow_analysis(request: ShadowAnalysisRequest):
    provider = settings.ai_shadow_provider.lower()
    if provider == "openai" and settings.openai_api_key and settings.openai_model:
        return await analyze_with_openai_compatible(settings.openai_base_url, settings.openai_api_key, settings.openai_model, request, provider)
    if provider == "deepseek" and settings.deepseek_api_key and settings.deepseek_model:
        return await analyze_with_openai_compatible(settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model, request, provider)
    if provider == "gemini" and settings.gemini_api_key and settings.gemini_model:
        return await analyze_with_gemini(settings.gemini_base_url, settings.gemini_api_key, settings.gemini_model, request)
    raise HTTPException(status_code=409, detail="AI shadow provider is not configured")


async def save_ai_shadow_assessment(request: ShadowAnalysisRequest, assessment, input_source: str) -> dict:
    payload = assessment.model_dump(mode="json")
    audit_payload = {**payload, "input_source": input_source, "prompt_version": PROMPT_VERSION}
    async with app.state.database.acquire() as connection:
        await connection.execute(
            "INSERT INTO ai_shadow_assessments (provider, model, request, assessment, observed_at) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)",
            assessment.provider,
            assessment.model,
            json.dumps({**request.model_dump(mode="json"), "input_source": input_source, "prompt_version": PROMPT_VERSION}),
            json.dumps(audit_payload),
            assessment.observed_at,
        )
    await record_event("ai_shadow_assessment_recorded", audit_payload)
    return audit_payload


async def require_ai_shadow_interval() -> None:
    async with app.state.database.acquire() as connection:
        last_run = await connection.fetchval("SELECT created_at FROM ai_shadow_assessments ORDER BY id DESC LIMIT 1")
    if last_run is None:
        return
    elapsed = (datetime.now(timezone.utc) - last_run).total_seconds()
    if elapsed < settings.ai_shadow_min_interval_seconds:
        wait = int(settings.ai_shadow_min_interval_seconds - elapsed)
        raise HTTPException(status_code=429, detail=f"AI shadow cooldown active; retry in {wait} seconds")


async def purge_older_than(table: str, days: int) -> int:
    timestamp_columns = {
        "bot_audit_events": "created_at",
        "market_context_snapshots": "created_at",
        "news_headlines": "collected_at",
        "ai_shadow_assessments": "created_at",
    }
    column = timestamp_columns.get(table)
    if column is None:
        raise ValueError("Unsupported retention table")
    async with app.state.database.acquire() as connection:
        result = await connection.execute(f"DELETE FROM {table} WHERE {column} < NOW() - ($1::int * INTERVAL '1 day')", days)
    return int(result.rsplit(" ", 1)[-1])


async def count_older_than(table: str, days: int) -> int:
    timestamp_columns = {
        "bot_audit_events": "created_at",
        "market_context_snapshots": "created_at",
        "news_headlines": "collected_at",
        "ai_shadow_assessments": "created_at",
    }
    column = timestamp_columns.get(table)
    if column is None:
        raise ValueError("Unsupported retention table")
    async with app.state.database.acquire() as connection:
        return int(await connection.fetchval(f"SELECT COUNT(*) FROM {table} WHERE {column} < NOW() - ($1::int * INTERVAL '1 day')", days))


async def retention_counts() -> dict[str, int]:
    return {
        "audit_events": await count_older_than("bot_audit_events", settings.audit_retention_days),
        "market_context": await count_older_than("market_context_snapshots", settings.context_retention_days),
        "news_headlines": await count_older_than("news_headlines", settings.news_retention_days),
        "ai_shadow": await count_older_than("ai_shadow_assessments", settings.ai_shadow_retention_days),
    }


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


@app.get("/internal/kill-switch")
async def kill_switch_state() -> dict:
    """Return the entry gate only while the audit/control dependencies are healthy.

    The strategy treats any non-success response as a rejected entry. Checking
    both stores here therefore makes a database or Redis outage fail closed,
    instead of allowing un-auditable trades to be opened.
    """
    try:
        await app.state.database.fetchval("SELECT 1")
        enabled = await app.state.redis.get("trading:kill-switch") == "enabled"
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Trading control state unavailable") from exc
    return {"enabled": enabled}


@app.get("/v1/bot/status")
async def bot_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.freqtrade_api_url}/api/v1/status", headers=await freqtrade_headers(client))
            response.raise_for_status()
            return {"mode": settings.trading_environment, "freqtrade": response.json()}
    except httpx.HTTPError as exc:
        return {"mode": settings.trading_environment, "freqtrade": "unavailable", "detail": str(exc)}


@app.get("/v1/bot/performance")
async def bot_performance() -> dict:
    """Expose Freqtrade's aggregate profit report without exchange credentials."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.freqtrade_api_url}/api/v1/profit", headers=await freqtrade_headers(client))
            response.raise_for_status()
            return {"status": "available", "mode": settings.trading_environment, "performance": response.json()}
    except httpx.HTTPError as exc:
        return {"status": "unavailable", "mode": settings.trading_environment, "detail": str(exc)}


@app.get("/v1/operational-state")
async def operational_state() -> dict:
    bot = await bot_status()
    return {
        "environment": settings.trading_environment,
        "kill_switch_enabled": await app.state.redis.get("trading:kill-switch") == "enabled",
        "freqtrade_reachable": bot["freqtrade"] != "unavailable",
    }


def paper_run_status(
    observations: int, first_observed_at: datetime | None, last_observed_at: datetime | None, now: datetime
) -> str:
    if observations == 0 or first_observed_at is None or last_observed_at is None:
        return "not_started"
    if (now - last_observed_at).total_seconds() > settings.paper_run_continuity_gap_seconds:
        return "interrupted"
    if (now - first_observed_at).total_seconds() < settings.paper_run_required_days * 86_400:
        return "collecting"
    return "ready_for_release_evidence"


def paper_run_identity(payload: object) -> tuple[str, str, str, str]:
    """Identify the exact paper configuration that produced an evidence segment."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return (
        str(payload.get("strategy") or "unknown"),
        str(payload.get("profile") or "unknown"),
        str(payload.get("revision") or "unknown"),
        str(payload.get("source_sha256") or "unknown"),
    )


def latest_continuous_paper_run_segment(rows: list[dict]) -> tuple[list[dict], tuple[str, str, str, str] | None]:
    """Restart release evidence on a continuity gap or frozen-identity change."""
    segment: list[dict] = []
    identity: tuple[str, str, str, str] | None = None
    previous: datetime | None = None
    for row in rows:
        observed_at = row["created_at"]
        row_identity = paper_run_identity(row.get("payload"))
        changed_identity = identity is not None and row_identity != identity
        interrupted = previous is not None and (observed_at - previous).total_seconds() > settings.paper_run_continuity_gap_seconds
        if changed_identity or interrupted:
            segment = []
        if not segment:
            identity = row_identity
        segment.append(row)
        previous = observed_at
    return segment, identity


async def paper_run_summary() -> dict:
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(
            "SELECT created_at, payload FROM bot_audit_events WHERE event_type = 'paper_run_heartbeat' ORDER BY created_at ASC"
        )
    now = datetime.now(timezone.utc)
    segment, identity = latest_continuous_paper_run_segment(list(rows))
    first_observed_at = segment[0]["created_at"] if segment else None
    last_observed_at = segment[-1]["created_at"] if segment else None
    duration_seconds = max((now - first_observed_at).total_seconds(), 0) if first_observed_at else 0
    expected_observations = int(duration_seconds // settings.paper_run_heartbeat_seconds) + 1 if first_observed_at else 0
    coverage_ratio = min(len(segment) / expected_observations, 1.0) if expected_observations else None
    return {
        "status": paper_run_status(len(segment), first_observed_at, last_observed_at, now),
        "observations": len(segment),
        "expected_observations": expected_observations,
        "coverage_ratio": coverage_ratio,
        "required_days": settings.paper_run_required_days,
        "first_observed_at": first_observed_at,
        "last_observed_at": last_observed_at,
        "strategy": identity[0] if identity else None,
        "profile": identity[1] if identity else None,
        "revision": identity[2] if identity else None,
        "source_sha256": identity[3] if identity else None,
    }


def release_readiness_checks(operations: dict, market: dict, paper_run: dict) -> list[dict[str, str | bool]]:
    """Expose only evidence-backed release checks; missing proof stays blocked."""
    return [
        {
            "key": "quant_validation",
            "passed": False,
            "detail": "Strategi aktif belum lolos quant gate yang dibekukan.",
        },
        {
            "key": "eight_week_paper_run",
            "passed": paper_run.get("status") == "ready_for_release_evidence"
            and paper_run.get("revision") not in {None, "unknown", "unqualified"}
            and isinstance(paper_run.get("source_sha256"), str)
            and len(paper_run["source_sha256"]) == 64,
            "detail": (
                "Delapan minggu paper run kontinu telah tercatat."
                if paper_run.get("status") == "ready_for_release_evidence"
                and paper_run.get("revision") not in {None, "unknown", "unqualified"}
                and isinstance(paper_run.get("source_sha256"), str)
                and len(paper_run["source_sha256"]) == 64
                else "Delapan minggu paper run kontinu dengan satu revisi strategi yang memenuhi syarat belum tercatat."
            ),
        },
        {
            "key": "execution_engine",
            "passed": bool(operations.get("freqtrade_reachable")),
            "detail": "Control API Freqtrade dapat dihubungi." if operations.get("freqtrade_reachable") else "Control API Freqtrade tidak dapat dihubungi.",
        },
        {
            "key": "kill_switch_ready",
            "passed": operations.get("kill_switch_enabled") is False,
            "detail": "Kill-switch siap digunakan." if operations.get("kill_switch_enabled") is False else "Kill-switch sedang memblokir entry baru.",
        },
        {
            "key": "binance_market",
            "passed": bool(market.get("reachable")),
            "detail": "BTCUSDT dan ETHUSDT berstatus dapat diperdagangkan." if market.get("reachable") else "Status market Binance belum tersedia.",
        },
        {
            "key": "clock_synchronized",
            "passed": market.get("clock_synchronized") is True,
            "detail": "Jam host sudah sinkron dengan Binance." if market.get("clock_synchronized") is True else "Jam host perlu disinkronkan dengan Binance.",
        },
    ]


@app.get("/v1/release/readiness")
async def release_readiness() -> dict:
    operations, market, paper_run = await asyncio.gather(operational_state(), binance_market_status(), paper_run_summary())
    checks = release_readiness_checks(operations, market, paper_run)
    return {
        "ready": all(bool(check["passed"]) for check in checks),
        "environment": settings.trading_environment,
        "checks": checks,
        "paper_run": paper_run,
    }


@app.get("/v1/paper-run")
async def paper_run() -> dict:
    return await paper_run_summary()


@app.get("/v1/market/binance/status")
async def binance_market_status() -> dict:
    cache_key = "market:binance-connectivity"
    cached = await app.state.redis.get(cache_key)
    if cached:
        return json.loads(cached)
    try:
        result = await fetch_market_connectivity(settings.binance_public_base_url)
    except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "reachable": False,
            "pairs": {},
            "clock_synchronized": False,
            "detail": "Binance public market data unavailable",
        }
        await record_event("binance_market_connectivity_failed", {"detail": str(exc)})
    await app.state.redis.set(cache_key, json.dumps(result), ex=60)
    return result


@app.get("/v1/context/orderbook")
async def orderbook_context() -> dict:
    context = await latest_context("binance", "orderbook")
    return context or {"status": "not_collected", "mode": "shadow"}


@app.get("/v1/context/orderbook/coverage")
async def orderbook_context_coverage() -> dict:
    return await orderbook_coverage()


@app.get("/v1/research/orderbook/report")
async def orderbook_research_report() -> dict:
    """Expose only the pre-registered microstructure comparisons to the cockpit."""
    coverage = await orderbook_coverage()
    pairs = list(WATCHED_SYMBOLS)
    horizons = [60, 240]
    if coverage["status"] != "ready_for_research":
        return {
            "status": coverage["status"],
            "mode": "shadow",
            "coverage": coverage,
            "pairs": pairs,
            "horizons_minutes": horizons,
            "evaluations": [],
        }
    samples = await asyncio.gather(
        *(orderbook_forward_returns(pair, horizon) for pair in pairs for horizon in horizons)
    )
    evaluations = [
        {
            "pair": pair,
            "horizon_minutes": horizon,
            "summary": summarize_forward_returns(pair_samples),
        }
        for (pair, horizon), pair_samples in zip(
            ((pair, horizon) for pair in pairs for horizon in horizons), samples, strict=True
        )
    ]
    return {
        "status": "evaluated",
        "mode": "shadow",
        "coverage": coverage,
        "pairs": pairs,
        "horizons_minutes": horizons,
        "evaluations": evaluations,
    }


@app.get("/v1/research/orderbook/forward-returns")
async def orderbook_forward_return_research(pair: str = "BTCUSDT", horizon_minutes: int = 60) -> dict:
    if pair not in WATCHED_SYMBOLS:
        raise HTTPException(status_code=422, detail="Pair is outside the order-book shadow watchlist")
    if horizon_minutes not in (60, 240):
        raise HTTPException(status_code=422, detail="Only pre-declared 60 or 240 minute horizons are supported")
    coverage = await orderbook_coverage()
    if coverage["status"] != "ready_for_research":
        return {
            "status": coverage["status"],
            "pair": pair,
            "horizon_minutes": horizon_minutes,
            "coverage": coverage,
            "summary": None,
        }
    samples = await orderbook_forward_returns(pair, horizon_minutes)
    return {
        "status": "evaluated",
        "pair": pair,
        "horizon_minutes": horizon_minutes,
        "coverage": coverage,
        "summary": summarize_forward_returns(samples),
    }


@app.get("/v1/context/fusion")
async def context_fusion() -> dict:
    global_context = await latest_global_context()
    macro_context = await latest_context("fred", "macro")
    ai_shadow = await latest_ai_assessment()
    fresh_global = global_context if global_context and global_context["status"] == "available" else None
    fresh_macro = macro_context if macro_context and macro_context["status"] == "available" else None
    fresh_ai = ai_shadow if ai_shadow and ai_shadow["status"] == "available" else None
    recommendation = recommend_context_risk(
        fresh_global["context"] if fresh_global else None,
        fresh_macro["context"] if fresh_macro else None,
        fresh_ai["assessment"] if fresh_ai else None,
    )
    return {
        "recommendation": recommendation.as_dict(),
        "inputs_available": {
            "global_market": fresh_global is not None,
            "macro": fresh_macro is not None,
            "ai": fresh_ai is not None,
        },
        "stale_inputs": {
            "global_market": bool(global_context and global_context["status"] == "stale"),
            "macro": bool(macro_context and macro_context["status"] == "stale"),
            "ai": bool(ai_shadow and ai_shadow["status"] == "stale"),
        },
    }


@app.get("/v1/context/shadow-snapshot")
async def context_shadow_snapshot() -> dict:
    """Return current advisory inputs without creating an execution decision."""
    global_context, macro_context, orderbook_context, ai_shadow = await asyncio.gather(
        latest_global_context(),
        latest_context("fred", "macro"),
        latest_context("binance", "orderbook"),
        latest_ai_assessment(),
    )
    async with app.state.database.acquire() as connection:
        headline_count = int(await connection.fetchval("SELECT COUNT(*) FROM news_headlines"))
    return {
        "available": any(
            context is not None and context["status"] == "available"
            for context in (global_context, macro_context, orderbook_context, ai_shadow)
        ) or headline_count > 0,
        "mode": "shadow",
        "inputs": {
            "global_market": global_context,
            "macro": macro_context,
            "orderbook": orderbook_context,
            "ai": ai_shadow,
            "news_headline_count": headline_count,
        },
        "execution_effect": "none",
    }


@app.get("/v1/research/experiments")
async def research_experiments() -> dict:
    """Expose experiment intent and gate requirements to the local cockpit."""
    return {"experiments": experiment_catalog()}


@app.post("/v1/maintenance/retention")
async def run_retention(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    removed = {
        "audit_events": await purge_older_than("bot_audit_events", settings.audit_retention_days),
        "market_context": await purge_older_than("market_context_snapshots", settings.context_retention_days),
        "news_headlines": await purge_older_than("news_headlines", settings.news_retention_days),
        "ai_shadow": await purge_older_than("ai_shadow_assessments", settings.ai_shadow_retention_days),
    }
    await record_event("retention_completed", {"removed": removed})
    return {"status": "completed", "removed": removed}


@app.get("/v1/maintenance/retention/preview")
async def preview_retention(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    return {
        "status": "preview",
        "would_remove": await retention_counts(),
        "retention_days": {
            "audit_events": settings.audit_retention_days,
            "market_context": settings.context_retention_days,
            "news_headlines": settings.news_retention_days,
            "ai_shadow": settings.ai_shadow_retention_days,
        },
    }


@app.get("/v1/context/global")
async def global_context() -> dict:
    context = await latest_global_context()
    return context or {"status": "not_collected", "mode": "shadow"}


@app.post("/v1/context/global/refresh")
async def refresh_global_context(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    try:
        payload = await refresh_global_context_from_provider()
    except GLOBAL_CONTEXT_PROVIDER_ERRORS as exc:
        raise HTTPException(status_code=503, detail="Global market context provider unavailable") from exc
    return {"status": "refreshed", "context": payload}


@app.get("/v1/context/macro")
async def macro_context() -> dict:
    context = await latest_context("fred", "macro")
    return context or {"status": "not_collected", "mode": "shadow"}


@app.post("/v1/context/macro/refresh")
async def refresh_macro_context(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    if not settings.fred_api_key:
        raise HTTPException(status_code=409, detail="FRED_API_KEY is not configured")
    try:
        context = await fetch_macro_context(settings.fred_base_url, settings.fred_api_key)
    except httpx.HTTPError as exc:
        await record_event("macro_context_refresh_failed", {"source": "fred", "detail": str(exc)})
        raise HTTPException(status_code=503, detail="Macro context provider unavailable") from exc
    payload = context.as_dict()
    await store_context("fred", "macro", payload, context.observed_at)
    await record_event("macro_context_refreshed", {"source": "fred", **payload})
    return {"status": "refreshed", "context": payload}


@app.get("/v1/news/headlines")
async def news_headlines(limit: int = 20) -> dict:
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(
            "SELECT source, title, url, published_at, collected_at FROM news_headlines ORDER BY published_at DESC NULLS LAST, id DESC LIMIT $1",
            min(max(limit, 1), 50),
        )
    return {"mode": "shadow", "headlines": [dict(row) for row in rows]}


@app.post("/v1/news/headlines/refresh")
async def refresh_news_headlines(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    if not settings.news_api_key:
        raise HTTPException(status_code=409, detail="NEWS_API_KEY is not configured")
    try:
        headlines = await fetch_crypto_headlines(settings.news_api_base_url, settings.news_api_key)
    except httpx.HTTPError as exc:
        await record_event("news_refresh_failed", {"source": "newsapi", "detail": str(exc)})
        raise HTTPException(status_code=503, detail="News provider unavailable") from exc
    stored = await store_headlines(headlines)
    await record_event("news_headlines_refreshed", {"source": "newsapi", "received": len(headlines), "stored": stored})
    return {"status": "refreshed", "mode": "shadow", "received": len(headlines), "stored": stored, "headlines": [headline.as_dict() for headline in headlines]}


@app.get("/v1/ai/shadow/latest")
async def latest_ai_shadow() -> dict:
    latest = await latest_ai_assessment()
    if latest is None:
        return {"status": "not_collected", "mode": "shadow"}
    return latest


@app.post("/v1/ai/shadow/analyze")
async def analyze_ai_shadow(request: ShadowAnalysisRequest, x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    await require_ai_shadow_interval()
    provider = settings.ai_shadow_provider.lower()
    try:
        assessment = await run_ai_shadow_analysis(request)
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        await record_event("ai_shadow_analysis_failed", {"provider": provider, "detail": str(exc)})
        raise HTTPException(status_code=503, detail="AI shadow provider unavailable or returned invalid JSON") from exc
    payload = await save_ai_shadow_assessment(request, assessment, "operator_headlines")
    return {"status": "recorded", "assessment": payload}


@app.post("/v1/ai/shadow/analyze-latest-news")
async def analyze_latest_news(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(
            "SELECT title FROM news_headlines ORDER BY published_at DESC NULLS LAST, id DESC LIMIT 20"
        )
    headlines = [str(row["title"]) for row in rows]
    if not headlines:
        raise HTTPException(status_code=409, detail="No stored headlines available for AI shadow analysis")
    await require_ai_shadow_interval()
    request = ShadowAnalysisRequest(headlines=headlines)
    provider = settings.ai_shadow_provider.lower()
    try:
        assessment = await run_ai_shadow_analysis(request)
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        await record_event("ai_shadow_analysis_failed", {"provider": provider, "input_source": "latest_news", "detail": str(exc)})
        raise HTTPException(status_code=503, detail="AI shadow provider unavailable or returned invalid JSON") from exc
    payload = await save_ai_shadow_assessment(request, assessment, "latest_news")
    return {"status": "recorded", "assessment": payload}


@app.get("/v1/decisions")
async def decisions(limit: int = 50) -> list[dict]:
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch("SELECT id, event_type, payload, created_at FROM bot_audit_events ORDER BY id DESC LIMIT $1", min(max(limit, 1), 100))
    return [normalize_audit_event(dict(row)) for row in rows]


@app.get("/v1/decisions/summary")
async def decision_summary(limit: int = 200) -> dict:
    """Read-only explanation of recent HOLD and risk decisions for the cockpit."""
    async with app.state.database.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, event_type, payload, created_at FROM bot_audit_events ORDER BY id DESC LIMIT $1",
            min(max(limit, 1), 500),
        )
    return summarize_decision_events([normalize_audit_event(dict(row)) for row in rows])


@app.post("/internal/freqtrade", status_code=202)
async def freqtrade_webhook(payload: dict = Body()) -> dict:
    """Accept lifecycle events from the Freqtrade container only.

    This endpoint is used on the Compose bridge network only. It does not expose
    credentials in URL paths or webhook payloads.
    """
    event_type = str(payload.get("event_type", "freqtrade_event"))
    event_payload = payload
    if event_type == "strategy_event" and isinstance(payload.get("message"), str):
        try:
            parsed = json.loads(payload["message"])
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            event_type = str(parsed.pop("event_type", "strategy_event"))
            event_payload = parsed
    await record_event(event_type, {"source": "freqtrade", **event_payload})
    return {"status": "accepted"}


@app.post("/v1/bot/stop")
async def stop_bot(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    await app.state.redis.set("trading:kill-switch", "enabled")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(f"{settings.freqtrade_api_url}/api/v1/stop", headers=await freqtrade_headers(client))
        response.raise_for_status()
    await record_event("bot_stop_requested", {"source": "local_api"})
    return {"status": "stop_requested"}


@app.post("/v1/bot/resume")
async def resume_bot(x_bot_control_token: str | None = Header(default=None)) -> dict:
    if x_bot_control_token != settings.bot_control_token:
        raise HTTPException(status_code=401, detail="Invalid bot control token")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(f"{settings.freqtrade_api_url}/api/v1/start", headers=await freqtrade_headers(client))
        response.raise_for_status()
    await app.state.redis.delete("trading:kill-switch")
    await record_event("bot_resume_requested", {"source": "local_api"})
    return {"status": "resume_requested"}
