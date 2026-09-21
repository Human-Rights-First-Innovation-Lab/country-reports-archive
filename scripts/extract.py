#!/usr/bin/env python3
"""PDF -> cleaned text + structured sections, with schema-drift detection.

The 2024 edition restructured the report outline ("Section 1. Life") away from
the long-standing 2023-and-earlier outline ("Section 1. Respect for the
Integrity of the Person"), and shortened the text dramatically.  Nothing here
assumes a fixed outline: headings are discovered per document, then reported
corpus-wide so a future edition's re-restructuring is visible immediately
rather than silently producing empty sections.

Usage:  extract.py --year 2024
"""
from __future__ import annotations
import argparse, re, sys, json, collections
from pypdf import PdfReader
from common import DATA, OUTPUT, year_dir, load_manifest, clean_text

# Running header/footer furniture repeated on every page of every report.
FURNITURE = [
    re.compile(r"^Country Reports on Human Rights Practices for \d{4}\s*$", re.I),
    re.compile(r"^United States Department of State\b.*$", re.I),
    re.compile(r"^Page \d+ of \d+\s*$", re.I),
]

# A heading is a short line that opens a numbered section or a lettered
# subsection.  Kept deliberately loose so an unfamiliar outline still parses.
RE_SECTION = re.compile(r"^(Section\s+\d+\.\s*.+)$")
RE_SUBSEC  = re.compile(r"^([a-z]\.\s+[A-Z].*)$")
RE_EXECSUM = re.compile(r"^(Executive Summary)\s*$", re.I)


def pdf_text(path) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def strip_furniture(raw: str) -> str:
    out = []
    for line in raw.split("\n"):
        s = line.strip()
        if not s or any(rx.match(s) for rx in FURNITURE):
            continue
        out.append(s)
    return "\n".join(out)


def rejoin(lines: list[str]) -> str:
    """PDF extraction hard-wraps prose; rejoin into flowing paragraphs."""
    return clean_text(" ".join(lines))


def parse_sections(text: str) -> list[dict]:
    """Split into [{section, subsection, text}] using discovered headings."""
    lines = text.split("\n")
    blocks, cur_sec, cur_sub, buf = [], None, None, []

    def flush():
        if buf and (body := rejoin(buf)):
            blocks.append({"section": cur_sec or "(front matter)",
                           "subsection": cur_sub, "text": body})
        buf.clear()

    for i, line in enumerate(lines):
        # A heading candidate must be short and not end mid-sentence.
        short = len(line) < 95
        if short and RE_EXECSUM.match(line):
            flush(); cur_sec, cur_sub = "Executive Summary", None; continue
        if short and (m := RE_SECTION.match(line)):
            flush(); cur_sec, cur_sub = clean_text(m.group(1)), None; continue
        if short and (m := RE_SUBSEC.match(line)):
            # Heading text can wrap onto the next line ("...Degrading Treatment or\nPunishment").
            head = clean_text(m.group(1))
            if head.rstrip().endswith(("or", "and", "of", "the")) and i + 1 < len(lines):
                head = clean_text(head + " " + lines[i + 1])
            flush(); cur_sub = head; continue
        buf.append(line)
    flush()
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    a = ap.parse_args()

    man = load_manifest(a.year)
    if not man["countries"]:
        raise SystemExit(f"No manifest for {a.year}; run fetch.py first.")

    tdir, sdir = year_dir(a.year, "text"), year_dir(a.year, "sections")
    outline = collections.Counter()
    per_country, failures = {}, []

    # State sometimes publishes one report under two slugs (2023 Burma appears
    # as both "burma" and "burma-draft", byte-identical).  Keep one copy --
    # otherwise the country is double-counted in every downstream total.
    items, seen_hash, dupes = [], {}, []
    for slug, rec in sorted(man["countries"].items(), key=lambda kv: (len(kv[0]), kv[0])):
        h = rec.get("sha256")
        if h and h in seen_hash:
            dupes.append((slug, seen_hash[h]))
            continue
        if h:
            seen_hash[h] = slug
        items.append((slug, rec))
    if dupes:
        print(f"  skipping {len(dupes)} duplicate-content slug(s): " +
              ", ".join(f"{d}=={k}" for d, k in dupes[:6]))
    # Remove any output a previous run wrote for a slug we now skip -- analyze.py
    # globs these directories, so a stale file silently double-counts a country.
    for slug, _ in dupes:
        for stale in (year_dir(a.year, "text") / f"{slug}.txt",
                      year_dir(a.year, "sections") / f"{slug}.json"):
            if stale.exists():
                stale.unlink()
                print(f"  removed stale {stale.parent.name}/{stale.name}")

    for i, (slug, rec) in enumerate(items, 1):
        pdf = DATA / str(a.year) / "pdf" / f"{slug}.pdf"
        if not pdf.exists():
            failures.append((slug, "missing pdf")); continue
        try:
            text = strip_furniture(pdf_text(pdf))
            blocks = parse_sections(text)
        except Exception as e:
            failures.append((slug, f"parse error: {e}")); continue

        (tdir / f"{slug}.txt").write_text(text, encoding="utf-8")
        (sdir / f"{slug}.json").write_text(json.dumps(
            {"slug": slug, "name": rec.get("name", slug), "year": a.year,
             "blocks": blocks}, indent=2, ensure_ascii=False), encoding="utf-8")

        heads = {b["section"] for b in blocks} | {
            b["subsection"] for b in blocks if b["subsection"]}
        outline.update(heads)
        per_country[slug] = {"chars": len(text), "blocks": len(blocks),
                             "sections": sorted(heads)}
        if i % 40 == 0:
            print(f"  ...{i}/{len(items)}")

    chars = [v["chars"] for v in per_country.values()]
    report = {
        "year": a.year,
        "documents": len(per_country),
        "median_chars": sorted(chars)[len(chars) // 2] if chars else 0,
        "total_chars": sum(chars),
        # Headings seen in >=20% of documents define this edition's schema.
        "schema": [{"heading": h, "documents": n,
                    "share": round(n / max(len(per_country), 1), 3)}
                   for h, n in outline.most_common() if n >= 0.2 * len(per_country)],
        "rare_headings": [{"heading": h, "documents": n}
                          for h, n in outline.most_common()
                          if n < 0.2 * len(per_country)][:40],
        "failures": failures,
    }
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f"schema_{a.year}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{a.year}: {len(per_country)} documents, "
          f"median {report['median_chars']:,} chars")
    print("Edition schema (headings in >=20% of reports):")
    for s in report["schema"]:
        print(f"  {s['documents']:4}  {int(s['share']*100):3}%  {s['heading'][:72]}")
    if failures:
        print(f"\n{len(failures)} failures:")
        for slug, why in failures[:20]:
            print(f"  {slug}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
