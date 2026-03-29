---
description: "Refresh AI dev tool landscape and update discovery.json. Use when: update sources, refresh trends, discover new AI coding tools, monthly source refresh."
agent: "agent"
---

Refresh the discovery.json configuration file that controls which news sources, keywords, and repositories the weekly blog pipeline monitors.

## Your Task

1. **Research the current AI-assisted development landscape** using web search:
   - What are the most popular AI coding tools right now? (not just from memory — search for current rankings, comparisons, and trending discussions)
   - What new tools or major updates have emerged in the last month?
   - Which blogs, RSS feeds, and subreddits are developers actively reading for AI dev tool news?
   - What GitHub repos are trending in the AI coding tools space?

2. **Read the current [discovery.json](../../discovery.json)** and identify what's outdated:
   - Tools that have lost relevance or shut down
   - Missing tools that developers are talking about now
   - RSS feeds that may have moved or died
   - New subreddits or communities that have formed

3. **Generate an updated discovery.json** with:
   - `updated`: today's date
   - `focus`: kept as "AI-assisted software development tools, techniques, and workflows for developers"
   - `keywords`: 30-50 terms covering current AI dev tools by name, categories, and techniques
   - `rss_sources`: 8-12 high-signal RSS/Atom feeds (verify URLs are real), each with name, url, and authority score (2.0 = first-party tool blogs, 1.5 = quality tech blogs, 1.0 = general)
   - `subreddits`: 4-6 active developer communities focused on AI coding tools
   - `github_repos`: 5-10 actively maintained repos worth tracking for releases (awesome lists, popular tools)
   - `search_queries`: 2-4 broad web search queries for dynamic content discovery

4. **Show me the diff** between old and new discovery.json before writing. Explain:
   - What was added and why
   - What was removed and why
   - Any notable shifts in the landscape

5. **After I approve**, write the updated discovery.json and commit it.

## Guidelines

- Prioritize **developer-focused AI coding tools** (GitHub Copilot, Claude Code, Cursor, etc.) over general AI news
- Include both established tools AND emerging ones
- RSS feeds must be real, working URLs — verify them
- Subreddits should be active (>10K members or high recent activity)
- Don't remove a source just because it's quiet this month — only remove if it's truly dead or irrelevant
- The awesome-copilot repo (github/awesome-copilot) should always be included
