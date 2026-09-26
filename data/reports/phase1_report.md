# Phase 1 Report - Baseline Pipeline

Generated at `2026-09-26T03:38:56+00:00`. Flow: Ingest -> Clean -> Quality gate -> Index (ChromaDB) -> Test set -> Evaluate.

## 1. Source and configuration

| Item | Value |
| --- | --- |
| Source API | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter (configured) | from-pub-date:2026-03-30,has-abstract:true |
| Source mode | local raw snapshot data/raw/crossref_records.json |
| Raw records | 24 |
| Clean rows | 24 |
| Run date (UTC) | 2026-09-26T03:38:30+00:00 |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Vector collection | papers-baseline |
| Retrieval top_k | 4 |
| LLM provider / model | openai / gpt-6-luna |
| Test set | data/eval/test_set.json (10 questions, reused) |

## 2. Baseline evaluation

| Metric | Value |
| --- | ---: |
| Samples | 10 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 1.0000 |
| Judge accuracy | 1.0000 |
| Mean judge score (1-5) | 5.0000 |
| Judge mode | LLM judge (10/10 answers) |
| Ragas | skipped (set RUN_RAGAS=1 to enable) |

### Per-question results

| ID | Type | Retrieval hit | Token F1 | Judge score | Answer |
| --- | --- | --- | ---: | ---: | --- |
| eval_001 | summary | yes | 1.0000 | 5 | Abstract Diagnosing jawbone lesions in oral and maxillofacial radio... |
| eval_002 | summary | yes | 1.0000 | 5 | Abstract Introduction While Large Language Models (LLMs) offer gene... |
| eval_003 | summary | yes | 1.0000 | 5 | This study investigates a method that integrates retrieval-augmente... |
| eval_004 | authors | yes | 1.0000 | 5 | Fardin Jalil Piran, Rajiv Malhotra, Farhad Imani |
| eval_005 | authors | yes | 1.0000 | 5 | Janet L. Autrey, Lacey S. Duckworth, Ashly N. Horner, Thomas Sigler... |
| eval_006 | authors | yes | 1.0000 | 5 | Qianwen Cao, Chiyu Zhang, Junxiong Ning, Gongru Li |
| eval_007 | date | yes | 1.0000 | 5 | 2026-06-15 |
| eval_008 | date | yes | 1.0000 | 5 | 2026-07-10 |
| eval_009 | categories | yes | 1.0000 | 5 | posted-content |
| eval_010 | categories | yes | 1.0000 | 5 | posted-content |

## 3. Data quality gate (Great Expectations)

Suite `papers_baseline_suite` on GX 1.23.2: **PASS 6/6** expectations passed. Overall gate (expectations AND freshness): **PASS**. Dataset: 24 rows, 24 unique `paper_id`, content fingerprint `8b5b9cc5e8239eab`.

| Expectation | Column | Result |
| --- | --- | --- |
| expect_table_row_count_to_be_between | - | PASS (24) |
| expect_column_values_to_not_be_null | paper_id | PASS (0 unexpected) |
| expect_column_values_to_be_unique | paper_id | PASS (0 unexpected) |
| expect_column_values_to_not_be_null | title | PASS (0 unexpected) |
| expect_column_values_to_not_be_null | text_for_embedding | PASS (0 unexpected) |
| expect_column_value_lengths_to_be_between | summary | PASS (0 unexpected) |

## 4. Freshness SLA

| Item | Value |
| --- | --- |
| Latest published | 2026-09-15 |
| Oldest published | 2026-04-01 |
| Stale rule | age_days > 180 |
| Stale rows | 0/24 (0.0%) |
| Max stale ratio | 25% |
| Status | FRESH |
