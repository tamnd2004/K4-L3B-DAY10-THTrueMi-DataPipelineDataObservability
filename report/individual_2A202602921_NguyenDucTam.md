# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                                                                                          |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Đức Tâm                                                                                                                    |
| MSSV            | 2A202602921                                                                                                                       |
| Khóa/Lớp        | K4 — lớp L3B                                                                                                                      |
| Tên nhóm        | THTrueMi                                                                                                                          |
| Vai trò chính   | Observability & Integration owner: quality gate (GX 1.x + Freshness SLA), corruption/repair, orchestration hai pipeline và report |
| Repository      | https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability                                                  |
| Ngày hoàn thành | 2026-09-26                                                                                                                        |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable           | File/hàm phụ trách                                                                                            | Input nhận vào                                                                    | Output bàn giao                                                                                                                          | Trạng thái |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Quality gate & Freshness SLA | `src/observability/quality.py`: `run_data_quality_checks`, `evaluate_freshness_sla`, `build_freshness_report` | Clean DataFrame (schema của `cleaning.py`), `Settings`                            | `data/quality/<stage>_quality_report.json`, `data/quality/gx/<stage>_validation.json`, `data/quality/*freshness_report.json`             | Hoàn thành |
| Baseline orchestration       | `src/pipelines/phase1.py`: `run_phase1_pipeline`                                                              | Raw snapshot `data/raw/crossref_records.json`, test set `data/eval/test_set.json` | Clean CSV/JSON, collection `papers-baseline`, `baseline_metrics.json`, `baseline_answers.json`, `data/reports/phase1_report.md`          | Hoàn thành |
| Corruption suite             | `src/ingestion/corruption.py`: `corrupt_clean_dataframe`                                                      | `data/clean/papers_clean.json`                                                    | DataFrame bẩn (22 dòng), `data/results/corruption_log.json`                                                                              | Hoàn thành |
| Corruption flow & repair     | `src/pipelines/corruption_flow.py`: `run_corruption_flow_pipeline`, `repair_from_raw_snapshot`                | Artifact baseline của phase 1, raw snapshot                                       | `data/clean/papers_clean_{corrupted,repaired}.*`, collection `papers-corrupted` / `papers-repaired`, `{corrupted,repaired}_metrics.json` | Hoàn thành |
| Reporting                    | `src/observability/reporting.py`: `generate_phase1_report`, `generate_corruption_report`                      | Metrics, quality, freshness, corruption log, answers                              | `data/reports/phase1_report.md`, `data/reports/corruption_report.md`                                                                     | Hoàn thành |

Phần việc của tôi nằm ở cuối chuỗi. Tôi nhận raw records (ingestion), clean schema (cleaning) và test set (evaluation set) do các thành viên khác bàn giao, rồi ghép chúng thành hai pipeline chạy end-to-end. Mọi thay đổi đều đã được chạy và kiểm chứng bằng các lệnh ở mục 4.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                                             | Thành viên/module được hỗ trợ       | Kết quả                                                                                                                                                                             |
| --------------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Debug tích hợp: judge LLM âm thầm rơi về heuristic (chi tiết ở mục 6) | `src/retrieval/llm.py` (LLM router) | Không gửi `temperature` cho reasoning model OpenAI: fallback từ 10/10 câu ở lần chạy baseline đầu tiên giảm còn 0/10 ở cả ba trạng thái sau khi sửa (`data/results/*_answers.json`) |
| Refactor không đổi hành vi: tách `build_embedding_text`               | `src/ingestion/cleaning.py`         | Corruption dựng lại `text_for_embedding` đúng định dạng của cleaning; đã so khớp 24/24 dòng giống hệt bản trước refactor                                                            |
| Portability cho artifact                                              | `src/retrieval/index.py`            | Manifest embedding lưu `"persist_path": "data/chroma"` thay vì đường dẫn tuyệt đối của máy                                                                                          |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                                           | File/hàm/artifact liên quan                                          | Kết quả bàn giao                                                | Cách xác minh                                                                                                 |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Quality gate GX 1.x (ephemeral context) với 4 loại expectation (6 expectation) và Freshness SLA | `src/observability/quality.py`                                       | Baseline: PASS 6/6, FRESH (0/24 bài stale)                      | Lệnh kiểm tra bước 4 in `Quality check status = True`; `data/quality/baseline_quality_report.json`            |
| Baseline pipeline 6 bước                                                                        | `src/pipelines/phase1.py`                                            | Hit rate 1.0, token F1 1.0, judge accuracy 1.0, judge score 5.0 | `python script/run_phase1.py` (exit 0); `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| 6 kịch bản corruption có seed, log từng dòng                                                    | `src/ingestion/corruption.py`                                        | 24 → 22 dòng; 20/24 paper bị xóa hoặc sửa                       | Lệnh kiểm tra bước 7 in `Corrupted 22 dòng`; `data/results/corruption_log.json`                               |
| Corrupt → đo suy giảm → repair → đánh giá lại → so sánh 3 trạng thái                            | `src/pipelines/corruption_flow.py`, `src/observability/reporting.py` | Bảng 3 trạng thái bên dưới                                      | `python script/run_corruption_flow.py` (exit 0); `data/reports/corruption_report.md`                          |

Output cụ thể: bảng so sánh do `run_corruption_flow.py` in ra console và ghi vào `data/reports/corruption_report.md` (lần chạy ngày 2026-09-26):

| Metric / signal        |           Baseline |            Corrupted |           Repaired | Recovery |
| ---------------------- | -----------------: | -------------------: | -----------------: | -------: |
| Retrieval hit rate     |             1.0000 |               0.9000 |             1.0000 |     100% |
| Mean token F1          |             1.0000 |               0.9000 |             1.0000 |     100% |
| Judge accuracy         |             1.0000 |               0.9000 |             1.0000 |     100% |
| Mean judge score (1-5) |             5.0000 |               4.6000 |             5.0000 |     100% |
| Quality gate (GX)      |           PASS 6/6 |             FAIL 4/6 |           PASS 6/6 |          |
| Freshness SLA          |       FRESH (0/24) | STALE (8/22 = 36.4%) |       FRESH (0/24) |          |
| Content fingerprint    | `8b5b9cc5e8239eab` |   `7bf7953b239d393a` | `8b5b9cc5e8239eab` |          |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Khi dữ liệu hỏng, RAG agent không crash mà vẫn trả lời tự tin nhưng sai (silent failure). Phần của tôi giải quyết ba việc:

1. Chặn dữ liệu xấu trước khi vào vector DB bằng một quality gate có thể kiểm chứng.
2. Dựng thí nghiệm có kiểm soát để đo dữ liệu bẩn làm agent suy giảm bao nhiêu và gate phát hiện được những gì.
3. Phục hồi an toàn, lặp lại được và chứng minh được bằng số liệu.

### Cách triển khai

- **Quality gate** (`quality.py`):
  - Luồng GX 1.x: ephemeral context → pandas data source → dataframe asset → batch definition whole-dataframe → batch.
  - Suite gồm `ExpectTableRowCountToBeBetween(5, 5000)`, `ExpectColumnValuesToNotBeNull` cho `paper_id`, `title`, `text_for_embedding`, `ExpectColumnValuesToBeUnique(paper_id)` và `ExpectColumnValueLengthsToBeBetween(summary, min_value=30)`, validate bằng `batch.validate(suite)`.
  - Freshness: một bài là _stale_ khi `age_days > 180`; `is_fresh = False` khi tỉ lệ bài stale vượt 25%.
  - `success = gx_success AND is_fresh`.
  - Mỗi report ghi thêm fingerprint SHA-256 của cặp (`paper_id`, `text_for_embedding`) để đối chiếu version dữ liệu giữa các trạng thái.
- **Phase 1** (`phase1.py`), theo thứ tự:
  - Ingest: mặc định đọc raw snapshot để tái lập được; chỉ gọi Crossref khi đặt `REFRESH_SOURCE=1`.
  - Clean.
  - **Quality gate, đặt trước bước Index**: expectation fail thì dừng hẳn, không index dữ liệu hỏng; freshness fail chỉ in cảnh báo.
  - Index vào ChromaDB.
  - Test set: dùng lại file có sẵn để ba trạng thái cùng một bộ câu hỏi.
  - Evaluate, rồi sinh report.
- **Corruption** (`corruption.py`), seed cố định 42:
  - Bỏ 20% bài mới nhất (5 bài).
  - Xáo 19 dòng còn lại và chia thành 4 nhóm **không giao nhau**, để mỗi paper chỉ dính một loại lỗi và truy được lỗi nào gây ra suy giảm:
    - blank summary: 3 dòng;
    - inject noise: 3 dòng (chèn token rác sau khoảng 25% số từ; token không chứa `.!?` để không làm lệch ranh giới câu);
    - truncate title: 3 dòng (còn 7 ký tự);
    - stale date: 6 dòng (lùi ngày 365 ngày và cộng 365 vào `age_days`).
  - Cuối cùng nhân bản 3 dòng.
  - `text_for_embedding` được dựng lại bằng chính hàm `build_embedding_text` của cleaning. Log ghi giá trị before/after của từng dòng.
- **Corruption flow** (`corruption_flow.py`), theo thứ tự:
  - Index dữ liệu bẩn **mà không enforce gate** (mô phỏng một pipeline không có gate) để đo tác động.
  - `repair_from_raw_snapshot()` dựng lại clean data từ raw snapshot bất biến.
  - Dữ liệu sau repair phải qua gate mới được index vào `papers-repaired`.
  - Đánh giá lại trên đúng test set cũ (kiểm tra id câu hỏi của baseline khớp test set).
  - Sinh report 3 trạng thái.

### Input, output và contract

| Thành phần              | Mô tả                                                                                                                                                                                                                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input                   | Raw records `data/raw/crossref_records.json`; clean schema 16 cột (`paper_id`, `title`, `summary`, `published`, `age_days`, `text_for_embedding`, ...); test set 10 câu `data/eval/test_set.json`                                                                                         |
| Output                  | Quality dict `{success, gx_success, statistics, expectations, freshness, dataset}`; DataFrame bẩn và `corruption_log.json`; metrics/answers của 3 trạng thái; 2 report markdown                                                                                                           |
| Module phụ thuộc        | `ingestion/crossref.py`, `ingestion/cleaning.py`, `evaluation/testset.py`, `evaluation/metrics.py`, `retrieval/index.py`                                                                                                                                                                  |
| Module sử dụng output   | `script/run_phase1.py`, `script/run_corruption_flow.py`; `reporting.py` đọc quality/freshness/log; group report                                                                                                                                                                           |
| Điều kiện lỗi cần xử lý | Thiếu artifact baseline thì báo chạy phase 1 trước; baseline được đánh giá trên test set khác thì dừng; baseline hoặc dữ liệu repair không qua GX thì không index; test set trỏ tới paper không còn trong corpus thì build lại; GX gặp cột bị thiếu thì trả `success=False` thay vì crash |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Tín hiệu hoàn thành: Quality check status =', res['success'])"
python script/run_phase1.py
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:**
  - Quality check trả `True`.
  - Phase 1 sinh clean CSV, baseline metrics và `phase1_report.md`.
  - Corruption log ghi đủ 6 kịch bản.
  - Console in bảng 3 trạng thái và sinh `corruption_report.md`.
- **Kết quả thực tế:**
  - `Quality check status = True`.
  - Phase 1 exit 0 (48 giây), hit rate 1.0, token F1 1.0.
  - Bước 7 in `Corrupted 22 dòng`.
  - Corruption flow exit 0 (64 giây), bảng in ra cho hit rate và token F1 là Baseline 1.0 → Corrupted 0.9 → Repaired 1.0.
- **Artifact/log:** `data/quality/`, `data/results/`, `data/results/corruption_log.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau khi bị làm bẩn, dữ liệu mất những thông tin không thể suy ngược: 5 bài bị xóa, 3 tiêu đề chỉ còn 7 ký tự (`Integra`, `JADE-Pl`, `A Found`), 6 ngày xuất bản bị lùi 365 ngày. Cần chọn cách repair.
- **Các phương án đã cân nhắc:**
  1. Vá tại chỗ trên bản bẩn: dedupe, bỏ dòng có summary rỗng, lọc token rác bằng regex.
  2. Rollback về artifact clean gần nhất (`papers_clean.json`).
  3. Dựng lại clean data từ raw snapshot bất biến `data/raw/crossref_records.json` bằng chính hàm cleaning.
- **Phương án đã chọn:** phương án 3, tức hàm `repair_from_raw_snapshot()`.
- **Lý do:**
  - Phương án 1 không khôi phục được giá trị đã mất (tiêu đề bị cắt, ngày bị lùi, dòng bị xóa) và dễ che lỗi thay vì sửa lỗi.
  - Phương án 2 chỉ an toàn nếu artifact clean chưa bị ghi đè, trong khi trong luồng thật chính artifact clean là nơi dễ hỏng nhất.
  - Raw snapshot là nguồn sự thật được lưu để giữ data lineage, và cleaning là hàm tất định. Vì vậy repair **idempotent**: chạy lại bao nhiêu lần cũng ra cùng một corpus, với chi phí chỉ là dựng lại 24 dòng.
- **Bằng chứng quyết định phù hợp:**
  - Fingerprint nội dung sau repair là `8b5b9cc5e8239eab`, trùng khớp baseline; bản bẩn là `7bf7953b239d393a`.
  - Dữ liệu repair đạt PASS 6/6 và FRESH 0/24.
  - Cả 4 metric phục hồi 100% (`data/reports/corruption_report.md`).
  - Chạy corruption flow hai lần cho cùng kết quả.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lần chạy phase 1 đầu tiên báo `judge_accuracy=1.0` và console không có lỗi nào. Nhưng cả 10 câu trong `baseline_answers.json` đều có `reasoning = "Fallback heuristic judge used because the LLM evaluator was unavailable."`. Gọi trực tiếp judge thì nhận lỗi: `openai.BadRequestError: Error code: 400 - {'error': {'message': "Unsupported value: 'temperature' does not support 0.0 with this model. Only the default (1) value is supported.", 'type': 'invalid_request_error', 'param': 'temperature', 'code': 'unsupported_value'}}`
- **Lệnh hoặc bước tái hiện:**
  1. Chạy `python script/run_phase1.py`.
  2. Kiểm tra trường `judge.reasoning` trong `data/results/baseline_answers.json`.
  3. Gọi `build_llm(settings, temperature=0.0).with_structured_output(JudgeVerdict).invoke(...)` với `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-6-luna`.
- **Nguyên nhân gốc:**
  - `_judge_answer` gọi `build_llm(temperature=0.0)`.
  - `gpt-6-luna` là reasoning model, chỉ nhận temperature mặc định.
  - `langchain-openai` 1.6.6 chỉ tự bỏ temperature cho họ model `gpt-5`, không áp dụng cho `gpt-6`.
  - Khối `except Exception` trong `_judge_answer` nuốt lỗi 400 và âm thầm chuyển sang heuristic chấm theo token F1.
- **Cách xử lý:**
  - Thêm hàm `_openai_supports_temperature()` trong `src/retrieval/llm.py`: với model OpenAI họ `o1`, `o3`, `o4`, `gpt-5`, `gpt-6` (trừ bản `-chat`) thì không gửi `temperature`.
  - Report in thêm dòng "Judge mode" để luôn biết metric được chấm bởi LLM hay bởi heuristic.
- **Cách xác minh sau khi sửa:**
  - Gọi trực tiếp judge nhận được `score=1, correct=False, reasoning="The model gives 2025-06-15, but the reference date is 2026-06-15; the year is incorrect."`.
  - Chạy lại hai pipeline: số câu fallback là 0/10 ở cả baseline, corrupted và repaired.
- **Điều học được:** Chính code evaluation cũng có thể silent failure: metric trông hoàn hảo nhưng thực ra do một judge khác chấm. Metric phải đi kèm thông tin về cách nó được tạo ra.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - `fetch_source_records` gọi Crossref `/works` với query về agentic RAG, filter lấy bài 180 ngày gần nhất và phải có abstract, tối đa 24 record.
   - Hàm có retry/backoff cho lỗi 429/5xx và fallback về snapshot local; lưu cả raw response lẫn raw records để giữ lineage.
   - `build_clean_dataframe` bỏ record thiếu DOI/title/abstract/ngày xuất bản, chuẩn hóa khoảng trắng, dedupe theo `paper_id` (DOI), tính `age_days` và ghép `text_for_embedding` gồm 5 phần.
   - Dữ liệu phải qua quality gate rồi mới được embed bằng `all-MiniLM-L6-v2` (vector chuẩn hóa) và nạp vào collection ChromaDB (HNSW cosine) kèm metadata.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Bộ gồm 10 câu hỏi: 3 summary, 3 authors, 2 date, 2 categories. Mỗi câu có `ground_truth` và `ground_truth_doc_ids` (DOI).
   - Retrieval hit nghĩa là DOI đúng nằm trong top-4 kết quả.
   - Chất lượng câu trả lời đo bằng token F1 (độ trùng token với ground truth) và LLM judge (điểm 1–5, đúng/sai).
3. **Quality checks khác freshness monitoring ở điểm nào?**
   - Quality checks là ràng buộc tĩnh của data contract trên snapshot hiện tại: số dòng, không null, không trùng id, độ dài summary. Kết quả đúng/sai không phụ thuộc thời điểm chạy.
   - Freshness là SLA theo thời gian trên phân bố tuổi bài báo. Dữ liệu có thể hợp lệ nhưng đã cũ, và cùng một snapshot sẽ hết fresh khi thời gian trôi qua.
   - Trong lab, GX bắt được duplicate và summary rỗng, còn stale date thì chỉ freshness bắt được.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?** Để biến duy nhất thay đổi là dữ liệu; khi đó mọi chênh lệch metric mới quy được cho corruption hoặc repair. Corruption flow kiểm tra id câu hỏi của baseline khớp test set trước khi so sánh.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - `repaired_quality_report.json` đạt PASS 6/6 và FRESH 0/24.
   - Fingerprint của dữ liệu repair trùng baseline.
   - `repaired_metrics.json` bằng baseline.
   - Cột Recovery trong `corruption_report.md` đạt 100%.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal        |   Baseline |          Corrupted |   Repaired | Nhận xét của cá nhân                                                                                   |
| -------------------- | ---------: | -----------------: | ---------: | ------------------------------------------------------------------------------------------------------ |
| `retrieval_hit_rate` |     1.0000 |             0.9000 |     1.0000 | `eval_009`: bài gốc bị drop; bản sao của một bài khác chiếm 2/4 vị trí top-k                           |
| `mean_token_f1`      |     1.0000 |             0.9000 |     1.0000 | `eval_003`: summary bị xóa trắng nên câu trả lời rỗng, F1 = 0                                          |
| `judge_accuracy`     |     1.0000 |             0.9000 |     1.0000 | Chỉ `eval_003` bị chấm sai; `eval_009` vẫn "đúng" vì bài bị lấy nhầm có cùng category `posted-content` |
| `mean_judge_score`   |     5.0000 |             4.6000 |     5.0000 | `eval_003` bị chấm 1 điểm                                                                              |
| Quality checks       |   PASS 6/6 |           FAIL 4/6 |   PASS 6/6 | Fail `unique(paper_id)` (6 unexpected) và `summary` ≥ 30 ký tự (3 unexpected)                          |
| Freshness status     | FRESH 0/24 | STALE 8/22 (36.4%) | FRESH 0/24 | 6 dòng bị lùi ngày + 2 bản sao của dòng stale, vượt ngưỡng 25%                                         |

### Kết luận từ số liệu

1. `blank_summary` (3 dòng) làm GX `expect_column_value_lengths_to_be_between(summary)` FAIL (3 unexpected). Hệ quả là `eval_003` trả lời rỗng: token F1 1.00 → 0.00, judge 5 → 1, kéo `mean_token_f1` và `judge_accuracy` từ 1.0 xuống 0.9.
2. `repair_from_raw_snapshot()` đưa gate về PASS 6/6 và FRESH, fingerprint trùng baseline, nên cả 4 metric trở về đúng mức baseline (recovery 100%).

**Corruption nào ảnh hưởng rõ nhất và vì sao?**

- `blank_summary` là loại duy nhất làm giảm metric câu trả lời, vì câu hỏi summary lấy câu đầu của trường `summary` làm đáp án.
- `drop_latest_records` làm giảm retrieval hit rate (`eval_009` bị miss) nhưng **không** bị gate phát hiện, vì 22 dòng vẫn nằm trong khoảng 5–5000.
- Đây là silent failure thật: agent vẫn trả lời `posted-content` và được judge chấm 5/5, nhưng dựa trên một bài khác. Nói cách khác là đúng đáp án nhưng sai bằng chứng.

**Kết quả nào khác với kỳ vọng ban đầu?**

- Tôi kỳ vọng metric sụt mạnh vì 20/24 paper (83%) bị xóa hoặc sửa, nhưng thực tế chỉ 2/10 câu hỏi suy giảm.
- Bảng per-question trong `corruption_report.md` cho thấy nguyên nhân là loại lỗi không trùng với loại câu hỏi:
  - noise rơi vào 3 câu authors/date, mà đáp án của các câu này không lấy từ summary;
  - stale date rơi vào câu authors/categories;
  - `truncate_title` (`eval_001`) không làm hỏng retrieval, vì semantic search vẫn tìm đúng bài ở top-1 nhờ summary và authors còn nguyên.
- Vậy metric của agent phản ánh thấp hơn mức hư hại thật của dữ liệu. Trong khi đó freshness vẫn báo STALE dù không câu hỏi date nào bị ảnh hưởng: observability ở tầng dữ liệu bắt được những gì test set không phủ tới.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Giữ raw snapshot bất biến và cleaning tất định thì repair trở thành rebuild idempotent. Fingerprint nội dung chứng minh repair đưa dữ liệu về đúng trạng thái baseline, chứ không chỉ là "metric trông ổn".
2. **Về data quality/observability:** Gate chỉ bắt được những gì nó được thiết kế để bắt: 3/6 loại lỗi (drop 20%, noise, cắt tiêu đề) lọt qua. Ngay cả code evaluation cũng có thể silent failure (judge fallback), nên metric cần kèm thông tin về cách nó được tạo ra.
3. **Về ảnh hưởng của dữ liệu đến RAG agent:** Mức suy giảm nhìn thấy được phụ thuộc vào độ phủ của test set, và agent có thể trả lời đúng từ sai tài liệu. Vì vậy cần đo retrieval metric song song với answer metric.

### Nếu có thêm thời gian

Tôi sẽ bổ sung expectation cho 3 loại lỗi đang silent:

- `ExpectColumnValueLengthsToBeBetween(title, min_value=15)` cho tiêu đề bị cắt.
- Kiểm tra số dòng tương đối so với lần chạy trước (ví dụ ≥ 90% baseline) cho drop latest.
- Kiểm tra tỉ lệ token rác trong `summary` (regex bắt ký tự `#@$%&*~^` trộn chữ số) cho noise.

Cách đo: chạy lại `run_corruption_flow.py`. Bảng "Corruption scenarios and detection" phải tăng từ 3/6 lên 6/6 DETECTED, trong khi baseline vẫn PASS.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Tâm
**Ngày xác nhận:** 2026-09-26
