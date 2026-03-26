"""Tests for the publisher module."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.content_generator import BlogPost, BlogSection
from src.publisher import _slugify, git_commit_and_push, render_blog_post, write_post


# ── Slugify tests ────────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert _slugify("AI Dev Weekly: The Rise of Agents!") == "ai-dev-weekly-the-rise-of-agents"

    def test_max_length(self):
        long = "a" * 200
        assert len(_slugify(long)) <= 80

    def test_strips_trailing_hyphens(self):
        assert _slugify("test---") == "test"


# ── Render tests ─────────────────────────────────────────────────────────────

class TestRenderBlogPost:
    def _make_post(self) -> BlogPost:
        return BlogPost(
            title="AI Dev Weekly: Test Edition",
            description="A test blog post for validation",
            tags=["ai", "testing"],
            introduction="Welcome to this week's edition.",
            sections=[
                BlogSection(heading="Big AI News", body="Something happened."),
                BlogSection(heading="Developer Tools", body="New tools released."),
            ],
            conclusion="Exciting times ahead.",
        )

    def test_frontmatter_present(self):
        rendered = render_blog_post(self._make_post())
        assert rendered.startswith("---")
        assert 'title: "AI Dev Weekly: Test Edition"' in rendered
        assert 'description: "A test blog post for validation"' in rendered

    def test_tags_in_frontmatter(self):
        rendered = render_blog_post(self._make_post())
        assert '"ai"' in rendered
        assert '"testing"' in rendered

    def test_sections_rendered(self):
        rendered = render_blog_post(self._make_post())
        assert "## Big AI News" in rendered
        assert "Something happened." in rendered
        assert "## Developer Tools" in rendered

    def test_conclusion_under_looking_ahead(self):
        rendered = render_blog_post(self._make_post())
        assert "## Looking Ahead" in rendered
        assert "Exciting times ahead." in rendered

    def test_not_draft(self):
        rendered = render_blog_post(self._make_post())
        assert "draft: false" in rendered


# ── Write post tests ─────────────────────────────────────────────────────────

class TestWritePost:
    def test_writes_file(self, tmp_path: Path):
        post = BlogPost(
            title="Test Post",
            description="Desc",
            tags=["test"],
            introduction="Intro",
            sections=[BlogSection(heading="H1", body="B1")],
            conclusion="End",
        )
        with patch("src.publisher.BLOG_CONTENT_DIR", tmp_path):
            filepath = write_post(post)
            assert filepath.exists()
            assert filepath.suffix == ".md"
            content = filepath.read_text()
            assert "Test Post" in content

    def test_filename_format(self, tmp_path: Path):
        post = BlogPost(
            title="AI Agents Are Here",
            description="Desc",
            tags=[],
            introduction="Intro",
            sections=[],
            conclusion="End",
        )
        with patch("src.publisher.BLOG_CONTENT_DIR", tmp_path):
            filepath = write_post(post)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            assert filepath.name.startswith(today)
            assert "ai-agents-are-here" in filepath.name


# ── Git tests ────────────────────────────────────────────────────────────────

class TestGitCommitAndPush:
    @patch("src.publisher.subprocess.run")
    def test_success(self, mock_run, tmp_path: Path):
        mock_run.return_value = MagicMock(returncode=0)
        filepath = tmp_path / "blog" / "content" / "posts" / "test.md"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.touch()

        with patch("src.publisher.ROOT_DIR", tmp_path):
            result = git_commit_and_push(filepath, "Test Post")
            assert result is True
            assert mock_run.call_count == 3  # add, commit, push

    @patch("src.publisher.subprocess.run")
    def test_failure(self, mock_run, tmp_path: Path):
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", output="error", stderr="failed"
        )
        filepath = tmp_path / "test.md"

        with patch("src.publisher.ROOT_DIR", tmp_path):
            result = git_commit_and_push(filepath, "Test")
            assert result is False
