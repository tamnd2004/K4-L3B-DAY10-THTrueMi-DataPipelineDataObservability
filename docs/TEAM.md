# Danh sách thành viên và phân công nhóm

- **Tên nhóm:** THTrueMi
- **Khóa/Lớp:** K4-L3B-DAY10
- **Repository:** https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability
- **Ngày xác nhận:** 2026-09-26

## Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò và phạm vi | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Nguyễn Thị Hải Mi | 2A202602667 | haimi612003@gmail.com  | Raw Data Ingestion & Data Lineage; hỗ trợ dashboard | [`individual-2A202602667-NguyenThiHaiMi.md`](../report/individual-2A202602667-NguyenThiHaiMi.md) |
| 2 | Mai Huy Hoàng | 2A202602685 | huyhoangg1706@gmail.com  | Data Cleaning & Pre-embed Modeling | [`individual_2A202602685_MaiHuyHoang.md`](../report/individual_2A202602685_MaiHuyHoang.md) |
| 3 | Trần Nguyễn Trí Dũng | 2A202602784 | trantridung38@gmail.com | Benchmark Evaluation Test Set; tích hợp evaluation | [`individual_2A202602784_TranNguyenTriDung.md`](../report/individual_2A202602784_TranNguyenTriDung.md) |
| 4 | Nguyễn Đức Tâm | 2A202602921 | tamnd04@gmail.com | Quality Gate, Freshness, Corruption/Repair & Pipeline Integration | [`individual_2A202602921_NguyenDucTam.md`](../report/individual_2A202602921_NguyenDucTam.md) |

## Phân công và bằng chứng bàn giao

### Nguyễn Thị Hải Mi — Raw Data Ingestion & Lineage

- Hoàn thiện retry/backoff cho Crossref, fallback về snapshot khi API lỗi và bảo vệ snapshot chỉ sau khi response hợp lệ.
- Parse DOI, title, abstract, authors, categories và ngày xuất bản thành `PaperRecord` trong `src/ingestion/crossref.py`.
- Bàn giao `data/raw/crossref_response.json` và `data/raw/crossref_records.json` gồm 24 records; raw snapshot được dùng làm nguồn repair.
- Hỗ trợ xây dashboard đọc artifacts thật trong `ui/dashboard.html` và `script/build_dashboard.py`.

### Mai Huy Hoàng — Data Cleaning & Pre-embed Modeling

- Hoàn thiện `build_clean_dataframe()` trong `src/ingestion/cleaning.py`.
- Chuẩn hóa whitespace/text, tính `age_days`, khử trùng lặp theo `paper_id` và tạo `text_for_embedding` từ title/authors/published/categories/summary.
- Bàn giao `data/clean/papers_clean.csv` và `.json` với 24 dòng, 24 `paper_id` duy nhất.
- Kiểm tra tương thích giữa schema clean, embedding/index và corruption flow.

### Trần Nguyễn Trí Dũng — Benchmark Evaluation Test Set

- Hoàn thiện `build_test_set()` trong `src/evaluation/testset.py`.
- Sinh 10 câu hỏi ground truth, phủ 4 loại `summary`, `authors`, `date`, `categories`; mỗi câu giữ DOI trong `ground_truth_doc_ids`.
- Bàn giao `data/eval/test_set.json` và hỗ trợ xác minh metrics, cùng test set cho baseline/corrupted/repaired.
- Đóng góp phân tích hiện tượng retrieval miss không nhất thiết làm answer sai và giới hạn của heuristic/LLM judge.

### Nguyễn Đức Tâm — Observability, Corruption/Repair & Integration

- Thiết lập Great Expectations 1.x Ephemeral Context, 6 expectations thực tế (row count, not-null, unique, summary length) và Freshness SLA 180 ngày/25%.
- Điều phối `script/run_phase1.py`, `script/run_corruption_flow.py`, quality reports và comparison report.
- Thực hiện 6 kịch bản corruption với seed 42, repair idempotent từ raw snapshot và tái đánh giá 3 trạng thái.
- Bàn giao `data/quality/`, `data/results/`, `data/reports/phase1_report.md` và `data/reports/corruption_report.md`.

## Kết quả nhóm đã xác nhận

- Baseline: 24 dòng, 24 IDs duy nhất, GX 6/6, Freshness 0/24 stale, fingerprint `8b5b9cc5e8239eab`.
- Corrupted: 22 dòng, 19 IDs duy nhất, GX 4/6, Freshness 8/22 stale (36.4%), fingerprint `7bf7953b239d393a`.
- Repaired: 24 dòng, GX 6/6, Freshness 0/24 stale, fingerprint trùng baseline.
- Metrics `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`: `1.0 → 0.9 → 1.0`; `mean_judge_score`: `5.0 → 4.6 → 5.0`.

Mỗi thành viên chịu trách nhiệm kiểm tra và ký xác nhận trong báo cáo cá nhân tương ứng. Các trải nghiệm cá nhân, khó khăn thực tế và ngày xác nhận được giữ ở từng file cá nhân để tránh ghi nhận đóng góp không có bằng chứng.
