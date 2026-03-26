"""Tests for the content generator module."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import NewsItem
from src.content_generator import (
    BlogPost,
    BlogSection,
    _build_user_prompt,
    generate_blog_post,
)


# ── Prompt construction tests ────────────────────────────────────────────────

class TestBuildUserPrompt:
    def test_includes_all_stories(self):
        items = [
            NewsItem("Story 1", "https://a.com", "HN", "Summary 1",
                     datetime(2026, 3, 20, tzinfo=timezone.utc), 0.8, ["ai"]),
            NewsItem("Story 2", "https://b.com", "Dev.to", "Summary 2",
                     datetime(2026, 3, 21, tzinfo=timezone.utc), 0.6, ["llm"]),
        ]
        prompt = _build_user_prompt(items)
        assert "Story 1" in prompt
        assert "Story 2" in prompt
        assert "https://a.com" in prompt
        assert "HN" in prompt

    def test_handles_none_date(self):
        items = [
            NewsItem("Story", "https://a.com", "Test", "Summ", None, 0.5, []),
        ]
        prompt = _build_user_prompt(items)
        assert "recent" in prompt


# ── Pydantic model tests ────────────────────────────────────────────────────

class TestBlogPostModel:
    def test_valid_model(self):
        post = BlogPost(
            title="Test Post",
            description="A test description",
            tags=["ai", "test"],
            introduction="Intro paragraph",
            sections=[BlogSection(heading="Section 1", body="Body text")],
            conclusion="Conclusion text",
        )
        assert post.title == "Test Post"
        assert len(post.sections) == 1

    def test_empty_sections_allowed(self):
        post = BlogPost(
            title="Test", description="Desc", tags=[],
            introduction="Intro", sections=[], conclusion="End",
        )
        assert post.sections == []


# ── Generation tests (mocked OpenAI) ────────────────────────────────────────

class TestGenerateBlogPost:
    @patch("src.content_generator.LLM_API_KEY", "test-key")
    @patch("src.content_generator.OpenAI")
    def test_successful_generation(self, mock_openai_cls):
        # Build mock response chain
        mock_post = BlogPost(
            title="AI Dev Weekly: The Rise of Coding Agents",
            description="This week's top AI development stories",
            tags=["ai-agents", "coding"],
            introduction="An exciting week in AI development.",
            sections=[
                BlogSection(heading="Coding Agents Go Mainstream", body="Details here..."),
                BlogSection(heading="New LLM Benchmarks", body="Results show..."),
            ],
            conclusion="The future looks bright.",
        )

        mock_message = MagicMock()
        mock_message.parsed = mock_post

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        items = [
            NewsItem("AI agents", "https://a.com", "HN", "Big news",
                     datetime(2026, 3, 20, tzinfo=timezone.utc), 0.8, ["ai"]),
        ]

        result = generate_blog_post(items)
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"
        assert len(result.sections) == 2
        mock_client.beta.chat.completions.parse.assert_called_once()

    @patch("src.content_generator.LLM_API_KEY", "")
    def test_missing_api_key_raises(self):
        items = [
            NewsItem("Story", "https://a.com", "HN", "",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            generate_blog_post(items)

    @patch("src.content_generator.LLM_API_KEY", "test-key")
    @patch("src.content_generator.OpenAI")
    def test_empty_parsed_raises(self, mock_openai_cls):
        mock_message = MagicMock()
        mock_message.parsed = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        items = [
            NewsItem("Story", "https://a.com", "HN", "",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        with pytest.raises(RuntimeError, match="empty structured output"):
            generate_blog_post(items)
