"""Multi-source news aggregation with relevance ranking."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import feedparser
import requests

from .config import (
    AI_KEYWORDS,
    BLOG_CONTENT_DIR,
    CACHE_DIR,
    CACHE_TTL_HOURS,
    DEVTO_API_URL,
    FETCH_TIMEOUT,
    HN_API_BASE,
    HN_TOP_STORIES_LIMIT,
    HTTP_USER_AGENT,
    MAX_STORIES,
    REDDIT_SUBREDDITS,
    RSS_SOURCES,
    NewsItem,
    RSSSource,
)

logger = logging.getLogger(__name__)

# ── HTTP helpers ─────────────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({"User-Agent": HTTP_USER_AGENT})


def _get_json(url: str, **kwargs: Any) -> Any:
    """GET request returning parsed JSON. Returns None on failure."""
    try:
        resp = _session.get(url, timeout=FETCH_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


# ── Caching ──────────────────────────────────────────────────────────────────

def _cache_key(label: str) -> Path:
    h = hashlib.md5(label.encode()).hexdigest()[:12]  # noqa: S324
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{h}.json"


def _read_cache(label: str) -> list[dict[str, Any]] | None:
    path = _cache_key(label)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > CACHE_TTL_HOURS * 3600:
            return None
        items = data.get("items", [])
        # Parse date strings back to datetime objects
        for item in items:
            pd = item.get("published_date")
            if pd and isinstance(pd, str):
                try:
                    item["published_date"] = datetime.fromisoformat(pd)
                except ValueError:
                    item["published_date"] = None
        return items
    except Exception:
        return None


def _write_cache(label: str, items: list[dict[str, Any]]) -> None:
    path = _cache_key(label)
    path.write_text(json.dumps({"cached_at": time.time(), "items": items}, default=str))


# ── Keyword & scoring helpers ────────────────────────────────────────────────

_kw_pattern = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in AI_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _keyword_score(text: str) -> float:
    """Return score 0-1 based on how many AI keywords appear in text."""
    if not text:
        return 0.0
    matches = set(_kw_pattern.findall(text.lower()))
    return min(len(matches) / 3.0, 1.0)


def _recency_score(dt: datetime | None) -> float:
    """Return 0-1 score; 1.0 for today, decaying over 14 days."""
    if dt is None:
        return 0.3  # Unknown date gets a middling score
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (now - dt).total_seconds() / 86400
    if age_days < 0:
        age_days = 0
    return max(0.0, 1.0 - (age_days / 14.0))


def _is_ai_relevant(title: str, summary: str = "") -> bool:
    """Check if a story is relevant to AI/dev topics."""
    text = f"{title} {summary}".lower()
    return bool(_kw_pattern.search(text))


# ── Source fetchers ──────────────────────────────────────────────────────────

def fetch_hackernews() -> list[NewsItem]:
    """Fetch top HackerNews stories filtered for AI relevance."""
    cached = _read_cache("hackernews")
    if cached is not None:
        return [NewsItem(**item) for item in cached]

    story_ids = _get_json(f"{HN_API_BASE}/topstories.json")
    if not story_ids:
        return []

    items: list[NewsItem] = []
    # Fetch stories in parallel, limited to top N
    ids_to_check = story_ids[:HN_TOP_STORIES_LIMIT]

    def _fetch_story(sid: int) -> NewsItem | None:
        data = _get_json(f"{HN_API_BASE}/item/{sid}.json")
        if not data or data.get("type") != "story":
            return None
        title = data.get("title", "")
        url = data.get("url", f"https://news.ycombinator.com/item?id={sid}")
        if not _is_ai_relevant(title):
            return None
        ts = data.get("time")
        pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        points = data.get("score", 0)
        return NewsItem(
            title=title,
            url=url,
            source="HackerNews",
            summary="",
            published_date=pub_date,
            score=points / 500.0,  # Normalize; 500 points → 1.0
            tags=["hackernews"],
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_story, sid): sid for sid in ids_to_check}
        for future in as_completed(futures):
            result = future.result()
            if result:
                items.append(result)

    _write_cache("hackernews", [_item_to_dict(i) for i in items])
    logger.info("HackerNews: fetched %d AI-relevant stories", len(items))
    return items


def fetch_devto() -> list[NewsItem]:
    """Fetch top Dev.to AI articles from the past week."""
    cached = _read_cache("devto")
    if cached is not None:
        return [NewsItem(**item) for item in cached]

    params = {"tag": "ai", "top": 7, "per_page": 25}
    data = _get_json(DEVTO_API_URL, params=params)
    if not data:
        return []

    items: list[NewsItem] = []
    for article in data:
        title = article.get("title", "")
        if not _is_ai_relevant(title, article.get("description", "")):
            continue
        pub_str = article.get("published_at", "")
        pub_date = None
        if pub_str:
            try:
                pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        reactions = article.get("positive_reactions_count", 0)
        items.append(NewsItem(
            title=title,
            url=article.get("url", ""),
            source="Dev.to",
            summary=article.get("description", ""),
            published_date=pub_date,
            score=reactions / 200.0,
            tags=article.get("tag_list", []),
        ))

    _write_cache("devto", [_item_to_dict(i) for i in items])
    logger.info("Dev.to: fetched %d AI articles", len(items))
    return items


def fetch_reddit() -> list[NewsItem]:
    """Fetch top weekly posts from AI-related subreddits."""
    cached = _read_cache("reddit")
    if cached is not None:
        return [NewsItem(**item) for item in cached]

    items: list[NewsItem] = []
    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/top/.json?t=week&limit=20"
        data = _get_json(url)
        if not data or "data" not in data:
            continue
        for child in data["data"].get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            if not _is_ai_relevant(title, post.get("selftext", "")[:300]):
                continue
            ts = post.get("created_utc")
            pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            ups = post.get("ups", 0)
            post_url = post.get("url", "")
            # Prefer external link; fall back to reddit permalink
            if post_url.startswith("/r/") or not post_url.startswith("http"):
                post_url = f"https://www.reddit.com{post.get('permalink', '')}"
            items.append(NewsItem(
                title=title,
                url=post_url,
                source=f"Reddit r/{sub}",
                summary=post.get("selftext", "")[:300],
                published_date=pub_date,
                score=ups / 1000.0,
                tags=["reddit", sub.lower()],
            ))

    _write_cache("reddit", [_item_to_dict(i) for i in items])
    logger.info("Reddit: fetched %d AI posts", len(items))
    return items


def fetch_rss(source: RSSSource) -> list[NewsItem]:
    """Fetch and parse a single RSS feed."""
    cached = _read_cache(f"rss_{source.name}")
    if cached is not None:
        return [NewsItem(**item) for item in cached]

    items: list[NewsItem] = []
    try:
        feed = feedparser.parse(source.url)
    except Exception as exc:
        logger.warning("RSS parse error for %s: %s", source.name, exc)
        return []

    for entry in feed.entries[:20]:
        title = entry.get("title", "")
        summary = entry.get("summary", entry.get("description", ""))
        link = entry.get("link", "")

        # For authoritative sources, include all posts; for general feeds, filter
        if source.authority_score < 1.5 and not _is_ai_relevant(title, summary):
            continue

        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        # Strip HTML from summary
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:300]

        items.append(NewsItem(
            title=title,
            url=link,
            source=source.name,
            summary=clean_summary,
            published_date=pub_date,
            score=source.authority_score * 0.3,  # Base score from authority
            tags=["rss", source.name.lower().replace(" ", "-")],
        ))

    _write_cache(f"rss_{source.name}", [_item_to_dict(i) for i in items])
    logger.info("RSS %s: fetched %d items", source.name, len(items))
    return items


# ── Aggregation & ranking ────────────────────────────────────────────────────

def _item_to_dict(item: NewsItem) -> dict[str, Any]:
    """Serialize a NewsItem so it can be cached as JSON."""
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "summary": item.summary,
        "published_date": item.published_date.isoformat() if item.published_date else None,
        "score": item.score,
        "tags": item.tags,
    }


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Remove duplicate stories by URL and fuzzy title matching."""
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    unique: list[NewsItem] = []

    for item in items:
        # URL dedup
        normalized_url = item.url.rstrip("/").lower()
        if normalized_url in seen_urls:
            continue

        # Fuzzy title dedup
        is_dup = False
        for prev_title in seen_titles:
            if SequenceMatcher(None, item.title.lower(), prev_title).ratio() > 0.75:
                is_dup = True
                break
        if is_dup:
            continue

        seen_urls.add(normalized_url)
        seen_titles.append(item.title.lower())
        unique.append(item)

    return unique


def _compute_final_score(item: NewsItem) -> float:
    """Compute a weighted final score for ranking."""
    kw = _keyword_score(f"{item.title} {item.summary}")
    recency = _recency_score(item.published_date)
    engagement = min(item.score, 1.0)  # Already normalized per-source

    # Weighted combination
    return (kw * 0.35) + (recency * 0.30) + (engagement * 0.35)


def _get_cutoff_date() -> datetime:
    """Determine the news cutoff date based on the last published blog post.

    If <1 month since last post: use last post date as cutoff.
    If >1 month or no posts: use 1 month ago.
    """
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)

    try:
        posts = sorted(BLOG_CONTENT_DIR.glob("*.md"), reverse=True)
        for post_path in posts:
            if post_path.name == ".gitkeep":
                continue
            # Parse date from filename: YYYY-MM-DD-slug.md
            parts = post_path.stem.split("-", 3)
            if len(parts) >= 3:
                try:
                    post_date = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
                    if post_date >= one_month_ago:
                        logger.info("Last post date: %s — fetching news since then", post_date.date())
                        return post_date
                except (ValueError, IndexError):
                    continue
    except Exception as exc:
        logger.warning("Could not read posts directory: %s", exc)

    logger.info("No recent posts found — fetching news from last 30 days")
    return one_month_ago


def _is_within_window(item: NewsItem, cutoff: datetime) -> bool:
    """Check if a news item was published after the cutoff date."""
    if item.published_date is None:
        return True  # Keep items with unknown dates
    dt = item.published_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= cutoff


def fetch_all_news() -> list[NewsItem]:
    """Fetch from all sources, deduplicate, rank, and return top stories."""
    cutoff = _get_cutoff_date()
    all_items: list[NewsItem] = []

    # Run all fetchers in parallel
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = []
        futures.append(pool.submit(fetch_hackernews))
        futures.append(pool.submit(fetch_devto))
        futures.append(pool.submit(fetch_reddit))
        for rss_src in RSS_SOURCES:
            futures.append(pool.submit(fetch_rss, rss_src))

        for future in as_completed(futures):
            try:
                results = future.result()
                all_items.extend(results)
            except Exception as exc:
                logger.error("Fetcher failed: %s", exc)

    logger.info("Total raw items: %d", len(all_items))

    # Filter to time window
    all_items = [item for item in all_items if _is_within_window(item, cutoff)]
    logger.info("After time filter (since %s): %d", cutoff.date(), len(all_items))

    # Deduplicate
    unique = _deduplicate(all_items)
    logger.info("After dedup: %d", len(unique))

    # Score and rank
    for item in unique:
        item.score = _compute_final_score(item)

    unique.sort(key=lambda x: x.score, reverse=True)

    top = unique[:MAX_STORIES]
    logger.info("Top %d stories selected", len(top))
    for i, item in enumerate(top):
        logger.info("  %d. [%.2f] %s (%s)", i + 1, item.score, item.title, item.source)

    return top
