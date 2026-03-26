"""Configuration constants and news source definitions."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
BLOG_CONTENT_DIR = ROOT_DIR / "blog" / "content" / "posts"
TEMPLATE_DIR = ROOT_DIR / "templates"
CACHE_DIR = ROOT_DIR / ".cache"

# ── API Keys ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Fetcher Settings ─────────────────────────────────────────────────────────
MAX_STORIES = 8  # Top N stories to include in a blog post
FETCH_TIMEOUT = 15  # Seconds per HTTP request
CACHE_TTL_HOURS = 6
HN_TOP_STORIES_LIMIT = 80  # How many HN stories to scan

# ── AI-relevance keywords (case-insensitive matching) ────────────────────────
AI_KEYWORDS: list[str] = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "gpt", "chatgpt", "openai", "anthropic",
    "claude", "gemini", "copilot", "github copilot", "coding assistant",
    "code generation", "agent", "ai agent", "agentic", "rag",
    "retrieval augmented", "fine-tuning", "fine tuning", "transformer",
    "diffusion", "stable diffusion", "midjourney", "dall-e",
    "neural network", "nlp", "natural language", "computer vision",
    "hugging face", "langchain", "vector database", "embedding",
    "prompt engineering", "ai safety", "alignment", "rlhf",
    "developer tools", "devtools", "ide", "vscode",
]

# ── News Sources ─────────────────────────────────────────────────────────────

@dataclass
class RSSSource:
    name: str
    url: str
    authority_score: float = 1.0  # Higher = more authoritative


RSS_SOURCES: list[RSSSource] = [
    RSSSource("OpenAI Blog", "https://openai.com/blog/rss.xml", authority_score=2.0),
    RSSSource("Google AI Blog", "https://blog.google/technology/ai/rss/", authority_score=2.0),
    RSSSource("Anthropic", "https://www.anthropic.com/rss.xml", authority_score=2.0),
    RSSSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", authority_score=1.5),
    RSSSource("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/", authority_score=1.5),
    RSSSource("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", authority_score=1.0),
    RSSSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", authority_score=1.0),
    RSSSource("MIT Technology Review", "https://www.technologyreview.com/feed/", authority_score=1.5),
]

DEVTO_API_URL = "https://dev.to/api/articles"
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
REDDIT_SUBREDDITS: list[str] = ["MachineLearning", "artificial"]

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
