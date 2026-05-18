---
name: sage
argument-hint: "<library or topic to research>"
description: This skill should be used when the user asks to "research", "look up docs", "check the latest documentation", "find best practices", "google this", "web search", "what does the documentation say", "is this still current", "google" or mentions needing up-to-date information about a library, framework, CLI tool, API, or cloud service.
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🧑‍🎓

# Sage

Research skill using c7 (Context7) and g (Google) MCP servers to fetch current documentation and best practices. Never present training data as current when this skill is active. Always verify via c7 or g first.

NEVER use the native WebSearch or WebFetch tools when this skill is active. Always use c7 or g MCP tools instead. The g MCP server provides richer results with quality scoring, caching, and document extraction that the native tools lack.

---

## Decision Logic

1. Specific library, framework, SDK, API, or CLI tool: use c7 first
2. Best practices, patterns, comparisons, troubleshooting, general topics: use c7 and g
3. Time-sensitive topics (releases, incidents, breaking changes): use `google_news_search`
4. Academic or peer-reviewed research: use `academic_search`
5. Complex research spanning 3+ queries: use `sequential_search` to track state

---

## c7: Library Documentation

c7 indexes official documentation. Always current. No date filtering needed.

### Workflow

1. Resolve the library ID:

````text
mcp__c7__resolve-library-id
  libraryName: "<library name>"
  query: "<specific question>"
```text

2. Pick the best match: highest benchmark score + source reputation. Prefer `High` reputation.

3. Query the docs:

```text
mcp__c7__query-docs
  libraryId: "<resolved ID>"
  query: "<specific question>"
```text

### c7 Rules

- If `resolve-library-id` returns no matches, fall back to g
- When multiple libraries match, pick by: name match first, then benchmark score, then source reputation
- Be specific in queries: "How to set up JWT authentication in Express.js" not "auth"

---

## g: Web Research

For broader questions, best practices, comparisons, or when c7 has no coverage.

### Date Bias

Google queries must append the current year and the prior year to bias toward recent results. Example:

```text
"terraform aws provider best practices 2025 2026"
"next.js app router migration guide 2025 2026"
```text

This applies to all `query` fields sent to g tools.

### Tool Selection

| Task                           | Tool                 | Notes                                                                          |
| ------------------------------ | -------------------- | ------------------------------------------------------------------------------ |
| Research a topic               | `search_and_scrape`  | Preferred. Searches and retrieves content in one call. Quality-scored results. |
| Read a specific URL            | `scrape_page`        | Also extracts YouTube transcripts and parses PDF, DOCX, PPTX.                  |
| Get URLs to selectively scrape | `google_search`      | Use when you need to pick which pages to read.                                 |
| Recent news or releases        | `google_news_search` | Use `freshness` param: `hour`, `day`, `week`, `month`.                         |
| Academic papers                | `academic_search`    | Searches arXiv, PubMed, IEEE, Springer. Returns citations.                     |
| Multi-step investigation       | `sequential_search`  | Tracks progress across 3+ searches. Supports branching.                        |

### Tool Examples

**`search_and_scrape` (preferred for most queries):**

```text
mcp__g__search_and_scrape
  query: "<topic> <current_year> <prior_year>"
  num_results: 3-5
```text

Use 3 results for quick lookups, 5-8 for thorough research.

**`google_news_search` (time-sensitive topics):**

```text
mcp__g__google_news_search
  query: "<topic>"
  freshness: "week"
  num_results: 5
```text

**`academic_search` (peer-reviewed sources):**

```text
mcp__g__academic_search
  query: "<research topic>"
  num_results: 5
```text

**`google_search` then `scrape_page` (selective reading):**

```text
mcp__g__google_search
  query: "<topic> <current_year> <prior_year>"
  num_results: 5
```text

Then scrape only the most relevant URLs from the results.

**`sequential_search` (complex multi-step):**

```text
mcp__g__sequential_search
  searchStep: "Starting research on <topic>"
  stepNumber: 1
  nextStepNeeded: true
```text

Track findings across steps. Record sources with quality scores.

### g Rules

- Always append year strings to queries (current year and prior year)
- Prefer `search_and_scrape` over separate search + scrape calls
- `scrape_page` handles web pages, YouTube transcripts, and documents (PDF, DOCX, PPTX)
- Use `scrape_page` with `mode: "preview"` first on large pages to check size before full fetch
- Results are cached (30 min for search, 1 hr for scrape). Repeated queries are free.
- Responses include `estimatedTokens` and `truncated` metadata for size awareness
- Cite source URLs in findings
- State clearly when information could not be found

---

## Output

Report findings inline in the conversation. Include:

- Source citations (URLs from g, library IDs from c7)
- Version numbers when relevant
- Date of source material when available from g results
- Clear statement if information was not found or results were inconclusive
````
