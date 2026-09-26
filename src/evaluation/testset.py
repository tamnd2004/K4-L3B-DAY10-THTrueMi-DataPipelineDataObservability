from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


QUESTION_TYPES = (
    "summary",
    "summary",
    "summary",
    "authors",
    "authors",
    "authors",
    "date",
    "date",
    "categories",
    "categories",
)


def _published_date(value: Any) -> str:
    published = pd.to_datetime(value, errors="coerce", utc=True)
    return "" if pd.isna(published) else published.date().isoformat()


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build and persist a deterministic ten-question evaluation set."""
    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    papers = df.loc[:, sorted(required_columns)].copy()
    for column in required_columns - {"published"}:
        papers[column] = papers[column].fillna("").astype(str).map(normalize_whitespace)
    papers["published"] = papers["published"].map(_published_date)

    papers = papers.drop_duplicates(subset="paper_id", keep="first")
    papers = papers[
        papers[list(required_columns)].ne("").all(axis=1)
        & ~papers["title"].str.contains("'", regex=False)
    ].sort_values("paper_id", kind="stable")

    if len(papers) < len(QUESTION_TYPES):
        raise ValueError(
            "At least 10 unique papers with complete evaluation fields and quote-safe titles are required."
        )

    test_set: list[dict[str, Any]] = []
    for index, (question_type, (_, paper)) in enumerate(
        zip(QUESTION_TYPES, papers.head(len(QUESTION_TYPES)).iterrows(), strict=True),
        start=1,
    ):
        title = paper["title"]
        if question_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(paper["summary"])
        elif question_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = paper["authors_joined"]
        elif question_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = paper["published"]
        else:
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = paper["categories_joined"]

        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper["paper_id"]],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
