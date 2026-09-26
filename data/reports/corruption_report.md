# Corruption Report - Baseline vs Corrupted vs Repaired

Generated at `2026-09-26T03:40:00+00:00`. All three states are evaluated on the same test set (10 questions). Corrupted = clean data after the corruption suite, indexed WITHOUT enforcing the gate to measure the impact; Repaired = rebuilt from the raw snapshot and re-validated before indexing.

## 1. Three-state comparison

| Metric / signal | Baseline | Corrupted | Repaired | Change (C-B) | Recovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| Retrieval hit rate | 1.0000 | 0.9000 | 1.0000 | -0.1000 | 100% |
| Mean token F1 | 1.0000 | 0.9000 | 1.0000 | -0.1000 | 100% |
| Judge accuracy | 1.0000 | 0.9000 | 1.0000 | -0.1000 | 100% |
| Mean judge score (1-5) | 5.0000 | 4.6000 | 5.0000 | -0.4000 | 100% |
| Quality gate (GX) | PASS 6/6 | FAIL 4/6 | PASS 6/6 |  |  |
| Freshness SLA | FRESH (0/24 stale, 0.0%) | STALE (8/22 stale, 36.4%) | FRESH (0/24 stale, 0.0%) |  |  |
| Rows / unique paper_id | 24 / 24 | 22 / 19 | 24 / 24 |  |  |
| Content fingerprint | 8b5b9cc5e8239eab | 7bf7953b239d393a | 8b5b9cc5e8239eab |  |  |

Change = Corrupted - Baseline. Recovery = (Repaired - Corrupted) / (Baseline - Corrupted). Judge mode: Baseline: LLM judge (10/10 answers) | Corrupted: LLM judge (10/10 answers) | Repaired: LLM judge (10/10 answers).

## 2. Quality gate per expectation

| Expectation | Column | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- | --- |
| expect_table_row_count_to_be_between | - | PASS (24) | PASS (22) | PASS (24) |
| expect_column_values_to_not_be_null | paper_id | PASS (0 unexpected) | PASS (0 unexpected) | PASS (0 unexpected) |
| expect_column_values_to_be_unique | paper_id | PASS (0 unexpected) | FAIL (6 unexpected) | PASS (0 unexpected) |
| expect_column_values_to_not_be_null | title | PASS (0 unexpected) | PASS (0 unexpected) | PASS (0 unexpected) |
| expect_column_values_to_not_be_null | text_for_embedding | PASS (0 unexpected) | PASS (0 unexpected) | PASS (0 unexpected) |
| expect_column_value_lengths_to_be_between | summary | PASS (0 unexpected) | FAIL (3 unexpected) | PASS (0 unexpected) |

## 3. Corruption scenarios and detection

| Scenario | What was done | Rows | Designed signal | Corrupted-state signal | Verdict |
| --- | --- | ---: | --- | --- | --- |
| drop_latest_records | Drop 20% newest papers | 5 | expect_table_row_count_to_be_between | PASS (22) | MISSED |
| blank_summary | Set summary to an empty string | 3 | expect_column_value_lengths_to_be_between(summary) | FAIL (3 unexpected) | DETECTED |
| inject_noise | Insert random junk tokens after ~25% of summary words | 3 | none | - | SILENT (no check covers it) |
| truncate_title | Cut title to 7 characters | 3 | none | - | SILENT (no check covers it) |
| stale_date | Shift published date back 365 days | 6 | freshness: stale ratio <= 25% | STALE (8/22 stale, 36.4%) | DETECTED |
| duplicate_rows | Append exact copies of rows | 3 | expect_column_values_to_be_unique(paper_id) | FAIL (6 unexpected) | DETECTED |

## 4. Per-question impact

| ID | Type | Corruption on ground-truth paper | Hit B/C/R | Token F1 B/C/R | Judge B/C/R | Corrupted answer |
| --- | --- | --- | --- | --- | --- | --- |
| eval_001 | summary | truncate_title | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | Abstract Diagnosing jawbone lesions in oral and maxillofacial radio... |
| eval_002 | summary | none | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | Abstract Introduction While Large Language Models (LLMs) offer gene... |
| eval_003 | summary | blank_summary | Y / Y / Y | 1.00 / 0.00 / 1.00 | 5 / 1 / 5 | (empty answer) |
| eval_004 | authors | none | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | Fardin Jalil Piran, Rajiv Malhotra, Farhad Imani |
| eval_005 | authors | inject_noise | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | Janet L. Autrey, Lacey S. Duckworth, Ashly N. Horner, Thomas Sigler... |
| eval_006 | authors | stale_date | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | Qianwen Cao, Chiyu Zhang, Junxiong Ning, Gongru Li |
| eval_007 | date | inject_noise | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | 2026-06-15 |
| eval_008 | date | inject_noise | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | 2026-07-10 |
| eval_009 | categories | drop_latest_records | Y / N / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | posted-content |
| eval_010 | categories | stale_date, duplicate_rows | Y / Y / Y | 1.00 / 1.00 / 1.00 | 5 / 5 / 5 | posted-content |

## 5. Key findings

- Retrieval hit rate: 1.0000 -> 0.9000 after corruption (-0.1000); repaired 1.0000 (recovery 100%).
- Mean token F1: 1.0000 -> 0.9000 after corruption (-0.1000); repaired 1.0000 (recovery 100%).
- Judge accuracy: 1.0000 -> 0.9000 after corruption (-0.1000); repaired 1.0000 (recovery 100%).
- Mean judge score (1-5): 5.0000 -> 4.6000 after corruption (-0.4000); repaired 5.0000 (recovery 100%).
- Quality gate on corrupted data: FAIL 4/6 (failed: expect_column_values_to_be_unique(paper_id), expect_column_value_lengths_to_be_between(summary)); freshness STALE (8/22 stale, 36.4%).
- Corruptions with no quality signal (silent failure risk): drop_latest_records, inject_noise, truncate_title.
- Questions degraded by corruption: eval_003 (summary; blank_summary: F1 1.00->0.00, hit Y->Y); eval_009 (categories; drop_latest_records [silent]: F1 1.00->1.00, hit Y->N).
- Questions whose ground-truth paper was not corrupted: eval_002, eval_004.
- Repaired content fingerprint matches baseline (8b5b9cc5e8239eab): repair restored the exact baseline corpus from the raw snapshot.
