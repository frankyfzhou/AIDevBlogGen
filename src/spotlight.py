"""Feature Spotlight discovery — dynamically finds deep-dive topics."""
from __future__ import annotations

import json
import logging
import re

import requests
from pydantic import BaseModel

from .config import BLOG_CONTENT_DIR, FETCH_TIMEOUT, ROOT_DIR, SPOTLIGHT_VELOCITY_THRESHOLD
from .content_generator import call_llm

logger = logging.getLogger(__name__)


# ── Pydantic models ─────────────────────────────────────────────────────────

class ToolInfo(BaseModel):
    name: str
    docs_url: str
    changelog_url: str
    rss_url: str | None = None


class SpotlightTopic(BaseModel):
    tool: str
    feature: str
    source_url: str
    justification: str
    source_content: str = ""  # fetched page text, populated after topic selection


# ── Step 1: Discover dominant tools ──────────────────────────────────────────

TOOL_DISCOVERY_PROMPT = """\
What are the 1-2 dominant AI coding assistants/agents that senior developers \
are actually using day-to-day right now? Not every tool on the market — just \
the ones with real mainstream adoption.

For each, provide: name, official docs URL, changelog or release notes URL, \
and RSS/blog feed URL if available. If there is a notable newcomer gaining \
real traction, include it as a third. Maximum 3.

Respond ONLY with valid JSON matching this schema:
{"tools": [{"name": "string", "docs_url": "string", "changelog_url": "string", "rss_url": "string or null"}]}
No markdown, no explanation — just raw JSON.
"""


def discover_tools() -> list[ToolInfo]:
    """Ask the LLM for currently dominant AI coding tools, then validate URLs."""
    raw = call_llm(TOOL_DISCOVERY_PROMPT)
    try:
        from .content_generator import _extract_json
        data = json.loads(_extract_json(raw))
        tools = [ToolInfo(**t) for t in data.get("tools", [])]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse tool discovery response: %s", exc)
        return []

    # Validate URLs — discard tools with unreachable docs
    validated = []
    for tool in tools:
        try:
            resp = requests.get(tool.docs_url, timeout=FETCH_TIMEOUT, allow_redirects=True)
            if resp.status_code < 400:
                validated.append(tool)
                logger.info("Validated tool: %s (%s)", tool.name, tool.docs_url)
            else:
                logger.warning("Tool %s docs URL returned %d, skipping", tool.name, resp.status_code)
        except requests.RequestException as exc:
            logger.warning("Tool %s docs URL unreachable: %s", tool.name, exc)

    return validated


# ── Step 2: Fetch changelogs ─────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace to extract readable text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)  # HTML entities
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_urls(html: str, base_url: str) -> list[str]:
    """Extract href URLs from HTML, returning only absolute http(s) URLs."""
    from urllib.parse import urljoin
    raw_urls = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    urls: list[str] = []
    seen: set[str] = set()
    for u in raw_urls:
        full = urljoin(base_url, u)
        if full.startswith("http") and full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def fetch_changelogs(tools: list[ToolInfo]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Fetch changelog text and URLs for each tool.

    Returns (changelogs, changelog_urls) where:
    - changelogs: {tool_name: plain_text}
    - changelog_urls: {tool_name: [url1, url2, ...]}
    """
    changelogs: dict[str, str] = {}
    changelog_urls: dict[str, list[str]] = {}
    for tool in tools:
        try:
            resp = requests.get(tool.changelog_url, timeout=FETCH_TIMEOUT, allow_redirects=True)
            if resp.status_code < 400:
                text = _html_to_text(resp.text)
                text = text[:3000]
                changelogs[tool.name] = text
                changelog_urls[tool.name] = _extract_urls(resp.text, tool.changelog_url)[:50]
                logger.info("Fetched changelog for %s (%d chars, %d URLs)",
                            tool.name, len(text), len(changelog_urls[tool.name]))
            else:
                logger.warning("Changelog for %s returned %d", tool.name, resp.status_code)
        except requests.RequestException as exc:
            logger.warning("Failed to fetch changelog for %s: %s", tool.name, exc)
    return changelogs, changelog_urls


# ── Step 3+4: Pick and validate spotlight topic ─────────────────────────────

def _read_past_post_titles() -> list[str]:
    """Read titles from past blog post frontmatter (YAML title: lines)."""
    titles = []
    if not BLOG_CONTENT_DIR.exists():
        return titles
    for md_file in sorted(BLOG_CONTENT_DIR.glob("*.md")):
        for line in md_file.read_text(encoding="utf-8").splitlines()[:15]:
            if line.startswith("title:"):
                title = line.split("title:", 1)[1].strip().strip('"').strip("'")
                titles.append(title)
                break
    return titles


TOPIC_SELECTION_PROMPT = """\
You are selecting a Feature Spotlight topic for a weekly AI developer blog.

The target audience is senior engineers who use AI coding tools daily.
Skip basics. Pick a specific, actionable, deep feature.

Here are the dominant AI coding tools and their recent changes:

{changelog_context}

Here are REAL URLs extracted from the changelog pages above. You MUST pick your \
source_url from this list — do NOT invent or guess URLs:
{available_urls}

We have already published these blog posts — do NOT pick a topic we've already covered:
{past_posts}

Pick ONE feature to spotlight that:
1. Is recently released or updated (within the last month if possible)
2. Has NOT been covered in our past blog posts listed above
3. Is useful for day-to-day development (not niche or theoretical)
4. Has enough depth for 800-1200 words of practical content
5. The source_url MUST be one of the URLs listed above — never invent a URL

Respond ONLY with valid JSON:
{{"tool": "string", "feature": "string", "source_url": "string", "justification": "string"}}
No markdown, no explanation — just raw JSON.
"""


_MAX_TOPIC_RETRIES = 2


def select_spotlight_topic(
    changelogs: dict[str, str],
    changelog_urls: dict[str, list[str]] | None = None,
) -> SpotlightTopic | None:
    """Use LLM to pick a spotlight topic based on changelogs and past coverage.

    Retries up to _MAX_TOPIC_RETRIES times if the LLM picks an invalid URL.
    """
    if not changelogs:
        logger.info("No changelogs available, skipping spotlight")
        return None

    changelog_context = ""
    for tool_name, text in changelogs.items():
        changelog_context += f"\n--- {tool_name} Recent Changes ---\n{text}\n"

    # Build list of real URLs the LLM must choose from
    all_urls: list[str] = []
    if changelog_urls:
        for urls in changelog_urls.values():
            all_urls.extend(urls)
    available_urls = "\n".join(f"- {u}" for u in all_urls) if all_urls else "(no URLs extracted)"

    past_titles = _read_past_post_titles()
    past_posts = "\n".join(f"- {t}" for t in past_titles) if past_titles else "(none yet)"

    prompt = TOPIC_SELECTION_PROMPT.format(
        changelog_context=changelog_context,
        available_urls=available_urls,
        past_posts=past_posts,
    )

    for attempt in range(_MAX_TOPIC_RETRIES):
        raw = call_llm(prompt=prompt)

        try:
            from .content_generator import _extract_json
            data = json.loads(_extract_json(raw))
            topic = SpotlightTopic(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse spotlight topic (attempt %d): %s", attempt + 1, exc)
            continue

        # Check that the URL is from the allowed list (if we have one)
        if all_urls and topic.source_url not in all_urls:
            logger.warning("LLM picked URL not in allowed list (attempt %d): %s", attempt + 1, topic.source_url)
            prompt += "\n\nYour previous answer used an invalid URL. Pick a source_url ONLY from the list above."
            continue

        # Validate the source URL and fetch content for the generation prompt
        try:
            resp = requests.get(topic.source_url, timeout=FETCH_TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                logger.warning("Spotlight source URL returned %d (attempt %d)", resp.status_code, attempt + 1)
                prompt += f"\n\nYour previous answer used URL {topic.source_url} which returned HTTP {resp.status_code}. Pick a different, working URL from the list."
                continue
            topic.source_content = _html_to_text(resp.text)[:4000]
            logger.info("Spotlight topic validated: %s — %s (%d chars of source content)",
                         topic.tool, topic.feature, len(topic.source_content))
        except requests.RequestException as exc:
            logger.warning("Spotlight source URL unreachable (attempt %d): %s", attempt + 1, exc)
            continue

        return topic

    logger.warning("Failed to find valid spotlight topic after %d attempts", _MAX_TOPIC_RETRIES)
    return None


# ── Main entry point ─────────────────────────────────────────────────────────

def should_skip_spotlight(news_items: list) -> bool:
    """Check if top story velocity exceeds threshold (breaking news mode)."""
    if not news_items:
        return True
    top_score = news_items[0].score if news_items else 0
    if top_score > SPOTLIGHT_VELOCITY_THRESHOLD:
        logger.info("Top story velocity %.2f > %.2f threshold — breaking news mode, skipping spotlight",
                     top_score, SPOTLIGHT_VELOCITY_THRESHOLD)
        return True
    return False


def discover_spotlight(news_items: list) -> SpotlightTopic | None:
    """Full spotlight discovery pipeline. Returns None if spotlight should be skipped."""
    if should_skip_spotlight(news_items):
        return None

    # Step 1: Discover tools
    logger.info("=== Spotlight: Discovering dominant AI coding tools ===")
    tools = discover_tools()
    if not tools:
        logger.warning("No validated tools found, skipping spotlight")
        return None

    # Step 2: Fetch changelogs
    logger.info("=== Spotlight: Fetching changelogs ===")
    changelogs, changelog_urls = fetch_changelogs(tools)

    # Step 3+4: Pick and validate topic
    logger.info("=== Spotlight: Selecting topic ===")
    topic = select_spotlight_topic(changelogs, changelog_urls)

    if topic:
        logger.info("Spotlight selected: %s — %s", topic.tool, topic.feature)
    else:
        logger.info("No suitable spotlight topic found, will generate news-only post")

    return topic
