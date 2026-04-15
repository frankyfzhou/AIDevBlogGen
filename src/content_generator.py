"""LLM-powered blog post generation via GitHub Copilot SDK."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone

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


# ── Copilot SDK LLM interface ───────────────────────────────────────────────

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
    """Make a single LLM call via the Copilot SDK. Returns raw response text."""
    from copilot import CopilotClient, SubprocessConfig
    from copilot.session import PermissionHandler, SystemMessageAppendConfig

    token = _get_github_token()
    config = SubprocessConfig(github_token=token)

    async with CopilotClient(config=config) as client:
        session_kwargs: dict = {
            "on_permission_request": PermissionHandler.approve_all,
            "model": model,
        }
        if working_directory:
            session_kwargs["working_directory"] = working_directory
        if system_message:
            session_kwargs["system_message"] = SystemMessageAppendConfig(
                content=system_message,
            )

        async with await client.create_session(**session_kwargs) as session:
            response = await session.send_and_wait(prompt, timeout=timeout)
            return response.data.content


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
section covering:
- What the feature is and why it matters for day-to-day development workflows
- Real CLI commands, config snippets, or code that a senior engineer would actually run
- Gotchas, edge cases, and non-obvious behavior you know from the docs
- How it composes with other features of the same tool
- Cite the source docs/changelog inline with markdown links

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
        raw = call_llm(
            prompt=prompt,
            model=active_model,
            system_message=system,
        )
        logger.debug("LLM raw response (first 200 chars): %s", repr(raw[:200]) if raw else "<empty>")
        try:
            data = json.loads(_extract_json(raw))
            post = BlogPost(**data)
            logger.info("Generated post: %s (%d sections)", post.title, len(post.sections))
            return post
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == 0:
                logger.warning("JSON parse failed (attempt 1): %s — retrying with stricter prompt", exc)
                prompt += "\n\nPREVIOUS ATTEMPT FAILED TO PARSE. Return ONLY raw JSON. No markdown, no explanation."
                continue
            raise RuntimeError(f"Blog generation failed after 2 attempts: {exc}") from exc

    raise RuntimeError("Blog generation failed unexpectedly.")
