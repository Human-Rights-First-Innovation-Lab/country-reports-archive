#!/usr/bin/env python3
"""Package the parsed reports for upload as Claude Project knowledge.

Produces three granularities so the corpus can be fitted to whatever the
destination accepts:

  by-country/<country>.md   one file per country, every edition together --
                            best for Q&A, since a question about a country
                            retrieves one self-contained file
  by-edition/<year>-<nn>.md alphabetical shards of a single edition
  INDEX.md, METHODOLOGY.md  what is here, and what it can bear

Usage:  package_corpus.py [--years 2023,2024] [--shard-mb 4]
"""
from __future__ import annotations
import argparse, json, re, pathlib, collections
from common import DATA, ROOT

OUT = ROOT / "corpus"


def canon(slug: str) -> str:
    s = slug.lower().replace("_", "-").replace("-", "")
    s = re.sub(r"draft$", "", s)
    return re.sub(r"^(?:the|republicofthe|democraticrepublicofthe)", "", s)


def load(year: int) -> dict[str, dict]:
    man = json.loads((DATA / str(year) / "manifest.json").read_text())["countries"]
    docs = {}
    for f in sorted((DATA / str(year) / "sections").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rec = man.get(d["slug"], {})
        docs[canon(d["slug"])] = {
            "name": rec.get("name") or d["name"], "slug": d["slug"], "year": year,
            "pdf_url": rec.get("pdf_url"), "sha256": rec.get("sha256"),
            "blocks": d["blocks"],
        }
    return docs


def render(doc: dict) -> str:
    out = [f"## {doc['name']} — {doc['year']} Human Rights Report", ""]
    if doc.get("pdf_url"):
        out += [f"Source PDF: {doc['pdf_url']}", ""]
    cur = None
    for b in doc["blocks"]:
        if b["section"] == "(front matter)":
            continue
        if b["section"] != cur:
            cur = b["section"]; out += [f"### {cur}", ""]
        if b.get("subsection"):
            out += [f"#### {b['subsection']}", ""]
        out += [b["text"], ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2023,2024")
    ap.add_argument("--shard-mb", type=float, default=4.0)
    # Each run clears its output directory, so a narrower --years run must not
    # be able to silently destroy a wider one already sitting in corpus/.
    ap.add_argument("--out", default=None,
                    help="output directory (default: corpus/, or corpus-<years>/ "
                         "when --years narrows the default set)")
    a = ap.parse_args()
    years = [int(y) for y in a.years.split(",")]

    global OUT
    OUT = pathlib.Path(a.out) if a.out else (
        ROOT / "corpus" if a.years == "2023,2024"
        else ROOT / ("corpus-" + a.years.replace(",", "-")))
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"writing to {OUT.name}/")

    editions = {y: load(y) for y in years}
    keys = sorted({k for e in editions.values() for k in e})
    names = {}
    for y in sorted(years, reverse=True):
        for k, d in editions[y].items():
            names.setdefault(k, d["name"])

    # ---- one file per country, all editions together ----
    bc = OUT / "by-country"; bc.mkdir(parents=True, exist_ok=True)
    for old in bc.glob("*.md"): old.unlink()
    for k in keys:
        present = [y for y in years if k in editions[y]]
        parts = [f"# {names[k]} — Country Reports on Human Rights Practices", "",
                 f"Editions included: {', '.join(str(y) for y in present)}", ""]
        for y in sorted(present, reverse=True):
            parts.append(render(editions[y][k]))
        (bc / f"{k}.md").write_text("\n".join(parts), encoding="utf-8")

    # ---- alphabetical shards per edition ----
    be = OUT / "by-edition"; be.mkdir(parents=True, exist_ok=True)
    for old in be.glob("*.md"): old.unlink()
    limit = int(a.shard_mb * 1024 * 1024)
    shard_manifest = []
    for y in years:
        buf, n, first = [], 0, None
        size = 0
        def flush(last):
            nonlocal buf, n, first, size
            if not buf: return
            n += 1
            p = be / f"{y}-{n:02d}.md"
            head = [f"# {y} Country Reports on Human Rights Practices",
                    f"", f"Countries in this file: {first} — {last}", ""]
            p.write_text("\n".join(head + buf), encoding="utf-8")
            shard_manifest.append((p.name, first, last, p.stat().st_size))
            buf, first, size = [], None, 0
        for k in sorted(editions[y]):
            doc = editions[y][k]
            txt = render(doc)
            if size and size + len(txt) > limit:
                flush(prev_name)
            if first is None: first = doc["name"]
            buf.append(txt); size += len(txt); prev_name = doc["name"]
        flush(prev_name)

    # ---- index ----
    lines = ["# Country Reports corpus — index", "",
             "US State Department *Country Reports on Human Rights Practices*, "
             "parsed from the published PDFs.", ""]
    for y in years:
        chars = sum(sum(len(b["text"]) for b in d["blocks"]) for d in editions[y].values())
        lines.append(f"- **{y} edition** — {len(editions[y])} reports, {chars:,} characters")
    lines += ["", "## Files", "",
              f"- `by-country/` — {len(keys)} files, one per country, all editions together",
              f"- `by-edition/` — {len(shard_manifest)} alphabetical shards",
              "- `METHODOLOGY.md` — **read this before relying on any figure**", "",
              "## Countries", ""]
    for k in keys:
        yrs = ", ".join(str(y) for y in years if k in editions[y])
        lines.append(f"- {names[k]} ({yrs})")
    (OUT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    tot = sum(p.stat().st_size for p in OUT.rglob("*.md"))
    print(f"by-country: {len(keys)} files")
    print(f"by-edition: {len(shard_manifest)} shards")
    for n, f0, l0, sz in shard_manifest:
        print(f"   {n}  {sz/1024/1024:5.2f} MB  {f0} — {l0}")
    print(f"total markdown: {tot/1024/1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
