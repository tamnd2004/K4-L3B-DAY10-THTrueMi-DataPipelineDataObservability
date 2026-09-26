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

Output của tôi là đầu vào trực tiếp của `build_clean_dataframe` (`cleaning.py`), gián tiếp cho `testset.py` (ground-truth doc IDs là DOI do tôi bóc tách) và cho bước Repair (khôi phục từ raw snapshot).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                          | Thành viên/module được hỗ trợ | Kết quả                                                                                                   |
| ----------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Kiểm tra tích hợp raw records với module cleaning | `src/ingestion/cleaning.py`          | Chạy lệnh kiểm tra Bước 3 trên raw data của tôi → `Clean thành công 24 dòng`, không mất bản ghi nào. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                     | File/hàm/artifact liên quan          | Kết quả bàn giao                               | Cách xác minh                                                        |
| ---------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------- |
| Gọi Crossref REST API, retry 429/5xx, fallback snapshot local               | `fetch_source_records`, `_request_crossref` | 24 bài báo live, lưu `crossref_response.json` | Lệnh kiểm tra Bước 2 → `Đã tải 24 bài báo`                          |
| Chuẩn hóa DOI, title, abstract (bỏ thẻ `<jats:p>`), authors, categories, ngày | `parse_crossref_payload`              | `crossref_records.json` (24 records)             | Parse snapshot gốc của đề → khớp 100% với `crossref_records.json` mẫu |
| Kiểm thử nhánh fallback khi mất mạng                                       | `fetch_source_records`                 | Pipeline không gián đoạn khi API lỗi            | Trỏ API về cổng đóng → 3 lần thử thất bại → đọc snapshot → 24 records |
| Commit & push code + raw artifacts                                           | commit `582fb95`                       | Raw data lineage có trên repo nhóm               | `git log` trên `main`                                                |

Output cụ thể: `data/raw/crossref_records.json` gồm **24 bài báo** xuất bản trong khoảng **2026-04-01 → 2026-09-15** (trong cửa sổ freshness 180 ngày), summary dài 826–3814 ký tự, không bản ghi nào thiếu tác giả. Quality gate của thành viên phụ trách `quality.py` chạy trên dữ liệu này đạt **6/6 expectations**, `stale_rows = 0`, `is_fresh = true` (`data/quality/test_quality_report.json`). Cả 10 câu hỏi trong `data/eval/test_set.json` đều dùng `ground_truth_doc_ids` là DOI lấy từ records của tôi.

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
5. **Repair thành công khi:** dữ liệu được dựng lại từ raw snapshot (`crossref_records.json` / `crossref_response.json`), quality report pass lại toàn bộ expectations, freshness `is_fresh = true`, và các metric (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`) quay về xấp xỉ baseline trên cùng test set.

## 8. Phân tích kết quả

> Tại thời điểm viết (2026-09-26), nhóm chưa chạy `script/run_phase1.py` và `script/run_corruption_flow.py`, thư mục `data/results/` còn trống. Các ô dưới đây sẽ được cập nhật khi có artifact; tôi không điền số chưa kiểm chứng.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | Chưa có | Chưa có | Chưa có | Chờ `data/results/*_metrics.json` |
| `mean_token_f1`      | Chưa có | Chưa có | Chưa có | Chờ `data/results/*_metrics.json` |
| `judge_accuracy`     | Chưa có | Chưa có | Chưa có | Chờ `data/results/*_metrics.json` |
| `mean_judge_score`   | Chưa có | Chưa có | Chưa có | Chờ `data/results/*_metrics.json` |
| Quality checks         | 6/6 pass¹ | Chưa có | Chưa có | Raw data của tôi qua được toàn bộ gate |
| Freshness status       | Fresh¹ (0/24 stale) | Chưa có | Chưa có | Bài cũ nhất 2026-04-01, trong ngưỡng 180 ngày |

¹ Từ `data/quality/test_quality_report.json` (lần chạy thử quality gate trên dữ liệu sạch, 2026-09-26).

### Kết luận từ số liệu

Chưa đủ số liệu để kết luận. Giả thuyết cần kiểm chứng khi có kết quả:

1. Duplicate rows / blank summary / stale date → gate `unique paper_id`, `summary length`, freshness fail → `retrieval_hit_rate` giảm do bản trùng chiếm chỗ trong top-k và bài bị xóa summary không còn được truy xuất.
2. Repair từ `data/raw/crossref_records.json` → gate và freshness pass lại → metric quay về xấp xỉ baseline, vì raw snapshot không bị corruption chạm vào.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Chưa có số liệu. Dự đoán: *blank summary* và *drop latest records* ảnh hưởng mạnh nhất vì làm mất trực tiếp nội dung chứa đáp án của các câu hỏi loại `summary`.

Kết quả nào khác với kỳ vọng ban đầu?

Ở phần của tôi: dữ liệu Crossref live khác snapshot mẫu (không có `subject`, có bài tiếng Nga/Indonesia) — đã xử lý như mục 6. Phần metrics sẽ cập nhật sau.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** Giữ nguyên bản raw là điều kiện để repair được. Nếu chỉ lưu dữ liệu đã biến đổi thì khi corruption xảy ra sẽ không có điểm tựa để khôi phục, và phải gọi lại API (rủi ro rate limit, dữ liệu đã khác).
2. **Data quality/observability:** Lỗi nguy hiểm nhất là lỗi không raise exception — như `categories` rỗng hàng loạt hay snapshot bị ghi đè bằng response hỏng. Phải validate trước khi ghi và theo dõi phân phối dữ liệu, không chỉ kiểm tra code chạy qua.
3. **Ảnh hưởng đến RAG agent:** Chất lượng câu trả lời phụ thuộc trực tiếp vào metadata ingestion: DOI là khóa để đo retrieval hit, abstract là nội dung để embed, categories/authors là metadata để trả lời câu hỏi. Ingestion sai thì mọi metric phía sau đều sai.

### Nếu có thêm thời gian

Thêm kiểm tra **ngôn ngữ** ở bước ingestion/quality gate (vd lọc hoặc gắn cờ bài không phải tiếng Anh), vì dữ liệu live có bài tiếng Nga và tiếng Indonesia trong khi test set và embedding model (MiniLM tiếng Anh) tối ưu cho tiếng Anh. Cách đo: chạy baseline hai lần — có và không có bộ lọc — trên cùng test set, so sánh `retrieval_hit_rate` và `mean_token_f1`.

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
