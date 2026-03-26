"""LLM-powered blog post generation from ranked news items."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from openai import OpenAI, RateLimitError, BadRequestError, AuthenticationError
from pydantic import BaseModel

from .config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_FALLBACK_API_KEY, LLM_FALLBACK_BASE_URL, LLM_FALLBACK_MODEL,
    NewsItem,
)

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


# ── Prompt construction ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert technical blogger who writes a weekly column called "AI Dev Weekly" \
covering the latest developments in AI-assisted software development.

Your audience is software developers and engineering managers who want to stay current \
with AI tools, frameworks, and techniques that impact their daily work.

Writing guidelines:
- Tone: informative, practical, accessible — not academic or hype-driven
- Structure: clear sections with descriptive headings
- For each story: explain WHAT happened, WHY it matters for developers, and HOW they can use it
- Include concrete code snippets, tool commands, or practical examples where relevant
- Use markdown formatting (code blocks with language tags, bold for emphasis, links)
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

def _try_generate(
    client: OpenAI,
    model: str,
    news_items: list[NewsItem],
    max_retries: int = 5,
) -> BlogPost:
    """Attempt generation with a single provider. Raises on exhaustion."""
    use_structured = True

    for attempt in range(max_retries):
        try:
            if use_structured:
                response = client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(news_items)},
                    ],
                    response_format=BlogPost,
                    temperature=0.7,
                    max_tokens=4096,
                )
                post = response.choices[0].message.parsed
                if post is not None:
                    logger.info("Generated post: %s (%d sections)", post.title, len(post.sections))
                    return post
                raise RuntimeError("LLM returned empty structured output.")
            else:
                # Fallback: JSON mode with manual parsing
                json_instruction = (
                    "\n\nIMPORTANT: Respond ONLY with a valid JSON object matching this schema:\n"
                    '{"title": "string", "description": "string", "tags": ["string"], '
                    '"cover_keywords": "string", '
                    '"introduction": "string", "sections": [{"heading": "string", "body": "string"}], '
                    '"conclusion": "string", "sources": [{"title": "string", "url": "string"}]}\n'
                    "No markdown, no code fences, just raw JSON."
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT + json_instruction},
                        {"role": "user", "content": _build_user_prompt(news_items)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=4096,
                )
                raw = response.choices[0].message.content
                data = json.loads(raw)
                post = BlogPost(**data)
                logger.info("Generated post (json fallback): %s (%d sections)", post.title, len(post.sections))
                return post
        except BadRequestError as exc:
            if "response format" in str(exc).lower() or "json_schema" in str(exc).lower():
                logger.info("Structured output not supported, falling back to JSON mode")
                use_structured = False
                continue
            raise
        except RateLimitError as exc:
            wait = 2 ** attempt * 5
            if attempt == max_retries - 1:
                raise
            logger.warning("Rate limited (attempt %d/%d). Waiting %ds...", attempt + 1, max_retries, wait)
            time.sleep(wait)

    raise RuntimeError(f"Generation failed after {max_retries} retries with {model}.")


def generate_blog_post(news_items: list[NewsItem]) -> BlogPost:
    """Generate a structured blog post, falling back to a secondary provider if needed."""
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. Add it to your .env file or environment."
        )

    # --- Primary provider ---
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    logger.info("Generating blog post with %s from %d news items...", LLM_MODEL, len(news_items))

    try:
        return _try_generate(client, LLM_MODEL, news_items)
    except (RateLimitError, RuntimeError, AuthenticationError) as primary_exc:
        if not LLM_FALLBACK_API_KEY:
            raise RuntimeError(
                f"Primary LLM failed ({primary_exc}) and no fallback is configured. "
                "Set LLM_FALLBACK_API_KEY / LLM_FALLBACK_MODEL / LLM_FALLBACK_BASE_URL."
            ) from primary_exc

        # --- Fallback provider ---
        logger.warning(
            "Primary LLM (%s) failed: %s — switching to fallback (%s)",
            LLM_MODEL, primary_exc, LLM_FALLBACK_MODEL,
        )
        fallback_client = OpenAI(api_key=LLM_FALLBACK_API_KEY, base_url=LLM_FALLBACK_BASE_URL)
        return _try_generate(fallback_client, LLM_FALLBACK_MODEL, news_items)
