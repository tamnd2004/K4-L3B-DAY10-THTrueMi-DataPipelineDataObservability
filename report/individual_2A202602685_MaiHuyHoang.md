# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Mai Huy Hoàng |
| MSSV | 2A202602685 |
| Khóa/Lớp | K4 — L3B |
| Tên nhóm | THTrueMi |
| Vai trò chính | Cleaning và data modeling cho dữ liệu Crossref |
| Repository | https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability |
| Ngày hoàn thành báo cáo | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Làm sạch và mô hình hóa paper | `src/ingestion/cleaning.py`: `build_clean_dataframe` | Danh sách `PaperRecord` từ `ingestion.crossref`, `run_date` | DataFrame 16 cột, mỗi `paper_id` một dòng, có `age_days` và `text_for_embedding`; pipeline lưu thành `data/clean/papers_clean.csv` và `.json` | Hoàn thành; commit `dfdebba` |

Tôi triển khai hàm cleaning từ bản TODO chưa chạy được. `phase1.py` nhận DataFrame này để chạy quality gate, tạo vector index và test set. `corruption_flow.py` dùng lại cùng hàm khi dựng dữ liệu repaired từ raw snapshot. Tôi không nhận ownership cho Crossref ingestion, evaluation, quality gate hay orchestration vì các phần đó do thành viên khác triển khai.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất clean schema với các module phía sau | `src/pipelines/phase1.py`, `src/evaluation/testset.py`, `src/retrieval/index.py` | DataFrame có `paper_id`, `published`, `summary`, `authors_joined`, `categories_joined`, `age_days`, `text_for_embedding`; artifact trong `data/clean/` cho thấy luồng đã sử dụng schema này. |
| Bỏ qua thư mục build sinh tại máy | `.gitignore` | Thêm `build/` trong cùng commit `dfdebba`; không ảnh hưởng dữ liệu pipeline. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa ID, title, summary, authors và categories; loại dòng thiếu ID/title/summary hoặc ngày xuất bản không hợp lệ; khử trùng lặp theo `paper_id` | `src/ingestion/cleaning.py`; `data/clean/papers_clean.json` | Artifact baseline hiện có 24 dòng và 24 `paper_id` duy nhất | `git show dfdebba -- src/ingestion/cleaning.py`; `data/quality/baseline_quality_report.json` |
| Tạo ngày dạng ISO, `age_days`, các cột nối và văn bản embedding gồm 5 phần | `src/ingestion/cleaning.py`; `data/clean/papers_clean.csv` | Cột `text_for_embedding` theo thứ tự Title, Authors, Published, Categories, Summary | Kiểm tra tập trung ở mục 4: 24/24 dòng baseline khớp |

Output cụ thể của phần tôi là DataFrame sạch. Lần chạy được lưu trong repo có 24 paper từ raw snapshot và 24 dòng clean. Quality report xác nhận `paper_id` không null, không trùng và `text_for_embedding` không null. Đây là bằng chứng về output của cleaning trong lần chạy chung; artifact được thành viên khác sinh khi tích hợp, không phải do tôi tự nhận đã chạy toàn bộ pipeline.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw `PaperRecord` có thể thiếu trường, có chuỗi thừa khoảng trắng, ngày không hợp lệ hoặc ID lặp. Nếu chuyển thẳng vào vector index, một paper có thể bị index nhiều lần, còn embedding text có thể thiếu ngữ cảnh. Cleaning tạo một contract ổn định trước khi quality gate và retrieval sử dụng dữ liệu.

### Cách triển khai

Với từng record, hàm chuẩn hóa khoảng trắng của ID, title, summary và từng tên tác giả/danh mục. Dòng thiếu `paper_id`, title, summary hoặc `published` hợp lệ bị bỏ. Ngày được parse theo UTC rồi lưu dạng `YYYY-MM-DD`; `updated` sai hoặc thiếu thì lấy `published`. Hàm nối authors/categories, đếm `summary_chars`, tính `age_days` theo ngày chạy và tạo `text_for_embedding` gồm năm phần theo thứ tự cố định. Sau cùng DataFrame được khử trùng lặp theo `paper_id` (giữ dòng đầu), sắp theo `published` giảm dần rồi `paper_id` tăng dần. Danh sách cột cố định giúp cả khi không có dòng hợp lệ, DataFrame vẫn có schema dự kiến.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]` và `datetime run_date`; nguồn raw trong lần chạy lưu lại là `data/raw/crossref_records.json`. |
| Output | `pandas.DataFrame` gồm 16 cột: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment`, `authors_joined`, `categories_joined`, `summary_chars`, `age_days`, `text_for_embedding`. |
| Module phụ thuộc | `ingestion.crossref.PaperRecord`, `core.utils.normalize_whitespace`, pandas. |
| Module sử dụng output | `pipelines.phase1` ghi clean CSV/JSON, kiểm tra quality và build index/test set; `pipelines.corruption_flow` gọi lại để repair. |
| Điều kiện lỗi cần xử lý | Thiếu ID/title/summary, ngày xuất bản không parse được, `updated` không hợp lệ, ID trùng. |

### Cách xác minh

Tôi chạy kiểm tra tập trung trên các artifact đã lưu bằng Python của `.venv`, nạp `build_embedding_text` rồi dựng lại text từ năm cột nguồn cho từng dòng trong ba file JSON. Kết quả thực tế: `papers_clean` **24/24**, `papers_clean_corrupted` **22/22**, `papers_clean_repaired` **24/24** dòng khớp. Helper `build_embedding_text` được thành viên tích hợp tách ra sau commit cleaning của tôi; kiểm tra này xác nhận contract hiện tại, không quy phần refactor đó cho tôi.

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from ingestion.cleaning import build_embedding_text

for name in ('papers_clean', 'papers_clean_corrupted', 'papers_clean_repaired'):
    rows = json.loads((Path('data/clean') / f'{name}.json').read_text())
    matches = sum(
        build_embedding_text(*(row[key] for key in
            ('title', 'authors_joined', 'published', 'categories_joined', 'summary')))
        == row['text_for_embedding'] for row in rows
    )
    print(f'{name}: {matches}/{len(rows)} embedding texts match')
PY
```

- **Kết quả mong đợi:** Mọi dòng đã lưu có `text_for_embedding` đúng năm phần.
- **Kết quả thực tế:** 24/24, 22/22, 24/24 như trên; exit code 0.
- **Artifact:** `data/clean/papers_clean.json`, `data/clean/papers_clean_corrupted.json`, `data/clean/papers_clean_repaired.json`. Chưa chạy lại hai pipeline end-to-end trong lần kiểm tra report này.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Một record thiếu ID, title, summary hoặc ngày xuất bản sẽ làm mất định danh, giảm chất lượng văn bản truy xuất hoặc khiến `age_days` không tính được.
- **Các phương án đã cân nhắc:** Giữ dòng và điền chuỗi/ngày mặc định; hoặc loại dòng thiếu trường cốt lõi trước khi index.
- **Phương án đã chọn:** Loại dòng thiếu trường cốt lõi, còn `updated` không hợp lệ thì thay bằng `published` vì trường này không quyết định danh tính paper hoặc freshness.
- **Lý do:** Tránh đưa dữ liệu thiếu ngữ cảnh vào index và tránh ngày giả làm sai freshness. Đổi lại, số dòng có thể giảm, nên phải theo dõi row count ở quality report.
- **Bằng chứng quyết định phù hợp:** Artifact baseline có 24 dòng, 24 ID duy nhất; quality gate baseline PASS 6/6. Điều này xác nhận tập dữ liệu lưu lại hợp lệ theo các check hiện có, chưa chứng minh quy tắc loại dòng hoạt động đúng với mọi đầu vào lỗi.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Bản starter của `build_clean_dataframe` kết thúc bằng `raise NotImplementedError("Student task: implement cleaning pipeline.")`; đây là blocker đọc được từ mã nguồn trước commit, không phải log của một lần chạy đã lưu.
- **Bước tái hiện:** `git show dfdebba^:src/ingestion/cleaning.py` để xem bản TODO; gọi hàm đó sẽ đi tới `NotImplementedError`.
- **Nguyên nhân gốc:** Starter mới có pseudo-code, chưa có logic tạo DataFrame.
- **Cách xử lý:** Commit `dfdebba` thay TODO bằng chuẩn hóa, lọc dữ liệu, khử trùng lặp, tính cột dẫn xuất và sắp xếp.
- **Cách xác minh sau khi sửa:** Artifact `data/clean/papers_clean.json` có 24 dòng; quality report baseline ghi 24 ID duy nhất và PASS 6/6. Kiểm tra trực tiếp `text_for_embedding` ở mục 4 cũng khớp 24/24 dòng baseline.
- **Điều học được:** Khi một module chưa có implementation, cần chốt schema với các module downstream và kiểm tra output thực, thay vì chỉ xác nhận hàm hết ném lỗi.

## 7. Hiểu biết về luồng end-to-end

1. `crossref.py` lấy và lưu raw response/records. `cleaning.py` chuyển `PaperRecord` thành bảng sạch, có ID, ngày, tuổi paper và `text_for_embedding`. Sau quality gate, `retrieval/index.py` tạo embedding và index vào collection ChromaDB. Flow baseline tạo/dùng lại test set rồi đánh giá retrieval và câu trả lời.
2. `data/eval/test_set.json` lưu câu hỏi, đáp án tham chiếu và `ground_truth_doc_ids`. Retrieval hit kiểm tra ID tài liệu đúng có nằm trong top-k; token F1 và judge đánh giá câu trả lời. Cùng một câu trả lời đúng chưa chắc đã lấy đúng paper, nên cần xem cả hai lớp metric.
3. Quality checks kiểm tra thuộc tính dữ liệu như số dòng, ID duy nhất, trường không null và độ dài summary. Freshness dùng `age_days > 180` và tỉ lệ stale tối đa 25%; dữ liệu có thể đúng schema nhưng đã cũ.
4. Cùng test set giữ nguyên độ khó và ground truth khi so baseline, corrupted, repaired. Nếu thay câu hỏi giữa các trạng thái, chênh lệch metric không còn quy rõ cho corruption/repair.
5. Repair dựng lại clean data từ raw snapshot, qua quality gate, index và evaluate lại. Artifact trong repo cho thấy fingerprint repaired bằng baseline (`8b5b9cc5e8239eab`), quality PASS 6/6, freshness FRESH và bốn metric trở về giá trị baseline.

## 8. Phân tích kết quả

### Metrics chính

Các số dưới đây là kết quả **pipeline chung** trong `data/reports/corruption_report.md` và `data/results/*_metrics.json`, không phải metric riêng của hàm cleaning.

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9000 | 1.0000 | Một câu mất ground-truth paper trong top-k sau corruption. |
| `mean_token_f1` | 1.0000 | 0.9000 | 1.0000 | `eval_003` mất summary nên answer F1 từ 1 xuống 0. |
| `judge_accuracy` | 1.0000 | 0.9000 | 1.0000 | Một câu trả lời bị judge đánh giá sai ở tập corrupted. |
| `mean_judge_score` | 5.0000 | 4.6000 | 5.0000 | Điểm trung bình giảm 0.4 rồi phục hồi. |
| Quality checks | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Corrupted fail uniqueness của `paper_id` và độ dài `summary`. |
| Freshness status | FRESH, 0/24 stale | STALE, 8/22 stale | FRESH, 0/24 stale | Tỉ lệ stale corrupted 36.4%, vượt ngưỡng 25%. |

### Kết luận từ số liệu

1. `blank_summary` làm 3 summary rỗng → GX fail check độ dài summary; câu `eval_003` có token F1 1.00 → 0.00 và judge score 5 → 1 dù retrieval vẫn hit. Clean schema là điều kiện cần, nhưng corruption sau cleaning vẫn có thể phá nội dung agent dùng để trả lời.
2. Rebuild từ raw snapshot → quality PASS 6/6 và freshness từ STALE về FRESH → hit rate, token F1, judge accuracy trở về 1.0000, judge score về 5.0000. Fingerprint repaired bằng baseline cho thấy corpus được phục hồi theo các trường mà report dùng để tính fingerprint.

**Ảnh hưởng rõ nhất:** Với câu trả lời, `blank_summary` tác động rõ nhất vì tạo ra một câu F1 bằng 0 và judge score 1. Với retrieval, `drop_latest_records` làm `eval_009` không còn hit, kéo hit rate xuống 0.9. Đây là hai tác động khác nhau; không thể quy toàn bộ mức giảm cho một scenario. Các lỗi `inject_noise`, `truncate_title` và drop 20% dòng chưa được quality checks hiện tại bắt đầy đủ.

**Khác kỳ vọng:** `eval_009` mất retrieval hit nhưng answer F1 vẫn 1.00, vì agent vẫn trả đúng category từ tài liệu khác. Bảng per-question trong `data/reports/corruption_report.md` cho thấy hit `Y → N → Y` trong khi F1 giữ `1.00 → 1.00 → 1.00`. Điều này giới hạn cách diễn giải answer metric: một câu trả lời đúng không tự chứng minh truy xuất đúng nguồn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Pipeline:** Clean schema cần có ID ổn định, thứ tự cột và quy tắc tạo text thống nhất để các bước index, evaluation và repair nhận cùng contract.
2. **Observability:** Quality gate hiện tại kiểm tra được null/trùng/summary ngắn, còn row loss và title bị cắt có thể lọt qua; cần đo thêm signal theo loại lỗi muốn phát hiện.
3. **RAG:** Data corruption có thể làm hỏng câu trả lời dù retrieval vẫn hit (`eval_003`), hoặc làm mất hit mà câu trả lời vẫn đúng (`eval_009`). Phải đọc metric theo từng câu và từng tầng.

### Nếu có thêm thời gian

Tôi sẽ thêm kiểm tra riêng cho `build_clean_dataframe` bằng raw records tối thiểu có ID trùng, ngày sai, khoảng trắng và thiếu summary; đo số dòng được giữ/bỏ và đối chiếu trực tiếp 16 cột. Việc này kiểm chứng các nhánh cleaning mà artifact baseline toàn dữ liệu hợp lệ chưa phủ tới.

## 10. Cam kết của thành viên

Các mục sau cần chính tôi xác nhận trước khi nộp; việc hoàn thiện báo cáo bằng công cụ không thay cho xác nhận cá nhân.

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Mai Huy Hoàng

**Ngày xác nhận:** 2026-09-26
