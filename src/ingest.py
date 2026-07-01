"""
Ingestion: pull raw items from configured sources and normalize them into
`RawItem`s. Two source types ship by default (RSS, one-off URL); add more
by following the same fetch-and-normalize shape.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class RawItem:
    source_name: str
    title: str
    url: str
    published: str  # ISO string; "" if unknown
    text: str
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def fingerprint(self) -> str:
        """Stable id for dedupe, independent of fetch time."""
        basis = f"{self.url}|{self.title}".encode("utf-8")
        return hashlib.sha256(basis).hexdigest()[:16]


def _extract_clean_text(html: str, url: str) -> str:
    """Best-effort readable-text extraction from raw HTML."""
    try:
        import trafilatura

        extracted = trafilatura.extract(html, url=url, include_comments=False)
        if extracted:
            return extracted.strip()
    except Exception:
        pass
    # Fallback: crude tag strip so the pipeline degrades instead of failing.
    import re

    text = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss(name: str, feed_url: str, limit: int = 20) -> list[RawItem]:
    import feedparser

    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries[:limit]:
        summary = entry.get("summary", "") or entry.get("description", "")
        items.append(
            RawItem(
                source_name=name,
                title=entry.get("title", "(untitled)"),
                url=entry.get("link", feed_url),
                published=entry.get("published", ""),
                text=_extract_clean_text(summary, entry.get("link", feed_url))
                or summary,
            )
        )
    return items


def fetch_url(name: str, url: str) -> list[RawItem]:
    import requests

    resp = requests.get(url, timeout=15, headers={"User-Agent": "signal-pipeline/1.0"})
    resp.raise_for_status()
    text = _extract_clean_text(resp.text, url)
    title = url
    try:
        import re

        m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.S | re.I)
        if m:
            title = m.group(1).strip()
    except Exception:
        pass
    return [
        RawItem(
            source_name=name,
            title=title,
            url=url,
            published="",
            text=text,
        )
    ]


def ingest_all(sources: list[dict]) -> list[RawItem]:
    """Fetch every configured source, skipping ones that fail rather than
    aborting the whole run — a single dead feed shouldn't block the pipeline."""
    items: list[RawItem] = []
    for src in sources:
        try:
            if src["type"] == "rss":
                items.extend(fetch_rss(src["name"], src["url"]))
            elif src["type"] == "url":
                items.extend(fetch_url(src["name"], src["url"]))
            else:
                raise ValueError(f"Unknown source type: {src['type']}")
        except Exception as exc:
            print(f"[ingest] skipping source '{src.get('name')}': {exc}")
    return items


def load_fixtures(items: Iterable[dict]) -> list[RawItem]:
    """Build RawItems directly from fixture dicts — used by `cli.py demo`."""
    return [RawItem(**item) for item in items]
