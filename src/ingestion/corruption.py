from __future__ import annotations

from pathlib import Path
import string
from typing import Any

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import build_embedding_text

SEED = 42
DROP_LATEST_FRACTION = 0.2
# Ty le tinh tren so dong con lai sau khi drop; 4 nhom nay khong giao nhau de truy vet tac dong tung loi.
BLANK_SUMMARY_FRACTION = 0.15
NOISE_FRACTION = 0.15
TRUNCATE_TITLE_FRACTION = 0.15
STALE_DATE_FRACTION = 0.3
DUPLICATE_FRACTION = 0.15
NOISE_WORD_RATIO = 0.25
TRUNCATED_TITLE_CHARS = 7
STALE_SHIFT_DAYS = 365
# Khong co . ! ? de noise khong lam lech ranh gioi cau ma `first_sentence` dua vao.
_NOISE_CHARS = list(string.ascii_letters + string.digits + "#@$%&*~^")


def _count(total: int, fraction: float) -> int:
    return min(total, max(1, round(total * fraction)))


def _inject_noise(text: str, rng: np.random.Generator) -> tuple[str, int]:
    words: list[str] = []
    inserted = 0
    for word in text.split():
        words.append(word)
        if rng.random() < NOISE_WORD_RATIO:
            words.append("".join(rng.choice(_NOISE_CHARS, size=6)))
            inserted += 1
    return " ".join(words), inserted


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Tiem 6 loai corruption (seed co dinh -> tai lap duoc) va ghi log tung dong bi bien doi."""
    rng = np.random.default_rng(SEED)
    frame = df.reset_index(drop=True).copy()
    scenarios: list[dict[str, Any]] = []

    def log(name: str, description: str, records: list[dict[str, Any]]) -> None:
        scenarios.append(
            {"scenario": name, "description": description, "affected_rows": len(records), "records": records}
        )

    # 1. Drop latest: mat 20% bai moi nhat (vd partition moi chua ingest kip).
    published = pd.to_datetime(frame["published"], errors="coerce")
    latest = published.sort_values(ascending=False, kind="stable").index[
        : _count(len(frame), DROP_LATEST_FRACTION)
    ]
    log(
        "drop_latest_records",
        f"Drop {DROP_LATEST_FRACTION:.0%} newest papers",
        [
            {"paper_id": frame.at[i, "paper_id"], "title": frame.at[i, "title"], "published": frame.at[i, "published"]}
            for i in latest
        ],
    )
    frame = frame.drop(index=latest).reset_index(drop=True)

    # 2-5. Chia cac dong con lai thanh 4 nhom rieng biet.
    remaining = rng.permutation(len(frame)).tolist()
    groups: dict[str, list[int]] = {}
    for name, fraction in (
        ("blank_summary", BLANK_SUMMARY_FRACTION),
        ("inject_noise", NOISE_FRACTION),
        ("truncate_title", TRUNCATE_TITLE_FRACTION),
        ("stale_date", STALE_DATE_FRACTION),
    ):
        size = _count(len(frame), fraction)
        groups[name], remaining = sorted(remaining[:size]), remaining[size:]

    records = []
    for i in groups["blank_summary"]:
        records.append({"paper_id": frame.at[i, "paper_id"], "summary_chars_before": len(frame.at[i, "summary"])})
        frame.at[i, "summary"] = ""
    log("blank_summary", "Set summary to an empty string", records)

    records = []
    for i in groups["inject_noise"]:
        noisy, inserted = _inject_noise(frame.at[i, "summary"], rng)
        frame.at[i, "summary"] = noisy
        records.append({"paper_id": frame.at[i, "paper_id"], "noise_tokens": inserted, "summary_after": noisy[:120]})
    log("inject_noise", f"Insert random junk tokens after ~{NOISE_WORD_RATIO:.0%} of summary words", records)

    records = []
    for i in groups["truncate_title"]:
        before = frame.at[i, "title"]
        frame.at[i, "title"] = before[:TRUNCATED_TITLE_CHARS].strip()
        records.append({"paper_id": frame.at[i, "paper_id"], "title_before": before, "title_after": frame.at[i, "title"]})
    log("truncate_title", f"Cut title to {TRUNCATED_TITLE_CHARS} characters", records)

    records = []
    for i in groups["stale_date"]:
        before, age_before = frame.at[i, "published"], int(frame.at[i, "age_days"])
        frame.at[i, "published"] = (pd.Timestamp(before) - pd.Timedelta(days=STALE_SHIFT_DAYS)).date().isoformat()
        frame.at[i, "age_days"] = age_before + STALE_SHIFT_DAYS
        records.append({
            "paper_id": frame.at[i, "paper_id"],
            "published_before": before,
            "published_after": frame.at[i, "published"],
            "age_days_before": age_before,
            "age_days_after": age_before + STALE_SHIFT_DAYS,
        })
    log("stale_date", f"Shift published date back {STALE_SHIFT_DAYS} days", records)

    # 6. Duplicate rows (sau cac loi khac nen ban sao mang ca noi dung da bi lam ban).
    duplicated = sorted(rng.choice(len(frame), size=_count(len(frame), DUPLICATE_FRACTION), replace=False).tolist())
    log(
        "duplicate_rows",
        "Append exact copies of rows",
        [{"paper_id": frame.at[i, "paper_id"], "title": frame.at[i, "title"]} for i in duplicated],
    )
    frame = pd.concat([frame, frame.loc[duplicated]], ignore_index=True)

    # Tinh lai cac cot dan xuat de index nhin thay dung du lieu da bi lam ban.
    frame["summary_chars"] = frame["summary"].str.len()
    frame["text_for_embedding"] = [
        build_embedding_text(row.title, row.authors_joined, row.published, row.categories_joined, row.summary)
        for row in frame.itertuples(index=False)
    ]

    write_json(
        Path(output_log_path),
        {
            "created_at": now_utc().isoformat(),
            "seed": SEED,
            "input_rows": len(df),
            "output_rows": len(frame),
            "scenarios": scenarios,
        },
    )
    counts = ", ".join(f"{entry['scenario']}={entry['affected_rows']}" for entry in scenarios)
    print(f"[corruption] {len(df)} -> {len(frame)} rows ({counts})")
    return frame
