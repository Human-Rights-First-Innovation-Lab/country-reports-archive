#!/usr/bin/env python3
"""Download every country report PDF for a given edition year.

Records a manifest with source URL, sha256 and fetch time for each file so the
archive is reproducible and any downstream claim is traceable to a known blob.

Usage:  fetch.py --year 2024 [--force] [--workers 5] [--only kenya,sudan]
"""
from __future__ import annotations
import argparse, re, sys, time, html, datetime, concurrent.futures as cf
import requests
from common import (UA, index_urls, year_dir, load_manifest, save_manifest,
                    sha256_file, slug_to_name)

TIMEOUT = 60
RETRIES = 6


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def get(s: requests.Session, url: str, binary: bool = False):
    """GET with backoff.  state.gov rate-limits bulk crawls with 429s, which are
    transient -- treat them as retryable and wait far longer than a network
    flake, honouring Retry-After when the server sends one."""
    last = None
    for attempt in range(RETRIES):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.content if binary else r.text
            last = f"HTTP {r.status_code}"
            if r.status_code in (429, 503):
                wait = float(r.headers.get("Retry-After") or 0) or 15 * (attempt + 1)
                time.sleep(min(wait, 120))
                continue
        except Exception as e:                      # network flake, retry
            last = str(e)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{url}: {last}")


def discover(s: requests.Session, year: int) -> dict[str, dict]:
    """Return {slug: {name, page_url}} from the edition index page."""
    # The index is inconsistent about trailing slashes (Japan and Thailand are
    # linked without one in the 2024 edition) and mixes <a> with <option>, so
    # accept both and normalise afterwards -- requiring either silently drops
    # countries, which is far worse than a duplicate.
    slug_re = re.compile(
        rf'(?:href|value)="(https?://[^"]*?/reports/{year}-country-reports-on-'
        rf'human-rights-practices/([a-z0-9-]+)/?)"[^>]*>(.*?)</(?:a|option)>',
        re.S | re.I)
    for idx in index_urls(year):
        try:
            page = get(s, idx)
        except RuntimeError:
            continue
        found: dict[str, dict] = {}
        for url, slug, label in slug_re.findall(page):
            if slug in ("translations",):
                continue
            name = html.unescape(re.sub(r"<[^>]+>", "", label)).strip()
            # Index anchors are sometimes empty/icon-only; fall back to the slug.
            if not name or len(name) > 80:
                name = slug_to_name(slug)
            url = url.replace("http://", "https://").rstrip("/") + "/"
            found.setdefault(slug, {"name": name, "page_url": url})
        if found:
            print(f"  index: {idx} -> {len(found)} countries")
            return found
    raise SystemExit(f"No country links found for {year}. Has the edition been published?")


def pdf_url_for(s: requests.Session, year: int, page_url: str) -> str | None:
    try:
        page = get(s, page_url)
    except RuntimeError:
        return None                      # country page 404s; caller falls back
    cands = re.findall(r'href="([^"]*?\.pdf)"', page, re.I)
    if not cands:
        return None
    # Prefer the canonical English report for this edition year.
    def score(u: str) -> tuple:
        up = u.upper()
        return (("HUMAN-RIGHTS-REPORT" in up), (str(year) in up), -len(u))
    return sorted(set(cands), key=score, reverse=True)[0]


def edition_prefix(man: dict) -> str | None:
    """The upload path+id shared by every PDF in one edition.

    State's PDF URLs look like
      /wp-content/uploads/2024/02/528267_KENYA-2023-HUMAN-RIGHTS-REPORT.pdf
    where "2024/02/528267" is constant across the whole edition -- it identifies
    the publication batch, not the country.  Deriving it from PDFs we already
    have lets us reach reports whose country page is broken or 404s (Burma 2023
    is published but its index link is dead).
    """
    counts: dict[str, int] = {}
    for rec in man.get("countries", {}).values():
        u = rec.get("pdf_url") or ""
        if m := re.match(r"(https?://[^/]+/wp-content/uploads/\d{4}/\d{2}/\d+_)", u):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return max(counts, key=counts.get) if counts else None


def constructed_url(prefix: str, name: str, year: int) -> str:
    """Build the canonical PDF URL for a country from the edition prefix."""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()
    return f"{prefix}{stem}-{year}-HUMAN-RIGHTS-REPORT.pdf"


def fetch_one(year: int, slug: str, meta: dict, force: bool) -> dict:
    s = session()
    dest = year_dir(year, "pdf") / f"{slug}.pdf"
    rec = dict(meta)
    rec["slug"] = slug
    try:
        if dest.exists() and not force:
            rec.update(status="cached", pdf_path=str(dest.relative_to(dest.parents[3])),
                       sha256=sha256_file(dest), bytes=dest.stat().st_size)
            return rec
        url = meta.get("pdf_url") or pdf_url_for(s, year, meta["page_url"])
        blob = None
        if url:
            try:
                blob = get(s, url, binary=True)
            except RuntimeError:
                blob = None
        # Fall back to the edition-wide URL pattern when the country page is
        # broken or the linked file will not serve.
        if (blob is None or not blob.startswith(b"%PDF")) and meta.get("_prefix"):
            for cand in {constructed_url(meta["_prefix"], meta.get("name", slug), year),
                         constructed_url(meta["_prefix"], slug.replace("-", " "), year)}:
                try:
                    alt = get(s, cand, binary=True)
                except RuntimeError:
                    continue
                if alt.startswith(b"%PDF"):
                    blob, url = alt, cand
                    break
        if blob is None:
            rec.update(status="no_pdf", pdf_url=url)
            return rec
        if not blob.startswith(b"%PDF"):
            rec.update(status="not_a_pdf", pdf_url=url)
            return rec
        dest.write_bytes(blob)
        rec.update(status="ok", pdf_url=url,
                   pdf_path=str(dest.relative_to(dest.parents[3])),
                   sha256=sha256_file(dest), bytes=len(blob),
                   fetched_at=datetime.datetime.now(datetime.UTC).isoformat())
    except Exception as e:
        rec.update(status="error", error=str(e))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--force", action="store_true", help="re-download cached PDFs")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--only", help="comma-separated slugs, for testing")
    a = ap.parse_args()

    s = session()
    print(f"Discovering {a.year} country reports...")
    countries = discover(s, a.year)
    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        countries = {k: v for k, v in countries.items() if k in keep}

    man = load_manifest(a.year)
    # Carry forward known pdf_urls so re-runs skip the per-country page fetch.
    prefix = edition_prefix(man)
    if prefix:
        print(f"  edition PDF prefix: {prefix}")
    for slug, meta in countries.items():
        prev = man["countries"].get(slug, {})
        if prev.get("pdf_url"):
            meta["pdf_url"] = prev["pdf_url"]
        if prefix:
            meta["_prefix"] = prefix

    results: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(fetch_one, a.year, k, v, a.force): k
                for k, v in countries.items()}
        for i, f in enumerate(cf.as_completed(futs), 1):
            slug = futs[f]
            rec = f.result()
            results[slug] = rec
            flag = {"ok": "+", "cached": ".", }.get(rec["status"], "!")
            print(f"  [{i:3}/{len(futs)}] {flag} {slug:38} {rec['status']}")

    # Merge, never replace: a --only run must not drop records for the
    # countries it did not touch.
    man["countries"].update(results)
    man["fetched_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    save_manifest(a.year, man)

    tally: dict[str, int] = {}
    for r in results.values():
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print(f"\n{a.year}: " + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    bad = {k: v for k, v in results.items() if v["status"] not in ("ok", "cached")}
    if bad:
        print("Needs attention:")
        for k, v in bad.items():
            print(f"  {k}: {v['status']} {v.get('error','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
