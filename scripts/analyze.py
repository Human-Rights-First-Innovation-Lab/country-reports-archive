#!/usr/bin/env python3
"""Extract cited sources and quantitative claims from parsed report sections.

IMPORTANT: these reports contain no footnotes or bibliography.  Sources appear
only as inline prose attributions ("according to UNICEF", "the KNCHR reported
82 cases").  Everything here is therefore *inferred* from sentence structure,
and every emitted row carries the verbatim sentence it came from so a human can
confirm or reject it.  Nothing in these outputs should be cited without that
check.

Two passes:
  rules  - deterministic patterns + an organisation gazetteer.  Reproducible,
           auditable, high precision, imperfect recall.
  llm    - optional second pass over sentences the rules did not resolve
           (llm_extract.py); emitted with method="llm" and always segregated.

Usage:  analyze.py --year 2024
"""
from __future__ import annotations
import argparse, re, sys, json, csv, collections
from common import DATA, OUTPUT, clean_text

# ---------------------------------------------------------------- sources ---

# Organisations that recur across the corpus.  Matching these gives a clean,
# high-precision spine; the generic patterns below catch the long tail.
GAZETTEER = {
    "Human Rights Watch": "international NGO",
    "Amnesty International": "international NGO",
    "Freedom House": "international NGO",
    "Reporters Without Borders": "international NGO",
    "Committee to Protect Journalists": "international NGO",
    "International Crisis Group": "international NGO",
    "Transparency International": "international NGO",
    "International Committee of the Red Cross": "international NGO",
    "UNICEF": "UN body", "UNHCR": "UN body", "UNESCO": "UN body",
    "UNDP": "UN body", "UNFPA": "UN body", "UN Women": "UN body",
    "World Food Program": "UN body", "World Health Organization": "UN body",
    "International Organization for Migration": "UN body",
    "International Labor Organization": "UN body",
    "International Labour Organization": "UN body",
    "Office of the UN High Commissioner for Human Rights": "UN body",
    "United Nations": "UN body",
    "World Bank": "IFI", "International Monetary Fund": "IFI",
    "European Union": "intergovernmental",
    "Organization for Security and Cooperation in Europe": "intergovernmental",
    "African Union": "intergovernmental",
    "Council of Europe": "intergovernmental",
    "Organization of American States": "intergovernmental",
    "International Criminal Court": "judicial",
    "European Court of Human Rights": "judicial",
}

# Generic attribution frames.  Group 'org' is the candidate source.
# Organisation names routinely contain lowercase connectors ("UN Working Group
# on Arbitrary Detention", "Ministry of Labor and Social Protection").  Allow
# them mid-name, but never at the start or end, so names stay whole without
# swallowing surrounding prose.
_CONN = r"(?:of|on|for|and|the|in|de|des|du|para|pour)"
_TOK = r"[A-Z][\w'&.-]*"
_ORG = rf"{_TOK}(?:\s+(?:{_CONN}\s+)?{_TOK}){{0,7}}(?:\s+\([A-Z]{{2,10}}\))?"

ATTRIB = [
    # "according to <Org>"
    re.compile(rf"\baccording to (?:the )?(?P<org>{_ORG})"),
    # "<Org> reported/estimated/documented/recorded/alleged/found/stated"
    re.compile(rf"\b(?:The |the )?(?P<org>{_ORG})\s+"
               r"(?:reported|estimated|documented|recorded|alleged|asserted|"
               r"found|stated|said|noted|observed|concluded|claimed|"
               r"published|released)\b"),
    # "as reported by <Org>" / "per <Org>"
    re.compile(rf"\b(?:as (?:reported|documented) by|per) (?:the )?(?P<org>{_ORG})"),
]

# Unnamed but meaningful attributions the reports lean on heavily.
GENERIC_ATTRIB = re.compile(
    r"\b((?:local |international |independent |domestic )?"
    r"(?:NGOs?|nongovernmental organizations?|civil society (?:groups?|organizations?)|"
    r"human rights (?:groups?|organizations?|activists?|defenders?|monitors?)|"
    r"media (?:outlets?|reports?)|press reports?|journalists?|observers?|"
    r"activists?|academics?|experts?|labor unions?|trade unions?))\b", re.I)

# Noise that the capitalised-phrase patterns pick up but which is not a source.
STOPWORDS = {
    "the government", "government", "the country", "the law", "the constitution",
    "the year", "the ministry", "the president", "the state", "the united states",
    "in", "there", "during", "however", "although", "while", "some", "many",
    "human rights", "the human rights", "section", "executive summary",
}

# ---------------------------------------------------------------- metrics ---

UNITS = (r"persons?|people|individuals?|deaths?|killings?|cases?|incidents?|"
         r"children|minors?|women|men|girls?|boys?|journalists?|prisoners?|"
         r"detainees?|inmates?|refugees?|migrants?|workers?|victims?|"
         r"complaints?|convictions?|prosecutions?|arrests?|investigations?|"
         r"attacks?|protesters?|demonstrators?|percent|households?|families")

NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
WORDNUM = (r"(?:more than|at least|approximately|about|nearly|fewer than|"
           r"up to|an estimated|some|over|around)")

RE_METRIC = re.compile(
    rf"(?P<qual>{WORDNUM}\s+)?(?P<value>{NUM})\s+(?P<unit>{UNITS})\b", re.I)
RE_PCT = re.compile(rf"(?P<qual>{WORDNUM}\s+)?(?P<value>{NUM})\s*percent\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def sentences(text: str):
    for s in SENT_SPLIT.split(text):
        s = clean_text(s)
        if 20 < len(s) < 900:
            yield s


# Leading quantifiers mark an unnamed group, however capitalised.
RE_QUANTIFIER = re.compile(
    r"^(?:An?|Several|Some|Many|Various|Numerous|Other|Local|International|"
    r"Independent|Domestic|Multiple|Two|Three|Four|Five)\s+", re.I)


def norm_org(raw: str) -> str:
    s = clean_text(raw).strip(" ,.;:")
    s = re.sub(r"^[Tt]he\s+", "", s)
    return s


def is_generic_org(name: str) -> bool:
    """True when the phrase names a category of actor rather than a body."""
    stripped = RE_QUANTIFIER.sub("", name)
    return bool(re.fullmatch(
        r"(?:NGOs?|Nongovernmental Organizations?|Organizations?|Groups?|"
        r"Activists?|Journalists?|Observers?|Sources?|Witnesses?|Outlets?|"
        r"Media|Experts?|Academics?|Unions?|Companies|Employers?)",
        stripped, re.I))


def find_sources(sent: str) -> list[dict]:
    hits, seen = [], set()
    for name, kind in GAZETTEER.items():
        if re.search(rf"\b{re.escape(name)}\b", sent):
            if name.lower() not in seen:
                seen.add(name.lower())
                hits.append({"source": name, "source_type": kind,
                             "match": "gazetteer", "confidence": "high"})
    for rx in ATTRIB:
        for m in rx.finditer(sent):
            org = norm_org(m.group("org"))
            low = org.lower()
            if (low in STOPWORDS or len(org) < 4 or low in seen
                    or any(low in s or s in low for s in seen)):
                continue
            # Require at least two capitalised tokens or a parenthetical acronym:
            # single capitalised words are usually sentence starts, not bodies.
            if not (len(org.split()) >= 2 or re.search(r"\([A-Z]{2,10}\)", org)):
                continue
            seen.add(low)
            if is_generic_org(org):
                hits.append({"source": org.lower(), "source_type": "unnamed/generic",
                             "match": "generic", "confidence": "low"})
            else:
                hits.append({"source": org, "source_type": "named (unclassified)",
                             "match": "pattern", "confidence": "medium"})
    for m in GENERIC_ATTRIB.finditer(sent):
        g = clean_text(m.group(1)).lower()
        if g not in seen:
            seen.add(g)
            hits.append({"source": g, "source_type": "unnamed/generic",
                         "match": "generic", "confidence": "low"})
    return hits


MONTHS = (r"January|February|March|April|May|June|July|August|September|"
          r"October|November|December")
# "the October 2023 attacks", "in 2019 cases" -- a bare 4-digit year sitting in
# front of a unit is a date, not a quantity.  Dates immediately preceded by a
# month, or by date prepositions, are the common trap.
RE_DATEY = re.compile(rf"(?:{MONTHS}|\bin|\bsince|\bduring|\bby|\bfrom|\bof|"
                      rf"\bbefore|\bafter|\bthe)\s+$", re.I)


def looks_like_year(value: str, sent: str, start: int) -> bool:
    if not re.fullmatch(r"(?:19|20)\d{2}", value):
        return False
    # A year preceded by a month/date word is certainly a date.
    if RE_DATEY.search(sent[:start]):
        return True
    # Otherwise treat a bare year-shaped number as a date unless it is
    # explicitly quantified ("more than 2,000 people" would carry a comma).
    return "," not in value


def find_metrics(sent: str) -> list[dict]:
    out, spans = [], set()
    for rx, kind in ((RE_PCT, "percentage"), (RE_METRIC, "count")):
        for m in rx.finditer(sent):
            if (m.start(), m.end()) in spans:
                continue
            spans.add((m.start(), m.end()))
            unit = "percent" if kind == "percentage" else clean_text(m.group("unit")).lower()
            if kind == "count" and unit == "percent":
                continue
            raw = m.group("value")
            qual = clean_text(m.group("qual") or "").lower() or None
            # Percentages are never years; counts can be.
            if kind == "count" and not qual and looks_like_year(raw, sent, m.start("value")):
                continue
            out.append({
                "value": raw.replace(",", ""),
                "unit": unit,
                "qualifier": qual,
                "metric_type": kind,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    a = ap.parse_args()

    sdir = DATA / str(a.year) / "sections"
    files = sorted(sdir.glob("*.json"))
    if not files:
        raise SystemExit(f"No parsed sections for {a.year}; run extract.py first.")

    src_rows, met_rows = [], []
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        for blk in doc["blocks"]:
            for sent in sentences(blk["text"]):
                base = {"year": a.year, "slug": doc["slug"], "country": doc["name"],
                        "section": blk["section"], "subsection": blk["subsection"]}
                for h in find_sources(sent):
                    src_rows.append({**base, **h, "sentence": sent, "method": "rules"})
                for m in find_metrics(sent):
                    met_rows.append({**base, **m, "sentence": sent, "method": "rules"})

    OUTPUT.mkdir(exist_ok=True)
    scols = ["year", "country", "slug", "source", "source_type", "match",
             "confidence", "section", "subsection", "method", "sentence"]
    mcols = ["year", "country", "slug", "value", "unit", "qualifier",
             "metric_type", "section", "subsection", "method", "sentence"]
    for rows, cols, name in ((src_rows, scols, "sources"), (met_rows, mcols, "metrics")):
        p = OUTPUT / f"{name}_{a.year}.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print(f"  wrote {p.name}: {len(rows):,} rows")

    # Roll-ups: which sources dominate, and in how many countries.
    by_src = collections.Counter(r["source"] for r in src_rows)
    cty_src = collections.defaultdict(set)
    for r in src_rows:
        cty_src[r["source"]].add(r["slug"])
    roll = OUTPUT / f"source_rollup_{a.year}.csv"
    with open(roll, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "source_type", "mentions", "countries", "confidence"])
        types = {r["source"]: r["source_type"] for r in src_rows}
        confs = {r["source"]: r["confidence"] for r in src_rows}
        for s, n in by_src.most_common():
            w.writerow([s, types[s], n, len(cty_src[s]), confs[s]])
    print(f"  wrote {roll.name}: {len(by_src):,} distinct sources")

    print(f"\n{a.year}: {len(src_rows):,} source mentions, {len(met_rows):,} metrics, "
          f"{len(files)} countries")
    print("\nTop named sources (mentions / countries):")
    named = [(s, n) for s, n in by_src.most_common()
             if types.get(s) not in ("unnamed/generic",)][:20]
    for s, n in named:
        print(f"  {n:5}  {len(cty_src[s]):3} countries  {s[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
