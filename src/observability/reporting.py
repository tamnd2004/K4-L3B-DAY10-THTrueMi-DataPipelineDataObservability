from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text

METRICS = (
    ("retrieval_hit_rate", "Retrieval hit rate"),
    ("mean_token_f1", "Mean token F1"),
    ("judge_accuracy", "Judge accuracy"),
    ("mean_judge_score", "Mean judge score (1-5)"),
)
STATES = ("Baseline", "Corrupted", "Repaired")
FALLBACK_JUDGE_MARKER = "Fallback heuristic judge"
# Check cua quality gate duoc thiet ke de bat tung loai corruption; None = khong co check nao (silent).
SCENARIO_SIGNALS: dict[str, Any] = {
    "drop_latest_records": ("expect_table_row_count_to_be_between", None),
    "blank_summary": ("expect_column_value_lengths_to_be_between", "summary"),
    "inject_noise": None,
    "truncate_title": None,
    "stale_date": "freshness",
    "duplicate_rows": ("expect_column_values_to_be_unique", "paper_id"),
}


def _cell(value: Any, limit: int = 70) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    text = " ".join(str(value).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _table(headers: list[str], rows: list[list[Any]], right: tuple[int, ...] = ()) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if i in right else "---" for i in range(len(headers))) + " |",
    ]
    lines += ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join(lines)


def _gate(quality: dict[str, Any] | None) -> str:
    if not quality:
        return "n/a"
    stats = quality["statistics"]
    verdict = "PASS" if quality["gx_success"] else "FAIL"
    return f"{verdict} {stats['successful_expectations']}/{stats['evaluated_expectations']}"


def _fresh(freshness: dict[str, Any] | None) -> str:
    if not freshness:
        return "n/a"
    verdict = "FRESH" if freshness["is_fresh"] else "STALE"
    return f"{verdict} ({freshness['stale_rows']}/{freshness['total_rows']} stale, {freshness['stale_ratio']:.1%})"


def _expectation_result(item: dict[str, Any]) -> str:
    detail = item["observed_value"] if item["unexpected_count"] is None else f"{item['unexpected_count']} unexpected"
    return f"{'PASS' if item['success'] else 'FAIL'} ({_cell(detail)})"


def _expectation_name(item: dict[str, Any]) -> str:
    return f"{item['expectation']}({item['column']})" if item["column"] else item["expectation"]


def _judge_mode(answers: list[dict[str, Any]] | None) -> str:
    if not answers:
        return "n/a"
    fallback = sum(FALLBACK_JUDGE_MARKER in item["judge"]["reasoning"] for item in answers)
    if not fallback:
        return f"LLM judge ({len(answers)}/{len(answers)} answers)"
    return f"heuristic fallback for {fallback}/{len(answers)} answers (LLM judge unavailable)"


def _ragas(metrics: dict[str, Any]) -> str:
    ragas = metrics.get("ragas") or {}
    if "skipped" in ragas:
        return "skipped (set RUN_RAGAS=1 to enable)"
    if "error" in ragas:
        return f"error: {ragas['error']}"
    return ", ".join(f"{key}={_cell(value)}" for key, value in ragas.items()) or "n/a"


def _recovery(base: float, corrupt: float, repair: float) -> str:
    drop = base - corrupt
    if abs(drop) < 1e-9:
        return "n/a (no drop)"
    return f"{(repair - corrupt) / drop:.0%}"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> None:
    """Viet markdown report baseline: nguon du lieu, metrics, tung cau hoi, quality gate va freshness."""
    metric_rows = [["Samples", metrics["samples"]]] + [[label, float(metrics[key])] for key, label in METRICS]
    metric_rows += [["Judge mode", _judge_mode(answers)], ["Ragas", _ragas(metrics)]]
    dataset = quality.get("dataset", {})
    sections = [
        "# Phase 1 Report - Baseline Pipeline",
        f"Generated at `{now_utc().isoformat(timespec='seconds')}`. "
        "Flow: Ingest -> Clean -> Quality gate -> Index (ChromaDB) -> Test set -> Evaluate.",
        "## 1. Source and configuration",
        _table(["Item", "Value"], [[key, value] for key, value in source_summary.items()]),
        "## 2. Baseline evaluation",
        _table(["Metric", "Value"], metric_rows, right=(1,)),
    ]
    if answers:
        sections += [
            "### Per-question results",
            _table(
                ["ID", "Type", "Retrieval hit", "Token F1", "Judge score", "Answer"],
                [
                    [a["id"], a["question_type"], a["retrieval_hit"], a["token_f1"], a["judge"]["score"], a["answer"]]
                    for a in answers
                ],
                right=(3, 4),
            ),
        ]
    sections += [
        "## 3. Data quality gate (Great Expectations)",
        f"Suite `{quality['suite_name']}` on GX {quality['great_expectations_version']}: "
        f"**{_gate(quality)}** expectations passed. Overall gate (expectations AND freshness): "
        f"**{'PASS' if quality['success'] else 'FAIL'}**. Dataset: {dataset.get('rows')} rows, "
        f"{dataset.get('unique_paper_ids')} unique `paper_id`, content fingerprint `{dataset.get('fingerprint')}`.",
        _table(
            ["Expectation", "Column", "Result"],
            [[item["expectation"], item["column"], _expectation_result(item)] for item in quality["expectations"]],
        ),
        "## 4. Freshness SLA",
        _table(
            ["Item", "Value"],
            [
                ["Latest published", freshness["latest_published"]],
                ["Oldest published", freshness["oldest_published"]],
                ["Stale rule", f"age_days > {freshness['threshold_days']}"],
                ["Stale rows", f"{freshness['stale_rows']}/{freshness['total_rows']} ({freshness['stale_ratio']:.1%})"],
                ["Max stale ratio", f"{freshness['max_stale_ratio']:.0%}"],
                ["Status", "FRESH" if freshness["is_fresh"] else "STALE"],
            ],
        ),
    ]
    write_text(Path(report_path), "\n\n".join(sections) + "\n")


def _dataset(quality: dict[str, Any] | None) -> dict[str, Any]:
    return (quality or {}).get("dataset") or {}


def _comparison_table(metrics: dict, quality: dict, freshness: dict) -> str:
    rows = []
    for key, label in METRICS:
        base, corrupt, repair = (float(metrics[state][key]) for state in STATES)
        rows.append([label, base, corrupt, repair, f"{corrupt - base:+.4f}", _recovery(base, corrupt, repair)])
    datasets = [_dataset(quality[state]) for state in STATES]
    rows += [
        ["Quality gate (GX)", *(_gate(quality[state]) for state in STATES), "", ""],
        ["Freshness SLA", *(_fresh(freshness[state]) for state in STATES), "", ""],
        ["Rows / unique paper_id", *(f"{d.get('rows')} / {d.get('unique_paper_ids')}" for d in datasets), "", ""],
        ["Content fingerprint", *(d.get("fingerprint") for d in datasets), "", ""],
    ]
    return _table(["Metric / signal", *STATES, "Change (C-B)", "Recovery"], rows, right=(1, 2, 3, 4, 5))


def _expectation_matrix(quality: dict) -> str:
    results: dict[tuple[str, str | None], dict[str, str]] = {}
    for state in STATES:
        for item in (quality[state] or {}).get("expectations", []):
            results.setdefault((item["expectation"], item["column"]), {})[state] = _expectation_result(item)
    rows = [[name, column, *(by_state.get(state, "n/a") for state in STATES)] for (name, column), by_state in results.items()]
    return _table(["Expectation", "Column", *STATES], rows)


def _detection(scenario: str, quality: dict[str, Any], freshness: dict[str, Any]) -> tuple[str, str, str]:
    signal = SCENARIO_SIGNALS.get(scenario)
    if signal is None:
        return "none", "-", "SILENT (no check covers it)"
    if signal == "freshness":
        verdict = "DETECTED" if not freshness["is_fresh"] else "MISSED"
        return f"freshness: stale ratio <= {freshness['max_stale_ratio']:.0%}", _fresh(freshness), verdict
    expectation, column = signal
    item = next((e for e in quality["expectations"] if (e["expectation"], e["column"]) == signal), None)
    if item is None:
        return expectation, "n/a", "n/a"
    return _expectation_name(item), _expectation_result(item), "MISSED" if item["success"] else "DETECTED"


def _touched_papers(corruption_log: dict[str, Any] | None) -> dict[str, list[str]]:
    touched: dict[str, list[str]] = {}
    for entry in (corruption_log or {}).get("scenarios", []):
        for record in entry["records"]:
            scenarios = touched.setdefault(record["paper_id"], [])
            if entry["scenario"] not in scenarios:
                scenarios.append(entry["scenario"])
    return touched


def _question_rows(answers: dict[str, list[dict[str, Any]]], corruption_log: dict[str, Any] | None) -> list[dict]:
    touched = _touched_papers(corruption_log)
    by_state = {state: {item["id"]: item for item in answers[state.lower()]} for state in STATES}
    rows = []
    for item in answers["baseline"]:
        runs = [by_state[state].get(item["id"]) for state in STATES]
        rows.append({
            "id": item["id"],
            "type": item["question_type"],
            "scenarios": touched.get(item["ground_truth_doc_ids"][0], []),
            "runs": runs,
        })
    return rows


def _question_table(rows: list[dict]) -> str:
    def join(values):
        return " / ".join(values)

    return _table(
        ["ID", "Type", "Corruption on ground-truth paper", "Hit B/C/R", "Token F1 B/C/R", "Judge B/C/R", "Corrupted answer"],
        [
            [
                row["id"],
                row["type"],
                ", ".join(row["scenarios"]) or "none",
                join("Y" if run and run["retrieval_hit"] else "N" for run in row["runs"]),
                join(f"{run['token_f1']:.2f}" if run else "-" for run in row["runs"]),
                join(str(run["judge"]["score"]) if run else "-" for run in row["runs"]),
                (row["runs"][1]["answer"] or "(empty answer)") if row["runs"][1] else "-",
            ]
            for row in rows
        ],
    )


def _findings(metrics: dict, quality: dict, freshness: dict, corruption_log, question_rows: list[dict]) -> str:
    lines = []
    for key, label in METRICS:
        base, corrupt, repair = (metrics[state][key] for state in STATES)
        lines.append(
            f"- {label}: {base:.4f} -> {corrupt:.4f} after corruption ({corrupt - base:+.4f}); "
            f"repaired {repair:.4f} (recovery {_recovery(base, corrupt, repair)})."
        )
    corrupted_quality, corrupted_freshness = quality["Corrupted"], freshness["Corrupted"]
    failed = [_expectation_name(item) for item in corrupted_quality["expectations"] if not item["success"]]
    lines.append(
        f"- Quality gate on corrupted data: {_gate(corrupted_quality)} (failed: {', '.join(failed) or 'none'}); "
        f"freshness {_fresh(corrupted_freshness)}."
    )
    undetected = []
    if corruption_log:
        undetected = [
            entry["scenario"]
            for entry in corruption_log["scenarios"]
            if _detection(entry["scenario"], corrupted_quality, corrupted_freshness)[2] != "DETECTED"
        ]
        lines.append(f"- Corruptions with no quality signal (silent failure risk): {', '.join(undetected) or 'none'}.")
    degraded = []
    for row in question_rows:
        base, corrupt = row["runs"][0], row["runs"][1]
        if corrupt and (corrupt["token_f1"] < base["token_f1"] - 1e-9 or base["retrieval_hit"] != corrupt["retrieval_hit"]):
            cause = ", ".join(row["scenarios"]) or "no direct corruption"
            silent = " [silent]" if row["scenarios"] and all(s in undetected for s in row["scenarios"]) else ""
            degraded.append(
                f"{row['id']} ({row['type']}; {cause}{silent}: F1 {base['token_f1']:.2f}->{corrupt['token_f1']:.2f}, "
                f"hit {'Y' if base['retrieval_hit'] else 'N'}->{'Y' if corrupt['retrieval_hit'] else 'N'})"
            )
    lines.append(f"- Questions degraded by corruption: {'; '.join(degraded) or 'none'}.")
    untouched = [row["id"] for row in question_rows if not row["scenarios"]]
    lines.append(f"- Questions whose ground-truth paper was not corrupted: {', '.join(untouched) or 'none'}.")
    baseline_fp, repaired_fp = _dataset(quality["Baseline"]).get("fingerprint"), _dataset(quality["Repaired"]).get("fingerprint")
    if baseline_fp and repaired_fp:
        same = baseline_fp == repaired_fp
        lines.append(
            f"- Repaired content fingerprint {'matches' if same else 'DIFFERS from'} baseline ({repaired_fp}): repair "
            f"{'restored the exact baseline corpus from the raw snapshot' if same else 'did not restore the baseline corpus'}."
        )
    return "\n".join(lines)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    *,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    answers: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Viet markdown report so sanh baseline/corrupted/repaired; tra ve bang so sanh de in ra console."""
    metrics = dict(zip(STATES, (baseline_metrics, corrupted_metrics, repaired_metrics)))
    quality = dict(zip(STATES, (baseline_quality, corrupted_quality, repaired_quality)))
    freshness = dict(zip(STATES, (baseline_freshness, corrupted_freshness, repaired_freshness)))
    question_rows = _question_rows(answers, corruption_log) if answers else []

    comparison = _comparison_table(metrics, quality, freshness)
    sections = [
        "# Corruption Report - Baseline vs Corrupted vs Repaired",
        f"Generated at `{now_utc().isoformat(timespec='seconds')}`. All three states are evaluated on the same "
        f"test set ({baseline_metrics['samples']} questions). Corrupted = clean data after the corruption suite, "
        "indexed WITHOUT enforcing the gate to measure the impact; Repaired = rebuilt from the raw snapshot and "
        "re-validated before indexing.",
        "## 1. Three-state comparison",
        comparison,
        "Change = Corrupted - Baseline. Recovery = (Repaired - Corrupted) / (Baseline - Corrupted). "
        f"Judge mode: {' | '.join(f'{state}: {_judge_mode(answers[state.lower()])}' for state in STATES) if answers else 'n/a'}.",
        "## 2. Quality gate per expectation",
        _expectation_matrix(quality),
        "## 3. Corruption scenarios and detection",
    ]
    if corruption_log:
        sections.append(
            _table(
                ["Scenario", "What was done", "Rows", "Designed signal", "Corrupted-state signal", "Verdict"],
                [
                    [entry["scenario"], entry["description"], entry["affected_rows"],
                     *_detection(entry["scenario"], corrupted_quality, corrupted_freshness)]
                    for entry in corruption_log["scenarios"]
                ],
                right=(2,),
            )
        )
    else:
        sections.append("No corruption log provided.")
    sections.append("## 4. Per-question impact")
    sections.append(_question_table(question_rows) if question_rows else "No per-question answers provided.")
    sections += ["## 5. Key findings", _findings(metrics, quality, freshness, corruption_log, question_rows)]
    write_text(Path(report_path), "\n\n".join(sections) + "\n")
    return comparison
