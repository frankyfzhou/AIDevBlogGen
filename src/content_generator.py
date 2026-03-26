"""LLM-powered blog post generation from ranked news items."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openai import OpenAI
from pydantic import BaseModel

from .config import OPENAI_API_KEY, OPENAI_MODEL, NewsItem

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
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file or environment."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    logger.info("Generating blog post with %s from %d news items...", OPENAI_MODEL, len(news_items))

    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(news_items)},
        ],
        response_format=BlogPost,
        temperature=0.7,
        max_tokens=4096,
    )

    post = response.choices[0].message.parsed
    if post is None:
        # Fallback: try to extract from content if structured parsing failed
        raise RuntimeError("LLM returned empty structured output. Check model compatibility.")

    logger.info("Generated post: %s (%d sections)", post.title, len(post.sections))
    return post
