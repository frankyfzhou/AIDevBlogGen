# Manual Setup Steps

This document walks you through the one-time manual steps required before the automated pipeline can run. **Everything else is already implemented** — just follow these steps in order.

---

## What's Already Done

The following has been built and tested:

- **Python pipeline** (`src/`): news fetcher, content generator, publisher, CLI
- **Hugo site structure** (`blog/`): config, archetypes, content directories
- **Jinja2 template** (`templates/blog_post.md.j2`)
- **GitHub Actions** (`.github/workflows/`): weekly cron + deploy to Pages
- **Copilot integration** (`.github/skills/`, `.github/prompts/`): on-demand `/generate-blog-post`
- **Test suite** (`tests/`): 39 tests, all passing
- **Python venv** created with all dependencies installed

---

## Prerequisites

- macOS (you're already on it)
- Git installed and configured
- A GitHub account
- VS Code with GitHub Copilot extension

---

## Step 1: Install Hugo

```bash
brew install hugo
```

Verify:
```bash
hugo version
# Should print hugo v0.1xx.x or later
```

## Step 2: Add the Hugo Theme

The PaperMod theme must be added as a git submodule:

```bash
cd blog
git submodule add https://github.com/adityatelange/hugo-PaperMod themes/PaperMod
cd ..
```

## Step 3: Activate the Python Environment

The venv is already created. Just activate it:

```bash
source venv/bin/activate
```

If you need to recreate it:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 4: Get an OpenAI API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click **"Create new secret key"**
4. Name it `AIDevBlogGen`
5. Copy the key (starts with `sk-`)
6. **Add billing**: Go to Settings → Billing → Add payment method
   - You need a minimum balance. $5 credit will last hundreds of blog posts with GPT-4o-mini.

## Step 5: Set Up Environment Variables

Copy the example file and fill in your key:
```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

> **IMPORTANT**: `.env` is in `.gitignore` and will NOT be committed. Never share your API key.

## Step 6: Update Hugo Config with Your Username

Edit `blog/hugo.toml` and replace `YOURUSERNAME` in two places:
```toml
baseURL = "https://YOURUSERNAME.github.io/AIDevBlogGen/"
# ...
url = "https://github.com/YOURUSERNAME/AIDevBlogGen"
```

## Step 7: Create the GitHub Repository

```bash
cd /Users/fyfz/Documents/dev/AIDevBlogGen
git add -A
git commit -m "Initial commit: full blog generation pipeline"
git remote add origin https://github.com/<your-username>/AIDevBlogGen.git
git push -u origin main
```

Replace `<your-username>` with your GitHub username.

**Repository visibility**: Can be public (free unlimited Actions minutes) or private (2000 free Actions minutes/month — plenty for weekly jobs).

## Step 8: Enable GitHub Pages

1. Go to your repo on GitHub: `https://github.com/<your-username>/AIDevBlogGen`
2. Click **Settings** → **Pages** (left sidebar)
3. Under **Source**, select **GitHub Actions**
4. That's it — the deploy workflow will handle the rest

Your blog will be live at: `https://<your-username>.github.io/AIDevBlogGen/`

## Step 9: Add the OpenAI Key as a GitHub Secret

This allows GitHub Actions to use your API key without exposing it:

1. Go to your repo on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Name: `OPENAI_API_KEY`
5. Value: paste your OpenAI API key
6. Click **"Add secret"**

## Step 10: Test Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Generate a blog post (local only)
python -m src.main --no-push --verbose

# Preview the blog
cd blog
hugo server -D
# Open http://localhost:1313 in your browser
```

## Step 11: Verify GitHub Actions

After pushing all code:

1. Go to your repo → **Actions** tab
2. You should see the "Weekly Blog Post" workflow
3. Click it → **"Run workflow"** → **"Run workflow"** (manual trigger to test)
4. Wait for it to complete (~1-2 minutes)
5. Check that a new post appeared in `blog/content/posts/`
6. Check that the blog deployed to GitHub Pages

## Step 12: (Optional) Custom Domain

If you want a custom domain instead of `<username>.github.io/AIDevBlogGen`:

1. Buy a domain (Namecheap, Cloudflare, etc.)
2. In your DNS settings, add:
   - **CNAME** record: `www` → `<your-username>.github.io`
   - **A** records pointing to GitHub's IPs:
     ```
     185.199.108.153
     185.199.109.153
     185.199.110.153
     185.199.111.153
     ```
3. In GitHub repo → Settings → Pages → Custom domain: enter your domain
4. Check "Enforce HTTPS"
5. Update `baseURL` in `blog/hugo.toml` to your custom domain

---

## Ongoing Maintenance

### Weekly (automated)
- GitHub Actions runs every Monday at 9 AM UTC
- Fetches news, generates post, publishes automatically
- No action needed from you

### Monthly (recommended)
- [ ] Review published posts for quality
- [ ] Check GitHub Actions runs haven't failed (you'll get email notifications on failure)
- [ ] Monitor OpenAI billing (should be < $0.15/month)
- [ ] Update RSS feed URLs if any sources change their feed locations

### As needed
- [ ] Add/remove news sources in `src/config.py`
- [ ] Adjust the LLM prompt in `src/content_generator.py` to refine tone/style
- [ ] Update Python dependencies: `pip install -r requirements.txt --upgrade`
- [ ] Update Hugo theme: `cd blog && git submodule update --remote`

---

## Troubleshooting

### GitHub Actions fails
- Check the Actions tab for error logs
- Most common: expired OpenAI key, rate limit, or changed API endpoints
- Re-run manually with the "Run workflow" button after fixing

### Blog doesn't deploy
- Ensure GitHub Pages source is set to "GitHub Actions" (not "Deploy from branch")
- Check the deploy workflow logs in the Actions tab

### News fetcher returns no results
- Some RSS feeds change URLs periodically — check and update in `src/config.py`
- HackerNews API is very reliable; if it fails, likely a network issue

### OpenAI API errors
- 401: Invalid API key — regenerate at platform.openai.com
- 429: Rate limit — the script has retry logic, but check your billing
- 500+: OpenAI outage — retry later or trigger manually next day

### Local Hugo preview not working
- Make sure you're in the `blog/` directory
- Run `hugo server -D` (the `-D` flag includes draft posts)
- Check that the theme submodule is initialized: `git submodule update --init`
