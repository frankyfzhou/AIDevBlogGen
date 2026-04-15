"""Tests for the content generator module."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import NewsItem
from src.content_generator import (
    BlogPost,
    BlogSection,
    SourceLink,
    _build_user_prompt,
    _extract_json,
    _normalize_url,
    _validate_blog_urls,
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

    @patch("src.content_generator.call_llm")
    def test_with_spotlight_uses_heavy_model(self, mock_call):
        """When spotlight is provided, the heavy model is used and addendum is in system prompt."""
        mock_call.return_value = MOCK_BLOG_JSON
        items = [
            NewsItem("Story", "https://a.com", "HN", "Summary",
                     datetime.now(timezone.utc), 0.5, []),
        ]
        spotlight = MagicMock()
        spotlight.tool = "GitHub Copilot"
        spotlight.feature = "Agent Mode"
        spotlight.source_url = "https://docs.github.com/copilot"
        spotlight.justification = "New feature"
        spotlight.source_content = "Agent mode allows autonomous coding."
        result = generate_blog_post(items, spotlight=spotlight)
        assert result.title == "AI Dev Weekly: The Rise of Coding Agents"
        # Verify heavy model was used
        call_kwargs = mock_call.call_args[1]
        from src.config import LLM_MODEL_HEAVY
        assert call_kwargs["model"] == LLM_MODEL_HEAVY
        # Verify spotlight addendum was included in system message
        assert "Feature Spotlight" in call_kwargs["system_message"]

    @patch("src.content_generator.call_llm")
    def test_rejects_empty_sections(self, mock_call):
        """Posts with no sections are rejected and retried."""
        empty_post = json.dumps({
            "title": "Empty", "description": "d", "tags": [],
            "cover_keywords": "ai", "introduction": "Intro",
            "sections": [], "conclusion": "End", "sources": [],
        })
        mock_call.side_effect = [empty_post, MOCK_BLOG_JSON]
        items = [NewsItem("Story", "https://a.com", "HN", "", datetime.now(timezone.utc), 0.5, [])]
        result = generate_blog_post(items)
        assert len(result.sections) == 2
        assert mock_call.call_count == 2

    @patch("src.content_generator.call_llm")
    def test_rejects_empty_introduction(self, mock_call):
        """Posts with empty introduction are rejected and retried."""
        bad_post = json.dumps({
            "title": "Bad", "description": "d", "tags": [],
            "cover_keywords": "ai", "introduction": "  ",
            "sections": [{"heading": "H", "body": "B"}],
            "conclusion": "End", "sources": [],
        })
        mock_call.side_effect = [bad_post, MOCK_BLOG_JSON]
        items = [NewsItem("Story", "https://a.com", "HN", "", datetime.now(timezone.utc), 0.5, [])]
        result = generate_blog_post(items)
        assert result.introduction.strip() != ""
        assert mock_call.call_count == 2
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


# ── URL normalization tests ─────────────────────────────────────────────────

class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_lowercases_scheme_and_host(self):
        assert _normalize_url("HTTPS://EXAMPLE.COM/Path") == "https://example.com/Path"

    def test_preserves_query_and_fragment(self):
        result = _normalize_url("https://example.com/p?q=1#frag")
        assert result == "https://example.com/p?q=1#frag"

    def test_handles_bare_domain(self):
        assert _normalize_url("https://example.com") == "https://example.com"

    def test_handles_bare_domain_trailing_slash(self):
        assert _normalize_url("https://example.com/") == "https://example.com"

    def test_strips_whitespace(self):
        assert _normalize_url("  https://example.com  ") == "https://example.com"


# ── URL validation tests ────────────────────────────────────────────────────

def _make_post(sources_urls: list[str], body: str = "Plain text.") -> BlogPost:
    """Helper to build a BlogPost with given source URLs and body text."""
    return BlogPost(
        title="Test",
        description="Desc",
        tags=["t"],
        cover_keywords="ai",
        introduction="Intro",
        sections=[BlogSection(heading="H1", body=body)],
        conclusion="End",
        sources=[SourceLink(title=f"Src {i}", url=u) for i, u in enumerate(sources_urls)],
    )


def _news(urls: list[str]) -> list[NewsItem]:
    """Helper to build NewsItem list from URLs."""
    return [
        NewsItem(f"Story {i}", u, "HN", "summary", datetime.now(timezone.utc), 0.5, [])
        for i, u in enumerate(urls)
    ]


class TestValidateBlogUrls:
    def test_keeps_valid_source_urls(self):
        post = _make_post(["https://a.com", "https://b.com"])
        result = _validate_blog_urls(post, _news(["https://a.com", "https://b.com"]))
        assert len(result.sources) == 2

    def test_removes_hallucinated_source_urls(self):
        post = _make_post(["https://a.com", "https://hallucinated.com/fake"])
        result = _validate_blog_urls(post, _news(["https://a.com"]))
        assert len(result.sources) == 1
        assert result.sources[0].url == "https://a.com"

    def test_removes_all_sources_when_none_match(self):
        post = _make_post(["https://fake1.com", "https://fake2.com"])
        result = _validate_blog_urls(post, _news(["https://real.com"]))
        assert result.sources == []

    def test_trailing_slash_normalization(self):
        post = _make_post(["https://a.com/path/"])
        result = _validate_blog_urls(post, _news(["https://a.com/path"]))
        assert len(result.sources) == 1

    def test_case_insensitive_host(self):
        post = _make_post(["HTTPS://A.COM/path"])
        result = _validate_blog_urls(post, _news(["https://a.com/path"]))
        assert len(result.sources) == 1

    def test_keeps_valid_inline_links(self):
        body = "Read [this article](https://a.com) for details."
        post = _make_post([], body=body)
        result = _validate_blog_urls(post, _news(["https://a.com"]))
        assert "https://a.com" in result.sections[0].body
        assert "[this article](https://a.com)" in result.sections[0].body

    def test_strips_hallucinated_inline_links(self):
        body = "Read [this article](https://fake.com/invented) for details."
        post = _make_post([], body=body)
        result = _validate_blog_urls(post, _news(["https://real.com"]))
        assert "https://fake.com" not in result.sections[0].body
        assert "this article" in result.sections[0].body

    def test_preserves_image_references(self):
        body = "![alt text](https://images.com/pic.png) and [link](https://fake.com)"
        post = _make_post([], body=body)
        result = _validate_blog_urls(post, _news(["https://real.com"]))
        assert "![alt text](https://images.com/pic.png)" in result.sections[0].body
        assert "https://fake.com" not in result.sections[0].body

    def test_sanitizes_introduction_and_conclusion(self):
        post = BlogPost(
            title="T", description="D", tags=[], cover_keywords="ai",
            introduction="See [this](https://fake.com) intro.",
            sections=[],
            conclusion="Also [here](https://fake.com/end) conclusion.",
            sources=[],
        )
        result = _validate_blog_urls(post, _news(["https://real.com"]))
        assert "https://fake.com" not in result.introduction
        assert "this" in result.introduction
        assert "https://fake.com" not in result.conclusion
        assert "here" in result.conclusion

    def test_spotlight_url_in_allowlist(self):
        spotlight = MagicMock()
        spotlight.source_url = "https://docs.tool.com/changelog"
        post = _make_post(["https://docs.tool.com/changelog"])
        result = _validate_blog_urls(post, _news(["https://a.com"]), spotlight=spotlight)
        assert len(result.sources) == 1

    def test_no_spotlight(self):
        post = _make_post(["https://a.com"])
        result = _validate_blog_urls(post, _news(["https://a.com"]), spotlight=None)
        assert len(result.sources) == 1

    def test_mixed_valid_and_invalid_inline_links(self):
        body = "[good](https://a.com) and [bad](https://evil.com) and [ok](https://b.com)"
        post = _make_post([], body=body)
        result = _validate_blog_urls(post, _news(["https://a.com", "https://b.com"]))
        assert "[good](https://a.com)" in result.sections[0].body
        assert "[ok](https://b.com)" in result.sections[0].body
        assert "https://evil.com" not in result.sections[0].body
        assert "bad" in result.sections[0].body

    def test_multiple_sections_all_sanitized(self):
        post = BlogPost(
            title="T", description="D", tags=[], cover_keywords="ai",
            introduction="Intro",
            sections=[
                BlogSection(heading="S1", body="[a](https://good.com)"),
                BlogSection(heading="S2", body="[b](https://bad.com)"),
            ],
            conclusion="End",
            sources=[],
        )
        result = _validate_blog_urls(post, _news(["https://good.com"]))
        assert "[a](https://good.com)" in result.sections[0].body
        assert "https://bad.com" not in result.sections[1].body
        assert "b" in result.sections[1].body


# ── generate_blog_post integration: URL validation is called ─────────────

class TestGenerateBlogPostValidation:
    @patch("src.content_generator.call_llm")
    def test_filters_hallucinated_sources(self, mock_call):
        """Sources not matching input news URLs are filtered out."""
        blog_data = {
            "title": "Test Post",
            "description": "desc",
            "tags": ["ai"],
            "cover_keywords": "ai",
            "introduction": "Intro",
            "sections": [{"heading": "H", "body": "Body"}],
            "conclusion": "End",
            "sources": [
                {"title": "Real", "url": "https://a.com"},
                {"title": "Fake", "url": "https://hallucinated.com/page"},
            ],
        }
        mock_call.return_value = json.dumps(blog_data)
        items = [NewsItem("Story", "https://a.com", "HN", "s", datetime.now(timezone.utc), 0.5, [])]
        result = generate_blog_post(items)
        assert len(result.sources) == 1
        assert result.sources[0].url == "https://a.com"

    @patch("src.content_generator.call_llm")
    def test_strips_hallucinated_inline_links(self, mock_call):
        """Inline links not matching input news URLs are stripped to plain text."""
        blog_data = {
            "title": "Test Post",
            "description": "desc",
            "tags": ["ai"],
            "cover_keywords": "ai",
            "introduction": "Intro",
            "sections": [{"heading": "H", "body": "See [article](https://fake.com/path) here."}],
            "conclusion": "End",
            "sources": [],
        }
        mock_call.return_value = json.dumps(blog_data)
        items = [NewsItem("Story", "https://a.com", "HN", "s", datetime.now(timezone.utc), 0.5, [])]
        result = generate_blog_post(items)
        assert "https://fake.com" not in result.sections[0].body
        assert "article" in result.sections[0].body
