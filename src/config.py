"""Configuration constants and news source definitions."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
BLOG_CONTENT_DIR = ROOT_DIR / "blog" / "content" / "posts"
TEMPLATE_DIR = ROOT_DIR / "templates"
CACHE_DIR = ROOT_DIR / ".cache"
DISCOVERY_FILE = ROOT_DIR / "discovery.json"

# ── LLM Configuration ────────────────────────────────────────────────────────
# Uses GitHub Copilot SDK — model configurable, auth via GITHUB_TOKEN or gh keyring
# LLM_MODEL: cheap model for tool discovery, topic selection, news-only posts
# LLM_MODEL_HEAVY: premium model used ONLY for blog generation with a Feature Spotlight
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4.5")
LLM_MODEL_HEAVY = os.getenv("LLM_MODEL_HEAVY", "claude-opus-4.6")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))  # seconds per LLM call

# ── Fetcher Settings ─────────────────────────────────────────────────────────
MAX_STORIES = 5  # Top N stories to include in a blog post
FETCH_TIMEOUT = 15  # Seconds per HTTP request
CACHE_TTL_HOURS = 6
HN_TOP_STORIES_LIMIT = 80  # How many HN stories to scan

# ── Spotlight Settings ───────────────────────────────────────────────────────
SPOTLIGHT_VELOCITY_THRESHOLD = 0.9  # If top story velocity > this, skip spotlight

# ── AI-relevance keywords (case-insensitive matching) ────────────────────────
# Fallback keywords — used only if discovery.json is missing
_FALLBACK_KEYWORDS: list[str] = [
    "ai", "llm", "copilot", "github copilot", "claude code", "cursor",
    "ai coding assistant", "code generation", "ai agent", "agentic",
    "model context protocol", "mcp", "prompt engineering", "vscode",
]

# ── News Sources ─────────────────────────────────────────────────────────────

@dataclass
class RSSSource:
    name: str
    url: str
    authority_score: float = 1.0  # Higher = more authoritative


# Fallback sources — used only if discovery.json is missing
_FALLBACK_RSS: list[RSSSource] = [
    RSSSource("GitHub Blog", "https://github.blog/feed/", authority_score=2.0),
    RSSSource("OpenAI Blog", "https://openai.com/blog/rss.xml", authority_score=2.0),
    RSSSource("Anthropic", "https://www.anthropic.com/rss.xml", authority_score=2.0),
]

_FALLBACK_SUBREDDITS: list[str] = ["ChatGPTCoding", "GithubCopilot"]


def _load_discovery() -> dict:
    """Load discovery.json or return empty dict."""
    if DISCOVERY_FILE.exists():
        try:
            data = json.loads(DISCOVERY_FILE.read_text(encoding="utf-8"))
            logger.info("Loaded discovery.json (updated: %s)", data.get("updated", "unknown"))
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read discovery.json, using fallbacks: %s", exc)
    else:
        logger.info("No discovery.json found, using fallback config")
    return {}


_discovery = _load_discovery()

AI_KEYWORDS: list[str] = _discovery.get("keywords", _FALLBACK_KEYWORDS)

RSS_SOURCES: list[RSSSource] = [
    RSSSource(s["name"], s["url"], authority_score=s.get("authority", 1.0))
    for s in _discovery.get("rss_sources", [])
] or _FALLBACK_RSS

REDDIT_SUBREDDITS: list[str] = _discovery.get("subreddits", _FALLBACK_SUBREDDITS)

DEVTO_API_URL = "https://dev.to/api/articles"
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

# ── HTTP ─────────────────────────────────────────────────────────────────────
HTTP_USER_AGENT = "AIDevBlogGen/1.0 (weekly blog generator; +https://github.com/AIDevBlogGen)"


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class NewsItem:
    """A normalized news item from any source."""
    title: str
    url: str
    source: str
    summary: str
    published_date: datetime | None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
