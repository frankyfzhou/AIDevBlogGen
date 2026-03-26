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

- Python virtual environment activated with dependencies installed
- `OPENAI_API_KEY` set in `.env` or environment
- Hugo theme installed (`git submodule update --init` in `blog/`)

## Procedure

### Step 1: Verify Environment

Run a quick check:
```bash
python -c "from src.config import OPENAI_API_KEY; print('API key configured:', bool(OPENAI_API_KEY))"
```

If the key is missing, remind the user to set it up per `MANUAL_STEPS.md`.

### Step 2: Fetch News & Generate

Run the pipeline in local-only mode first:
```bash
python -m src.main --no-push --verbose
```

This will:
1. Fetch from 10+ news sources (HackerNews, Dev.to, Reddit, RSS feeds)
2. Rank and deduplicate stories
3. Generate a blog post via GPT-4o-mini
4. Write the post to `blog/content/posts/`

### Step 3: Review Output

Check the generated post:
```bash
ls -la blog/content/posts/
cat blog/content/posts/$(ls -t blog/content/posts/ | head -1)
```

### Step 4: Preview (Optional)

Start the Hugo dev server:
```bash
cd blog && hugo server -D
```
Open http://localhost:1313 to preview.

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

## Troubleshooting

- **No news items**: Check internet connectivity; some RSS feeds may be down
- **OpenAI error**: Verify API key and billing at platform.openai.com
- **Hugo build fails**: Ensure theme submodule is initialized: `git submodule update --init`
