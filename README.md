# AIDevBlogGen

Automated weekly blog generator for AI-assisted software development news. Fetches from 10+ sources, generates polished posts with GPT-4o-mini, and publishes to GitHub Pages via Hugo.

## How It Works

```
News Sources (HN, Dev.to, Reddit, RSS) → Fetch & Rank → GPT-4o-mini → Hugo Markdown → GitHub Pages
```

Every Monday at 9 AM UTC, a GitHub Actions workflow:
1. Fetches AI/dev news from HackerNews, Dev.to, Reddit, and 8+ RSS feeds
2. Ranks stories by keyword relevance, recency, and engagement
3. Generates a structured blog post via OpenAI
4. Commits the post and deploys the Hugo site to GitHub Pages

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/frankyfzhou/AIDevBlogGen.git
cd AIDevBlogGen

# 2. Install Hugo
brew install hugo

# 3. Set up Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Add theme
cd blog && git submodule add https://github.com/adityatelange/hugo-PaperMod themes/PaperMod && cd ..

# 5. Configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 6. Generate a post
python -m src.main --no-push --verbose

# 7. Preview
cd blog && hugo server -D
# Open http://localhost:1313
```

See [MANUAL_STEPS.md](MANUAL_STEPS.md) for detailed setup instructions.

## Usage

### Generate locally (no git push)
```bash
python -m src.main --no-push --verbose
```

### Generate and publish
```bash
python -m src.main --verbose
```

### Preview blog
```bash
cd blog && hugo server -D
```

### Run tests
```bash
python -m pytest tests/ -v
```

### Copilot integration
Type `/generate-blog-post` in VS Code Copilot Chat for on-demand generation.

## Project Structure

```
├── src/                    Python pipeline
│   ├── config.py           Configuration & news source definitions
│   ├── news_fetcher.py     Multi-source fetcher with ranking
│   ├── content_generator.py  LLM blog generation (OpenAI)
│   ├── publisher.py        Hugo file writer + git operations
│   └── main.py             CLI orchestrator
├── blog/                   Hugo static site (PaperMod theme)
├── templates/              Jinja2 blog post template
├── tests/                  pytest test suite
├── .github/workflows/      GitHub Actions (weekly cron + deploy)
└── .github/skills/         Copilot skill for on-demand generation
```

## News Sources

| Source | Type | Items |
|--------|------|-------|
| HackerNews | API | Top AI-relevant stories |
| Dev.to | API | Weekly top AI articles |
| Reddit | JSON | r/MachineLearning, r/artificial |
| OpenAI, Google AI, Anthropic, Hugging Face, etc. | RSS | Latest blog posts |
| The Verge, Ars Technica, MIT Tech Review | RSS | AI news coverage |

## Cost

| Item | Cost |
|------|------|
| Hosting (GitHub Pages) | Free |
| CI/CD (GitHub Actions) | Free |
| OpenAI GPT-4o-mini | ~$0.03/post |
| **Monthly total** | **< $0.15** |

## License

MIT
