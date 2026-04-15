# AIDevBlogGen — Copilot Instructions

## Project Overview

This repository is an automated weekly blog generator focused on AI-assisted software development news. It fetches news from multiple sources, uses an LLM to generate a polished blog post, and publishes to a Hugo static site hosted on GitHub Pages.

## Architecture

- **`src/`** — Python pipeline: `config.py` → `news_fetcher.py` → `spotlight.py` → `content_generator.py` → `publisher.py` → `main.py`
- **`src/spotlight.py`** — Feature Spotlight discovery: identifies dominant AI tools, fetches changelogs, picks deep-dive topics
- **`discovery.json`** — Dynamic source config (keywords, RSS feeds, subreddits, GitHub repos). Updated monthly via `/discover-trends` prompt. Read by `config.py` at runtime; hardcoded fallbacks used if missing.
- **`blog/`** — Hugo static site with PaperMod theme
- **`templates/`** — Jinja2 templates for Hugo markdown rendering
- **`tests/`** — pytest test suite with mocked external calls
- **`.github/workflows/`** — GitHub Actions for weekly generation (Friday) and Hugo deploy

## Code Conventions

- Python 3.11+ with `from __future__ import annotations`
- Type hints on all function signatures
- Logging via `logging` module (not print statements)
- Pydantic models for structured data exchange
- LLM calls via GitHub Copilot SDK (`call_llm()` in `content_generator.py`)
- External API calls always have timeout and error handling
- Tests use `unittest.mock` to mock all HTTP/API calls

## Key Commands

- Run pipeline: `python -m src.main --no-push --verbose`
- Run tests: `python -m pytest tests/ -v`
- Preview blog: `cd blog && hugo server -D`

## LLM Model Usage

- **Two-model system:** `LLM_MODEL` (cheap) and `LLM_MODEL_HEAVY` (premium)
- `claude-haiku-4.5` (0 premium) — tool discovery, topic selection, news-only posts
- `claude-opus-4.6` (3 premium/call) — blog generation with Feature Spotlight only
- When testing locally, set both to `gpt-4.1`: `LLM_MODEL=gpt-4.1 LLM_MODEL_HEAVY=gpt-4.1`
- For CI testing, set repo variables via `gh variable set` then delete after
- Premium budget: ~3 per production run (only spotlight posts use heavy model)

## When Editing

- Never commit API keys or secrets
- LLM calls go through `call_llm()` in `content_generator.py` — uses GitHub Copilot SDK, auth via `GITHUB_TOKEN` env var or `gh auth token`
- When modifying news sources, update `discovery.json` (primary source config). Hardcoded fallbacks live in `src/config.py`. Update test mocks in `tests/` as needed.
- Blog post template changes go in `templates/blog_post.md.j2`
- Hugo config changes go in `blog/hugo.toml`
- Spotlight logic lives in `src/spotlight.py` — mock `call_llm` and `requests.get` in tests
