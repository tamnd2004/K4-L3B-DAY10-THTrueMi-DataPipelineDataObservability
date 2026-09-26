from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_embedding_text(
    title: str, authors_joined: str, published: str, categories_joined: str, summary: str
) -> str:
    """Five-part embedding text; shared with corruption so rebuilt rows keep the exact same format."""
    return (
        f"Title: {title}\n"
        f"Authors: {authors_joined}\n"
        f"Published: {published}\n"
        f"Categories: {categories_joined}\n"
        f"Summary: {summary}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw papers and prepare one embedding text per unique DOI."""
    columns = [
        "paper_id", "title", "summary", "authors", "categories",
        "primary_category", "published", "updated", "abs_url", "pdf_url",
        "comment", "authors_joined", "categories_joined", "summary_chars",
        "age_days", "text_for_embedding",
    ]
    rows = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        published = pd.to_datetime(record.published, errors="coerce", utc=True)
        if not paper_id or not title or not summary or pd.isna(published):
            continue

        updated = pd.to_datetime(record.updated, errors="coerce", utc=True)
        if pd.isna(updated):
            updated = published
        authors = [normalize_whitespace(name) for name in record.authors]
        authors = [name for name in authors if name]
        categories = [normalize_whitespace(name) for name in record.categories]
        categories = [name for name in categories if name]
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published_date = published.date().isoformat()

        rows.append({
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": categories[0] if categories else normalize_whitespace(record.primary_category),
            "published": published_date,
            "updated": updated.date().isoformat(),
            "abs_url": normalize_whitespace(record.abs_url),
            "pdf_url": normalize_whitespace(record.pdf_url),
            "comment": normalize_whitespace(record.comment),
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "age_days": (run_date.date() - published.date()).days,
            "text_for_embedding": build_embedding_text(
                title, authors_joined, published_date, categories_joined, summary
            ),
        })

    frame = pd.DataFrame(rows, columns=columns)
    return (
        frame.drop_duplicates(subset="paper_id", keep="first")
        .sort_values(["published", "paper_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
