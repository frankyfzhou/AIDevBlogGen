"""LLM-powered blog post generation from ranked news items."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from openai import OpenAI, RateLimitError, BadRequestError
from pydantic import BaseModel

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, NewsItem

logger = logging.getLogger(__name__)


# ── Pydantic models for structured output ────────────────────────────────────

class BlogSection(BaseModel):
    heading: str
    body: str


class BlogPost(BaseModel):
    title: str
    description: str  # SEO meta description, ~150 chars
    tags: list[str]
    introduction: str
    sections: list[BlogSection]
    conclusion: str


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
- Keep the total post between 1500-2500 words
- The conclusion should synthesize themes and offer a forward-looking perspective
- Tags should be lowercase, hyphenated, SEO-friendly (e.g. "ai-coding", "llm-tools")
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
4. An engaging introduction paragraph
5. 3-5 well-structured sections, each covering a story or theme
6. A conclusion with forward-looking perspective

For sections that involve tools or APIs, include a brief code example or CLI command \
that developers can try.
"""


# ── Generation ───────────────────────────────────────────────────────────────

def generate_blog_post(news_items: list[NewsItem]) -> BlogPost:
    """Generate a structured blog post from ranked news items using the LLM."""
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. Add it to your .env file or environment."
        )

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    logger.info("Generating blog post with %s from %d news items...", LLM_MODEL, len(news_items))

    max_retries = 5
    use_structured = True

    for attempt in range(max_retries):
        try:
            if use_structured:
                response = client.beta.chat.completions.parse(
                    model=LLM_MODEL,
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
                    '"introduction": "string", "sections": [{"heading": "string", "body": "string"}], '
                    '"conclusion": "string"}\n'
                    "No markdown, no code fences, just raw JSON."
                )
                response = client.chat.completions.create(
                    model=LLM_MODEL,
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
                raise RuntimeError(f"Rate limit exceeded after {max_retries} retries: {exc}") from exc
            logger.warning("Rate limited (attempt %d/%d). Waiting %ds...", attempt + 1, max_retries, wait)
            time.sleep(wait)

    raise RuntimeError("Blog generation failed after all retries.")
    return post
