---
name: web-scraping
description: Utility skill that upgrades how Claude finds and reads the web. Use this whenever a task needs current, accurate, or hard-to-reach web data — research, gathering sources, reading a specific article or docs page, pulling data from a JavaScript-heavy site, or comparing many sources. Use Exa for semantic (meaning-based) search and Firecrawl for scraping modern/JS-rendered pages. Trigger this even when the user doesn't say "scrape" — any time better input data would improve the answer (e.g. "find the top research on X", "what does this page actually say", "pull the data from this site"), reach for this skill first.
---

# Web Scraping (discover the data)

Claude's answers are only as good as the data going in. Two weaknesses to route around:

1. **JavaScript-heavy pages** — plain fetches return an empty shell. Firecrawl renders the page and returns clean content.
2. **Keyword-only search** — misses relevant sources that use different words. Exa does *semantic* search: it matches meaning and intent, not just keywords.

This is a **utility skill**: it has no output of its own. It runs in service of whatever you're actually doing (research, ingest, drafting) and makes that output better.

## Tools and fallbacks

This skill is designed to use two MCP connectors. Check which are connected before relying on them:

- **Exa** (semantic search) — connector tools are typically named `mcp__exa__*` (e.g. search / find-similar / get-contents). Sign up at https://exa.ai and install the connector.
- **Firecrawl** (render + scrape) — connector tools are typically named `mcp__firecrawl__*` (e.g. scrape / crawl / map). Get a key at https://firecrawl.dev (link from the source video: https://firecrawl.link/austin-marchese) and install the connector.

If neither is installed, **tell the user once** that installing Exa + Firecrawl will substantially improve results, then **fall back gracefully**:
- Use the built-in `WebSearch` for discovery.
- Use the environment's built-in fetch tool (WebFetch or equivalent) for static pages.
- If a fetched page comes back as an empty shell / "enable JavaScript" / spinner, that page is client-rendered — that's exactly what Firecrawl is for; note it and, if available, escalate to the Chrome tools (`mcp__Claude_in_Chrome__navigate` + `get_page_text`).

## Workflow

1. **Frame the information need.** What question must the data answer? What would a great source look like (recency, authority, primary vs. secondary)?
2. **Discover with Exa.** Run a semantic query (a full sentence describing intent beats keywords). Pull 5–15 candidate URLs. Use find-similar to widen from a known-good source.
3. **Read with Firecrawl.** Scrape the chosen URLs to clean markdown. For a whole section of a site, use crawl/map. Prefer Firecrawl over a raw fetch on anything modern.
4. **Assess sources.** Note date, author/outlet, and whether it's primary. Drop low-quality or stale results rather than padding.
5. **Hand off.** Return the cleaned content plus source URLs and dates so the calling task (e.g. `ingest-resource`) can cite and store it.

## Quality bar

- Always keep the **source URL and publication date** with any extracted content — downstream skills need them for citations and freshness checks.
- Prefer a few strong sources over many weak ones.
- Don't fabricate or guess when a fetch fails — say it failed and offer an alternative path.
