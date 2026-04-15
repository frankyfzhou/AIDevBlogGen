# AIDevBlogGen — Plan

## Architecture

```
GitHub Actions (cron Friday 9AM UTC)
  ├── Fetch news (HN, Dev.to, Reddit, RSS → rank & dedup)
  ├── Feature Spotlight (LLM tool discovery → changelog → grounded topic)
  ├── Generate blog post (Copilot SDK, two-model system)
  ├── Publish (Hugo markdown, git commit + push)
  └── Deploy (Hugo build → GitHub Pages)
```

## Anti-Hallucination Measures

- Spotlight URLs constrained to allowlist extracted from real changelog HTML
- Source URL validated via HTTP GET (must return 200), with retry loop
- Source page content injected into generation prompt for grounding
- Graceful fallback to news-only post if no valid spotlight topic found

## Future Ideas

- Newsletter integration (Buttondown or RSS-to-email)
- Cross-post to Dev.to and Medium via their APIs
- Draft review step with notification before publish
- YouTube/podcast transcript summarization
