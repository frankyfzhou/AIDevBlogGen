# AIDevBlogGen — Copilot Instructions

## Project Overview

This repository is an automated weekly blog generator focused on AI-assisted software development news. It fetches news from multiple sources, uses an LLM to generate a polished blog post, and publishes to a Hugo static site hosted on GitHub Pages.

## Architecture

- **`src/`** — Python pipeline: `config.py` → `news_fetcher.py` → `content_generator.py` → `publisher.py` → `main.py`
- **`blog/`** — Hugo static site with PaperMod theme
- **`templates/`** — Jinja2 templates for Hugo markdown rendering
- **`tests/`** — pytest test suite with mocked external calls
- **`.github/workflows/`** — GitHub Actions for weekly generation and Hugo deploy

## Code Conventions

- Python 3.9+ with `from __future__ import annotations`
- Type hints on all function signatures
- Logging via `logging` module (not print statements)
- Pydantic models for structured data exchange
- External API calls always have timeout and error handling
- Tests use `unittest.mock` to mock all HTTP/API calls

## Key Commands

- Run pipeline: `python -m src.main --no-push --verbose`
- Run tests: `python -m pytest tests/ -v`
- Preview blog: `cd blog && hugo server -D`

## When Editing

- Never commit API keys or secrets
- When modifying news sources, update both `src/config.py` and the test mocks in `tests/`
- Blog post template changes go in `templates/blog_post.md.j2`
- Hugo config changes go in `blog/hugo.toml`
