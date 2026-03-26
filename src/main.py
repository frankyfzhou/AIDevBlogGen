"""CLI entry point — orchestrates the full blog generation pipeline."""
from __future__ import annotations

import argparse
import logging
import sys

from .news_fetcher import fetch_all_news
from .content_generator import generate_blog_post
from .publisher import write_post, git_commit_and_push


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AIDevBlogGen — Generate weekly AI development blog posts",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Write the post locally but skip git commit/push",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    opts = parser.parse_args(args)
    _setup_logging(opts.verbose)

    logger = logging.getLogger(__name__)

    # Step 1: Fetch news
    logger.info("=== Step 1/3: Fetching AI development news ===")
    news_items = fetch_all_news()
    if not news_items:
        logger.error("No news items found. Aborting.")
        return 1
    logger.info("Collected %d top stories", len(news_items))

    # Step 2: Generate blog post
    logger.info("=== Step 2/3: Generating blog post via LLM ===")
    try:
        post = generate_blog_post(news_items)
    except Exception as exc:
        logger.error("Blog generation failed: %s", exc)
        return 1
    logger.info("Post generated: %s", post.title)

    # Step 3: Publish
    logger.info("=== Step 3/3: Publishing ===")
    filepath = write_post(post)
    logger.info("Blog post written to: %s", filepath)

    if not opts.no_push:
        success = git_commit_and_push(filepath, post.title)
        if not success:
            logger.warning("Git push failed — post is saved locally at %s", filepath)
            return 1
        logger.info("Successfully committed and pushed!")
    else:
        logger.info("--no-push specified; skipping git operations")

    logger.info("=== Done! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
