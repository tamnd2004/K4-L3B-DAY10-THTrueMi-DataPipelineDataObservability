from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import html
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(value: str | None) -> str:
    """Bo the JATS/HTML (vd `<jats:p>`), decode entity va gom khoang trang."""
    if not value:
        return ""
    return normalize_whitespace(html.unescape(_TAG_RE.sub(" ", value)))


def _first(values: list | None) -> str:
    return values[0] if values else ""


def _format_date_parts(date_obj: dict | None) -> str:
    """Crossref date `{"date-parts": [[2026, 5, 20]]}` -> `2026-05-20` (thieu thang/ngay -> 01)."""
    if not date_obj:
        return ""
    parts = _first(date_obj.get("date-parts"))
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _parse_authors(raw_authors: list[dict] | None) -> list[str]:
    authors = []
    for author in raw_authors or []:
        # Tac gia ca nhan co given/family; to chuc chi co `name`.
        name = _clean_text(" ".join(p for p in (author.get("given"), author.get("family")) if p))
        name = name or _clean_text(author.get("name"))
        if name:
            authors.append(name)
    return authors


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if link.get("content-type") == "application/pdf" and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref `/works` payload thanh list PaperRecord.

    Bo qua record thieu DOI/title/abstract va record trung DOI.
    """
    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in payload.get("message", {}).get("items", []):
        doi = (item.get("DOI") or "").strip().lower()
        title = _clean_text(_first(item.get("title")))
        summary = _clean_text(item.get("abstract"))
        if not doi or not title or not summary or doi in seen:
            continue
        seen.add(doi)

        # Crossref live hau nhu khong con tra `subject` -> dung `type` lam category du phong.
        categories = [c for c in (_clean_text(s) for s in item.get("subject") or []) if c]
        if not categories and item.get("type"):
            categories = [item["type"]]

        published = ""
        for key in ("published", "published-online", "published-print", "issued", "created"):
            published = _format_date_parts(item.get(key))
            if published:
                break
        created = item.get("created") or {}
        updated = (created.get("date-time") or "")[:10] or _format_date_parts(created) or published

        abs_url = item.get("URL") or f"https://doi.org/{doi}"
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=_parse_authors(item.get("author")),
                categories=categories,
                primary_category=_first(categories),
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {doi}",
            )
        )
    return records


def _request_crossref(settings: Settings) -> dict:
    """Goi Crossref voi retry + backoff cho 429/5xx. Raise neu het luot thu."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (student lab)"}
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("message", {}).get("items"):
                raise ValueError("Crossref response has no items")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status not in RETRYABLE_STATUS_CODES:
                break
            if attempt < MAX_ATTEMPTS:
                retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After", "")
                delay = int(retry_after) if retry_after.isdigit() else 2 ** attempt
                print(f"[crossref] Attempt {attempt}/{MAX_ATTEMPTS} failed ({exc}); retrying in {delay}s")
                time.sleep(delay)
    raise RuntimeError(f"Crossref request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API (fallback snapshot local khi loi), luu raw response va raw records."""
    raw_path = settings.paths.raw_api_response
    try:
        payload = _request_crossref(settings)
        records = parse_crossref_payload(payload)
        if not records:
            raise ValueError("Crossref response parsed to 0 valid records")
        # Chi ghi de snapshot khi response live hop le, de fallback luon con ban tot gan nhat.
        write_json(raw_path, payload)
        print(f"[crossref] Fetched {len(records)} records from {settings.source_api}")
    except (RuntimeError, ValueError) as exc:
        if not raw_path.exists():
            raise RuntimeError(f"Crossref unavailable and no local snapshot at {raw_path}") from exc
        print(f"[crossref] {exc} -> fallback to local snapshot {raw_path}")
        records = parse_crossref_payload(read_json(raw_path))

    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot (`crossref_records.json`) va map thanh `PaperRecord`."""
    field_names = {f.name for f in fields(PaperRecord)}
    return [PaperRecord(**{k: v for k, v in row.items() if k in field_names}) for row in read_json(path)]
