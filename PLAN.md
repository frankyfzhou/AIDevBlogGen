# AIDevBlogGen — Implementation Plan

Automated weekly blog generation pipeline: fetches priority AI-assisted software development news, generates polished blog posts via LLM, and publishes to a free static blog.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (weekly cron)                  │
│                    or Copilot Skill (on-demand)                   │
└──────────────┬───────────────────────────────────┬───────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────┐              ┌────────────────────────────┐
│   News Fetcher        │              │   Content Generator        │
│   (Python)            │─────────────▶│   (Groq / Cerebras LLM)    │
│                       │  ranked      │                            │
│ • Reads discovery.json│  stories     │ • Summarize top stories    │
│ • HackerNews API      │              │ • Inline source citations  │
│ • Dev.to API          │              │ • Mermaid diagrams         │
│ • RSS feeds (dynamic) │              │ • Code demos/examples      │
│ • Reddit API          │              │ • Format as Hugo markdown  │
│ • GitHub Trending     │              │ • Cover image + sources    │
└──────────────────────┘              └─────────────┬──────────────┘
                                                    │
               ┌────────────────────┐               ▼
               │  Discovery System  │ ┌────────────────────────────┐
               │  (monthly, manual) │ │   Publisher                 │
               │                    │ │                            │
               │ /discover-trends   │ │ • Write .md to blog/content│
               │ prompt in VS Code  │ │ • Git commit + push        │
               │ → discovery.json   │ │ • GitHub Pages auto-deploy │
               └────────────────────┘ └────────────────────────────┘
```

## Technology Decisions

| Component            | Choice            | Rationale                                                    |
|----------------------|-------------------|--------------------------------------------------------------|
| Blog framework       | **Hugo + PaperMod** | Fastest static site generator, free theme, excellent GitHub Pages support |
| Hosting              | **GitHub Pages**  | Free, auto-deploy on push, HTTPS                             |
| Scripting language   | **Python 3.9+**   | Best ecosystem for RSS parsing, HTTP, text processing        |
| LLM API             | **Groq (primary) + Cerebras (fallback)** | Both free tier, OpenAI-compatible API, auto-fallback on rate limits |
| News sources         | **Dynamic via discovery.json** | Keywords, RSS feeds, subreddits, GitHub repos — all configurable, refreshed monthly via Copilot |
| Automation           | **GitHub Actions** | Free for public repos, native cron, chained deploy           |
| Copilot integration  | **Skills + Prompts** | `/generate-blog-post` for posts, `/discover-trends` for source discovery |
| Templating           | **Jinja2**        | Clean separation of blog post structure from generation logic |
| Blog features        | **Sources, Mermaid, cover images** | Inline citations, diagrams, Unsplash CDN covers |

## Project Structure

```
AIDevBlogGen/
├── .github/
│   ├── workflows/
│   │   ├── weekly-blog.yml              # GitHub Actions weekly cron (Friday 9AM UTC)
│   │   └── deploy.yml                   # Hugo build + GitHub Pages deploy
│   ├── copilot-instructions.md          # Workspace-level Copilot instructions
│   ├── prompts/
│   │   ├── generate-blog-post.prompt.md # On-demand blog generation
│   │   └── discover-trends.prompt.md    # Monthly trend discovery → discovery.json
│   └── skills/
│       └── blog-generator/
│           └── SKILL.md                 # Copilot skill for generation
├── blog/                                # Hugo static site
│   ├── hugo.toml                        # Hugo configuration
│   ├── content/posts/                   # Generated blog posts land here
│   ├── layouts/partials/
│   │   └── extend_head.html             # Mermaid JS support
│   └── themes/PaperMod/                 # Git submodule
├── src/
│   ├── __init__.py
│   ├── config.py                        # Configuration, reads discovery.json
│   ├── news_fetcher.py                  # Multi-source news aggregation
│   ├── content_generator.py             # LLM blog post generation (with fallback)
│   ├── publisher.py                     # Write to Hugo + git operations + cover images
│   └── main.py                          # CLI entry point / orchestrator
├── templates/
│   └── blog_post.md.j2                  # Jinja2 template (frontmatter, sources, cover)
├── tests/
│   ├── test_news_fetcher.py
│   ├── test_content_generator.py
│   └── test_publisher.py
├── discovery.json                       # Dynamic source config (updated monthly via /discover-trends)
├── .env.example
├── .gitignore
├── requirements.txt
├── PLAN.md                              # This file
├── MANUAL_STEPS.md
└── README.md
```

---

## Implementation Steps

### Phase 1: Project Scaffolding

**Step 1.1 — Initialize Hugo site**
- Install Hugo (brew install hugo)
- Run `hugo new site blog` inside the repo
- Add a free theme as a git submodule (recommended: **PaperMod** — clean, fast, blog-focused)
  ```
  cd blog
  git submodule add https://github.com/adityatelange/hugo-PaperMod themes/PaperMod
  ```
- Configure `blog/hugo.toml` with site title, theme, base URL (GitHub Pages URL), and blog-specific settings

**Step 1.2 — Python project setup**
- Create `requirements.txt`:
  ```
  openai>=1.0
  feedparser>=6.0
  requests>=2.31
  jinja2>=3.1
  python-dotenv>=1.0
  pydantic>=2.0
  ```
- Create virtual environment and install deps
- Create `.env.example` with required variables:
  ```
  OPENAI_API_KEY=sk-...
  GITHUB_TOKEN=ghp_...     # Only needed for GitHub Actions
  BLOG_REPO_URL=https://github.com/<user>/AIDevBlogGen
  ```

**Step 1.3 — Copilot configuration**
- Create `.github/copilot-instructions.md` with project context and conventions
- Create `.github/prompts/generate-blog-post.prompt.md` for on-demand use
- Create `.github/skills/blog-generator/SKILL.md` for the generation workflow

---

### Phase 2: News Fetcher (`src/news_fetcher.py`)

**Step 2.1 — Define news sources in `src/config.py`**
- HackerNews API: `https://hacker-news.firebaseio.com/v0/` — top/best stories, filter by AI/ML/LLM keywords
- Dev.to API: `https://dev.to/api/articles?tag=ai&top=7` — top AI articles of the week
- RSS feeds (parse with `feedparser`):
  - OpenAI Blog: `https://openai.com/blog/rss.xml`
  - Google AI Blog: `https://blog.google/technology/ai/rss/`
  - Microsoft Research: `https://www.microsoft.com/en-us/research/feed/`
  - Anthropic: `https://www.anthropic.com/rss.xml`
  - Hugging Face Blog: `https://huggingface.co/blog/feed.xml`
  - The Verge AI: `https://www.theverge.com/rss/ai-artificial-intelligence/index.xml`
  - Ars Technica AI: `https://feeds.arstechnica.com/arstechnica/technology-lab`
  - MIT Technology Review AI: `https://www.technologyreview.com/feed/`
- Reddit (JSON, no auth): `https://www.reddit.com/r/MachineLearning/top/.json?t=week`

**Step 2.2 — Implement fetcher with ranking**
- Fetch from all sources concurrently (use `concurrent.futures.ThreadPoolExecutor`)
- Normalize results to a common `NewsItem` dataclass:
  ```python
  @dataclass
  class NewsItem:
      title: str
      url: str
      source: str
      summary: str           # excerpt or description
      published_date: datetime
      score: float           # engagement/relevance score
      tags: list[str]
  ```
- Relevance scoring:
  - Keyword match bonus (AI, LLM, copilot, agent, GPT, Claude, coding, developer, etc.)
  - Recency bonus (last 7 days weighted higher)
  - Engagement bonus (HN points, Reddit upvotes, Dev.to reactions)
  - Source authority bonus (OpenAI/Google/Anthropic official blogs ranked higher)
- Deduplicate by URL and fuzzy title matching
- Return top 5-8 ranked stories

**Step 2.3 — Caching layer**
- Cache fetched results to `.cache/` (JSON) to avoid re-fetching during development
- Cache invalidation after 6 hours

---

### Phase 3: Content Generator (`src/content_generator.py`)

**Step 3.1 — Build the LLM prompt**
- System prompt: persona as an AI development blogger, tone guidelines (informative but accessible, developer-focused, practical)
- Include the ranked news items as structured context
- Request:
  1. A catchy title
  2. An engaging introduction paragraph
  3. 3-5 sections each covering a key story/development
  4. For each section: summary, why it matters for developers, code example or practical demo where relevant
  5. A conclusion with forward-looking perspective
  6. SEO-optimized tags and description

**Step 3.2 — Structured output with Pydantic**
- Define a `BlogPost` Pydantic model for structured generation:
  ```python
  class BlogPost(BaseModel):
      title: str
      description: str        # SEO meta description
      tags: list[str]
      sections: list[Section]
      conclusion: str
  ```
- Use OpenAI's structured output (`response_format`) or parse from markdown

**Step 3.3 — Format as Hugo markdown**
- Use Jinja2 template (`templates/blog_post.md.j2`) to render:
  ```markdown
  ---
  title: "{{ title }}"
  date: {{ date }}
  description: "{{ description }}"
  tags: {{ tags }}
  draft: false
  ---

  {{ content }}
  ```
- Include front matter required by Hugo/PaperMod theme

---

### Phase 4: Publisher (`src/publisher.py`)

**Step 4.1 — Write to Hugo content directory**
- Generate filename from date and slugified title: `YYYY-MM-DD-slug.md`
- Write rendered markdown to `blog/content/posts/`
- Validate front matter is well-formed

**Step 4.2 — Git operations**
- Stage the new post file
- Create a commit with message: `blog: add weekly post — <title>`
- Push to the repository's main branch
- In GitHub Actions context: use `GITHUB_TOKEN` for auth
- In local context: rely on user's existing git credentials

---

### Phase 5: GitHub Actions Automation

**Step 5.1 — Weekly workflow (`.github/workflows/weekly-blog.yml`)**
```yaml
name: Weekly Blog Post
on:
  schedule:
    - cron: '0 9 * * 1'    # Every Monday at 9:00 AM UTC
  workflow_dispatch:          # Manual trigger button

permissions:
  contents: write             # Needed to push the new post

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python src/main.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "blog: add weekly AI dev post"
```

**Step 5.2 — Hugo deploy workflow (`.github/workflows/deploy.yml`)**
- Trigger on push to `main` when `blog/content/**` changes
- Build Hugo site
- Deploy to GitHub Pages using `peaceiris/actions-gh-pages` or the built-in `actions/deploy-pages`

---

### Phase 6: Copilot Skill & Prompt Integration

**Step 6.1 — Copilot workspace instructions**
- `.github/copilot-instructions.md`: project conventions, Python style, Hugo content format

**Step 6.2 — On-demand prompt**
- `.github/prompts/generate-blog-post.prompt.md`: user types `/generate-blog-post` in Copilot chat to trigger a manual blog post generation with interactive customization

**Step 6.3 — Blog generator skill**
- `.github/skills/blog-generator/SKILL.md`: full workflow skill that runs the pipeline end-to-end from within VS Code via Copilot. Describes when to invoke, what tools to use, and the step-by-step process.

---

### Phase 7: Testing & Polish

**Step 7.1 — Unit tests**
- Test news fetcher with mocked API responses
- Test content generator with mocked OpenAI responses
- Test publisher file writing and front matter validation

**Step 7.2 — Local end-to-end test**
- Run `python src/main.py` locally
- Verify blog post appears in `blog/content/posts/`
- Run `hugo server` to preview locally at `http://localhost:1313`

**Step 7.3 — README**
- Project overview, setup instructions, how to run manually, architecture diagram
- Link to live blog

---

## News Source Details

Sources are defined in `discovery.json` (not hardcoded). The file is updated monthly
via the `/discover-trends` Copilot prompt.

| Source Type | Method | Auth | Notes |
|-------------|--------|------|-------|
| HackerNews | REST API | No | Filter top stories by discovery.json keywords |
| Dev.to | REST API | No | Tags from discovery.json |
| Reddit | JSON endpoint | No | Subreddits from discovery.json |
| RSS feeds | feedparser | No | URLs from discovery.json |
| GitHub repos | Releases/README | No | Tracked repos from discovery.json |

---

## Dynamic Discovery System

### Problem
Hardcoded keyword lists and RSS feeds go stale. New tools (Claude Code, Cursor, etc.)
emerge; old ones fade. Static sources miss content from blogs we don't track.

### Solution: `discovery.json` + `/discover-trends` prompt

**`discovery.json`** — A single config file read by the pipeline at runtime:
```json
{
  "updated": "2026-03-29",
  "focus": "AI-assisted software development tools and techniques",
  "keywords": ["github copilot", "claude code", "cursor", ...],
  "rss_sources": [
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "authority": 2.0}
  ],
  "subreddits": ["ChatGPTPro", "CodingWithAI"],
  "github_repos": ["github/awesome-copilot", "continuedev/continue"],
  "search_queries": ["AI coding assistant news this week"]
}
```

**`/discover-trends`** — A Copilot prompt the user invokes monthly in VS Code:
1. Copilot researches current AI dev tool landscape (web search, GitHub trending)
2. Identifies top tools, their blogs/feeds, relevant subreddits and repos
3. Generates an updated `discovery.json`
4. Shows diff for user review before committing

### Flow
```
Monthly:  User runs /discover-trends → Copilot updates discovery.json → git commit
Weekly:   CI reads discovery.json → fetches news → generates blog → deploys
```

### Why not automate discovery in CI?
- Would require a paid search API (Tavily, etc.)
- Copilot is already included in the user's subscription — free
- Human review ensures quality and focus
- Future upgrade path: add Tavily key and automate Phase 0

---

## Cost Estimate

| Item | Cost |
|------|------|
| GitHub Pages hosting | **Free** |
| GitHub Actions (public repo) | **Free** (unlimited minutes) |
| Groq LLM (primary) | **Free** (100K tokens/day) |
| Cerebras LLM (fallback) | **Free** (1M tokens/day) |
| Hugo + PaperMod theme | **Free** |
| Copilot (for /discover-trends) | **Included** in existing subscription |
| Domain (optional) | Free with `.github.io` or ~$10/year for custom |
| **Total per month** | **$0** |

---

## Open Questions / Future Enhancements

- [x] ~~Add image generation for post thumbnails~~ → Using Unsplash CDN cover images
- [x] ~~Track which stories have been covered~~ → Dynamic timeframe from last post date
- [x] ~~Fallback LLM provider~~ → Cerebras auto-fallback when Groq hits limits
- [x] ~~Source citations~~ → Inline links + Sources & Further Reading section
- [x] ~~Mermaid diagrams~~ → JS loaded on demand, LLM prompted to include them
- [x] ~~Deploy not triggering~~ → Weekly workflow chains deploy via workflow_call
- [ ] Add Tavily search API for fully automated dynamic discovery (free tier: 1000/month)
- [ ] Add newsletter integration (Buttondown — free tier, or RSS-to-email)
- [ ] Cross-post to Dev.to and Medium via their APIs
- [ ] Add a draft review step: generate as draft, send notification, publish after approval
- [ ] Add social media posting (Twitter/X, LinkedIn) via their APIs
- [ ] YouTube/podcast transcript summarization for video-based AI dev content
