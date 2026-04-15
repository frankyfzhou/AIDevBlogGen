"""Tests for the news fetcher module."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import NewsItem, RSSSource
from src.news_fetcher import (
    _compute_final_score,
    _deduplicate,
    _is_ai_relevant,
    _keyword_score,
    _recency_score,
    fetch_all_news,
    fetch_devto,
    fetch_hackernews,
    fetch_reddit,
    fetch_rss,
)


# ── Keyword & relevance tests ───────────────────────────────────────────────

class TestKeywordScoring:
    def test_high_relevance(self):
        score = _keyword_score("GPT-4 is a large language model from OpenAI")
        assert score > 0.5

    def test_no_relevance(self):
        score = _keyword_score("How to cook pasta at home")
        assert score == 0.0

    def test_empty_string(self):
        assert _keyword_score("") == 0.0

    def test_is_ai_relevant_true(self):
        assert _is_ai_relevant("New AI coding assistant released")

    def test_is_ai_relevant_false(self):
        assert not _is_ai_relevant("Best restaurants in New York")


class TestRecencyScore:
    def test_today(self):
        now = datetime.now(timezone.utc)
        assert _recency_score(now) > 0.9

    def test_one_week_old(self):
        from datetime import timedelta
        old = datetime.now(timezone.utc) - timedelta(days=7)
        score = _recency_score(old)
        assert 0.4 < score < 0.6

    def test_none_date(self):
        assert _recency_score(None) == 0.3

    def test_very_old(self):
        from datetime import timedelta
        old = datetime.now(timezone.utc) - timedelta(days=30)
        assert _recency_score(old) == 0.0


# ── Deduplication tests ──────────────────────────────────────────────────────

class TestDeduplication:
    def _make_item(self, title: str, url: str) -> NewsItem:
        return NewsItem(
            title=title, url=url, source="test", summary="",
            published_date=None, score=1.0, tags=[],
        )

    def test_exact_url_dedup(self):
        items = [
            self._make_item("Story A", "https://example.com/a"),
            self._make_item("Story B", "https://example.com/a"),
        ]
        result = _deduplicate(items)
        assert len(result) == 1

    def test_fuzzy_title_dedup(self):
        items = [
            self._make_item("OpenAI releases GPT-5 model", "https://a.com"),
            self._make_item("OpenAI releases GPT-5 model today", "https://b.com"),
        ]
        result = _deduplicate(items)
        assert len(result) == 1

    def test_different_stories_kept(self):
        items = [
            self._make_item("OpenAI releases GPT-5", "https://a.com"),
            self._make_item("Google launches Gemini 2", "https://b.com"),
        ]
        result = _deduplicate(items)
        assert len(result) == 2


# ── HackerNews fetcher tests ────────────────────────────────────────────────

class TestFetchHackerNews:
    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json")
    def test_returns_ai_stories(self, mock_get, mock_write, mock_read):
        # Mock topstories endpoint
        mock_get.side_effect = lambda url, **kw: self._mock_hn_api(url)
        items = fetch_hackernews()
        assert len(items) >= 1
        assert items[0].source == "HackerNews"

    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json", return_value=None)
    def test_handles_api_failure(self, mock_get, mock_write, mock_read):
        items = fetch_hackernews()
        assert items == []

    @staticmethod
    def _mock_hn_api(url: str):
        if "topstories" in url:
            return [1, 2, 3]
        item_id = url.split("/")[-1].replace(".json", "")
        stories = {
            "1": {"type": "story", "title": "New AI coding agent released", "url": "https://ai.com/1", "time": 1711324800, "score": 300},
            "2": {"type": "story", "title": "Best pizza in NYC", "url": "https://food.com/2", "time": 1711324800, "score": 50},
            "3": {"type": "story", "title": "LLM benchmark results", "url": "https://ml.com/3", "time": 1711324800, "score": 200},
        }
        return stories.get(item_id)


# ── Dev.to fetcher tests ────────────────────────────────────────────────────

class TestFetchDevto:
    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json")
    def test_returns_articles(self, mock_get, mock_write, mock_read):
        mock_get.return_value = [
            {
                "title": "Building AI agents with LangChain",
                "description": "A guide to AI agent development",
                "url": "https://dev.to/test/ai-agents",
                "published_at": "2026-03-20T10:00:00Z",
                "positive_reactions_count": 150,
                "tag_list": ["ai", "langchain"],
            },
        ]
        items = fetch_devto()
        assert len(items) == 1
        assert items[0].source == "Dev.to"

    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json", return_value=None)
    def test_handles_api_failure(self, mock_get, mock_write, mock_read):
        items = fetch_devto()
        assert items == []


# ── Reddit fetcher tests ────────────────────────────────────────────────────

class TestFetchReddit:
    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json")
    def test_returns_posts(self, mock_get, mock_write, mock_read):
        mock_get.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "GPT-5 released with amazing coding ability",
                            "url": "https://openai.com/gpt5",
                            "permalink": "/r/MachineLearning/comments/abc/",
                            "selftext": "This is huge for AI development",
                            "created_utc": 1711324800,
                            "ups": 500,
                        }
                    },
                ]
            }
        }
        items = fetch_reddit()
        assert len(items) >= 1
        assert "reddit" in items[0].tags

    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher._get_json")
    def test_deduplicates_across_endpoints(self, mock_get, mock_write, mock_read):
        """Same post appearing in both /top and /hot should only appear once."""
        mock_get.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "same_post",
                            "title": "Claude Code source leaked",
                            "url": "https://reddit.com/r/ClaudeAI/comments/xyz/",
                            "permalink": "/r/ClaudeAI/comments/xyz/",
                            "selftext": "The source code for Claude Code was leaked",
                            "created_utc": 1711324800,
                            "ups": 2000,
                        }
                    },
                ]
            }
        }
        items = fetch_reddit()
        # Same id returned from both /top and /hot — should be deduped
        titles = [i.title for i in items]
        assert titles.count("Claude Code source leaked") == 1


# ── RSS fetcher tests ───────────────────────────────────────────────────────

class TestFetchRSS:
    @patch("src.news_fetcher._read_cache", return_value=None)
    @patch("src.news_fetcher._write_cache")
    @patch("src.news_fetcher.feedparser")
    def test_returns_items(self, mock_fp, mock_write, mock_read):
        mock_entry = MagicMock()
        mock_entry.get = lambda key, default="": {
            "title": "Advancing AI Safety Research",
            "summary": "New techniques for AI alignment",
            "link": "https://openai.com/blog/safety",
        }.get(key, default)
        mock_entry.published_parsed = (2026, 3, 20, 10, 0, 0, 0, 0, 0)

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        source = RSSSource("OpenAI Blog", "https://openai.com/blog/rss.xml", authority_score=2.0)
        items = fetch_rss(source)
        assert len(items) == 1
        assert items[0].source == "OpenAI Blog"


# ── Integration: fetch_all_news ──────────────────────────────────────────────

class TestFetchAllNews:
    @patch("src.news_fetcher.fetch_rss", return_value=[])
    @patch("src.news_fetcher.fetch_reddit", return_value=[])
    @patch("src.news_fetcher.fetch_devto", return_value=[])
    @patch("src.news_fetcher.fetch_hackernews")
    def test_aggregates_and_ranks(self, mock_hn, mock_devto, mock_reddit, mock_rss):
        now = datetime.now(timezone.utc)
        mock_hn.return_value = [
            NewsItem("AI coding revolution", "https://a.com", "HN", "Big news", now, 0.8, ["ai"]),
            NewsItem("New LLM benchmark", "https://b.com", "HN", "Results", now, 0.5, ["ai"]),
        ]
        items = fetch_all_news()
        assert len(items) <= 8
        assert len(items) >= 1
        # Should be sorted by score descending
        if len(items) > 1:
            assert items[0].score >= items[1].score
