from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class NewsHeadline:
    title: str
    source: str
    url: str
    published_at: datetime | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def deduplicate_headlines(headlines: list[NewsHeadline]) -> list[NewsHeadline]:
    seen: set[str] = set()
    unique: list[NewsHeadline] = []
    for headline in headlines:
        identity = normalized_title(headline.title)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        unique.append(headline)
    return unique


def parse_newsapi_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


async def fetch_crypto_headlines(base_url: str, api_key: str, limit: int = 20) -> list[NewsHeadline]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/everything",
            params={
                "q": "(bitcoin OR ethereum OR cryptocurrency)",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": min(max(limit, 1), 100),
                "apiKey": api_key,
            },
        )
        response.raise_for_status()
    articles = response.json().get("articles", [])
    headlines = [
        NewsHeadline(
            title=str(article["title"]).strip(),
            source=str(article.get("source", {}).get("name", "unknown")).strip() or "unknown",
            url=str(article.get("url", "")).strip(),
            published_at=parse_newsapi_timestamp(article.get("publishedAt")),
        )
        for article in articles
        if isinstance(article, dict) and isinstance(article.get("title"), str) and article["title"].strip()
    ]
    return deduplicate_headlines(headlines)
