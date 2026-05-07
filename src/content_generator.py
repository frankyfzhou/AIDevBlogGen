"""LLM-powered blog post generation via GitHub Models API (OpenAI-compatible)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel

from .config import LLM_MODEL, LLM_MODEL_HEAVY, LLM_TIMEOUT, ROOT_DIR, NewsItem

logger = logging.getLogger(__name__)


# ── Pydantic models for structured output ────────────────────────────────────

class BlogSection(BaseModel):
    heading: str
    body: str


class SourceLink(BaseModel):
    title: str
    url: str


class BlogPost(BaseModel):
    title: str
    description: str  # SEO meta description, ~150 chars
    tags: list[str]
    cover_keywords: str  # 1-3 word Unsplash search query for the cover image
    introduction: str
    sections: list[BlogSection]
    conclusion: str
    sources: list[SourceLink]


# ── URL validation ───────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Normalize a URL for comparison: lowercase scheme+host, strip trailing slash."""
    url = url.strip()
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
    return normalized


# Matches markdown links [text](url) but NOT image refs ![alt](url)
_LINK_RE = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')


def _validate_blog_urls(
    post: BlogPost,
    news_items: list[NewsItem],
    spotlight: object | None = None,
) -> BlogPost:
    """Validate all URLs in the blog post against an allowlist of input URLs.

    - Removes sources whose URL is not in the allowlist.
    - Strips inline markdown links whose URL is not in the allowlist,
      preserving the link text.
    """
    allowed: set[str] = set()
    for item in news_items:
        allowed.add(_normalize_url(item.url))
    if spotlight and hasattr(spotlight, "source_url") and spotlight.source_url:
        allowed.add(_normalize_url(spotlight.source_url))

    # Filter sources
    valid_sources: list[SourceLink] = []
    for src in post.sources:
        if _normalize_url(src.url) in allowed:
            valid_sources.append(src)
        else:
            logger.warning("Removed unverified source URL: %s", src.url)

    # Sanitise inline links in text fields
    def _sanitize(text: str) -> str:
        def _replace(m: re.Match) -> str:
            link_text, url = m.group(1), m.group(2)
            if _normalize_url(url) in allowed:
                return m.group(0)
            logger.warning("Removed unverified inline URL: %s", url)
            return link_text
        return _LINK_RE.sub(_replace, text)

    sanitized_sections = [
        BlogSection(heading=s.heading, body=_sanitize(s.body))
        for s in post.sections
    ]

    return BlogPost(
        title=post.title,
        description=post.description,
        tags=post.tags,
        cover_keywords=post.cover_keywords,
        introduction=_sanitize(post.introduction),
        sections=sanitized_sections,
        conclusion=_sanitize(post.conclusion),
        sources=valid_sources,
    )


# ── JSON extraction ──────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """Extract JSON from LLM response, stripping markdown fences if present.

    Only strips fences if the response itself is wrapped in them.
    Preserves code fences that appear *inside* JSON string values.
    """
    text = raw.strip()
    # Only strip if the entire response is wrapped in fences
    if text.startswith("```"):
        # Remove opening fence line and closing fence
        lines = text.split("\n")
        # First line is ```json or ```
        lines = lines[1:]
        # Find last ``` and remove it
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                lines = lines[:i]
                break
        text = "\n".join(lines).strip()
    return text


# ── GitHub Models API LLM interface ─────────────────────────────────────────

_GITHUB_MODELS_BASE_URL = "https://models.github.ai/inference"


def _get_github_token() -> str:
    """Get GitHub token from env or gh CLI keyring."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN env var or run 'gh auth login'."
    )


async def _call_llm_async(
    prompt: str,
    model: str,
    working_directory: str | None = None,
    system_message: str | None = None,
    timeout: int = 300,
) -> str:
    """Make a single LLM call via the GitHub Models API. Returns raw response text."""
    from openai import AsyncOpenAI

    token = _get_github_token()
    client = AsyncOpenAI(
        base_url=_GITHUB_MODELS_BASE_URL,
        api_key=token,
    )

    messages: list[dict] = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    response = await asyncio.wait_for(
        client.chat.completions.create(model=model, messages=messages),
        timeout=timeout,
    )
    return response.choices[0].message.content or ""


def call_llm(
    prompt: str,
    model: str | None = None,
    working_directory: str | None = None,
    system_message: str | None = None,
    timeout: int | None = None,
) -> str:
    """Synchronous wrapper for _call_llm_async. Returns raw response text."""
    return asyncio.run(_call_llm_async(
        prompt=prompt,
        model=model or LLM_MODEL,
        working_directory=working_directory,
        system_message=system_message,
        timeout=timeout or LLM_TIMEOUT,
    ))


# ── Prompt construction ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert technical blogger who writes a weekly column called "AI Dev Weekly" \
covering the latest developments in AI-assisted software development.

Your audience is software developers and engineering managers who want to stay current \
with AI tools, frameworks, and techniques that impact their daily work.

Writing guidelines:
- Tone: informative, practical, accessible — not academic or hype-driven
- Structure: clear sections with descriptive headings (no generic subtitles like "Why It Matters" or "How to Use It")
- For each story: cover what changed, its practical impact, and how developers can act on it — woven naturally into prose, not as labeled subsections
- Include concrete code snippets, tool commands, or practical examples where relevant
- Use markdown formatting (code blocks with language tags, bold for emphasis, links)
- Do NOT use bold-text subtitles (e.g. "**What Changed?**", "**Why It Matters**") — write flowing prose instead
- Include 1-2 Mermaid diagrams where they help explain architecture, workflows, or pipelines. \
Use standard markdown code fences with the "mermaid" language tag, e.g.:
  ```mermaid
  graph LR
    A[User Prompt] --> B[LLM] --> C[Generated Code]
  ```
  Good use cases: tool pipelines, data flow, comparison charts, decision trees, system architecture
- IMPORTANT: Use inline hyperlinks to cite sources throughout the text, e.g. [according to OpenAI](https://openai.com/blog/...)
- Every claim or news item MUST link back to its original source URL inline
- Keep the total post between 1500-2500 words
- The conclusion should synthesize themes and offer a forward-looking perspective
- Tags should be lowercase, hyphenated, SEO-friendly (e.g. "ai-coding", "llm-tools")
- cover_keywords: provide 1-3 words for a relevant cover photo (e.g. "artificial intelligence", "robot coding")
- sources: list ALL referenced URLs with a short descriptive title for each

IMPORTANT: Respond ONLY with a valid JSON object matching this schema:
{"title": "string", "description": "string", "tags": ["string"], \
"cover_keywords": "string", \
"introduction": "string", "sections": [{"heading": "string", "body": "string"}], \
"conclusion": "string", "sources": [{"title": "string", "url": "string"}]}
No markdown fences, no explanation — just raw JSON.
"""


def _build_user_prompt(news_items: list[NewsItem]) -> str:
    """Build the user prompt containing this week's top stories."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    stories_text = ""
    for i, item in enumerate(news_items, 1):
        pub = item.published_date.strftime("%Y-%m-%d") if item.published_date else "recent"
        stories_text += f"""
--- Story {i} ---
Title: {item.title}
Source: {item.source}
URL: {item.url}
Date: {pub}
Summary: {item.summary}
"""

    return f"""\
Today is {today}. Write this week's "AI Dev Weekly" blog post based on the following \
top stories from the AI-assisted software development world.

Pick the most interesting and impactful stories (you don't have to cover all of them). \
Group related stories together if it makes narrative sense.

{stories_text}

Generate a complete blog post with:
1. A catchy, specific title (not just "AI Dev Weekly" — include the key theme)
2. An SEO meta description (~150 characters)
3. 5-8 relevant tags
4. 1-3 word cover photo search keywords (e.g. "artificial intelligence")
5. An engaging introduction paragraph
6. 3-5 well-structured sections, each covering a story or theme
7. A conclusion with forward-looking perspective
8. A list of all sources referenced (title + URL for each)

For sections that involve tools or APIs, include a brief code example or CLI command \
that developers can try.

IMPORTANT: Use inline markdown links throughout the body to cite sources. \
Every news story mentioned must include at least one [link to its source](URL). \
Additionally, collect ALL referenced URLs into the "sources" list.
"""


# ── Generation ───────────────────────────────────────────────────────────────

SPOTLIGHT_SYSTEM_ADDENDUM = """
When a Feature Spotlight topic is provided, include a dedicated "Feature Spotlight" \
section. Write it as a cohesive technical deep-dive — NOT a list of labeled subsections. \
Do NOT use bold-text subtitles like "**Why It Matters**" or "**Gotchas**" — instead, \
weave these naturally into the narrative flow.

The spotlight should cover the feature's practical impact on daily dev workflows, \
include real CLI commands / config snippets / code a senior engineer would actually run, \
discuss non-obvious behavior and edge cases inline, explain how it composes with other \
features of the same tool, and cite the source docs/changelog with inline markdown links.

Target audience: senior engineers who already use the tool daily.
Skip basics and marketing fluff. Go straight to practical depth.
Do NOT invent features — only write about what is documented in the provided source content.
800-1200 words for the spotlight section.

The final JSON should include the spotlight as one of the sections (with a heading \
like "Feature Spotlight: [Feature Name]").
"""


def generate_blog_post(
    news_items: list[NewsItem],
    news_json_path: str | None = None,
    spotlight: object | None = None,
) -> BlogPost:
    """Generate a structured blog post using GitHub Copilot SDK.

    News items are included directly in the prompt.
    Past-post dedup is handled by the spotlight discovery step.

    If spotlight is provided (SpotlightTopic), the post includes a
    Feature Spotlight deep-dive section.
    """
    # Use heavy model when spotlight is present, cheap model for news-only
    active_model = LLM_MODEL_HEAVY if spotlight else LLM_MODEL
    logger.info("Generating blog post with %s from %d news items...", active_model, len(news_items))

    system = SYSTEM_PROMPT
    if spotlight:
        system += SPOTLIGHT_SYSTEM_ADDENDUM

    prompt = _build_user_prompt(news_items)

    if spotlight:
        source_docs = getattr(spotlight, 'source_content', '') or ''
        source_section = ""
        if source_docs:
            source_section = f"""

Here is the ACTUAL content from the source page — use this as your primary reference:
---
{source_docs}
---"""

        prompt += f"""

=== FEATURE SPOTLIGHT ===
Include a Feature Spotlight section on this topic:
- Tool: {spotlight.tool}
- Feature: {spotlight.feature}
- Source URL: {spotlight.source_url}
- Why: {spotlight.justification}
{source_section}

IMPORTANT: Base the spotlight ONLY on the source content provided above and your \
knowledge of this tool. Do NOT invent features or capabilities that aren't documented. \
Focus on practical developer workflow impact — real commands, config, and code that \
senior engineers would actually use.
This spotlight section should be 800-1200 words. The news sections should be briefer \
(2-3 stories, ~400-500 words total) to make room for the spotlight.
"""

    for attempt in range(2):
        try:
            raw = call_llm(
                prompt=prompt,
                model=active_model,
                system_message=system,
            )
        except Exception as exc:
            # If the configured heavy model is unavailable, fall back to the cheap model
            # so the pipeline doesn't crash entirely (e.g. when a model is retired).
            if active_model != LLM_MODEL and "not available" in str(exc).lower():
                logger.warning(
                    "Heavy model %s unavailable (%s) — falling back to %s",
                    active_model, exc, LLM_MODEL,
                )
                active_model = LLM_MODEL
                raw = call_llm(
                    prompt=prompt,
                    model=active_model,
                    system_message=system,
                )
            else:
                raise
        logger.debug("LLM raw response (first 200 chars): %s", repr(raw[:200]) if raw else "<empty>")
        try:
            data = json.loads(_extract_json(raw))
            post = BlogPost(**data)
            if not post.sections:
                raise ValueError("Generated post has no sections")
            if not post.introduction.strip():
                raise ValueError("Generated post has empty introduction")
            post = _validate_blog_urls(post, news_items, spotlight)
            logger.info("Generated post: %s (%d sections, %d sources)", post.title, len(post.sections), len(post.sources))
            return post
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == 0:
                logger.warning("JSON parse failed (attempt 1): %s — retrying with stricter prompt", exc)
                prompt += "\n\nPREVIOUS ATTEMPT FAILED TO PARSE. Return ONLY raw JSON. No markdown, no explanation."
                continue
            raise RuntimeError(f"Blog generation failed after 2 attempts: {exc}") from exc

    raise RuntimeError("Blog generation failed unexpectedly.")
