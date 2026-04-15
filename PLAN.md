# AIDevBlogGen — Implementation Plan

Automated weekly blog generation pipeline: fetches priority AI-assisted software development news, generates polished blog posts via LLM, and publishes to a free static blog.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│   Option B: GitHub Actions (cron Friday, Copilot SDK)            │
│   Option A: Local Mac Mini (launchd, gh copilot CLI)             │
└──────────────┬───────────────────────────────────┬───────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────┐              ┌────────────────────────────┐
│   News Fetcher        │              │   Content Generator        │
│   (Python)            │─────────────▶│   (Copilot SDK / CLI)      │
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
| Scripting language   | **Python 3.11+**  | Required for Copilot SDK; best ecosystem for RSS/HTTP/text   |
| LLM API             | **Copilot SDK** (CI) or **`gh copilot` CLI** (local) — Claude Opus 4.6 default | Free with Copilot, agent reads files from disk, no token stuffing |
| News sources         | **Dynamic via discovery.json** | Keywords, RSS feeds, subreddits, GitHub repos — all configurable, refreshed monthly via Copilot |
| Automation           | **GitHub Actions cron** (Option B) or **macOS launchd** (Option A) | Option B preferred — CI reliability, no local dependency |
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

## Implementation Steps (Completed)

Phases 1–7 are fully implemented and deployed. Key details preserved for reference.

### Phase 1: Project Scaffolding ✅
Hugo + PaperMod theme, Python project, Copilot configs, `.github/` structure.

### Phase 2: News Fetcher ✅
Multi-source aggregation (HN, Dev.to, Reddit /top + /hot, RSS, GitHub).
Scoring: keyword 0.30 + recency 0.25 + engagement 0.25 + velocity 0.20.
Reddit dedup by post ID. Sources defined in `discovery.json`.

### Phase 3: Content Generator ✅
OpenAI SDK with `base_url` swap. `BlogPost` Pydantic model for structured JSON output.
Groq primary (llama-3.3-70b-versatile) + Cerebras fallback (qwen-3-235b).
Dual-mode: `json_schema` + `json_object` fallback. *(Being replaced — see Phase 9)*

### Phase 4: Publisher ✅
Hugo markdown via Jinja2 template. Unsplash CDN cover images. Git commit + push.

### Phase 5: GitHub Actions ✅
`weekly-blog.yml` (Friday 9AM UTC) chains `deploy.yml` via `workflow_call`.
`deploy.yml` triggers on push to `blog/**` + `workflow_dispatch` + `workflow_call`.
*(weekly-blog.yml being removed — see Phase 9)*

### Phase 6: Copilot Integration ✅
`copilot-instructions.md`, `/generate-blog-post` prompt, `/discover-trends` prompt,
`blog-generator` skill. All configured and working.

### Phase 7: Testing ✅
45 tests passing. Mocked HTTP/API calls. Full local end-to-end validated.

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
| GitHub Actions (deploy only) | **Free** (unlimited minutes, public repo) |
| GitHub Models LLM (via Copilot) | **Free** (included in Copilot subscription) |
| Hugo + PaperMod theme | **Free** |
| Copilot (for /discover-trends + LLM) | **Included** in existing subscription |
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
- [x] ~~Breaking news detection~~ → Reddit /hot + velocity scoring
- [x] ~~Feature Spotlight system~~ → Phase 8 implemented: `src/spotlight.py`, 18 tests, E2E validated
- [x] ~~Copilot SDK migration~~ → Phase 9 Steps 2-4 done. Step 1 (CI auth) + Step 5 (schedule) pending CI push
- [ ] Add newsletter integration (Buttondown — free tier, or RSS-to-email)
- [ ] Cross-post to Dev.to and Medium via their APIs
- [ ] Add a draft review step: generate as draft, send notification, publish after approval
- [ ] Add social media posting (Twitter/X, LinkedIn) via their APIs
- [ ] YouTube/podcast transcript summarization for video-based AI dev content

---

## Phase 8: Feature Spotlight System

### Problem

Current posts are news roundups — commodity content that doesn't help a developer
actually get better at using AI coding tools. A senior engineer using GitHub Copilot
or Claude Code daily wants to learn **deep, actionable features** — not hear about
funding rounds and PR stunts.

### Goal

Every week, include a **Feature Spotlight** alongside a brief news section:
a deep-dive on a specific, current feature of a popular AI coding agent, written
for senior engineers, with real examples, gotchas, and source-verified content.

### Post Structure (New)

| Section | Word budget | Content |
|---------|-------------|---------|
| Introduction | ~100 words | This week's theme |
| News (2-3 stories) | ~400-500 words | Brief, high-signal items only |
| **Feature Spotlight** | ~800-1200 words | Deep-dive on one tool feature |
| Conclusion | ~100 words | Forward-looking synthesis |
| **Total** | ~1500-2000 words | Same length as current posts |

### Design Principles

1. **Nothing is hardcoded.** Tools, sources, topics — all discovered dynamically.
   Code never contains a list of tool names. The pipeline queries for what's current.
2. **Everything needs source links.** Before a topic is chosen, the source URL is
   fetched and validated for relevance. No hallucinated features.
3. **Senior-engineer depth.** Not "here's what custom instructions are" but
   "here's how to compose agents + skills + instructions with applyTo scoping
   in a monorepo, with a worked example and gotchas."
4. **Length is adaptive.** If a topic is deep and useful, it can go longer than
   800 words. But no 5000-word essays about niche tools nobody uses. Concise
   and dense, not wordy.
5. **Spotlight is optional.** If nothing is new and all major features have been
   covered in past posts → skip the deep-dive, run news-only.
6. **RSS sources follow tools, not the other way around.** The RSS feeds in
   `discovery.json` should reflect the _output_ of tool discovery, not be an
   independent manually curated list. If the LLM says "the dominant tools are
   GitHub Copilot and Claude Code," then the pipeline should ensure we're tracking
   blogs/feeds for those tools — and stop tracking feeds for tools that have faded.
   Currently the RSS list is manually maintained in `discovery.json` and refreshed
   monthly via `/discover-trends`. See **Open Question** below on whether to tie
   this directly to Step 1 tool discovery.

### Spotlight Topic Discovery (No Hardcoding)

The pipeline must dynamically determine:
- What are the currently popular AI coding agents?
- What features have they recently released or updated?
- What have we already covered in past posts?

#### Step 1: Identify the Dominant Tools (LLM + Live Data)

The pipeline makes an LLM call with a prompt like:

> "What are the 1-2 dominant AI coding assistants/agents that senior developers
> are actually using day-to-day right now? Not every tool on the market — just
> the ones with real mainstream adoption (think React vs Angular in the 2020
> framework wars). For each, provide: name, official docs URL, changelog or
> release notes URL. If there is a notable newcomer gaining real traction, include
> it as a third. Maximum 3. Return JSON."

The intent is to focus on the tools that matter — currently that's GitHub Copilot
and Claude Code. The LLM might add a third if something is genuinely breaking
through (like Cursor was in 2025). But not 5, not 10 — just what a serious
developer should know.

This replaces any hardcoded tool list. The LLM's training data gives a reasonable
starting point; the URLs are then validated by fetching them.

**Validation**: For each URL the LLM returns, the pipeline does an HTTP GET. If it
404s or doesn't contain relevant content → discard that tool. Only tools with
verified live docs pages proceed.

**CI requirement**: This step runs in CI, using the same Groq/Cerebras LLM we
already use. No new API keys needed. Cost: 1 extra LLM call (~500 tokens) per run.

#### Step 2: Fetch Release Notes / Changelogs

For each validated tool, fetch its changelog/release-notes page:
- HTTP GET the changelog URL
- Extract the last ~2000 chars of text (or latest entries)
- Pass this raw content to the LLM as context

No parsing needed — the LLM reads the raw changelog text and extracts new features.

#### Step 3: Read Past Posts for Coverage

Before generating, read ALL existing posts in `blog/content/posts/*.md`:
- Extract the full content of every past post
- Pass it all to the LLM: "Here are all our past posts. Pick a topic we
  haven't covered."

No separate tracking file. No cap on how many posts to read. The posts themselves
are the source of truth. Let the LLM handle the volume — even at 50+ posts the
total context is well within modern model limits (~8-12K tokens of post content).

#### Step 4: Decide & Validate

The LLM picks a spotlight topic and returns:
- Tool name
- Feature name
- Source URL (changelog entry, docs page, or blog post)
- Brief justification

**Mandatory validation**: The pipeline fetches the source URL and confirms the
content mentions the feature. If validation fails → try next candidate or skip
spotlight.

### Decision Flow

```
1. Fetch news stories (reduce MAX_STORIES to 5 candidates, show 2-3 in post)
2. Check if top story velocity > 0.9 (breaking news threshold)
   → YES: Full news mode, 3-4 stories, no spotlight
   → NO: Continue to spotlight
3. LLM call: "What are the 1-2 dominant AI coding tools right now?" → get tools + URLs
4. Validate tool URLs (HTTP GET, check for 200 + relevant content)
5. Fetch changelogs for validated tools (1-2 tools, maybe 3)
6. Read ALL past posts for coverage history (no cap)
7. LLM call: "Given these changelogs and past coverage, pick the best spotlight
   topic. Return tool, feature, source URL, justification."
8. Validate spotlight source URL
   → FAIL: Skip spotlight, news-only post
   → PASS: Generate hybrid post (2-3 news + spotlight)
```

### Content Generator Changes

The system prompt gains a new section:

> "When a Feature Spotlight topic is provided, write an in-depth section covering:
> - What the feature is and why it matters for day-to-day development
> - Real, working code/config examples (not toy demos)
> - Gotchas, edge cases, and non-obvious behavior
> - How it composes with other features of the same tool
> - Cite the source docs/changelog inline
>
> Target audience: senior engineers who already use the tool daily.
> Skip basics. Go straight to practical depth."

### Example Spotlight Topics (Illustrative, NOT Hardcoded)

These are the *kind* of topics the system should discover, not a fixed list:

- "GitHub Copilot: Composing agents, skills, and instructions with applyTo scoping"
- "Claude Code: Using /compact, CLAUDE.md, and memory files for long sessions"
- "Cursor: .cursor/rules per-directory scoping in a monorepo"
- "GitHub Copilot: MCP server integration for database and API queries"
- "Aider: Git-aware editing with auto-commits and dirty-commits"
- "Claude Code: Custom slash commands and tool restrictions"

### Pipeline Changes Summary

| File | Change |
|------|--------|
| `src/config.py` | Reduce `MAX_STORIES` from 8 to 5 |
| `src/news_fetcher.py` | No changes (already handles reduced story count) |
| `src/content_generator.py` | Add spotlight discovery flow: LLM tool query → fetch changelogs → read past posts → pick topic → validate → generate |
| `src/main.py` | Wire spotlight into pipeline between fetch and generate |
| `templates/blog_post.md.j2` | Add optional spotlight section rendering |
| `src/config.py` | Add `SPOTLIGHT_VELOCITY_THRESHOLD = 0.9` |

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM returns outdated/wrong tool URLs | Mandatory HTTP validation; discard on 404 or irrelevant content |
| LLM hallucinates features not in the docs | Feed raw changelog text as context; LLM summarizes rather than invents |
| Extra LLM calls hit rate limits | 2-3 extra calls (small prompts); well within Groq/Cerebras free tiers |
| Changelog pages change format | We don't parse — just fetch raw text and let LLM interpret |
| Runs dry on topics | Skip spotlight gracefully; news-only post is fine |
| Topic too niche / unpopular tool | LLM prompt explicitly limits to 1-2 dominant tools with real adoption |

### Implementation Order

1. Update PLAN.md with this design (this section)
2. Prototype in a local test run — wire up the LLM calls, fetch changelogs, generate one post
3. Review output quality and iterate on prompts
4. Once quality is good: commit, push, let CI handle it
5. After 2-3 weeks of CI runs: review and tune

### Open Question: RSS Feeds and Tool Discovery

**Current state:** `discovery.json` has 9 RSS feeds (GitHub Blog, Anthropic, OpenAI,
VS Code Blog, Cursor Blog, etc.) manually chosen via `/discover-trends` monthly.

**User concern:** These are manually curated. They should be there _because_ they
belong to the dominant tools, not because someone hand-picked them.

**Options:**

**A) Tie RSS to Step 1 tool discovery. ✅ DECIDED**
When the LLM identifies the 1-2 dominant tools in Step 1, also ask it for the
official blog/feed URL for each. The pipeline then uses _those feeds_ for news
fetching (in addition to HN, Reddit, Dev.to). `discovery.json` RSS list becomes
supplementary — general AI news feeds (Google AI, HuggingFace) stay, but
tool-specific feeds are auto-derived from Step 1.

Implementation: Step 1 LLM prompt returns `{"tools": [{"name": ..., "docs_url": ...,
"changelog_url": ..., "rss_url": ...}]}`. The `rss_url` is validated (HTTP GET,
check for valid feed XML) and passed to the news fetcher alongside the static
`discovery.json` feeds. The news fetcher gains a `extra_rss` parameter.

~~B) Augment /discover-trends prompt.~~

~~C) Fully automate.~~

---

## Phase 9: Local Execution via `gh copilot` CLI (Remove Groq/Cerebras)

### Problem

The pipeline currently depends on Groq (primary) and Cerebras (fallback) free-tier
LLM APIs. These have rate limits (Groq: 100K tokens/day), can go down, and require
managing separate API keys. Meanwhile, the user already pays for GitHub Copilot,
which includes `gh copilot` CLI — a way to call LLMs (including Claude Opus 4.6)
in non-interactive scripting mode.

Running in GitHub Actions also means:
- LLM API keys stored as GitHub Secrets (rotation, leak risk)
- No local preview before publish — CI generates and commits in one shot
- Debugging CI failures requires push-and-wait cycles

**Critical advantage of local execution: file system access.**
With any remote LLM API (Groq, Cerebras, GitHub Models), the pipeline must read
all past blog posts in Python, serialize them, and stuff them into the prompt.
As the blog grows (50+ posts), this:
- Blows up input token counts → 429 rate limits
- Wastes token budget on context that the LLM could read itself
- Risks hitting context window limits

With `gh copilot -p` + `--add-dir`, the agent has direct file system access.
The prompt is ~500 tokens of instructions; the agent reads files locally using
its built-in tools. **Past post content never enters the prompt.** The blog can
grow to 500+ posts with zero impact on token usage or rate limits.

### Validated Findings (April 14 2026)

Two LLM paths were tested. Results:

#### Path 1: GitHub Models API (`models.inference.ai.azure.com`)

**Tested and working:**
- Auth: `gho_` token from `gh auth token` works ✅
- `gpt-4o` ✅, `gpt-4o-mini` ✅, `gpt-4.1` ✅, `gpt-4.1-mini` ✅, `gpt-4.1-nano` ✅
- `Meta-Llama-3.1-405B-Instruct` ✅, `o4-mini` ✅, `o3-mini` ✅, `Grok-3` ✅
- `response_format: json_object` ✅
- `response_format: json_schema` (strict mode) ✅
- 2686 completion tokens returned in a single request (enough for blog posts) ✅

**NOT available:**
- ❌ **No Claude models** — no Anthropic models on GitHub Models API

**Rate limits (Copilot Pro — "Low" tier):**
- 15 req/min, 150 req/day, 8000 tokens in / 4000 tokens out

**Verdict:** Works but no Claude, and still requires stuffing all context into
the prompt (no file access). Rejected.

#### Path 2: `gh copilot` CLI (non-interactive mode) ✅ CHOSEN

**Tested and working:**

```bash
# GPT-4.1 — 0 premium requests (free!)
gh copilot -- --silent --no-ask-user --model gpt-4.1 \
  -p "Return only valid JSON: {\"test\": true}"
→ {"test": true}

# Claude Opus 4.6 — 3 premium requests per call
gh copilot -- --silent --no-ask-user --model claude-opus-4.6 \
  -p "Return only valid JSON: {\"test\": true}"
→ {"test": true}
```

**File system access validated:**
```bash
gh copilot -- --silent --no-ask-user --model gpt-4.1 \
  --add-dir /Users/fyfz/Documents/dev/AIDevBlogGen \
  -p "Read ALL files in blog/content/posts/. Analyze covered topics.
      Return JSON: {covered_topics: [...], suggested_new_topic: '...'}"
→ Agent read all 3 posts' full content, analyzed coverage, suggested topic ✅
→ Zero post content in prompt — agent read files via built-in tools ✅
```

**Key flags:**
- `-p "prompt"` — non-interactive mode (exits after completion)
- `--silent` — outputs only the agent response (no usage stats)
- `--no-ask-user` — fully autonomous, no prompts
- `--model <model>` — configurable model selection
- `--add-dir <path>` — grants file system access to agent

**Confirmed models:**
- `gpt-4.1` → 0 premium requests, fast ✅
- `claude-opus-4.6` → 3 premium requests per call ✅
- `claude-sonnet-4` → 1 premium request per call ✅

**Premium request budget (Copilot Pro = 300/month):**
- Blog pipeline needs ~4-5 LLM calls per run
- Claude Opus 4.6: ~15 premium requests/run × 4 runs/month = **~60/month** (20% of budget)
- GPT-4.1: **0 premium requests** (unlimited)

### Why `gh copilot` CLI, not an API

| Concern | Remote API (Groq/GitHub Models) | `gh copilot -p` (local) |
|---------|:---:|:---:|
| Past post reading | Must serialize all posts into prompt → token explosion | Agent reads files locally → prompt stays ~500 tokens |
| 429 risk as blog grows | ❌ More posts = more tokens = more rate limits | ✅ Post count doesn't affect token usage |
| Claude access | ❌ Not on GitHub Models | ✅ Any Copilot model |
| Structured output | ✅ `json_schema` mode | Prompt-based (validated: works reliably) |
| API keys to manage | Yes (stored in .env or secrets) | No — `gh` handles auth via keyring |
| Code change | Minimal (swap `base_url`) | Moderate (subprocess + JSON extraction) |

### Goal

Replace Groq/Cerebras LLM with Copilot-powered LLM. Two approaches researched;
**Option B (Copilot SDK in CI) is preferred** if it works headlessly.

### Option A: Local `gh copilot` CLI via launchd (validated, works now)

```
Local Mac Mini (launchd, Friday schedule)
  → git pull
  → Python fetches news → writes to /tmp/aidevblog-news.json
  → subprocess: gh copilot -- --silent --no-ask-user --model <MODEL>
      --add-dir <repo> -p "Read past posts + news, generate blog post JSON"
  → Python parses JSON, renders Hugo markdown
  → git commit + push
GitHub Actions (push to blog/**)
  → deploy.yml → build Hugo → deploy to GitHub Pages
```

**Pros:** Validated, works today, agent reads files from disk.
**Cons:** Requires Mac Mini always on, subprocess/JSON extraction is fragile.

### Option B: Copilot SDK in GitHub Actions ✅ PREFERRED (needs validation)

```
GitHub Actions (cron Friday 9AM UTC)
  → actions/checkout (gives agent file system access to repo)
  → pip install github-copilot-sdk
  → Python script using CopilotClient:
      - Agent reads blog/content/posts/*.md (past coverage) via built-in tools
      - Agent reads fetched news from temp file
      - Agent generates blog post JSON
  → Python parses JSON, renders Hugo markdown
  → git commit + push → deploy.yml triggers
```

**Why this is better:**
- CI-based: scheduled, no local machine dependency
- Agent has file system access after checkout (same as `gh copilot --add-dir`)
- No token stuffing — agent reads files from disk, prompt stays small
- Auth via `GITHUB_TOKEN` env var (no PAT, no API keys)
- Any Copilot model available (claude-opus-4.6, gpt-4.1, etc.)
- Premium request billing (same as CLI)

**Copilot SDK code (validated locally April 14 2026):**
```python
import asyncio, os
from copilot import CopilotClient, SubprocessConfig
from copilot.session import PermissionHandler, SystemMessageAppendConfig

async def generate_blog_post(news_json_path: str, model: str = "claude-opus-4.6") -> str:
    config = SubprocessConfig(
        github_token=os.environ["GITHUB_TOKEN"],  # gho_ or ghs_ token
    )
    async with CopilotClient(config=config) as client:
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model,
            working_directory=".",  # agent reads files from checkout dir
            system_message=SystemMessageAppendConfig(
                content="You are an expert technical blogger. Return only valid JSON."
            ),
        ) as session:
            response = await asyncio.wait_for(
                session.send_and_wait(  # NOTE: snake_case, not camelCase
                    prompt=(
                        f"Read all markdown files in blog/content/posts/ to understand past coverage. "
                        f"Read {news_json_path} for this week's news stories. "
                        "Generate a blog post in JSON format with: title, description, tags, "
                        "cover_keywords, introduction, sections (array), conclusion, sources. "
                        "Return ONLY valid JSON, no markdown fences."
                    )
                ),
                timeout=300,
            )
            return response.data.content  # raw string, parse with json.loads()
```

**Key SDK features (validated):**
- `CopilotClient(config)` auto-manages bundled CLI process lifecycle ✅
- `session.send_and_wait()` returns `SessionEvent` with `.data.content` (str) and `.data.output_tokens` (float) ✅
- Built-in file tools: agent reads/lists files in `working_directory` ✅
- `PermissionHandler.approve_all` for headless CI ✅
- Auth: `SubprocessConfig(github_token=...)` → sets `COPILOT_SDK_AUTH_TOKEN` env + `--auth-token-env` CLI flag ✅
- `SystemMessageAppendConfig(content=...)` to append custom system prompt ✅
- SDK v0.2.2: 55MB wheel bundles CLI binary (arm64 macOS, also linux x86_64) ✅
- `model` param on `create_session`: `gpt-4.1`, `claude-opus-4.6`, etc. ✅
- `on_permission_request` is **required** (not optional) ✅

**Locally validated (April 14 2026):**
- [x] SDK installs: `pip install github-copilot-sdk` → v0.2.2, Python 3.11+ ✅
- [x] `CopilotClient` starts bundled CLI, creates session ✅
- [x] Auth works with `gho_` token (from `gh auth token`) ✅
- [x] Agent reads files from `working_directory` (read requirements.txt, blog posts) ✅
- [x] Agent returns raw JSON (no fences) matching BlogPost schema ✅
- [x] `response.data.content` is the string content ✅
- [x] `SystemMessageAppendConfig` works for custom system prompt ✅
- [x] `send_and_wait()` is snake_case (not `sendAndWait`) ✅
- [x] Python 3.13 available locally; CI uses 3.11 ✅
- [x] All 45 existing tests pass ✅
- [x] `gh copilot` CLI flags (`--silent`, `--no-ask-user`, `--model`, `--add-dir`, `-p`) confirmed ✅

**Still needs CI validation (can only test in Actions):**
- [ ] Does `ghs_` token (Actions `GITHUB_TOKEN`) authenticate for Copilot SDK? (gho_ works locally — ghs_ is a different token format)
- [ ] Does the bundled CLI binary work on `ubuntu-latest` runner? (macOS arm64 validated locally)
- [ ] Premium request billing: does it count against repo owner's Copilot quota?
- [ ] Total premium requests per blog generation session (expect ~3-15 for Claude Opus 4.6)

**GitHub Actions workflow (Option B):**
```yaml
name: Weekly Blog Post
on:
  schedule:
    - cron: '0 9 * * 5'   # Every Friday at 9:00 AM UTC
  workflow_dispatch:

permissions:
  contents: write
  # NOTE: may need 'models: read' or 'copilot: read' for SDK auth — TBD in CI validation

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt github-copilot-sdk

      - name: Generate blog post
        run: python -m src.main --no-push --verbose
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LLM_MODEL: claude-opus-4.6

      - name: Commit and push
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "blog: weekly post"

  deploy:
    needs: generate
    if: needs.generate.result == 'success'
    uses: ./.github/workflows/deploy.yml
    permissions:
      contents: read
      pages: write
      id-token: write
```

**If `ghs_` token doesn't work for SDK**, alternative auth approaches:
1. Use a PAT stored in `secrets.COPILOT_TOKEN` instead of `GITHUB_TOKEN`
2. Use a GitHub App installation token
3. Fall back to Option A (local CLI with `gho_` token from keyring)

### Other Approaches Researched (April 14 2026)

**Copilot Cloud Agent (assign to issue):** Can be triggered by assigning Copilot
to an issue. Has full repo access. BUT: output is PR-based (designed for code
changes, not content generation), can't be cron-triggered natively, and using
"create issue → assign Copilot" is fragile. **Not suitable.**

**`copilot --remote` CLI:** Lets you monitor/steer a LOCAL CLI session from
GitHub web/mobile. This is a remote *viewer*, not remote *execution*. Still
requires a running terminal on a local machine. **Not useful for CI.**

**GitHub Models API (`models.github.ai`):** Confirmed working with `gho_` token.
`gpt-4.1`, `gpt-4o`, `DeepSeek-R1`, `Grok-3`, `o4-mini` all available. **No Claude.**
Also still requires stuffing all context into the prompt (API has no file access).
Free tier: 8K input / 4K output tokens — too restrictive for blog generation with
past post context. **Rejected for our use case.**

### Caveats & Considerations

| Issue | Solution | Status |
|-------|----------|--------|
| SDK is public preview (v0.2.2) | Monitor for breaking changes. Fallback to Option A if SDK breaks. | Validated locally |
| Python 3.11+ required | CI uses 3.11. Local: Python 3.13 available. Local venv upgrade needed. | ✅ Confirmed |
| Premium request budget | Claude Opus 4.6: ~15 premium/run × 4/month = ~60 out of 300. GPT-4.1: 0 premium. | ✅ Tested |
| No `response_format` | Agent returns raw JSON when prompted. `_extract_json()` strips fences as fallback. | ✅ Validated (no fences needed) |
| Agent reads wrong files | `working_directory` param scopes file access. Prompt specifies exact paths. | ✅ Validated |
| Model deprecation | `LLM_MODEL` env var makes it one-line swap. | ✅ Designed |
| `ghs_` token (CI) may not work | Fallback: PAT in `secrets.COPILOT_TOKEN`, or Option A. | ⚠️ Needs CI test |
| SDK method names are snake_case | `send_and_wait()`, not `sendAndWait()`. Validated in local tests. | ✅ Confirmed |
| `on_permission_request` is required | Always pass `PermissionHandler.approve_all` for headless. | ✅ Confirmed |

### Code Changes Required

| File | Change |
|------|--------|
| `src/config.py` | Remove `LLM_API_KEY`, `LLM_BASE_URL`, all `LLM_FALLBACK_*` vars. Add `LLM_MODEL` (default: `claude-opus-4.6`). |
| `src/content_generator.py` | Replace `OpenAI` SDK calls with Copilot SDK `CopilotClient` (Option B) or `subprocess.run(["gh", "copilot", ...])` (Option A). Agent reads past posts + news from disk. Add JSON extraction (strip code fences). Remove fallback provider logic. |
| `src/main.py` | Write fetched news to temp JSON file before calling content generator. |
| `.env` | Remove all API keys. Add `LLM_MODEL=claude-opus-4.6`. |
| `.github/workflows/weekly-blog.yml` | **Option B:** Rewrite with Copilot SDK. **Option A:** Delete entirely. |
| `.github/workflows/deploy.yml` | No changes — already triggers on push to `blog/**`. |
| `requirements.txt` | Add `github-copilot-sdk` (Option B). Remove `openai`. |
| `tests/` | Mock Copilot SDK / subprocess calls instead of `OpenAI` client. |

### Fallback Strategy

**No fallback.** If Copilot SDK fails → no post. If Mac is off (Option A) → no post.
The user explicitly chose this: "if mac is off on friday then no post."

### Validation Plan

Each step must be fully validated before proceeding to the next.
**Steps 2-4 can proceed in parallel regardless of Step 1 outcome** — they apply
to both Option A and B (just different `call_llm()` backend).

#### Step 1: Validate Copilot SDK in CI (Option B gate — non-blocking)
This determines whether we use Option A or B, but does NOT block Step 2-4.
Step 2 implements `call_llm()` with a backend flag; Step 1 tells us which backend.

- [x] ~~Create `.github/workflows/test-sdk.yml`~~ → Created, ready to push
- [ ] Push to GitHub and trigger via `workflow_dispatch`
- [ ] Verify `client.get_auth_status()` returns `isAuthenticated=True`
- [ ] If auth fails with `ghs_` token: try `permissions: models: read` or `copilot: read`
- [ ] If permissions don't help: try PAT in `secrets.COPILOT_TOKEN`
- [ ] Verify `session.send_and_wait("Reply with: ci-works")` returns response
- [ ] Verify file reading works in CI
- [ ] **Pass → Option B confirmed:** use Copilot SDK in CI
- [ ] **Fail → Option A:** use local `gh copilot` CLI via launchd
- **Done when:** SDK auth + file read confirmed in CI, OR decision made to use Option A
- **Validates:** ghs_ token auth, headless runner, linux x86_64 binary, file access
- **Does NOT block:** Steps 2-4 (they work with either backend)

#### Step 2: Refactor `content_generator.py` ✅ DONE
- [x] ~~Create `call_llm(prompt, model) -> str` that uses Copilot SDK~~
- [x] ~~Implement `_extract_json(raw: str) -> str`~~ — strips fences only when response is wrapped (not inline code blocks)
- [x] ~~Add retry logic (1 retry on JSON parse failure)~~
- [x] ~~Remove `OpenAI` SDK import and all `_try_generate()` / fallback logic~~
- [x] ~~Update `generate_blog_post()` with optional spotlight param~~
- [x] ~~Pydantic models (`BlogPost`, `BlogSection`, `SourceLink`) unchanged~~
- **Validated:** E2E pipeline generates valid BlogPost with gpt-4.1 (April 14 2026)

#### Step 3: Update `main.py` and config ✅ DONE
- [x] ~~`main.py`: Write news to temp JSON, pass path to generator, call spotlight~~
- [x] ~~`config.py`: Removed all `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_FALLBACK_*`~~
- [x] ~~`config.py`: `LLM_MODEL` defaults to `claude-opus-4.6`, `LLM_TIMEOUT=300`~~
- [x] ~~`.env` / `.env.example`: Cleaned — no old API keys~~
- [x] ~~`requirements.txt`: `github-copilot-sdk>=0.2`, `openai` removed~~
- **Validated:** `grep -ri 'gsk_\|csk_\|LLM_API_KEY\|LLM_BASE_URL\|LLM_FALLBACK' src/ .env.example requirements.txt` → clean

#### Step 4: Update tests ✅ DONE
- [x] ~~Removed all OpenAI SDK mocks, replaced with `_call_llm_async` / `_get_github_token` mocks~~
- [x] ~~Tests for: `_extract_json` (raw, fenced, plain fences, whitespace), `call_llm`, `generate_blog_post` (success, retry, fenced JSON, with spotlight), `_get_github_token` (env, CLI, missing)~~
- [x] ~~18 spotlight tests in `test_spotlight.py`~~
- **Validated:** 71 tests, all passing (0.19s) — Python 3.13, pytest 9.0.3

#### Step 5: Set up scheduled execution
- **Option B:** Rewrite `weekly-blog.yml` with Copilot SDK config (see workflow template above)
  - [ ] Add `github-copilot-sdk` to pip install step
  - [ ] Set `GITHUB_TOKEN` env var in generate step
  - [ ] Chain `deploy.yml` via `uses: ./.github/workflows/deploy.yml`
  - [ ] Trigger manually via `workflow_dispatch` and verify end-to-end
- **Option A:** Create `run_blog.sh` wrapper + `com.aidevblog.generate.plist` (launchd)
  - [ ] Wrapper: `cd repo && git pull && source venv/bin/activate && python -m src.main --no-push --verbose && git add blog/ && git commit && git push`
  - [ ] Plist: Friday 9AM, stdout/stderr to `/tmp/aidevblog.{log,err}`
  - [ ] `launchctl load` + `launchctl start` to test
- **Test command:** Trigger manually, then check:
  - [ ] New `.md` file in `blog/content/posts/`
  - [ ] `git log --oneline -1` shows commit
  - [ ] GitHub Actions shows deploy.yml triggered
  - [ ] Live site at `https://frankyfzhou.github.io/AIDevBlogGen/` shows new post
- **Validates:** Full end-to-end: trigger → fetch → generate → publish → deploy
- **Done when:** Live site shows the new post

#### Step 6: Cleanup (partially done)
- [ ] Remove Groq/Cerebras secrets from GitHub repo settings (Settings → Secrets) — requires GitHub UI
- [x] ~~Remove `openai` from `requirements.txt`~~ → done in Step 3
- [x] ~~Update `copilot-instructions.md`~~ → references Copilot SDK, LLM model usage policy added
- [x] ~~Update `.github/skills/blog-generator/SKILL.md`~~ → references Copilot SDK
- [ ] Delete `test-sdk.yml` workflow (after Step 1 validation completes)
- [x] ~~Verify: grep returns no stale references~~ → only OpenAI Blog (RSS source) and prompt example remain (both correct)
- **Remaining:** Remove GitHub repo secrets + delete test workflow (after CI validation)

### Migration Steps (Implementation Order)

1. ~~**Step 2 + 3** (LLM swap + config cleanup)~~ ✅ Done
2. ~~**Step 4** (tests)~~ ✅ Done — 71 tests passing
3. **Step 1** (CI gate) — `test-sdk.yml` created, needs push + trigger
4. **Step 5** (scheduled execution) — after Step 1 result determines Option A/B
5. **Step 6** (cleanup) — partially done, needs repo secrets removal + test workflow deletion
