# Build spec — Country Reports query tool

Paste this whole document as the first message of a fresh Claude Code session,
in the directory where you have already run `create-t3-app`.

---

## 0. Before you write any Anthropic API code

**Load the `claude-api` skill first.** Model IDs, thinking parameters and the
streaming API have changed materially through 2025–2026; do not write Anthropic
SDK code from memory. The skill is authoritative over anything you recall.

---

## 1. What this is

An internal question-answering tool over the US State Department's *Country
Reports on Human Rights Practices*, for a team of about 10 at Human Rights
First. People ask questions about a country, a group of countries, or an
edition as a whole, and get an answer with citations they can verify.

The organisation is a human rights NGO and may publish work derived from this
tool. **Every claim the tool surfaces must be traceable to a verbatim sentence
in a specific report.** An answer that cannot be traced is a defect, not a
limitation.

## 2. What already exists — do not rebuild it

A Python pipeline at:

```
/Users/jasonlong-hrf/HRFEngineering/Country Reports on Human Rights Practices/
```

It downloads, parses and analyses the reports. It is working and maintained.
**Your job is to build a web app on top of its outputs, not to reimplement it.**
Read its `README.md` first — it documents the quirks of the source site.

### Data it produces

```
data/<year>/pdf/<slug>.pdf           source PDFs (125 MB total — do NOT commit or upload)
data/<year>/text/<slug>.txt          extracted plain text
data/<year>/sections/<slug>.json     parsed section tree
data/<year>/manifest.json            per-report provenance
output/sources_<year>.csv            inferred source attributions
output/metrics_<year>.csv            inferred quantitative claims
output/schema_<year>.json            that edition's discovered outline
output/comparison_2023_2024.md       narrative comparison
```

### Shapes

`data/<year>/sections/<slug>.json`:
```json
{ "slug": "kenya", "name": "Kenya", "year": 2024,
  "blocks": [ { "section": "Section 1. Life",
                "subsection": "a. Extrajudicial Killings",
                "text": "There were numerous reports…" } ] }
```

`data/<year>/manifest.json` → `countries[slug]`:
```json
{ "slug": "kenya", "name": "Kenya",
  "page_url": "https://www.state.gov/reports/2024-…/kenya/",
  "pdf_url":  "https://www.state.gov/wp-content/uploads/2025/07/624521_KENYA-2024-HUMAN-RIGHTS-REPORT.pdf",
  "sha256": "263b4904…", "bytes": 164979, "status": "cached" }
```

`output/sources_<year>.csv` columns:
`year, country, slug, source, source_type, match, confidence, section, subsection, method, sentence`

`output/metrics_<year>.csv` columns:
`year, country, slug, value, unit, qualifier, metric_type, section, subsection, method, sentence`

### Volumes

| | 2023 | 2024 |
|---|---|---|
| Reports | 194 | 195 |
| Section blocks | 4,724 | 2,627 |
| Body text | 11.3 M chars | 3.85 M chars |
| Source mentions | 14,551 | 5,429 |
| Quantitative claims | 3,676 | 1,372 |

Total body text ≈ 14.5 MB. Small. Do not reach for a vector database.

## 3. Truths about the data that the product must respect

These are not trivia. Each one causes a wrong answer if ignored.

1. **The reports contain no footnotes or bibliography.** Every row in
   `sources_*.csv` and `metrics_*.csv` is *inferred from sentence structure*.
   The UI must never present these as citations the State Department made. Label
   them as extracted attributions and always show the source sentence.

2. **Rows carry a confidence grade.** `high` = matched against a fixed list of
   known organisations; `medium` = pattern-matched name; `low` = unnamed
   ("local NGOs reported"). Default views should filter to `high` + `medium`,
   with `low` available behind a toggle. Low-frequency names are often truncated
   phrases, not real organisations.

3. **The 2024 edition restructured the outline completely** — 7 sections became
   3, with 96% heading drift. **Section-level comparison across the 2023/2024
   boundary is invalid.** If a user asks for one, the app must say so and offer
   a country- or source-level comparison instead. Do not silently produce a
   section diff. `output/schema_<year>.json` records each edition's outline —
   compute drift from it rather than hardcoding, because the 2025 edition may
   restructure again.

4. **2023 reports are ~3× longer than 2024 reports** (median 53,471 vs 17,972
   chars). Retrieval budgets must be per-token, not per-document.

5. **North Macedonia 2024 is missing** — state.gov's WAF blocks automated
   retrieval of that one file. Exclude it explicitly and disclose it; never
   interpolate.

6. **Country slugs are not stable between editions** (`thebahamas` → `the-bahamas`),
   and some reports are published under two slugs with identical content
   (`burma` and `burma-draft` in 2023). Store a canonical country key and
   deduplicate by SHA-256.

## 4. Architecture

T3 stack: Next.js App Router, TypeScript, tRPC, Tailwind, NextAuth. Deployed on
Vercel.

**Database: Postgres** (Neon via the Vercel integration). Not SQLite — Vercel's
filesystem is ephemeral and read-only in practice. Postgres also gives native
full-text search, which removes the need for an embeddings service entirely.

**ORM: Drizzle.** You need a raw-SQL escape hatch for `tsvector` ranking, and
Drizzle makes that clean. Prisma is acceptable if the scaffold already uses it.

**Retrieval: Postgres full-text search** (`tsvector` + `ts_rank_cd`), no
embeddings. With 389 documents and 7,351 section blocks, lexical search is
sufficient and costs nothing. Revisit only if recall proves inadequate in use.

### Schema

```
editions        year PK, released_at, report_count, outline_json, schema_drift_vs_prior
reports         id PK, year, slug, country_key, country_name, pdf_url, page_url,
                sha256, char_count, UNIQUE(year, country_key)
sections        id PK, report_id FK, ordinal, section, subsection, text, tsv
source_mentions id PK, report_id FK, source, source_type, match, confidence,
                section, subsection, sentence, method, tsv
metrics         id PK, report_id FK, value NUMERIC, unit, qualifier, metric_type,
                section, subsection, sentence, method, tsv
queries         id PK, user_id, question, route, model, input_tokens, output_tokens,
                cost_usd, cached BOOL, created_at
answer_cache    hash PK, question, doc_ids, answer_json, created_at
```

Generated `tsv` columns with GIN indexes on `sections.text`,
`source_mentions.sentence`, `metrics.sentence`.

`country_key` is the canonical slug: lowercase, punctuation stripped, leading
articles removed — so 2023 and 2024 rows join correctly.

### Ingest

A `pnpm db:seed` script that reads the Python pipeline's outputs from a path in
`PIPELINE_DIR` and loads Postgres. Idempotent, re-runnable, and safe to point at
a 2025 edition when it lands. **Do not commit the PDFs.** Store `pdf_url` and
`sha256` only; the PDFs stay local and remain publicly available at state.gov.

## 5. Query routing

Two routes. A cheap classifier picks one; the user can override in the UI.

**Route A — structured (no LLM, $0, exact).**
Aggregate and factual questions answered by SQL and rendered as tables:
"which countries cite Human Rights Watch", "every child-labour figure in East
Africa", "how many reports mention transnational repression", "what changed in
sourcing between editions". These must return *exact* counts. Never let a
language model count rows.

**Route B — interpretive (retrieval + Claude).**
"What does the Kenya 2024 report say about press freedom?", "How do these three
countries differ on prison conditions?" Retrieve the top-ranked section blocks
by FTS, cap the context at a token budget, and send with a citation-enforcing
prompt.

The classifier should be a small structured-output call. When it is uncertain,
prefer Route B but render any exact counts from SQL alongside.

### Models

Budget is ~$10/month for roughly 200 queries; do not contort the design for
cost. Measured per-query costs on this corpus:

| Context | Haiku 4.5 | Sonnet 5 | Opus 5 |
|---|---|---|---|
| One 2024 report (~4.7k tok) | $0.010 | $0.020 | $0.050 |
| Five retrieved reports (~25k tok) | $0.029 | $0.058 | $0.144 |

**Default to Sonnet 5.** Offer an explicit "careful pass" toggle that uses Opus
5. Use Haiku 4.5 for the router. Enable prompt caching on the system prompt and
on retrieved context — it helps latency as much as cost.

### Guardrails

- Cap retrieved context at a configurable token budget (start ~40k).
- Per-user monthly query counter, with a soft cap from an env var.
- Log token usage and computed cost to the `queries` table so spend is visible.
- Cache answers keyed on normalised question + retrieved document IDs.

## 6. Answer contract

Every Route B answer returns:

```ts
{ answer: string,
  citations: Array<{
    reportId: string, country: string, year: number,
    section: string, subsection: string | null,
    sentence: string,        // verbatim from the report
    pdfUrl: string }>,
  caveats: string[],         // e.g. schema-drift warning, missing country
  route: "structured" | "interpretive",
  usage: { model, inputTokens, outputTokens, costUsd, cached } }
```

The system prompt must instruct Claude to answer **only** from supplied
passages, to quote verbatim in every citation, and to say plainly when the
passages do not support an answer. An uncited claim is a bug.

The UI renders citations inline, expandable to the full sentence, each linking
to the source PDF on state.gov.

## 7. Auth

NextAuth with Google, restricted to the `humanrightsfirst.org` email domain.
No public access. No self-registration.

## 8. UI

Utilitarian and fast; this is a working tool, not a landing page.

- Question box with route indicator and a model toggle.
- Streaming answer (**required** — LLM calls can exceed comfortable serverless
  response windows, and streaming is better UX regardless).
- Citations panel: country, year, section, verbatim sentence, PDF link.
- Filters: edition year, country multi-select, confidence tier.
- A browse mode: pick a country and year, read the report by section.
- A persistent, visible note that source and metric rows are *extracted from
  prose*, not official citations — with a link to a short methodology page
  covering the six points in §3.
- Query history for the signed-in user.

## 9. Build order

1. Schema + migrations; seed script; verify row counts against §2.
2. Route A end to end (SQL + tables + UI). Useful on its own, costs nothing.
3. FTS retrieval, with a test set of ~10 real questions to check recall.
4. Route B with citations and streaming.
5. Router, caching, usage logging.
6. Auth, then deploy to Vercel.

Ship 1–2 before starting 4. The structured route answers a large share of real
questions on its own and validates the schema before any LLM code exists.

## 10. Definition of done

- `pnpm db:seed` loads both editions from a clean database; counts match §2.
- Route A returns exact counts, verified against the CSVs.
- Every Route B citation quotes a sentence that exists verbatim in the cited
  report — add a test that asserts this against the database.
- Asking for a section-level 2023↔2024 comparison produces the drift warning,
  not a diff.
- North Macedonia 2024 is absent and disclosed, not interpolated.
- Per-query cost is logged and visible.
- Deploys on Vercel; only org-domain Google accounts can sign in.

## 11. Ask before assuming

- Whether to load 2023, 2024 or both at launch.
- Whether query history should be visible to the whole team or per-user.
- Where `PIPELINE_DIR` will live in CI/production (the seed is likely run
  locally against the production database rather than from a Vercel build).
