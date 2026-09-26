"""Nhung artifact cua pipeline (metrics, quality, freshness, corruption log) vao ui/dashboard.html.

Chay lai sau moi lan `run_phase1.py` / `run_corruption_flow.py`:
    python script/build_dashboard.py
"""

from __future__ import annotations

import json
import re

from core.config import load_settings
from core.utils import read_json
from observability.quality import MAX_ROWS, MIN_ROWS, MIN_SUMMARY_CHARS
from observability.reporting import SCENARIO_SIGNALS

REPO_URL = "https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability"
STATES = ("baseline", "corrupted", "repaired")
DATA_BLOCK = re.compile(
    r'(<script id="dashboard-data" type="application/json">)(.*?)(</script>)', re.DOTALL
)


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _state(settings, name: str) -> dict:
    data = settings.paths.project_dir / "data"
    quality = read_json(data / "quality" / f"{name}_quality_report.json")
    metrics = read_json(data / "results" / f"{name}_metrics.json")
    return {
        "metrics": {k: metrics[k] for k in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")},
        "gate": {
            "success": quality["success"],
            "passed": quality["statistics"]["successful_expectations"],
            "total": quality["statistics"]["evaluated_expectations"],
            "checked_at": quality["checked_at"],
            "expectations": [
                {
                    "name": e["expectation"],
                    "column": e["column"],
                    "success": e["success"],
                    "observed": e["observed_value"],
                    "unexpected": e["unexpected_count"],
                }
                for e in quality["expectations"]
            ],
        },
        "freshness": quality["freshness"],
        "dataset": quality["dataset"],
    }


def _verdict(signal, corrupted: dict) -> str:
    if signal is None:
        return "silent"
    if signal == "freshness":
        return "detected" if not corrupted["freshness"]["is_fresh"] else "missed"
    name, column = signal
    for e in corrupted["gate"]["expectations"]:
        if e["name"] == name and e["column"] == column:
            return "detected" if not e["success"] else "missed"
    return "missed"


def build_payload() -> dict:
    settings = load_settings()
    paths = settings.paths
    states = {name: _state(settings, name) for name in STATES}
    log = read_json(paths.corruption_log)

    scenarios = []
    flags: dict[str, list[str]] = {}
    for s in log["scenarios"]:
        ids = [r["paper_id"] for r in s["records"]]
        for pid in ids:
            flags.setdefault(pid, []).append(s["scenario"])
        signal = SCENARIO_SIGNALS.get(s["scenario"])
        scenarios.append(
            {
                "id": s["scenario"],
                "description": s["description"],
                "rows": s["affected_rows"],
                "signal": signal if signal in (None, "freshness") else list(signal),
                "verdict": _verdict(signal, states["corrupted"]),
                "records": s["records"],
            }
        )

    corrupted_rows = read_json(paths.corrupted_clean_json)
    corrupted_by_id: dict[str, list[dict]] = {}
    for row in corrupted_rows:
        corrupted_by_id.setdefault(row["paper_id"], []).append(row)

    papers = []
    for row in read_json(paths.clean_json):
        pid = row["paper_id"]
        copies = corrupted_by_id.get(pid, [])
        papers.append(
            {
                "id": pid,
                "title": row["title"],
                "authors": row["authors_joined"],
                "category": row["primary_category"],
                "published": row["published"],
                "age_days": int(row["age_days"]),
                "summary_chars": int(row["summary_chars"]),
                "url": row["abs_url"],
                "flags": flags.get(pid, []),
                "corrupted": None
                if not copies
                else {
                    "copies": len(copies),
                    "title": copies[0]["title"],
                    "published": copies[0]["published"],
                    "age_days": int(copies[0]["age_days"]),
                    "summary_chars": int(copies[0]["summary_chars"]),
                },
            }
        )

    answers = {name: read_json(paths.project_dir / "data" / "results" / f"{name}_answers.json") for name in STATES}
    questions = []
    for i, base in enumerate(answers["baseline"]):
        per_state = [answers[name][i] for name in STATES]
        gt = _as_list(base["ground_truth_doc_ids"])
        questions.append(
            {
                "id": base["id"],
                "type": base["question_type"],
                "question": base["question"],
                "ground_truth": base["ground_truth"],
                "ground_truth_doc_ids": gt,
                "corruptions": sorted({f for pid in gt for f in flags.get(pid, [])}),
                "hit": [bool(a["retrieval_hit"]) for a in per_state],
                "f1": [round(float(a["token_f1"]), 4) for a in per_state],
                "judge": [a["judge"]["score"] for a in per_state],
                "answers": [a["answer"] for a in per_state],
                "retrieved": [a["retrieved_doc_ids"] for a in per_state],
            }
        )

    return {
        "meta": {
            "repo": REPO_URL,
            "source": settings.source_api,
            "query": settings.source_query,
            "filter": settings.source_filter,
            "embedding_model": settings.embedding_model,
            "top_k": settings.top_k,
            "freshness_threshold_days": settings.freshness_threshold_days,
            "min_rows": MIN_ROWS,
            "max_rows": MAX_ROWS,
            "min_summary_chars": MIN_SUMMARY_CHARS,
            "seed": log["seed"],
            "corrupted_at": log["created_at"],
            "raw_items": len(read_json(paths.raw_api_response)["message"]["items"]),
        },
        "states": states,
        "scenarios": scenarios,
        "questions": questions,
        "papers": papers,
    }


def main() -> None:
    settings = load_settings()
    target = settings.paths.project_dir / "ui" / "dashboard.html"
    payload = json.dumps(build_payload(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html, count = DATA_BLOCK.subn(lambda m: m.group(1) + payload + m.group(3), target.read_text(encoding="utf-8"))
    if count != 1:
        raise RuntimeError(f"Khong tim thay block dashboard-data trong {target}")
    target.write_text(html, encoding="utf-8")
    print(f"Dashboard updated: {target} ({len(payload) // 1024} KB data)")


if __name__ == "__main__":
    main()
