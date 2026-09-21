#!/usr/bin/env python3
"""Year-over-year comparison of two report editions.

Compares, per country and corpus-wide:
  * coverage      - countries added / dropped between editions
  * length        - report length deltas (a proxy for detail retained or cut)
  * schema        - outline changes, so a restructuring is flagged rather than
                    silently producing empty or mismatched sections
  * sources       - which cited organisations appear, disappear, rise or fall
  * metrics       - volume of quantitative claims by country

Schema drift is reported first and loudly: the 2023->2024 transition renamed
and collapsed the entire outline, so section-level comparison across such a
boundary is not meaningful and is suppressed rather than presented as a delta.

Usage:  compare.py 2023 2024 [--top 40]
"""
from __future__ import annotations
import argparse, re, sys, json, csv, collections
from common import DATA, OUTPUT, load_manifest


# State's URL slugs are not stable between editions ("thebahamas" became
# "the-bahamas").  Canonicalise before any set comparison, or a rename shows up
# as a country being dropped and a different one added.
def canon(slug: str) -> str:
    s = slug.lower().replace("_", "-").replace("-", "")
    # "-draft" duplicates exist alongside the real slug (2023 Burma).
    s = re.sub(r"draft$", "", s)
    # Leading articles/qualifiers are applied inconsistently between editions
    # ("thebahamas" vs "the-bahamas"; "republic-of-the-congo").
    s = re.sub(r"^(?:the|republicofthe|democraticrepublicofthe)", "", s)
    return s


def read_csv(name: str) -> list[dict]:
    p = OUTPUT / name
    if not p.exists():
        raise SystemExit(f"Missing {p.name}; run analyze.py for that year first.")
    return list(csv.DictReader(open(p, encoding="utf-8")))


def load_schema(year: int) -> dict:
    p = OUTPUT / f"schema_{year}.json"
    if not p.exists():
        raise SystemExit(f"Missing {p.name}; run extract.py --year {year} first.")
    return json.loads(p.read_text(encoding="utf-8"))


def pct(new: float, old: float) -> str:
    if not old:
        return "n/a"
    return f"{(new - old) / old * 100:+.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old_year", type=int)
    ap.add_argument("new_year", type=int)
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    OLD, NEW = a.old_year, a.new_year

    s_old, s_new = load_schema(OLD), load_schema(NEW)
    h_old = {s["heading"] for s in s_old["schema"]}
    h_new = {s["heading"] for s in s_new["schema"]}
    shared = h_old & h_new
    drift = 1 - (len(shared) / max(len(h_old | h_new), 1))

    lines: list[str] = []
    def out(s: str = "") -> None:
        print(s); lines.append(s)

    out(f"# Country Reports comparison: {OLD} -> {NEW}\n")

    # ---------------------------------------------------------- schema ----
    out("## Schema")
    out(f"- {OLD} outline headings: {len(h_old)}")
    out(f"- {NEW} outline headings: {len(h_new)}")
    out(f"- shared headings: {len(shared)}  (drift {drift:.0%})")
    comparable = drift < 0.35
    if not comparable:
        out(f"\n**The outline was restructured between {OLD} and {NEW}.** "
            f"Section-level comparison is suppressed because the sections do "
            f"not correspond. Country-level and source-level comparisons below "
            f"remain valid.")
        out(f"\n  Only in {OLD}:")
        for h in sorted(h_old - h_new): out(f"    - {h}")
        out(f"\n  Only in {NEW}:")
        for h in sorted(h_new - h_old): out(f"    + {h}")
    else:
        out("  Outline is stable; section-level comparison is meaningful.")
        for h in sorted(h_old - h_new): out(f"    - dropped: {h}")
        for h in sorted(h_new - h_old): out(f"    + added:   {h}")

    # -------------------------------------------------------- coverage ----
    m_old, m_new = load_manifest(OLD), load_manifest(NEW)
    def covered(man: dict) -> set[str]:
        """Canonical slugs with a real report, one per distinct document."""
        seen_hash, out_ = {}, set()
        for k, v in sorted(man["countries"].items(), key=lambda kv: (len(kv[0]), kv[0])):
            if v.get("status") not in ("ok", "cached"):
                continue
            h = v.get("sha256")
            if h and h in seen_hash:
                continue                       # same document, alternate slug
            if h:
                seen_hash[h] = k
            out_.add(canon(k))
        return out_

    c_old, c_new = covered(m_old), covered(m_new)
    out(f"\n## Coverage")
    out(f"- {OLD}: {len(c_old)} reports    {NEW}: {len(c_new)} reports")
    if c_old - c_new: out(f"- dropped in {NEW}: {', '.join(sorted(c_old - c_new))}")
    if c_new - c_old: out(f"- added in {NEW}:   {', '.join(sorted(c_new - c_old))}")

    # ---------------------------------------------------------- length ----
    len_old = {canon(d["slug"]): d["chars"] for d in _doclens(OLD)}
    len_new = {canon(d["slug"]): d["chars"] for d in _doclens(NEW)}
    both = sorted(set(len_old) & set(len_new))
    tot_o, tot_n = sum(len_old[k] for k in both), sum(len_new[k] for k in both)
    out(f"\n## Report length ({len(both)} countries in both editions)")
    out(f"- total characters: {tot_o:,} -> {tot_n:,}  ({pct(tot_n, tot_o)})")
    med_o = sorted(len_old[k] for k in both)[len(both)//2]
    med_n = sorted(len_new[k] for k in both)[len(both)//2]
    out(f"- median per report: {med_o:,} -> {med_n:,}  ({pct(med_n, med_o)})")

    def ratio(k): return (len_new[k] - len_old[k]) / max(len_old[k], 1)
    deltas = sorted(both, key=ratio)
    grew = [k for k in both if ratio(k) > 0]
    out(f"\n  Countries longer than in {OLD}: {len(grew)} of {len(both)}")
    out(f"\n  Largest proportional contraction:")
    for k in deltas[:10]:
        out(f"    {k:32} {len_old[k]:7,} -> {len_new[k]:7,}  {pct(len_new[k], len_old[k])}")
    # Label the other tail honestly: when nothing grew, these are the reports
    # that shrank least, not reports that expanded.
    label = "Largest proportional expansion" if grew else "Smallest contraction (nothing expanded)"
    out(f"\n  {label}:")
    for k in deltas[-10:][::-1]:
        out(f"    {k:32} {len_old[k]:7,} -> {len_new[k]:7,}  {pct(len_new[k], len_old[k])}")

    # --------------------------------------------------------- sources ----
    so, sn = read_csv(f"sources_{OLD}.csv"), read_csv(f"sources_{NEW}.csv")
    def agg(rows):
        men = collections.Counter(); cty = collections.defaultdict(set); typ = {}
        for r in rows:
            if r["source_type"] == "unnamed/generic":
                continue
            men[r["source"]] += 1; cty[r["source"]].add(canon(r["slug"]))
            typ[r["source"]] = r["source_type"]
        return men, cty, typ
    mo, co, to_ = agg(so); mn, cn, tn_ = agg(sn)

    out(f"\n## Cited sources (named organisations only)")
    out(f"- distinct named sources: {len(mo):,} -> {len(mn):,}")
    out(f"- total named mentions:   {sum(mo.values()):,} -> {sum(mn.values()):,}")

    rows = []
    for s in set(mo) | set(mn):
        rows.append({"source": s, "type": to_.get(s) or tn_.get(s),
                     f"mentions_{OLD}": mo.get(s, 0), f"mentions_{NEW}": mn.get(s, 0),
                     f"countries_{OLD}": len(co.get(s, ())),
                     f"countries_{NEW}": len(cn.get(s, ())),
                     "mention_delta": mn.get(s, 0) - mo.get(s, 0),
                     "country_delta": len(cn.get(s, ())) - len(co.get(s, ()))})
    rows.sort(key=lambda r: -abs(r["mention_delta"]))
    p = OUTPUT / f"source_comparison_{OLD}_{NEW}.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    out(f"- wrote {p.name}")

    established = [r for r in rows if r[f"mentions_{OLD}"] >= 5 or r[f"mentions_{NEW}"] >= 5]
    out(f"\n  Largest shifts among established sources (>=5 mentions either year):")
    out(f"    {'source':46} {OLD:>7} {NEW:>7}   delta")
    for r in established[:a.top]:
        out(f"    {r['source'][:45]:46} {r[f'mentions_{OLD}']:7} "
            f"{r[f'mentions_{NEW}']:7}  {r['mention_delta']:+5}")

    gone = [r for r in rows if r[f"mentions_{NEW}"] == 0 and r[f"mentions_{OLD}"] >= 3]
    new_ = [r for r in rows if r[f"mentions_{OLD}"] == 0 and r[f"mentions_{NEW}"] >= 3]
    out(f"\n  No longer cited in {NEW} (>=3 mentions in {OLD}): {len(gone)}")
    for r in sorted(gone, key=lambda r: -r[f"mentions_{OLD}"])[:15]:
        out(f"    - {r['source'][:60]:62} was {r[f'mentions_{OLD}']}")
    out(f"\n  Newly cited in {NEW} (>=3 mentions): {len(new_)}")
    for r in sorted(new_, key=lambda r: -r[f"mentions_{NEW}"])[:15]:
        out(f"    + {r['source'][:60]:62} now {r[f'mentions_{NEW}']}")

    # --------------------------------------------------------- metrics ----
    qo, qn = read_csv(f"metrics_{OLD}.csv"), read_csv(f"metrics_{NEW}.csv")
    out(f"\n## Quantitative claims")
    out(f"- rows: {len(qo):,} -> {len(qn):,}  ({pct(len(qn), len(qo))})")
    for label, rows_ in ((OLD, qo), (NEW, qn)):
        by = collections.Counter(r["unit"] for r in rows_)
        out(f"  {label} top units: " + ", ".join(f"{u}={n}" for u, n in by.most_common(8)))

    rpt = OUTPUT / f"comparison_{OLD}_{NEW}.md"
    rpt.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {rpt}")
    return 0


def _doclens(year: int) -> list[dict]:
    out = []
    for f in sorted((DATA / str(year) / "sections").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out.append({"slug": d["slug"],
                    "chars": sum(len(b["text"]) for b in d["blocks"])})
    return out


if __name__ == "__main__":
    sys.exit(main())
