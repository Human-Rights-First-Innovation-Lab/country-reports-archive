"""Shared helpers for the Country Reports pipeline."""
from __future__ import annotations
import os, re, json, hashlib, pathlib

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"

# state.gov serves current + recent years from www; older editions live on the
# 2021-2025 archive host. www has redirected correctly for every year tested,
# so we try it first and fall back to the archive.
INDEX_HOSTS = ["https://www.state.gov", "https://2021-2025.state.gov"]


def index_urls(year: int) -> list[str]:
    slug = f"/reports/{year}-country-reports-on-human-rights-practices/"
    return [h + slug for h in INDEX_HOSTS]


def year_dir(year: int, kind: str) -> pathlib.Path:
    p = DATA / str(year) / kind
    p.mkdir(parents=True, exist_ok=True)
    return p


def manifest_path(year: int) -> pathlib.Path:
    (DATA / str(year)).mkdir(parents=True, exist_ok=True)
    return DATA / str(year) / "manifest.json"


def load_manifest(year: int) -> dict:
    p = manifest_path(year)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"year": year, "countries": {}}


def save_manifest(year: int, man: dict) -> None:
    manifest_path(year).write_text(
        json.dumps(man, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").title()


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()
