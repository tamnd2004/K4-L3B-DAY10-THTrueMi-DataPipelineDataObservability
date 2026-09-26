from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations.data_context.types.base import ProgressBarsConfig
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS = 5
MAX_ROWS = 5000
NOT_NULL_COLUMNS = ("paper_id", "title", "text_for_embedding")
MIN_SUMMARY_CHARS = 30
# Freshness SLA: data het fresh khi qua 25% bai bao cu hon `settings.freshness_threshold_days`.
MAX_STALE_RATIO = 0.25


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Do ty le bai bao stale (`age_days > threshold`) va gan co `is_fresh`."""
    total_rows = len(df)
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    published = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna()
    return {
        "latest_published": published.max().date().isoformat() if not published.empty else None,
        "oldest_published": published.min().date().isoformat() if not published.empty else None,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }


def _build_expectation_suite(context, name: str) -> gx.ExpectationSuite:
    suite = context.suites.add(gx.ExpectationSuite(name=name))
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS))
    for column in NOT_NULL_COLUMNS:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS)
    )
    return suite


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Quality gate truoc khi index: GX 1.x (ephemeral context) + Freshness SLA.

    `success` chi True khi pass het expectations VA data con fresh. Ghi summary vao
    `data/quality/<report_name>_quality_report.json`, full GX result vao `data/quality/gx/`.
    """
    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False)
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = _build_expectation_suite(context, f"papers_{report_name}_suite")
    validation = batch.validate(suite)
    described = validation.describe_dict()
    freshness = evaluate_freshness_sla(df, settings)

    expectations = []
    for item in described["expectations"]:
        result = item.get("result") or {}
        expectations.append({
            "expectation": item["expectation_type"],
            "column": item["kwargs"].get("column"),
            "success": item["success"],
            "observed_value": result.get("observed_value"),
            "unexpected_count": result.get("unexpected_count"),
        })

    gx_success = bool(validation.success)
    report = {
        "report_name": report_name,
        "checked_at": now_utc().isoformat(),
        "great_expectations_version": gx.__version__,
        "suite_name": suite.name,
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "statistics": described["statistics"],
        "expectations": expectations,
        "freshness": freshness,
    }
    write_json(settings.paths.gx_dir / f"{report_name}_validation.json", validation.to_json_dict())
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)

    stats = described["statistics"]
    print(
        f"[quality] {report_name}: GX {stats['successful_expectations']}/{stats['evaluated_expectations']} "
        f"expectations passed, stale {freshness['stale_rows']}/{freshness['total_rows']} "
        f"(is_fresh={freshness['is_fresh']}) -> success={report['success']}"
    )
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Ghi freshness report (latest/oldest published, stale rows, is_fresh) ra JSON."""
    report = {"checked_at": now_utc().isoformat(), **evaluate_freshness_sla(df, settings)}
    write_json(Path(report_path), report)
    return report
