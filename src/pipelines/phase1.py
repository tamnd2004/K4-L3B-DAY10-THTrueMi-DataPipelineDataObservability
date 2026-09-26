from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings
from core.utils import display_path, now_utc, read_json, write_frame
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Baseline end-to-end: Ingest -> Clean -> Quality gate -> Index -> Test set -> Evaluate -> Report."""
    paths = settings.paths
    run_date = now_utc()

    def rel(path) -> str:
        return display_path(path, paths.project_dir)

    # 1. Ingest: mac dinh doc raw snapshot de ket qua tai lap duoc; REFRESH_SOURCE=1 moi goi Crossref live.
    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
        source_mode = "Crossref API (fallback: local snapshot)"
    else:
        records = load_raw_records(paths.raw_records_json)
        source_mode = f"local raw snapshot {rel(paths.raw_records_json)}"
    print(f"[phase1] 1/6 Ingest: {len(records)} raw records from {source_mode}")

    # 2. Clean
    clean_df = build_clean_dataframe(records, run_date)
    write_frame(clean_df, paths.clean_csv, paths.clean_json)
    print(f"[phase1] 2/6 Clean: {len(clean_df)} rows -> {rel(paths.clean_csv)}, {rel(paths.clean_json)}")

    # 3. Quality gate TRUOC khi index: expectation fail -> dung pipeline; freshness fail -> chi canh bao.
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    if not quality["gx_success"]:
        raise RuntimeError(f"Baseline quality gate failed, not indexing. See {rel(paths.baseline_quality_report)}")
    if not freshness["is_fresh"]:
        print(
            f"[phase1] WARNING: freshness SLA breached ({freshness['stale_ratio']:.1%} stale > "
            f"{freshness['max_stale_ratio']:.0%}); set REFRESH_SOURCE=1 to re-fetch."
        )
    print(f"[phase1] 3/6 Quality gate: expectations passed -> {rel(paths.baseline_quality_report)}")

    # 4. Index
    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)
    print(f"[phase1] 4/6 Index: {len(index.documents)} docs -> Chroma collection '{index.collection_name}'")

    # 5. Test set: giu nguyen file co san de baseline/corrupted/repaired dung chung bo cau hoi;
    #    chi build lai khi REFRESH_TEST_SET=1 hoac test set tro toi paper khong con trong corpus.
    test_set = read_json(paths.eval_testset) if paths.eval_testset.exists() else []
    known_ids = set(clean_df["paper_id"])
    orphaned = any(doc_id not in known_ids for item in test_set for doc_id in item["ground_truth_doc_ids"])
    if settings.refresh_test_set or not test_set or orphaned:
        test_set = build_test_set(clean_df, paths.eval_testset)
        test_set_mode = "rebuilt"
    else:
        test_set_mode = "reused"
    print(f"[phase1] 5/6 Test set: {len(test_set)} questions ({test_set_mode}) -> {rel(paths.eval_testset)}")

    # 6. Evaluate
    bundle = evaluate_pipeline(settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers)
    metrics = bundle.summary
    print(
        f"[phase1] 6/6 Evaluate: retrieval_hit_rate={metrics['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={metrics['mean_token_f1']:.4f} judge_accuracy={metrics['judge_accuracy']:.4f} "
        f"-> {rel(paths.baseline_metrics)}"
    )

    source_summary = {
        "Source API": settings.source_api,
        "Query": settings.source_query,
        "Filter (configured)": settings.source_filter,
        "Source mode": source_mode,
        "Raw records": len(records),
        "Clean rows": len(clean_df),
        "Run date (UTC)": run_date.isoformat(timespec="seconds"),
        "Embedding model": settings.embedding_model,
        "Vector collection": index.collection_name,
        "Retrieval top_k": settings.top_k,
        "LLM provider / model": f"{settings.llm_provider} / {settings.model_name}",
        "Test set": f"{rel(paths.eval_testset)} ({len(test_set)} questions, {test_set_mode})",
    }
    generate_phase1_report(paths.baseline_report, source_summary, metrics, quality, freshness, answers=bundle.answers)
    print(f"[phase1] Report -> {rel(paths.baseline_report)}")
    return {"metrics": metrics, "quality": quality, "freshness": freshness}


def main() -> None:
    run_phase1_pipeline(load_settings())
