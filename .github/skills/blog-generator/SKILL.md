---
name: blog-generator
description: "Full AI Dev Weekly blog generation workflow. Use when: generate blog, weekly post, AI news roundup, run blog pipeline, publish blog post, create article."
---

# Blog Generator Skill

End-to-end workflow for generating and publishing an AI Dev Weekly blog post.

## When to Use

- Weekly blog post generation (automated or manual)
- Regenerating a post with different news or parameters
- Testing the pipeline end-to-end

## Prerequisites

- Python 3.11+ virtual environment activated with dependencies installed
- GitHub Copilot access (auth via `gh auth login` or `GITHUB_TOKEN` env var)
- Hugo theme installed (`git submodule update --init` in `blog/`)

## Procedure

### Step 0: Refresh Sources (Monthly / Optional)

Check if `discovery.json` is stale (updated > 1 month ago):
```bash
cat discovery.json | python -c "import json,sys; print(json.load(sys.stdin)['updated'])"
```

If stale or if the user wants fresh sources, run the `/discover-trends` prompt:
1. Research the current AI dev tool landscape using web search
2. Read the current `discovery.json` and identify outdated entries
3. Generate an updated `discovery.json` with refreshed keywords, RSS feeds, subreddits, repos
4. Show the user a diff between old and new
5. After user approval, write the updated file and commit

This ensures the pipeline fetches from the most relevant, current sources.

### Step 1: Verify Environment

Run a quick check:
```bash
source venv/bin/activate
gh auth status
python -c "from src.config import LLM_MODEL; print('LLM model:', LLM_MODEL)"
```

If `gh auth` fails, run `gh auth login` or set `GITHUB_TOKEN` env var.

### Step 2: Fetch News & Generate

Run the pipeline in local-only mode first:
```bash
python -m src.main --no-push --verbose
```

This will:
1. Read source config from `discovery.json` (keywords, RSS feeds, subreddits)
2. Fetch from HackerNews, Dev.to, Reddit, and RSS feeds
3. Rank by keyword relevance + recency + engagement, deduplicate
4. Discover Feature Spotlight topic (dominant tools → changelogs → pick topic)
5. Generate a blog post via GitHub Copilot SDK (agent reads past posts from disk)
6. Write the post to `blog/content/posts/`

### Step 3: Review Output

Check the generated post:
```bash
ls -la blog/content/posts/
cat blog/content/posts/$(ls -t blog/content/posts/ | head -1)
```

Review for:
- Content quality and focus on AI-assisted development
- Inline source citations (every claim should link to its source)
- Mermaid diagrams render correctly
- Cover image URL works

### Step 4: Preview (Optional)

Start the Hugo dev server:
```bash
cd blog && hugo server -D
```
Open http://localhost:1313/AIDevBlogGen/ to preview.

### Step 5: Publish

If the post looks good, commit and push:
```bash
python -m src.main --verbose
```

Or manually:
```bash
git add blog/content/posts/
git commit -m "blog: add weekly AI dev post"
git push
```

GitHub Actions will automatically build and deploy the Hugo site to GitHub Pages.

## Full Workflow Summary

```
Monthly:  /discover-trends → update discovery.json → commit
Weekly:   python -m src.main --no-push → review → python -m src.main → deploy
Automated: GitHub Actions runs every Friday 9AM UTC (reads discovery.json, generates, deploys)
```

## Troubleshooting

- **No news items**: Check internet connectivity; some RSS feeds may be down. Verify `discovery.json` has valid sources.
- **No GitHub token**: Run `gh auth login` or set `GITHUB_TOKEN` env var.
- **Copilot SDK errors**: Ensure Python 3.11+ and `github-copilot-sdk` is installed. Check `gh auth status`.
- **Hugo build fails**: Ensure theme submodule is initialized: `git submodule update --init`
- **Stale content**: Run `/discover-trends` to refresh keywords and sources in `discovery.json`.
- **No spotlight topic**: This is normal — if no new features are found, the pipeline generates a news-only post.
