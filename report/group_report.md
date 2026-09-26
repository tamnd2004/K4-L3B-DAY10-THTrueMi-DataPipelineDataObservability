# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
|---|---|
| Khóa/Lớp | K4-L3B-DAY10 |
| Tên nhóm | THTrueMi |
| Repository | https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
|---:|---|---|---|---|
| 1 | Nguyễn Thị Hải Mi | 2A202602667 | Raw ingestion & lineage | `src/ingestion/crossref.py`, `data/raw/` |
| 2 | Mai Huy Hoàng | 2A202602685 | Cleaning & data modeling | `src/ingestion/cleaning.py`, `data/clean/` |
| 3 | Trần Nguyễn Trí Dũng | 2A202602784 | Benchmark evaluation | `src/evaluation/testset.py`, `data/eval/` |
| 4 | Nguyễn Đức Tâm | 2A202602921 | Observability & integration | `src/observability/`, `src/pipelines/`, corruption/repair reports |

Chi tiết trải nghiệm cá nhân, khó khăn và cam kết nằm trong bốn file `report/individual*.md`.

## 2. Tóm tắt kết quả

Nhóm xây dựng pipeline RAG từ Crossref raw snapshot qua ingestion, cleaning, quality gate, embedding ChromaDB, evaluation và repair. Baseline tạo 24 bài báo, 24 `paper_id` duy nhất, 10 câu hỏi benchmark và đạt `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0`, điểm judge trung bình 5.0. Nhóm tiêm 6 kịch bản corruption với seed 42: bỏ 5 bài mới nhất, xóa summary ở 3 dòng, chèn noise ở 3 dòng, cắt title ở 3 dòng, lùi ngày ở 6 dòng và nhân bản 3 dòng. Corpus corrupted còn 22 dòng/19 IDs; quality gate còn 4/6 expectations và freshness báo stale 8/22 dòng (36.4%). Metrics giảm còn 0.9 và judge trung bình 4.6. Repair dựng lại từ raw snapshot bất biến, khôi phục 24 dòng, fingerprint baseline, quality 6/6, freshness 0/24 stale và toàn bộ metrics về baseline. Giới hạn còn lại là một số lỗi nội dung như noise/truncated title chưa bị 4 nhóm expectation hiện tại bắt được; dashboard hiện là artifact HTML được build từ JSON, không phải service theo dõi live.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref REST API / local snapshot
    -> raw response + raw records
    -> cleaning + age_days + text_for_embedding
    -> Great Expectations + Freshness gate
    -> MiniLM embeddings + ChromaDB
    -> fixed 10-question evaluation
    -> baseline report
    -> six corruption scenarios
    -> corrupted index/evaluation
    -> repair from immutable raw snapshot
    -> repaired gate/index/evaluation
    -> three-state comparison + dashboard
```

| Khối | Input | Xử lý chính | Output | Owner |
|---|---|---|---|---|
| Ingestion | Crossref `/works` hoặc snapshot | retry 429/5xx, fallback, parse | `data/raw/*.json` | Hải Mi |
| Cleaning | `PaperRecord` | normalize, dedupe, `age_days`, embedding text | `data/clean/papers_clean.*` | Huy Hoàng |
| Embedding/index | clean dataframe | `all-MiniLM-L6-v2`, ChromaDB top-k=4 | `data/embeddings/`, `data/chroma/` | Nhóm integration |
| Evaluation | clean/index + test set | retrieval hit, token F1, judge | `data/results/*_metrics.json` | Trí Dũng |
| Observability | dataframe + settings | GX 1.x expectations, freshness | `data/quality/` | Đức Tâm |
| Corruption/repair | clean + raw snapshot | 6 scenarios, idempotent rebuild | corrupted/repaired artifacts | Đức Tâm |
| Reporting/UI | all artifacts | markdown comparison and generated dashboard | `data/reports/`, `ui/dashboard.html` | Nhóm |

## 4. Cách tái hiện kết quả

```bash
uv sync
python script/run_phase1.py
python script/run_corruption_flow.py
python script/build_dashboard.py
```

Dashboard có thể phục vụ bằng:

```bash
python script/serve_dashboard.py
```

Pipeline mặc định đọc `data/raw/crossref_records.json` để tái lập; chỉ gọi Crossref live khi cấu hình `REFRESH_SOURCE=1`. Không ghi API key vào report.

| Lệnh | Trạng thái | Bằng chứng |
|---|---|---|
| Baseline pipeline | Thành công | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công | `data/results/corruption_log.json`, `data/reports/corruption_report.md` |
| Dashboard build | Thành công | `ui/dashboard.html` đọc artifacts trong `data/` |

## 5. Ingestion, cleaning và data contract

| Thuộc tính | Giá trị |
|---|---|
| Source | Crossref REST API hoặc local snapshot |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:<run_date-180d>,has-abstract:true` |
| Max records | 24 |
| Raw records | 24 |
| Published range | 2026-04-01 đến 2026-09-15 |
| Retry/fallback | Tối đa 3 lần cho lỗi tạm thời, exponential backoff, sau đó đọc snapshot |

Các trường contract chính gồm `paper_id`, `title`, `summary`, `authors`, `published`, `categories`, `age_days` và `text_for_embedding`. Record thiếu DOI/title/abstract/ngày bị loại ở ingestion/cleaning; whitespace và JATS/HTML được chuẩn hóa. `paper_id` là DOI lowercase; `text_for_embedding` ghép năm phần Title, Authors, Published, Categories, Summary. `age_days=(run_date-published).days`. Cleaning dedupe theo `paper_id` trước khi ghi JSON/CSV.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
|---|---|
| Số câu hỏi | 10 |
| Question types | 3 summary, 3 authors, 2 date, 2 categories |
| Ground truth IDs | DOI từ `data/raw/crossref_records.json` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | ChromaDB local, collections baseline/corrupted/repaired |
| Retrieval | `top_k=4` |
| LLM | cấu hình provider trong `.env`; artifacts hiện lưu judge hợp lệ, không lộ secret |
| Test set | `data/eval/test_set.json`, giữ nguyên cho cả 3 trạng thái |

Giữ nguyên test set là biến kiểm soát: thay đổi metrics chỉ phản ánh dữ liệu/index bị corruption hoặc repair, không phải thay đổi câu hỏi.

## 7. Kết quả baseline

| Artifact | Trạng thái |
|---|---|
| Raw response/records | Có, `data/raw/` |
| Cleaned dataset | Có, `data/clean/papers_clean.csv/.json` |
| Embedding/index | Có, `data/embeddings/` và `data/chroma/` |
| Evaluation set | Có, `data/eval/test_set.json` |
| Baseline metrics | Có, `data/results/baseline_metrics.json` |
| Quality/freshness | Có, `data/quality/` |
| Baseline report | Có, `data/reports/phase1_report.md` |

| Metric | Baseline |
|---|---:|
| `retrieval_hit_rate` | 1.00 |
| `mean_token_f1` | 1.00 |
| `judge_accuracy` | 1.00 |
| `mean_judge_score` | 5.00/5 |
| Ragas | Skipped; artifact ghi rõ cần `RUN_RAGAS=1` |

## 8. Data quality và freshness

Quality gate dùng GX 1.x Ephemeral Context. Sáu expectation được đánh giá là row count 5–5000, non-null cho `paper_id/title/text_for_embedding`, unique `paper_id` và summary dài tối thiểu 30 ký tự.

| Check | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| GX expectations | 6/6 PASS | 4/6 PASS | 6/6 PASS |
| Rows / unique IDs | 24 / 24 | 22 / 19 | 24 / 24 |
| Freshness | 0/24 stale, FRESH | 8/22 stale, 36.4%, STALE | 0/24 stale, FRESH |
| Threshold | `age_days > 180`, stale ratio tối đa 25% | vượt ngưỡng | đạt ngưỡng |

Bằng chứng: `data/quality/*_quality_report.json`, `data/quality/*freshness_report.json` và `data/quality/gx/*_validation.json`.

## 9. Corruption scenarios và repair

| Corruption | Record bị tác động | Tín hiệu | Repair |
|---|---:|---|---|
| Drop latest records | 5 | row count vẫn trong range; retrieval một câu bị miss | raw snapshot |
| Blank summary | 3 | summary length fail; eval_003 sai | raw snapshot |
| Inject noise | 3 | chưa bị gate hiện tại bắt | raw snapshot |
| Truncate title | 3 | chưa bị gate hiện tại bắt | raw snapshot |
| Stale date | 6 | freshness vượt 25% | raw snapshot |
| Duplicate rows | 3 bản sao | unique `paper_id` fail | raw snapshot |

Corruption log: `data/results/corruption_log.json`, seed 42, 24 input rows → 22 output rows. Repair dùng `repair_from_raw_snapshot()` và chạy lại cleaning/gate/index/evaluation; không vá giá trị đã hỏng tại chỗ. Fingerprint repaired `8b5b9cc5e8239eab` trùng baseline chứng minh tính idempotent.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Kết luận |
|---|---:|---:|---:|---|
| Retrieval hit rate | 1.00 | 0.90 | 1.00 | phục hồi 100% |
| Mean token F1 | 1.00 | 0.90 | 1.00 | summary rỗng làm một câu trả lời mất nội dung |
| Judge accuracy | 1.00 | 0.90 | 1.00 | phục hồi 100% |
| Mean judge score | 5.0 | 4.6 | 5.0 | eval_003 giảm từ 5 xuống 1 |
| Quality gate | 6/6 | 4/6 | 6/6 | duplicate + blank summary bị bắt |
| Freshness | 0/24 stale | 8/22 stale | 0/24 stale | stale date vượt SLA 25% |
| Content fingerprint | `8b5b9cc5e8239eab` | `7bf7953b239d393a` | `8b5b9cc5e8239eab` | repaired khớp baseline |

Quan hệ nhân quả chính:

1. `blank_summary` → summary length fail → eval_003 trả lời rỗng → F1/judge accuracy giảm 1.0 xuống 0.9.
2. `stale_date` + duplicate stale rows → 8/22 stale (36.4%) → Freshness SLA fail; raw-snapshot repair → 0/24 stale và metrics trở lại baseline.
3. `drop_latest_records` làm thiếu tài liệu mục tiêu của eval_009; retrieval hit giảm, nhưng answer vẫn đúng nhờ tài liệu còn lại, nên retrieval và answer quality không luôn đồng biến.

## 11. Vấn đề tích hợp quan trọng

Trong lần chạy đầu, OpenAI reasoning model bị gửi `temperature=0.0`, API trả lỗi 400 nhưng evaluator fallback sang heuristic nên metric có nguy cơ trông tốt giả tạo. Nhóm truy vết `judge.reasoning`, bổ sung nhận diện model không hỗ trợ temperature trong `src/retrieval/llm.py`, rồi chạy lại pipeline. Sau sửa, cả ba trạng thái có 0/10 câu fallback; report có thông tin judge mode. Đây là ví dụ cho thấy evaluation code cũng cần observability.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
|---|---|---|
| Noise và title bị cắt chưa bị 4 nhóm expectation hiện tại bắt | Một số silent failure vẫn pass gate | thêm kiểm tra regex noise, min title length và completeness/relative drift; đo lại false positive |
| Dashboard là HTML build từ snapshot JSON | Chưa có live monitoring/trigger repair | thêm run manifest, timestamp/fingerprint và nút chạy pipeline local |
| Ragas chưa chạy | Chưa có context/faithfulness metrics | chạy `RUN_RAGAS=1` trong môi trường đủ dependencies |
| Chưa có pytest CI hoàn chỉnh | Regression phải kiểm tra thủ công | thêm test ingestion/cleaning/GX/retrieval và GitHub Actions |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm, thành viên và repository đã điền.
- [x] Phân công khớp với module, artifact và báo cáo cá nhân.
- [x] Baseline/corrupted/repaired dùng cùng `data/eval/test_set.json`.
- [x] Metrics khớp `data/results/*.json`.
- [x] Quality/freshness khớp `data/quality/`.
- [x] Corruption log và comparison report tồn tại.
- [x] Bốn báo cáo cá nhân đã có cam kết và ngày xác nhận.
- [x] Không đưa API key/token/secret vào báo cáo.

### Unresolved questions

