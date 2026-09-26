from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import display_path, now_utc, read_json, write_frame
from evaluation.metrics import EvaluationBundle, evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Idempotent repair: dung lai clean data tu raw snapshot bat bien thay vi va tung dong hong.

    Cung raw snapshot -> cung clean data, nen chay lai bao nhieu lan cung cho mot ket qua.
    """
    records = load_raw_records(settings.paths.raw_records_json)
    repaired = build_clean_dataframe(records, now_utc())
    write_frame(repaired, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    return repaired


def _index_and_evaluate(
    settings: Settings, df: pd.DataFrame, embeddings_path: Path, metrics_path: Path, answers_path: Path
) -> EvaluationBundle:
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    return evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Corrupt -> do suy giam (silent failure) -> repair tu raw snapshot -> danh gia lai -> report 3 trang thai."""
    paths = settings.paths

    def rel(path) -> str:
        return display_path(path, paths.project_dir)

    required = [
        paths.clean_json, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers,
        paths.baseline_quality_report, paths.freshness_report, paths.raw_records_json,
    ]
    missing = [rel(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing baseline artifacts: {', '.join(missing)}. Run `python script/run_phase1.py` first.")

    # 1. Baseline tu phase 1; bat buoc cung test set thi so sanh 3 trang thai moi co y nghia.
    baseline_answers = read_json(paths.baseline_answers)
    if [item["id"] for item in baseline_answers] != [item["id"] for item in read_json(paths.eval_testset)]:
        raise RuntimeError("Baseline was evaluated on a different test set. Re-run `python script/run_phase1.py`.")
    clean_df = pd.read_json(paths.clean_json)

    # 2. Corrupt: gate chi ghi nhan chu KHONG chan, de do tac dong khi du lieu ban lot vao index.
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    write_frame(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )
    corrupted = _index_and_evaluate(
        settings, corrupted_df, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers
    )
    print(
        f"[corruption_flow] Corrupted: gate success={corrupted_quality['success']} but indexed anyway -> "
        f"retrieval_hit_rate={corrupted.summary['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={corrupted.summary['mean_token_f1']:.4f}"
    )

    # 3. Repair tu raw snapshot; data sau repair phai qua gate truoc khi duoc index lai.
    repaired_df = repair_from_raw_snapshot(settings)
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )
    if not repaired_quality["gx_success"]:
        raise RuntimeError("Repaired data still fails the quality gate; refusing to index it.")
    repaired = _index_and_evaluate(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers
    )
    print(
        f"[corruption_flow] Repaired from {rel(paths.raw_records_json)}: {len(repaired_df)} rows -> "
        f"retrieval_hit_rate={repaired.summary['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={repaired.summary['mean_token_f1']:.4f}"
    )

    # 4. Bao cao 3 trang thai.
    comparison = generate_corruption_report(
        paths.comparison_report,
        read_json(paths.baseline_metrics),
        corrupted.summary,
        repaired.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=read_json(paths.baseline_quality_report),
        baseline_freshness=read_json(paths.freshness_report),
        corruption_log=read_json(paths.corruption_log),
        answers={"baseline": baseline_answers, "corrupted": corrupted.answers, "repaired": repaired.answers},
    )
    print("\n=== Baseline vs Corrupted vs Repaired ===\n" + comparison + "\n")
    print(f"[corruption_flow] Report -> {rel(paths.comparison_report)}")
    return {
        "corrupted": {"metrics": corrupted.summary, "quality": corrupted_quality, "freshness": corrupted_freshness},
        "repaired": {"metrics": repaired.summary, "quality": repaired_quality, "freshness": repaired_freshness},
    }


def main() -> None:
    run_corruption_flow_pipeline(load_settings())
