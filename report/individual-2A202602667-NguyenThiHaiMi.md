# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                          |
| ------------------ | ---------------------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Thị Hải Mi                                                                |
| MSSV               | 2A202602667                                                                        |
| Khóa/Lớp         | K4                                                                                 |
| Tên nhóm         | THTrueMi                                                                           |
| Vai trò chính    | Source owner — Raw Data Ingestion & Lineage (Bước 2)                            |
| Repository         | https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26                                                                         |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                  | File/hàm phụ trách                                                     | Input nhận vào                                                                    | Output bàn giao                                              | Trạng thái |
| ------------------------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------ |
| Thu thập dữ liệu Crossref có retry + fallback | `src/ingestion/crossref.py` — `fetch_source_records`, `_request_crossref` | `Settings` (`source_query`, `source_filter`, `max_results`, `paths`)                | `data/raw/crossref_response.json` (JSON gốc, không chỉnh sửa) | Hoàn thành  |
| Bóc tách & chuẩn hóa payload         | `src/ingestion/crossref.py` — `parse_crossref_payload`                   | Payload JSON `/works` của Crossref                                                  | `list[PaperRecord]` + `data/raw/crossref_records.json`         | Hoàn thành  |
| Đọc lại raw records cho các bước sau | `src/ingestion/crossref.py` — `load_raw_records`                         | `data/raw/crossref_records.json`                                                    | `list[PaperRecord]` cho `cleaning.py`                          | Hoàn thành  |

Output của tôi là đầu vào trực tiếp của `build_clean_dataframe` (`cleaning.py`) và gián tiếp của `testset.py` (ground-truth doc IDs là DOI do tôi bóc tách). `load_raw_records` được dùng ở hai chỗ quan trọng: `pipelines/phase1.py` mặc định đọc raw snapshot để kết quả tái lập được (chỉ gọi Crossref live khi `REFRESH_SOURCE=1`), và `repair_from_raw_snapshot` trong `pipelines/corruption_flow.py` dựng lại dữ liệu sạch từ `data/raw/crossref_records.json`.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                          | Thành viên/module được hỗ trợ | Kết quả                                                                                                   |
| ----------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Kiểm tra tích hợp raw records với module cleaning | `src/ingestion/cleaning.py`          | Chạy lệnh kiểm tra Bước 3 trên raw data của tôi → `Clean thành công 24 dòng`, không mất bản ghi nào. |
| Xây dashboard observability (bonus B1)              | Cả nhóm; đọc artifact của `quality.py`, `corruption_flow.py`, `metrics.py` | `ui/dashboard.html` + `script/build_dashboard.py` (commit `6d6ddf0`): pipeline 7 bước, quality gate, histogram tuổi bài báo với SLA 180 ngày, cây 6 kịch bản corruption, fingerprint lineage và tác động từng câu hỏi qua 3 trạng thái. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                     | File/hàm/artifact liên quan          | Kết quả bàn giao                               | Cách xác minh                                                        |
| ---------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------- |
| Gọi Crossref REST API, retry 429/5xx, fallback snapshot local               | `fetch_source_records`, `_request_crossref` | 24 bài báo live, lưu `crossref_response.json` | Lệnh kiểm tra Bước 2 → `Đã tải 24 bài báo`                          |
| Chuẩn hóa DOI, title, abstract (bỏ thẻ `<jats:p>`), authors, categories, ngày | `parse_crossref_payload`              | `crossref_records.json` (24 records)             | Parse snapshot gốc của đề → khớp 100% với `crossref_records.json` mẫu |
| Kiểm thử nhánh fallback khi mất mạng                                       | `fetch_source_records`                 | Pipeline không gián đoạn khi API lỗi            | Trỏ API về cổng đóng → 3 lần thử thất bại → đọc snapshot → 24 records |
| Commit & push code + raw artifacts                                           | commit `582fb95`                       | Raw data lineage có trên repo nhóm               | `git log` trên `main`                                                |
| Raw snapshot làm nguồn cho Repair                                          | `data/raw/crossref_records.json`, `load_raw_records` | Dữ liệu Repaired giống hệt Baseline            | Fingerprint `8b5b9cc5e8239eab` ở cả `baseline_quality_report.json` và `repaired_quality_report.json` |
| Dashboard observability                                                     | `ui/dashboard.html`, `script/build_dashboard.py` | Trang HTML tự chứa, nhúng số liệu thật từ `data/` | `python script/build_dashboard.py` → `Dashboard updated ... (31 KB data)` |

Output cụ thể: `data/raw/crossref_records.json` gồm **24 bài báo** xuất bản trong khoảng **2026-04-01 → 2026-09-15** (trong cửa sổ freshness 180 ngày), summary dài 826–3814 ký tự, không bản ghi nào thiếu tác giả. Quality gate chạy trên dữ liệu này đạt **6/6 expectations**, `stale_rows = 0`, `is_fresh = true` (`data/quality/baseline_quality_report.json`). Cả 10 câu hỏi trong `data/eval/test_set.json` đều dùng `ground_truth_doc_ids` là DOI lấy từ records của tôi. Sau corruption, bước Repair đọc lại chính file này và cho ra đúng fingerprint của Baseline, nên toàn bộ metric được khôi phục 100%.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một nguồn dữ liệu đầu vào **ổn định và truy vết được**. Crossref là nguồn sống bên ngoài: có thể lỗi mạng, bị rate limit (429) hoặc quá tải (503), và trả về JSON lồng nhiều tầng có thẻ JATS/HTML trong abstract. Phần của tôi phải (1) lấy được dữ liệu dù API không ổn định, (2) giữ nguyên bản gốc làm lineage anchor cho bước Repair, (3) bàn giao schema `PaperRecord` sạch, nhất quán cho các bước sau.

### Cách triển khai

- **Gọi API có retry:** tối đa 3 lần, chỉ thử lại với lỗi tạm thời (429, 500, 502, 503, 504) hoặc lỗi kết nối; tôn trọng header `Retry-After` nếu có, nếu không thì exponential backoff (2s, 4s). Lỗi không tạm thời (vd 400) dừng ngay, không thử lại vô ích.
- **Fallback:** nếu hết lượt thử hoặc response parse ra 0 record hợp lệ → đọc `data/raw/crossref_response.json` có sẵn; nếu cả snapshot cũng không có thì raise lỗi rõ ràng thay vì trả về list rỗng.
- **Bảo vệ snapshot:** chỉ ghi đè `crossref_response.json` **sau khi** response live đã được validate và parse thành công, để file fallback luôn là bản tốt gần nhất.
- **Parse & chuẩn hóa:**
  - Title/abstract: bỏ thẻ bằng regex `<[^>]+>`, decode HTML entity, gom khoảng trắng.
  - DOI: `strip().lower()` làm `paper_id`; khử trùng lặp theo DOI.
  - Bỏ record thiếu DOI, title hoặc abstract (không có abstract thì không có gì để embed).
  - Authors: ghép `given + family`; tác giả là tổ chức thì dùng `name`.
  - Ngày: `date-parts` → `YYYY-MM-DD`, thử lần lượt `published` → `published-online` → `published-print` → `issued` → `created`; thiếu tháng/ngày thì điền `01`.
  - Categories: dùng `subject`, nếu rỗng thì fallback sang `type` (xem mục 6).
  - `pdf_url`: link có `content-type = application/pdf` nếu có, ngược lại dùng URL DOI.

### Input, output và contract

| Thành phần                   | Mô tả                                                                                                                                                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input                          | `Settings`: `source_query="agentic retrieval augmented generation large language model"`, `source_filter="from-pub-date:<hôm nay-180d>,has-abstract:true"`, `max_results=24` |
| Output                         | `list[PaperRecord]` (`paper_id, title, summary, authors, categories, primary_category, published, updated, abs_url, pdf_url, comment`); 2 file `data/raw/*.json` |
| Module phụ thuộc             | `core/config.py` (Settings, Paths), `core/utils.py` (`normalize_whitespace`, `read_json`, `write_json`)                                                |
| Module sử dụng output        | `ingestion/cleaning.py`, `evaluation/testset.py`, luồng Repair trong `pipelines/`                                                                     |
| Điều kiện lỗi cần xử lý | Mất mạng/timeout; 429/5xx; response không có `items`; item thiếu DOI/title/abstract; DOI trùng; thiếu `subject`; ngày thiếu tháng/ngày; không có snapshot khi API lỗi |

### Cách xác minh

```bash
# 1. Lệnh kiểm tra chính thức Bước 2 (gọi API live)
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# 2. Parser tái tạo đúng records mẫu của đề (chạy trước khi snapshot bị ghi đè)
python -c "from dataclasses import asdict; from core.utils import read_json; from ingestion.crossref import parse_crossref_payload; from core.config import load_settings; s=load_settings(); print([asdict(r) for r in parse_crossref_payload(read_json(s.paths.raw_api_response))]==read_json(s.paths.raw_records_json))"

# 3. Giả lập mất mạng để kiểm tra fallback
python -c "import ingestion.crossref as c; c.CROSSREF_WORKS_URL='http://127.0.0.1:9/works'; c.time.sleep=lambda s: None; from core.config import load_settings; print(len(c.fetch_source_records(load_settings())))"
```

- **Kết quả mong đợi:** (1) tải đủ 24 bài; (2) `True`; (3) log 3 lần thử thất bại rồi fallback, vẫn trả về 24 records.
- **Kết quả thực tế:** (1) `[crossref] Fetched 24 records from Crossref REST API` / `Tín hiệu hoàn thành: Đã tải 24 bài báo`; (2) `True`, 24 records; (3) `Connection refused` ×3 → `fallback to local snapshot` → `24`.
- **Artifact/log:** `data/raw/crossref_response.json` (`total-results: 103868`, 24 items), `data/raw/crossref_records.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `crossref_response.json` vừa là nơi lưu JSON gốc mới nhất, vừa là snapshot fallback khi API lỗi. Nếu ghi đè sai lúc, pipeline có thể mất luôn phương án dự phòng.
- **Các phương án đã cân nhắc:**
  1. Luôn ghi response vào file ngay khi nhận được (đơn giản nhất).
  2. Không bao giờ gọi API, chỉ đọc snapshot (ổn định tuyệt đối nhưng dữ liệu không bao giờ mới).
  3. Gọi API, validate + parse thành công rồi mới ghi đè snapshot; lỗi thì fallback đọc snapshot cũ.
- **Phương án đã chọn:** Phương án 3.
- **Lý do:** Phương án 1 có rủi ro: một response hỏng (vd 200 nhưng `items` rỗng) sẽ ghi đè snapshot tốt → lần sau mất mạng thì fallback cũng hỏng — đúng kiểu silent corruption mà bài lab muốn tránh. Phương án 2 đi ngược mục tiêu freshness. Phương án 3 giữ được dữ liệu mới khi API khỏe và luôn có "last known good" khi API lỗi, đổi lại thêm vài dòng validate.
- **Bằng chứng quyết định phù hợp:** Ở test fallback (lệnh 3 mục 4), sau khi API lỗi, `git status` cho thấy `data/raw/` **không bị thay đổi** — snapshot được giữ nguyên, pipeline vẫn trả về 24 records.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi probe API live, cả 24 item đều có `subject None` — trường `categories` sẽ rỗng cho toàn bộ dữ liệu, trong khi snapshot mẫu của đề có `subject` đầy đủ.
- **Lệnh hoặc bước tái hiện:** Gọi `GET https://api.crossref.org/works?query=...&filter=from-pub-date:...,has-abstract:true&rows=24` và in `item.get("subject")` cho từng item.
- **Nguyên nhân gốc:** Crossref live hiện gần như không còn trả trường `subject` cho các bản ghi mới; snapshot mẫu là dữ liệu dựng sẵn nên vẫn có. Code chỉ đọc `subject` sẽ chạy "thành công" nhưng sinh `categories=[]`, `primary_category=""` — lỗi âm thầm làm hỏng câu hỏi loại *categories* trong test set và metadata `categories_joined` khi retrieval.
- **Cách xử lý:** Nếu `subject` rỗng, fallback sang trường `type` của Crossref (`journal-article`, `posted-content`, `report`...) làm `categories` / `primary_category`.
- **Cách xác minh sau khi sửa:** Thống kê `crossref_records.json`: `journal-article: 15, posted-content: 8, report: 1` — không còn record nào có `primary_category` rỗng. Test set của nhóm có 2 câu hỏi loại `categories` (`eval_009`, `eval_010`) dựa trên trường này.
- **Điều học được:** Snapshot mẫu không đại diện đầy đủ cho nguồn sống. Phải probe dữ liệu thật trước khi tin schema, và coi "trường rỗng hàng loạt" là tín hiệu lỗi chứ không phải dữ liệu hợp lệ.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index:** `fetch_source_records` gọi Crossref (hoặc fallback snapshot), lưu JSON gốc và `PaperRecord` vào `data/raw/`. `cleaning.py` chuẩn hóa text, parse ngày, tính `age_days`, khử trùng `paper_id`, tạo `text_for_embedding` (Title/Authors/Published/Categories/Summary) → `data/clean/`. Quality gate (Great Expectations) kiểm tra bảng sạch. Sau đó `text_for_embedding` được embed bằng MiniLM (`all-MiniLM-L6-v2`) và nạp vào ChromaDB kèm metadata (`authors_joined`, `categories_joined`...).
2. **Evaluation set:** mỗi câu hỏi trong `test_set.json` có `ground_truth` (câu trả lời đúng) và `ground_truth_doc_ids` (DOI của bài chứa đáp án). `retrieval_hit_rate` đo tỉ lệ câu hỏi mà top-k tài liệu truy xuất có chứa DOI đúng → đo chất lượng retrieval. `mean_token_f1`, `judge_accuracy`, `mean_judge_score` so câu trả lời của agent với `ground_truth` → đo chất lượng answer.
3. **Quality checks vs freshness:** quality checks kiểm tra *tính đúng đắn về cấu trúc/nội dung* tại một thời điểm (số dòng, not-null, unique `paper_id`, độ dài summary). Freshness kiểm tra *dữ liệu còn mới không* theo thời gian: dựa trên `age_days` so với ngưỡng 180 ngày và tỉ lệ dòng stale. Dữ liệu có thể pass hết quality checks nhưng vẫn stale (vd corruption "lùi ngày 365 ngày").
4. **Cùng test set:** để thay đổi metric chỉ đến từ thay đổi dữ liệu (baseline/corrupted/repaired), không phải do câu hỏi dễ/khó khác nhau. Đây là nguyên tắc biến kiểm soát — đổi test set thì so sánh mất ý nghĩa.
5. **Repair thành công khi:** dữ liệu được dựng lại từ raw snapshot (`data/raw/crossref_records.json`), `repaired_quality_report.json` pass lại 6/6 expectations, freshness `is_fresh = true`, và các metric trong `repaired_metrics.json` quay về bằng baseline trên cùng test set. Bằng chứng mạnh nhất là fingerprint nội dung: Repaired `8b5b9cc5e8239eab` trùng Baseline, trong khi Corrupted là `7bf7953b239d393a`. Nhờ vậy repair là idempotent: chạy lại bao nhiêu lần cũng ra cùng một dữ liệu.

## 8. Phân tích kết quả

Nguồn số liệu: `data/results/{baseline,corrupted,repaired}_metrics.json`, `data/quality/*_quality_report.json`, `data/results/corruption_log.json` và `data/reports/corruption_report.md`. Cả 3 trạng thái dùng cùng test set 10 câu hỏi và LLM judge cho cả 10/10 câu trả lời.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.90 |     1.00 | Chỉ `eval_009` bị miss: bài gốc `10.21203/rs.3.rs-10349437/v1` bị `drop_latest_records` xóa, và bản trùng `10.21203/rs.3.rs-10423755/v1` chiếm 2/4 chỗ top-k. |
| `mean_token_f1`      |     1.00 |      0.90 |     1.00 | Giảm hoàn toàn do `eval_003`: summary bị xóa trắng nên agent trả lời rỗng, F1 1.00 → 0.00. |
| `judge_accuracy`     |     1.00 |      0.90 |     1.00 | Chỉ `eval_003` sai. `eval_009` miss retrieval nhưng vẫn được chấm đúng (xem phần "khác kỳ vọng"). |
| `mean_judge_score`   |      5.0 |       4.6 |      5.0 | `eval_003` từ 5 xuống 1 kéo trung bình giảm 0.4. |
| Quality checks         | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Fail ở `paper_id` unique (6 dòng: 3 id bị nhân đôi, tính cả 2 bản) và `summary ≥ 30 ký tự` (3 dòng rỗng). |
| Freshness status       | FRESH, 0/24 stale | STALE, 8/22 stale (36.4%) | FRESH, 0/24 stale | 8 dòng stale = 6 dòng bị lùi ngày + 2 bản trùng của chính các dòng đó; vượt ngưỡng 25%. |
| Rows / unique `paper_id` | 24 / 24 | 22 / 19 | 24 / 24 | 24 − 5 dòng bị bỏ + 3 dòng nhân đôi = 22 dòng. |
| Content fingerprint    | `8b5b9cc5e8239eab` | `7bf7953b239d393a` | `8b5b9cc5e8239eab` | Repaired trùng Baseline: raw snapshot của tôi là nguồn phục hồi chính xác. |

### Kết luận từ số liệu

1. **Blank summary** (3 dòng) → gate `summary ≥ 30 ký tự` FAIL (3 dòng lỗi) → `eval_003` vẫn truy xuất đúng tài liệu nhưng trả lời rỗng: judge 5 → 1, token F1 1.00 → 0.00, kéo `mean_token_f1` và `judge_accuracy` xuống 0.90. **Duplicate rows + drop latest** → gate unique FAIL (6 dòng), nhưng row count vẫn PASS (22 dòng) → `eval_009` mất tài liệu gốc, `retrieval_hit_rate` 1.00 → 0.90.
2. **Repair** đọc lại `data/raw/crossref_records.json` → gate PASS 6/6, freshness FRESH 0/24, fingerprint trùng Baseline → cả 4 metric quay về đúng Baseline, tức khôi phục 100% `(Repaired − Corrupted) / (Baseline − Corrupted)`.

Corruption nào ảnh hưởng rõ nhất và vì sao?

**Blank summary** ảnh hưởng rõ nhất: đây là lỗi duy nhất làm agent trả lời sai (`eval_003`, judge 5 → 1). Retrieval vẫn tìm đúng bài vì title và metadata còn nguyên trong `text_for_embedding`, nhưng phần nội dung chứa đáp án đã mất, nên agent không có gì để trả lời. Điều này cho thấy retrieval hit không đủ để đánh giá; phải đo cả chất lượng câu trả lời. **Duplicate rows** nguy hiểm theo cách khác: một bài trùng chiếm 2/4 chỗ top-k ở cả `eval_007` và `eval_009`, làm giảm độ đa dạng ngữ cảnh.

Kết quả nào khác với kỳ vọng ban đầu?

- **`eval_009` miss retrieval nhưng vẫn được chấm đúng.** Giả thuyết: câu hỏi loại *categories* có đáp án `posted-content`, mà vì Crossref live không trả `subject`, tôi đã fallback sang `type` (mục 6). Trường này chỉ có 3 giá trị trong toàn bộ dữ liệu (`journal-article` 15, `posted-content` 8, `report` 1), nên agent đọc một bài khác cùng loại vẫn trả lời "đúng". Kiểm tra: tài liệu top-1 của `eval_009` ở trạng thái Corrupted là `10.21203/rs.3.rs-10423755/v1`, cũng là `posted-content`. Kết luận: quyết định ở phần ingestion của tôi làm câu hỏi *categories* kém phân biệt, và `judge_accuracy` đánh giá quá cao chất lượng thật cho loại câu hỏi này.
- **3/6 kịch bản lọt qua gate mà metric cũng không đổi.** `inject_noise` (`eval_005`, `eval_007`, `eval_008`) và `truncate_title` (`eval_001`) vẫn đạt judge 5 vì câu hỏi hỏi tác giả, ngày hoặc summary, là những trường không bị chạm. `drop_latest_records` chỉ lộ ra qua `latest_published` lùi từ 2026-09-15 về 2026-08-26 chứ row count vẫn PASS. Đây là silent failure thật sự: cả gate lẫn metric đều không báo.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** Giữ nguyên bản raw là điều kiện để repair được. Nếu chỉ lưu dữ liệu đã biến đổi thì khi corruption xảy ra sẽ không có điểm tựa để khôi phục, và phải gọi lại API (rủi ro rate limit, dữ liệu đã khác).
2. **Data quality/observability:** Lỗi nguy hiểm nhất là lỗi không raise exception — như `categories` rỗng hàng loạt hay snapshot bị ghi đè bằng response hỏng. Phải validate trước khi ghi và theo dõi phân phối dữ liệu, không chỉ kiểm tra code chạy qua.
3. **Ảnh hưởng đến RAG agent:** Chất lượng câu trả lời phụ thuộc trực tiếp vào metadata ingestion: DOI là khóa để đo retrieval hit, abstract là nội dung để embed, categories/authors là metadata để trả lời câu hỏi. Ingestion sai thì mọi metric phía sau đều sai.

### Nếu có thêm thời gian

Làm `categories` có ý nghĩa hơn ở bước ingestion: khi Crossref không có `subject`, lấy thêm `container-title` (tên tạp chí/nơi đăng) hoặc tra khái niệm từ OpenAlex theo DOI, thay vì chỉ dùng `type` với 3 giá trị. Lý do: kết quả mục 8 cho thấy `eval_009` được chấm đúng dù truy xuất sai tài liệu, vì `type` quá ít giá trị. Cách đo: đếm số giá trị khác nhau của `primary_category` (hiện là 3), rồi chạy lại corruption flow trên cùng test set và kiểm tra câu hỏi *categories* có bị chấm sai khi tài liệu gốc bị drop hay không. Nếu có, metric đã phản ánh đúng tác động thật. Ngoài ra nên thêm bộ lọc hoặc cờ ngôn ngữ, vì dữ liệu live có bài tiếng Nga và tiếng Indonesia trong khi MiniLM tối ưu cho tiếng Anh.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thị Hải Mi
**Ngày xác nhận:** 2026-09-26
