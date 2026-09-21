# Working in this repository

This repo holds the US State Department's *Country Reports on Human Rights
Practices* — the source PDFs, the parsed text, extracted source attributions and
quantitative claims, and a pipeline that repeats the whole thing each year.

Most people opening this repo want to **ask questions about the reports**. This
file tells you how to answer them without getting them wrong.

## Rules for answering questions about this data

**1. Quote, don't paraphrase from memory.** Every claim you make about what a
report says must be grounded in text you actually read from this repo, with the
country, edition year and section named. Staff here publish work based on these
answers.

**2. Never count by reading.** Do not scan documents and report a tally — you
will miscount across 389 reports and the error will be invisible. Counts come
from the CSVs, computed. See *Exact counts* below.

**3. Absence of reporting is not evidence of absence.** The 2024 reports are
about two-thirds shorter than 2023 (median ~53,000 → ~18,000 characters), and
not one of the 192 countries in both editions got longer. When a topic is
missing from a 2024 report, the likeliest explanation is that the reporting was
cut, not that the situation improved. **Say this every time you note something
is absent.**

**4. Never compare the editions section by section.** 2023 used seven thematic
sections; 2024 uses three (Life, Liberty, Security of the Person), with 96%
heading drift. The sections do not correspond. Country-level, length-level and
source-level comparisons are valid; section-level ones are not. Compute drift
from `output/schema_<year>.json` rather than assuming — a future edition may
restructure again.

**5. Sources are inferred, not cited.** These reports have no footnotes or
bibliography. Attributions appear inline in prose ("according to UNICEF"). Rows
in `output/sources_*.csv` were extracted by pattern-matching sentences. Describe
them as attributions made in the text, never as formal citations, and check the
`sentence` column before relying on a row. Filter to `confidence` of `high` or
`medium`; `low` rows are unnamed attributions and truncated fragments.

**6. North Macedonia 2024 is missing** — state.gov blocks automated retrieval of
that one file. Say it is missing; do not read the gap as a finding.

Full detail: `corpus/METHODOLOGY.md`.

## Where things are

```
data/<year>/pdf/<slug>.pdf        source PDFs as published
data/<year>/text/<slug>.txt       extracted plain text
data/<year>/sections/<slug>.json  parsed section tree  {slug,name,year,blocks[{section,subsection,text}]}
data/<year>/manifest.json         per-report source URL + sha256
corpus/by-country/<country>.md    one file per country, all editions — best for reading
corpus/by-edition/<year>-NN.md    whole-edition shards
output/sources_<year>.csv         year,country,slug,source,source_type,match,confidence,section,subsection,method,sentence
output/metrics_<year>.csv         year,country,slug,value,unit,qualifier,metric_type,section,subsection,method,sentence
output/schema_<year>.json         that edition's discovered outline
output/comparison_2023_2024.md    narrative comparison
scripts/                          the pipeline (fetch, extract, analyze, compare, package)
```

Editions present: **2023** (194 reports) and **2024** (195 reports).

## Exact counts

Use the CSVs and compute. `.venv/bin/python` has the dependencies.

```bash
# How many countries cite a given organisation, and how often
.venv/bin/python -c "
import csv
r=[x for x in csv.DictReader(open('output/sources_2024.csv')) if x['source']=='Human Rights Watch']
print(len({x['country'] for x in r}),'countries,',len(r),'mentions')"

# Every quantitative claim for one country
.venv/bin/python -c "
import csv
for x in csv.DictReader(open('output/metrics_2024.csv')):
    if x['slug']=='kenya': print(x['value'],x['unit'],'|',x['sentence'][:100])"

# Which countries have a given subsection
.venv/bin/python -c "
import json,pathlib
print([p.stem for p in pathlib.Path('data/2024/sections').glob('*.json')
       if any(b.get('subsection','')=='e. Instances of Transnational Repression'
              for b in json.load(open(p))['blocks'])])"
```

For free-text search, grep the corpus files — they are plain markdown:

```bash
grep -n "transnational repression" corpus/by-edition/2024-01.md | head
grep -rl "enforced disappearance" corpus/by-country/ | head
```

## Adding the next edition

```bash
./run.sh 2025 2024                                  # fetch, extract, analyze, compare
.venv/bin/python scripts/package_corpus.py --years 2023,2024,2025
```

`fetch.py` is resumable and skips PDFs already on disk. state.gov rate-limits
bulk crawling — 3 to 5 workers is the practical ceiling; the scraper backs off on
429s. `extract.py` discovers headings per document rather than assuming a fixed
outline, so if State restructures again it reports the drift instead of silently
producing empty sections. **Check `output/schema_2025.json` before trusting any
comparison.**

## Conventions

- Python runs from `.venv/bin/python`; don't install into the system interpreter.
- The PDFs are committed deliberately — they are the primary sources, and the
  2024 edition already showed these reports can be cut without notice.
- `data/<year>/manifest.json` is the provenance record. Keep it with any
  published derivative.
- Do not rewrite the pipeline in another language. It works and it is the thing
  that will be re-run each year.
