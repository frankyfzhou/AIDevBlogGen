"""Tests for the spotlight discovery module."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.config import NewsItem
from src.spotlight import (
    ToolInfo,
    SpotlightTopic,
    discover_tools,
    fetch_changelogs,
    select_spotlight_topic,
    should_skip_spotlight,
    discover_spotlight,
)


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

    @patch("src.spotlight.call_llm", return_value="not json")
    def test_returns_empty_on_parse_error(self, mock_llm):
        tools = discover_tools()
        assert tools == []


# ── fetch_changelogs ─────────────────────────────────────────────────────────

class TestFetchChangelogs:
    @patch("src.spotlight.requests.get")
    def test_fetches_changelog_text(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text="New feature: X\nBug fix: Y")
        tools = [ToolInfo(name="TestTool", docs_url="https://a.com", changelog_url="https://a.com/changelog")]
        result = fetch_changelogs(tools)
        assert "TestTool" in result
        assert "New feature" in result["TestTool"]

    @patch("src.spotlight.requests.get")
    def test_skips_on_error(self, mock_get):
        from requests import RequestException
        mock_get.side_effect = RequestException("timeout")
        tools = [ToolInfo(name="TestTool", docs_url="https://a.com", changelog_url="https://a.com/changelog")]
        result = fetch_changelogs(tools)
        assert result == {}


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
        mock_get.return_value = MagicMock(status_code=200)
        topic = select_spotlight_topic({"GitHub Copilot": "changelog text..."})
        assert topic is not None
        assert topic.tool == "GitHub Copilot"
        assert topic.feature == "Agent mode with custom tools"

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
        mock_changelogs.return_value = {"Copilot": "new stuff"}
        mock_topic.return_value = SpotlightTopic(
            tool="Copilot", feature="Custom agents",
            source_url="https://x.com", justification="New",
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
