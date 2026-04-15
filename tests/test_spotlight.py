"""Tests for the spotlight discovery module."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.config import NewsItem
from src.spotlight import (
    ToolInfo,
    SpotlightTopic,
    _html_to_text,
    _extract_urls,
    discover_tools,
    fetch_changelogs,
    select_spotlight_topic,
    should_skip_spotlight,
    discover_spotlight,
)


# ── _html_to_text ────────────────────────────────────────────────────────────

class TestHtmlToText:
    def test_strips_tags(self):
        assert _html_to_text("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strips_scripts_and_styles(self):
        html = "<style>body{}</style><script>alert(1)</script><div>Content</div>"
        assert _html_to_text(html) == "Content"

    def test_collapses_whitespace(self):
        assert _html_to_text("<p>a</p>  <p>b</p>") == "a b"

    def test_plain_text_passthrough(self):
        assert _html_to_text("just plain text") == "just plain text"


# ── _extract_urls ────────────────────────────────────────────────────────────

class TestExtractUrls:
    def test_extracts_absolute_urls(self):
        html = '<a href="https://example.com/a">A</a><a href="https://example.com/b">B</a>'
        urls = _extract_urls(html, "https://example.com")
        assert urls == ["https://example.com/a", "https://example.com/b"]

    def test_resolves_relative_urls(self):
        html = '<a href="/changelog/feature-x">X</a>'
        urls = _extract_urls(html, "https://github.blog/changelog/")
        assert urls == ["https://github.blog/changelog/feature-x"]

    def test_deduplicates(self):
        html = '<a href="https://a.com/x">1</a><a href="https://a.com/x">2</a>'
        urls = _extract_urls(html, "https://a.com")
        assert len(urls) == 1


# ── should_skip_spotlight ────────────────────────────────────────────────────

class TestShouldSkipSpotlight:
    def test_skips_on_empty_news(self):
        assert should_skip_spotlight([]) is True

    def test_skips_on_high_velocity(self):
        item = MagicMock(score=0.95)
        assert should_skip_spotlight([item]) is True

    def test_does_not_skip_normal_velocity(self):
        item = MagicMock(score=0.5)
        assert should_skip_spotlight([item]) is False

    @patch("src.spotlight.SPOTLIGHT_VELOCITY_THRESHOLD", 0.9)
    def test_threshold_boundary(self):
        item = MagicMock(score=0.9)
        assert should_skip_spotlight([item]) is False  # Not strictly greater

        item2 = MagicMock(score=0.91)
        assert should_skip_spotlight([item2]) is True


# ── discover_tools ───────────────────────────────────────────────────────────

MOCK_TOOLS_JSON = json.dumps({
    "tools": [
        {
            "name": "GitHub Copilot",
            "docs_url": "https://docs.github.com/copilot",
            "changelog_url": "https://github.blog/changelog/",
            "rss_url": "https://github.blog/feed/",
        },
        {
            "name": "Claude Code",
            "docs_url": "https://docs.anthropic.com/claude-code",
            "changelog_url": "https://docs.anthropic.com/changelog",
            "rss_url": None,
        },
    ]
})


class TestDiscoverTools:
    @patch("src.spotlight.requests.get")
    @patch("src.spotlight.call_llm", return_value=MOCK_TOOLS_JSON)
    def test_returns_validated_tools(self, mock_llm, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        tools = discover_tools()
        assert len(tools) == 2
        assert tools[0].name == "GitHub Copilot"
        assert tools[1].name == "Claude Code"

    @patch("src.spotlight.requests.get")
    @patch("src.spotlight.call_llm", return_value=MOCK_TOOLS_JSON)
    def test_filters_unreachable_tools(self, mock_llm, mock_get):
        # First tool OK, second tool 404
        mock_get.side_effect = [
            MagicMock(status_code=200),
            MagicMock(status_code=404),
        ]
        tools = discover_tools()
        assert len(tools) == 1
        assert tools[0].name == "GitHub Copilot"

    @patch("src.spotlight.call_llm")
    def test_rejects_invalid_url_scheme(self, mock_llm):
        """Tools with non-HTTP(S) URLs are rejected without fetching."""
        mock_llm.return_value = json.dumps({"tools": [
            {"name": "Bad", "docs_url": "file:///etc/passwd", "changelog_url": "ftp://x.com", "rss_url": None},
        ]})
        tools = discover_tools()
        assert tools == []

    @patch("src.spotlight.call_llm", return_value="not json")
    def test_returns_empty_on_parse_error(self, mock_llm):
        tools = discover_tools()
        assert tools == []


# ── fetch_changelogs ─────────────────────────────────────────────────────────

class TestFetchChangelogs:
    @patch("src.spotlight.requests.get")
    def test_fetches_changelog_text_and_urls(self, mock_get):
        html = '<h1>Changelog</h1><p>New feature: X</p><a href="https://a.com/feature-x">Details</a>'
        mock_get.return_value = MagicMock(status_code=200, text=html)
        tools = [ToolInfo(name="TestTool", docs_url="https://a.com", changelog_url="https://a.com/changelog")]
        changelogs, changelog_urls = fetch_changelogs(tools)
        assert "TestTool" in changelogs
        assert "New feature" in changelogs["TestTool"]
        assert "<p>" not in changelogs["TestTool"]
        assert "https://a.com/feature-x" in changelog_urls["TestTool"]

    @patch("src.spotlight.requests.get")
    def test_skips_on_error(self, mock_get):
        from requests import RequestException
        mock_get.side_effect = RequestException("timeout")
        tools = [ToolInfo(name="TestTool", docs_url="https://a.com", changelog_url="https://a.com/changelog")]
        changelogs, changelog_urls = fetch_changelogs(tools)
        assert changelogs == {}
        assert changelog_urls == {}


# ── select_spotlight_topic ───────────────────────────────────────────────────

MOCK_TOPIC_JSON = json.dumps({
    "tool": "GitHub Copilot",
    "feature": "Agent mode with custom tools",
    "source_url": "https://github.blog/changelog/agent-mode",
    "justification": "Major new feature enabling custom tool integration",
})


class TestSelectSpotlightTopic:
    @patch("src.spotlight.requests.get")
    @patch("src.spotlight.call_llm", return_value=MOCK_TOPIC_JSON)
    def test_returns_validated_topic(self, mock_llm, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text="<h1>Agent Mode</h1><p>Details here</p>")
        urls = {"GitHub Copilot": ["https://github.blog/changelog/agent-mode"]}
        topic = select_spotlight_topic({"GitHub Copilot": "changelog text..."}, urls)
        assert topic is not None
        assert topic.tool == "GitHub Copilot"
        assert topic.feature == "Agent mode with custom tools"
        assert "Agent Mode" in topic.source_content
        assert "<h1>" not in topic.source_content

    @patch("src.spotlight.requests.get")
    @patch("src.spotlight.call_llm", return_value=MOCK_TOPIC_JSON)
    def test_rejects_url_not_in_allowed_list(self, mock_llm, mock_get):
        urls = {"GitHub Copilot": ["https://github.blog/changelog/other-feature"]}
        topic = select_spotlight_topic({"GitHub Copilot": "changelog..."}, urls)
        assert topic is None

    @patch("src.spotlight.requests.get")
    @patch("src.spotlight.call_llm", return_value=MOCK_TOPIC_JSON)
    def test_returns_none_on_invalid_source_url(self, mock_llm, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        topic = select_spotlight_topic({"GitHub Copilot": "changelog..."})
        assert topic is None

    def test_returns_none_on_empty_changelogs(self):
        topic = select_spotlight_topic({})
        assert topic is None

    @patch("src.spotlight.call_llm", return_value="not json")
    def test_returns_none_on_parse_error(self, mock_llm):
        topic = select_spotlight_topic({"Tool": "changelog..."})
        assert topic is None


# ── discover_spotlight (integration) ─────────────────────────────────────────

class TestDiscoverSpotlight:
    @patch("src.spotlight.select_spotlight_topic")
    @patch("src.spotlight.fetch_changelogs")
    @patch("src.spotlight.discover_tools")
    def test_full_pipeline(self, mock_tools, mock_changelogs, mock_topic):
        mock_tools.return_value = [
            ToolInfo(name="Copilot", docs_url="https://d.com", changelog_url="https://c.com"),
        ]
        mock_changelogs.return_value = (
            {"Copilot": "new stuff"},
            {"Copilot": ["https://c.com/feature-1"]},
        )
        mock_topic.return_value = SpotlightTopic(
            tool="Copilot", feature="Custom agents",
            source_url="https://c.com/feature-1", justification="New",
        )
        item = MagicMock(score=0.5)
        result = discover_spotlight([item])
        assert result is not None
        assert result.tool == "Copilot"

    def test_skips_on_high_velocity(self):
        item = MagicMock(score=0.95)
        result = discover_spotlight([item])
        assert result is None

    @patch("src.spotlight.discover_tools", return_value=[])
    def test_returns_none_on_no_tools(self, mock_tools):
        item = MagicMock(score=0.5)
        result = discover_spotlight([item])
        assert result is None
