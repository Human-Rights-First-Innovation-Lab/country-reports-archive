# Methodology and limits

Read this before relying on anything in this corpus.

## What these files are

The text of the US State Department's *Country Reports on Human Rights
Practices*, extracted from the PDFs the Department published, reorganised so
each country's reports across editions sit in one file. The wording is the
State Department's, unedited. The structure — which headings exist, which text
belongs under them — was parsed programmatically and can contain errors.

Each report's source PDF URL is recorded at the top of its section. The
canonical record is `data/<year>/manifest.json`, which holds every report's
source URL and SHA-256 checksum.

## Six things that cause wrong answers if ignored

**1. There is no bibliography.** These reports carry no footnotes. Sources are
attributed inline, in prose — *"according to UNICEF"*, *"the KNCHR reported 82
cases"*. The `output/sources_*.csv` files are therefore **inferred from sentence
structure**, not read off a citation list. They are a research index, not a
record of what the State Department formally cited. Always check the sentence.

**2. Extracted rows carry confidence grades.** `high` means the organisation was
matched against a fixed list of known bodies (UNHCR, Human Rights Watch, …).
`medium` means a name was pattern-matched and may be truncated or wrong. `low`
means the attribution was unnamed ("local NGOs reported"). Low-frequency names
in particular are often sentence fragments rather than real organisations.

**3. The 2024 edition restructured the outline completely.** The 2023 edition
used seven thematic sections; 2024 uses three, with 96% heading drift. **Section
-level comparison across that boundary is not valid** — the sections do not
correspond, and a section-by-section diff produces confident-looking numbers
that mean nothing. Country-level, length and source-level comparisons remain
valid. A future edition may restructure again.

**4. The 2024 reports are roughly two-thirds shorter than 2023.** Median report
length fell from about 53,000 characters to 18,000, and not one of the 192
countries present in both editions got longer. When a topic is absent from a
2024 report, that is frequently because the reporting was cut, not because the
situation changed. Absence is not evidence.

**5. Number extraction is deliberately conservative.** An ambiguous four-digit
figure — "2000 refugees" — is discarded rather than risk recording a year as a
quantity. Real counts are lost this way. `output/metrics_*.csv` undercounts; it
does not overcount.

**6. North Macedonia's 2024 report is missing** from this corpus. The report
exists, but state.gov blocks automated retrieval of that one file. It is
excluded from every figure rather than estimated. The URL is in the project
README if you want to fetch it by hand.

## What the figures mean

Report "length" is measured in characters of extracted body text, with running
headers and page furniture removed. It is a proxy for how much detail the
Department published, not a measure of quality, accuracy or coverage.

## Provenance

Every PDF in `data/<year>/pdf/` is recorded in that year's manifest with the URL
it came from and its SHA-256. If you publish anything derived from this corpus,
that manifest is the record that supports it.

These reports are works of the US Government and are in the public domain.
