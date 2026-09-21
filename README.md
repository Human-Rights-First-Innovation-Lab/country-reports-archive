# Country Reports on Human Rights Practices — archive & comparison

Downloads the State Department's annual *Country Reports on Human Rights
Practices*, extracts the sources they cite and the figures they state, and
compares one edition against another.

Built to answer a specific question each year: **what changed** — in coverage,
in length, and in who the reports rely on as evidence.

## If you just want to read or search the reports

You do not need to run anything.

| What you want | Where to look |
|---|---|
| One country, all editions in one file | `corpus/by-country/<country>.md` |
| A whole edition in a few large files | `corpus/by-edition/` |
| The 2024 edition only | `corpus-2024/` |
| What changed between 2023 and 2024 | [`output/comparison_2023_2024.md`](output/comparison_2023_2024.md) |
| The original PDFs as published | `data/<year>/pdf/` |
| **What these figures can and cannot bear** | [`corpus/METHODOLOGY.md`](corpus/METHODOLOGY.md) |

**Read `corpus/METHODOLOGY.md` before citing anything.** These reports carry no
footnotes, so the extracted sources and figures are inferred from prose rather
than read off a citation list, and the 2023→2024 restructuring makes some
comparisons invalid. The methodology note explains both.

The reports are works of the US Government and are in the public domain.

## Quick start

```bash
./run.sh 2025 2024      # fetch + extract + analyze 2025, then compare with 2024
./run.sh 2025           # without the comparison
```

Each step can also be run alone:

```bash
.venv/bin/python scripts/fetch.py    --year 2025
.venv/bin/python scripts/extract.py  --year 2025
.venv/bin/python scripts/analyze.py  --year 2025
.venv/bin/python scripts/compare.py  2024 2025
```

`fetch.py` is resumable — it skips PDFs already on disk. Re-run it after a
rate-limited run; use `--force` to re-download and re-verify checksums.

## Read this before citing anything

**The reports contain no footnotes and no bibliography.** Sources are
attributed inline, in prose:

> "More than 80 percent of employees worked in the informal sector, according to
> World Bank data."

Everything in `output/sources_*.csv` and `output/metrics_*.csv` is therefore
*inferred from sentence structure*, not read off a citation list. Every row
carries the verbatim `sentence` it came from. **Check the sentence before using
a row in published work.** Treat the CSVs as a research index, not as findings.

Two deliberate choices shape the numbers:

- **Precision over recall.** A bare four-digit count with no comma
  (`2000 refugees`) is dropped, because it is far more often a year than a
  quantity. Real counts are lost this way; corrupted counts are not introduced.
- **Confidence is recorded, not hidden.** `confidence` is `high` for
  gazetteer organisations (UNHCR, Human Rights Watch, …), `medium` for
  pattern-matched names, `low` for unnamed attributions ("local NGOs
  reported"). Filter on it.

`scripts/llm_extract.py` is an optional second pass that reads the prose
directly and recovers what the rules miss. It writes to separate
`*_llm_*.csv` files and is **never merged automatically** — LLM output varies
between runs and needs review. Estimate the cost before running it:

```bash
.venv/bin/python scripts/llm_extract.py --year 2024 --estimate
```

## Schema drift is the thing to watch

The 2024 edition restructured the report outline completely and cut length by
roughly two-thirds. `extract.py` discovers headings per document rather than
assuming a fixed outline, and writes what it found to `output/schema_<year>.json`.
`compare.py` measures drift between two editions and **suppresses section-level
comparison when the outlines don't correspond**, rather than presenting
mismatched sections as a delta.

When the next edition lands, check `output/schema_<year>.json` first. If drift
against the prior year is high, section-level comparison is off the table —
country-level, length and source-level comparisons still hold.

## Layout

```
data/<year>/pdf/        source PDFs, one per country
data/<year>/text/       extracted plain text
data/<year>/sections/   parsed section tree (JSON)
data/<year>/manifest.json   source URL, sha256, byte size, fetch time
output/                 CSVs, schema reports, comparison markdown
```

`manifest.json` is the provenance record — every PDF's origin URL and SHA-256.
Keep it with the data if any of this is cited.

## Known gaps

| Edition | Country | Issue |
|---|---|---|
| 2024 | North Macedonia | The PDF exists but state.gov's WAF returns 403 to scripted requests. Download it manually in a browser from the URL below and save as `data/2024/pdf/north-macedonia.pdf`, then re-run `extract.py`. |

North Macedonia 2024:
`https://www.state.gov/wp-content/uploads/2025/07/624521_NORTH-MACEDONIA-2024-HUMAN-RIGHTS-REPORT.pdf`

Because of this gap, `compare.py` currently lists North Macedonia as "dropped in
2024". It was not dropped — the report exists. Adding the PDF and re-running
`extract.py` removes it from that line.

2023 `manifest.json` records lack `pdf_url` for most countries (a one-time bug,
since fixed). Restore full provenance with
`.venv/bin/python scripts/fetch.py --year 2023 --force`.

## Fetching notes

state.gov rate-limits bulk crawling (HTTP 429) and blocks the default fetch
tooling; the scraper sends a browser user-agent, backs off on 429/503, and
honours `Retry-After`. Three to five workers is the practical ceiling.

Two quirks the scraper handles, both of which silently lose countries if
ignored:

- Index links are inconsistent about trailing slashes — `…/practices/japan`
  has none, most others do.
- When a country page is broken or 404s, the PDF is still reachable: the upload
  path and numeric id are **per-edition, not per-country**
  (`…/uploads/2024/02/528267_<COUNTRY>-2023-HUMAN-RIGHTS-REPORT.pdf`), so the
  URL can be constructed from any other country's. This recovers Burma 2023,
  whose index link is dead.
