"""Publish generated blog posts to Hugo and optionally commit/push."""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from .config import BLOG_CONTENT_DIR, TEMPLATE_DIR, ROOT_DIR
from .content_generator import BlogPost

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def _unsplash_cover_url(keywords: str) -> str:
    """Build a cover image URL. Uses picsum.photos with a seed derived from keywords."""
    # picsum.photos is reliable, free, no API key, and seed ensures consistency
    seed = quote(keywords.strip()) if keywords.strip() else "ai"
    return f"https://picsum.photos/seed/{seed}/1200/630"


def render_blog_post(post: BlogPost) -> str:
    """Render a BlogPost to Hugo-compatible markdown using the Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("blog_post.md.j2")

    now = datetime.now(timezone.utc)
    cover_url = _unsplash_cover_url(getattr(post, "cover_keywords", "artificial intelligence"))

    return template.render(
        title=post.title,
        date=now.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        description=post.description,
        tags=post.tags,
        cover_image_url=cover_url,
        introduction=post.introduction,
        sections=post.sections,
        conclusion=post.conclusion,
        sources=getattr(post, "sources", []),
    )


def write_post(post: BlogPost) -> Path:
    """Write the rendered blog post to the Hugo content directory. Returns the file path."""
    BLOG_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    slug = _slugify(post.title)
    filename = f"{now.strftime('%Y-%m-%d')}-{slug}.md"
    filepath = BLOG_CONTENT_DIR / filename

    content = render_blog_post(post)
    filepath.write_text(content, encoding="utf-8")

    logger.info("Wrote blog post to %s (%d bytes)", filepath, len(content))
    return filepath


def git_commit_and_push(filepath: Path, post_title: str) -> bool:
    """Stage, commit, and push the new blog post. Returns True on success."""
    try:
        rel_path = filepath.relative_to(ROOT_DIR)
    except ValueError:
        rel_path = filepath

    try:
        # Stage
        subprocess.run(
            ["git", "add", str(rel_path)],
            cwd=str(ROOT_DIR),
            check=True,
            capture_output=True,
            text=True,
        )

        # Commit
        commit_msg = f"blog: add weekly post — {post_title}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(ROOT_DIR),
            check=True,
            capture_output=True,
            text=True,
        )

        # Push
        subprocess.run(
            ["git", "push"],
            cwd=str(ROOT_DIR),
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info("Committed and pushed: %s", commit_msg)
        return True

    except subprocess.CalledProcessError as exc:
        logger.error("Git operation failed: %s\nstdout: %s\nstderr: %s",
                      exc, exc.stdout, exc.stderr)
        return False
