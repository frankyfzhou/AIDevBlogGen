"""Tests for the content generator module."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import NewsItem
from src.content_generator import (
    BlogPost,
    BlogSection,
    SourceLink,
    _build_user_prompt,
    _extract_json,
    call_llm,
    generate_blog_post,
)


# ── JSON extraction tests ───────────────────────────────────────────────────

class TestExtractJson:
    def test_raw_json_passthrough(self):
        raw = '{"title": "Test"}'
        assert _extract_json(raw) == '{"title": "Test"}'

    def test_strips_json_fences(self):
        raw = '```json\n{"title": "Test"}\n```'
        assert _extract_json(raw) == '{"title": "Test"}'

    def test_strips_plain_fences(self):
        raw = '```\n{"title": "Test"}\n```'
        assert _extract_json(raw) == '{"title": "Test"}'

    def test_handles_whitespace(self):
        raw = '  \n  {"title": "Test"}  \n  '
        assert _extract_json(raw) == '{"title": "Test"}'


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
            cover_keywords="ai coding",
            introduction="Intro paragraph",
            sections=[BlogSection(heading="Section 1", body="Body text")],
            conclusion="Conclusion text",
            sources=[SourceLink(title="Example", url="https://example.com")],
        )
        assert post.title == "Test Post"
        assert len(post.sections) == 1
        assert len(post.sources) == 1

    def test_empty_sections_allowed(self):
        post = BlogPost(
            title="Test", description="Desc", tags=[],
            cover_keywords="ai",
            introduction="Intro", sections=[], conclusion="End",
            sources=[],
        )
        assert post.sections == []


# ── call_llm tests (mocked Copilot SDK) ─────────────────────────────────────

MOCK_BLOG_JSON = json.dumps({
    "title": "AI Dev Weekly: The Rise of Coding Agents",
    "description": "This week's top AI development stories",
    "tags": ["ai-agents", "coding"],
    "cover_keywords": "ai agents",
    "introduction": "An exciting week in AI development.",
    "sections": [
        {"heading": "Coding Agents Go Mainstream", "body": "Details here..."},
        {"heading": "New LLM Benchmarks", "body": "Results show..."},
    ],
    "conclusion": "The future looks bright.",
    "sources": [{"title": "HN Post", "url": "https://a.com"}],
})


def _make_mock_response(content: str) -> MagicMock:
    """Create a mock SessionEvent with .data.content."""
    response = MagicMock()
    response.data.content = content
    return response


class TestCallLlm:
    @patch("src.content_generator._get_github_token", return_value="fake-token")
    @patch("src.content_generator._call_llm_async")
    def test_returns_raw_content(self, mock_async, mock_token):
        mock_async.return_value = "test response"
        result = call_llm("test prompt")
        assert result == "test response"
        mock_async.assert_called_once()

    @patch("src.content_generator._get_github_token", return_value="fake-token")
    @patch("src.content_generator._call_llm_async")
    def test_passes_model_and_working_dir(self, mock_async, mock_token):
        mock_async.return_value = "ok"
        call_llm("prompt", model="gpt-4.1", working_directory="/tmp")
        _, kwargs = mock_async.call_args
        assert kwargs["model"] == "gpt-4.1"
        assert kwargs["working_directory"] == "/tmp"


# ── generate_blog_post tests (mocked call_llm) ──────────────────────────────

class TestGenerateBlogPost:
    @patch("src.content_generator.call_llm", return_value=MOCK_BLOG_JSON)
    def test_successful_generation(self, mock_call):
        items = [
            NewsItem("AI agents", "https://a.com", "HN", "Big news",
                     datetime(2026, 3, 20, tzinfo=timezone.utc), 0.8, ["ai"]),
        ]
        result = generate_blog_post(items)
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"
        assert len(result.sections) == 2
        mock_call.assert_called_once()

    @patch("src.content_generator.call_llm", return_value=MOCK_BLOG_JSON)
    def test_with_news_json_path(self, mock_call):
        """news_json_path is accepted but no longer changes the prompt."""
        items = [
            NewsItem("Story", "https://a.com", "HN", "Summary",
                     datetime(2026, 3, 20, tzinfo=timezone.utc), 0.8, ["ai"]),
        ]
        result = generate_blog_post(items, news_json_path="/tmp/news.json")
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"
        prompt_arg = mock_call.call_args[1].get("prompt") or mock_call.call_args[0][0]
        assert "Story" in prompt_arg

    @patch("src.content_generator.call_llm")
    def test_retry_on_invalid_json(self, mock_call):
        # First call returns invalid JSON, second returns valid
        mock_call.side_effect = ["not valid json at all", MOCK_BLOG_JSON]
        items = [
            NewsItem("Story", "https://a.com", "HN", "",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        result = generate_blog_post(items)
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"
        assert mock_call.call_count == 2

    @patch("src.content_generator.call_llm", return_value="totally broken")
    def test_raises_after_retries_exhausted(self, mock_call):
        items = [
            NewsItem("Story", "https://a.com", "HN", "",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        with pytest.raises(RuntimeError, match="Blog generation failed"):
            generate_blog_post(items)

    @patch("src.content_generator.call_llm")
    def test_handles_fenced_json(self, mock_call):
        fenced = f"```json\n{MOCK_BLOG_JSON}\n```"
        mock_call.return_value = fenced
        items = [
            NewsItem("Story", "https://a.com", "HN", "Summary",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        result = generate_blog_post(items)
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"


# ── _get_github_token tests ─────────────────────────────────────────────────

class TestGetGithubToken:
    @patch.dict("os.environ", {"GITHUB_TOKEN": "gho_test123"})
    def test_reads_from_env(self):
        from src.content_generator import _get_github_token
        assert _get_github_token() == "gho_test123"

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.content_generator.subprocess.run")
    def test_falls_back_to_gh_cli(self, mock_run):
        # Remove GITHUB_TOKEN from env
        import os
        os.environ.pop("GITHUB_TOKEN", None)
        mock_run.return_value = MagicMock(returncode=0, stdout="gho_from_cli\n")
        from src.content_generator import _get_github_token
        assert _get_github_token() == "gho_from_cli"

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.content_generator.subprocess.run")
    def test_raises_when_no_token(self, mock_run):
        import os
        os.environ.pop("GITHUB_TOKEN", None)
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        from src.content_generator import _get_github_token
        with pytest.raises(RuntimeError, match="No GitHub token"):
            _get_github_token()
