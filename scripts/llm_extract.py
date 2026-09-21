#!/usr/bin/env python3
"""Second-pass extraction with Claude, for what the rules miss.

The rules pass in analyze.py is deliberately conservative: it drops ambiguous
figures (a bare "2000 refugees" reads as a year) and only recognises
attributions that match a known frame.  This pass reads the prose directly and
recovers the rest.

Output is written to separate files (*_llm_*.csv) and tagged method="llm".  It
is never merged into the rules output automatically -- LLM results vary between
runs and must be reviewed before use.  Every row carries the verbatim sentence
so a reviewer can confirm it against the source PDF.

Usage:
  llm_extract.py --year 2024 [--limit 5] [--model claude-opus-5] [--workers 4]
  llm_extract.py --year 2024 --estimate      # cost estimate only, no API calls
"""
from __future__ import annotations
import argparse, sys, json, csv, os, concurrent.futures as cf
import anthropic
from common import DATA, OUTPUT

MODEL = "claude-opus-5"

SYSTEM = """\
You extract structured data from US State Department Country Reports on Human \
Rights Practices. These reports contain no footnotes; sources are attributed \
inline in prose.

Extract two things from the text given to you:

1. SOURCES - any organisation, body, official, publication or study that the \
text attributes information to. Include NGOs, UN bodies, government ministries \
and commissions, courts, media outlets, unions, and academic or research \
institutions. Use the fullest form of the name that appears in the text. Do NOT \
include entities that are merely the subject of a statement rather than the \
source of it. If the attribution is unnamed ("local NGOs reported"), record it \
with is_named = false.

2. METRICS - quantitative claims: counts, percentages, monetary amounts, rates. \
Record the number exactly as written, the unit, and what it measures. Do NOT \
record dates, years, article or section numbers of laws, or ages used to define \
a legal category.

For every item, quote the complete sentence it came from, verbatim, in \
`sentence`. Accuracy matters more than volume: if you are unsure whether \
something qualifies, omit it. Never infer or supply a figure the text does not \
state."""

SCHEMA = {
    "type": "object",
    "properties": {
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "source_type": {"type": "string", "enum": [
                        "international NGO", "local/national NGO", "UN body",
                        "government body", "judicial", "media", "union",
                        "academic/research", "intergovernmental", "IFI", "other"]},
                    "is_named": {"type": "boolean"},
                    "sentence": {"type": "string"},
                },
                "required": ["source", "source_type", "is_named", "sentence"],
                "additionalProperties": False,
            },
        },
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "measures": {"type": "string"},
                    "attributed_to": {"type": "string"},
                    "sentence": {"type": "string"},
                },
                "required": ["value", "unit", "measures", "attributed_to", "sentence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sources", "metrics"],
    "additionalProperties": False,
}


def extract_one(client, model: str, slug: str, name: str, year: int, text: str) -> dict:
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user",
                   "content": f"Country: {name}\nReport year: {year}\n\n{text}"}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"refusal: {getattr(resp.stop_details, 'category', '?')}")
    body = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(body)
    data["_usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                      "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0)}
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--limit", type=int, help="process only N countries (testing)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--estimate", action="store_true",
                    help="estimate token cost and exit without calling the API")
    a = ap.parse_args()

    tdir = DATA / str(a.year) / "text"
    files = sorted(tdir.glob("*.txt"))
    if not files:
        raise SystemExit(f"No extracted text for {a.year}; run extract.py first.")
    if a.limit:
        files = files[:a.limit]

    if a.estimate:
        chars = sum(f.stat().st_size for f in files)
        approx_in = chars / 3.7 + len(files) * 400          # ~3.7 chars/token + system
        approx_out = len(files) * 3000
        cost = approx_in / 1e6 * 5.00 + approx_out / 1e6 * 25.00
        print(f"{len(files)} documents, ~{chars:,} chars")
        print(f"~{approx_in/1e6:.2f}M input + ~{approx_out/1e6:.2f}M output tokens")
        print(f"Rough cost on {a.model}: ${cost:,.2f} "
              f"(Batches API would halve this; Sonnet ~60% less)")
        return 0

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("No ANTHROPIC_API_KEY set -- relying on an `ant auth login` profile.",
              file=sys.stderr)
    client = anthropic.Anthropic()

    man = json.loads((DATA / str(a.year) / "manifest.json").read_text(encoding="utf-8"))
    src_rows, met_rows, errs = [], [], []
    usage = {"in": 0, "out": 0, "cache_read": 0}

    def work(f):
        slug = f.stem
        name = man["countries"].get(slug, {}).get("name", slug)
        return slug, name, extract_one(client, a.model, slug, name, a.year,
                                       f.read_text(encoding="utf-8"))

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, f): f.stem for f in files}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            slug = futs[fut]
            try:
                slug, name, data = fut.result()
            except Exception as e:
                errs.append((slug, str(e)))
                print(f"  [{i:3}/{len(files)}] ! {slug}: {e}")
                continue
            for k in usage:
                usage[k] += data["_usage"].get(k, 0)
            for r in data["sources"]:
                src_rows.append({"year": a.year, "country": name, "slug": slug,
                                 "method": "llm", **r})
            for r in data["metrics"]:
                met_rows.append({"year": a.year, "country": name, "slug": slug,
                                 "method": "llm", **r})
            print(f"  [{i:3}/{len(files)}] + {slug:34} "
                  f"{len(data['sources']):3} sources  {len(data['metrics']):3} metrics")

    OUTPUT.mkdir(exist_ok=True)
    for rows, name in ((src_rows, "sources"), (met_rows, "metrics")):
        if not rows:
            continue
        p = OUTPUT / f"{name}_llm_{a.year}.csv"
        cols = list({k: None for r in rows for k in r})
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
        print(f"  wrote {p.name}: {len(rows):,} rows")

    cost = usage["in"] / 1e6 * 5.00 + usage["out"] / 1e6 * 25.00
    print(f"\ntokens in {usage['in']:,} (cache reads {usage['cache_read']:,}), "
          f"out {usage['out']:,}  ~${cost:,.2f} on {a.model}")
    if errs:
        print(f"{len(errs)} failures: " + ", ".join(s for s, _ in errs[:10]))
    print("\nThese rows are NOT merged into the rules output. Review before use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
