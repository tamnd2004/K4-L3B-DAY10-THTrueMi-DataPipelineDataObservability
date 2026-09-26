# Báo cáo vai trò thành viên: Data Pipeline & Data Observability

> Bản báo cáo này chỉ ghi nhận phần việc có thể đối chiếu từ mã nguồn, Git history và artifact của dự án. Sinh viên cần tự đọc, bổ sung trải nghiệm cá nhân và xác nhận trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Nguyễn Trí Dũng |
| MSSV | 2A202602784 |
| Khóa/Lớp | K4, lớp L3B |
| Tên nhóm | THTrueMi |
| Vai trò chính | Benchmark Evaluation Test Set owner |
| Repository | https://github.com/tamnd2004/K4-L3B-DAY10-THTrueMi-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Benchmark test set | `src/evaluation/testset.py`, hàm `build_test_set` | Clean DataFrame 24 bài báo | Danh sách 10 câu hỏi benchmark | Hoàn thành |
| Evaluation artifact | `data/eval/test_set.json` | Kết quả từ `build_test_set` | JSON gồm câu hỏi, ground truth và DOI tham chiếu | Hoàn thành |

Phạm vi cá nhân tập trung vào Bước 5. Tôi không nhận ownership cho Great Expectations, corruption flow, vector index hoặc orchestration pipeline của thành viên khác.

### Bằng chứng Git

```text
Commit: d7663cfdf3a43d83d6c97cea2a2d1d404eb5664e
Author: bananayass <trantridung38@gmail.com>
Message: updated step 5 Benchmark Test Set
Files: src/evaluation/testset.py, data/eval/test_set.json
```

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Kiểm tra schema đầu vào | `build_test_set` | Báo lỗi rõ khi thiếu cột bắt buộc | Truyền DataFrame thiếu một trong 6 cột yêu cầu |
| Chuẩn hóa dữ liệu benchmark | `build_test_set`, `_published_date` | Chuẩn hóa khoảng trắng, ngày ISO `YYYY-MM-DD`, loại DOI trùng | Đọc code và kiểm tra JSON đầu ra |
| Sinh câu hỏi có tính tái lập | `QUESTION_TYPES`, `build_test_set` | 10 câu, phân bổ `3 summary`, `3 authors`, `2 date`, `2 categories` | Chạy lệnh ở mục 4 |
| Liên kết ground truth với nguồn | `ground_truth_doc_ids` | Mỗi câu trỏ về đúng `paper_id` của bài báo | Kiểm tra `data/eval/test_set.json` |
| Ghi artifact | `write_json(Path(output_path), test_set)` | Tạo `data/eval/test_set.json` | Kiểm tra file tồn tại và parse được |

Kết quả xác minh hiện tại:

```text
Tín hiệu hoàn thành: Sinh được 10 câu hỏi test
Phân bổ: {'summary': 3, 'authors': 3, 'date': 2, 'categories': 2}
ID duy nhất: True
Ground truth hợp lệ: True
File JSON tồn tại: True
```

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một bộ benchmark cố định để đo retrieval và chất lượng câu trả lời trong ba trạng thái baseline, corrupted và repaired. Nếu chọn câu hỏi ngẫu nhiên ở mỗi lần chạy, chênh lệch metric có thể do test set thay đổi thay vì do dữ liệu thay đổi.

### Cách triển khai

1. Kiểm tra sáu cột bắt buộc: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`.
2. Chuẩn hóa chuỗi bằng `normalize_whitespace` và đưa ngày xuất bản về ISO date.
3. Khử trùng lặp theo `paper_id`, loại bản ghi thiếu dữ liệu và tiêu đề không an toàn cho cú pháp trích xuất bằng dấu nháy đơn.
4. Sắp xếp ổn định theo `paper_id` để cùng một DataFrame luôn tạo cùng một bộ câu hỏi.
5. Chọn 10 bài duy nhất và gán bốn loại câu hỏi theo tỉ lệ 3, 3, 2, 2.
6. Dùng `first_sentence(summary)` làm ground truth cho câu summary. Ba loại còn lại lấy trực tiếp authors, published và categories.
7. Sinh ID từ `eval_001` đến `eval_010`, lưu DOI nguồn trong `ground_truth_doc_ids`, sau đó ghi JSON bằng utility chung của dự án.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pandas.DataFrame` sạch và `output_path` |
| Output | `list[dict[str, Any]]` gồm đúng 10 phần tử và file JSON tương ứng |
| Module phụ thuộc | `pandas`, `core.utils.first_sentence`, `normalize_whitespace`, `write_json` |
| Module sử dụng output | `evaluation.metrics.evaluate_pipeline`, baseline/corruption evaluation |
| Điều kiện lỗi | Thiếu cột hoặc có dưới 10 paper hợp lệ thì phát sinh `ValueError` |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

- Kết quả mong đợi: `Tín hiệu hoàn thành: Sinh được 10 câu hỏi test`.
- Kết quả thực tế: sinh 10 câu; đủ bốn loại; ID duy nhất; ground truth không rỗng.
- Artifact: `data/eval/test_set.json`.

## 5. Một quyết định kỹ thuật quan trọng

- Bối cảnh: cần bảo đảm phép so sánh baseline, corrupted và repaired sử dụng cùng một benchmark.
- Phương án 1: dùng `DataFrame.sample()` không cố định seed. Cách này đa dạng nhưng không tái lập.
- Phương án 2: dùng random seed. Cách này tái lập trong cùng môi trường nhưng vẫn phụ thuộc thứ tự đầu vào và cách sampling.
- Phương án chọn: chuẩn hóa, sắp xếp ổn định theo `paper_id`, sau đó lấy 10 bản ghi đầu tiên.
- Lý do: đơn giản, tất định, dễ debug và tuân thủ KISS.
- Bằng chứng: gọi lại hàm trên cùng dữ liệu tạo các ID `eval_001` đến `eval_010` cùng phân bổ loại câu hỏi.

## 6. Một blocker kỹ thuật đã xử lý

- Blocker: `retrieval/qa.py` trích tiêu đề bằng regex dựa trên dấu nháy đơn trong câu hỏi.
- Rủi ro: nếu bản thân title chứa dấu nháy đơn, regex có thể lấy title bị cắt và exact lookup thất bại.
- Cách xử lý: chỉ chọn các paper có title không chứa dấu nháy đơn cho benchmark hiện tại.
- Trade-off: mất một số ứng viên nhưng giữ đúng contract của QA mà không mở rộng phạm vi sang sửa module retrieval.
- Cách xác minh: toàn bộ 10 câu hỏi đã tạo có title được bao bởi một cặp dấu nháy đơn và có DOI nguồn hợp lệ.

## 7. Hiểu biết về luồng end-to-end

1. Crossref records được parse thành `PaperRecord`. Cleaning chuẩn hóa nội dung, tính `age_days`, khử trùng lặp và tạo `text_for_embedding`. Dữ liệu sạch qua quality gate trước khi được embed và nạp vào ChromaDB.
2. Mỗi câu benchmark có `ground_truth` để chấm câu trả lời và `ground_truth_doc_ids` để kiểm tra DOI đúng có xuất hiện trong kết quả retrieval hay không.
3. Quality checks kiểm tra data contract của snapshot như số dòng, null, unique và độ dài summary. Freshness kiểm tra tuổi dữ liệu theo thời điểm chạy và tỉ lệ bài quá 180 ngày.
4. Cùng một test set phải được dùng cho cả ba trạng thái để biến số thay đổi duy nhất là chất lượng corpus.
5. Repair thành công khi quality gate và freshness phục hồi, fingerprint hoặc nội dung trở lại baseline, và các metric repaired trở lại mức baseline.

## 8. Phân tích kết quả chung của pipeline

Các số liệu dưới đây được đọc từ artifact chung của nhóm. Chúng không được trình bày như phần code cá nhân ngoài Step 5.

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9000 | 1.0000 | Corruption làm mất một retrieval hit; repair khôi phục hoàn toàn |
| `mean_token_f1` | 1.0000 | 0.9000 | 1.0000 | Ground truth của test set cho thấy chất lượng câu trả lời giảm rồi phục hồi |
| `judge_accuracy` | 1.0000 | 0.9000 | 1.0000 | Một câu bị đánh giá sai trong corpus corrupted |
| `mean_judge_score` | 5.0000 | 4.6000 | 5.0000 | Điểm trung bình giảm 0.4 rồi trở lại baseline |
| Quality gate | PASS | FAIL | PASS | Dữ liệu corrupted vi phạm expectation |
| Freshness | FRESH, 0/24 stale | STALE, 8/22 stale | FRESH, 0/24 stale | Corrupted vượt ngưỡng stale 25% |

Chuỗi nguyên nhân và bằng chứng:

1. Corruption làm hỏng hoặc loại bỏ dữ liệu, quality/freshness chuyển sang FAIL/STALE, retrieval hit rate và token F1 giảm từ 1.0 xuống 0.9.
2. Repair dựng lại corpus từ raw snapshot, quality/freshness trở lại PASS/FRESH, các metric trở lại mức baseline.

Test set có vai trò làm thước đo cố định. Tuy nhiên, 10 câu chỉ là mẫu nhỏ nên có thể chưa phủ hết mọi dạng corruption. Kết quả metric cần được đọc cùng quality report và corruption log.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng

1. Benchmark phải tất định thì so sánh trước và sau corruption mới có ý nghĩa.
2. Ground-truth document ID đo đúng tài liệu được truy xuất, còn ground-truth answer đo đúng nội dung câu trả lời. Hai tín hiệu bổ sung cho nhau.
3. Validation đầu vào giúp lỗi schema xuất hiện sớm ở boundary của module thay vì gây lỗi khó hiểu trong pipeline đánh giá.

### Trải nghiệm cá nhân và khó khăn thực tế

Trong Bước 5, phần khó nhất không phải tạo đủ 10 câu hỏi mà là bảo đảm bộ câu hỏi có thể tái lập và tương thích với module QA. Nếu chọn paper ngẫu nhiên, mỗi lần chạy có thể sinh test set khác nhau và làm sai lệch phép so sánh baseline, corrupted và repaired. Tôi xử lý bằng cách chuẩn hóa dữ liệu, sắp xếp ổn định theo `paper_id` và cố định phân bổ câu hỏi theo tỉ lệ 3, 3, 2, 2.

Khi đối chiếu với `retrieval/qa.py`, tôi nhận thấy title được lấy từ câu hỏi bằng regex dựa trên dấu nháy đơn. Title chứa dấu nháy đơn có thể làm exact lookup nhận sai chuỗi. Tôi giới hạn candidate pool ở các title an toàn để giữ đúng contract hiện có mà không sửa sang module retrieval. Sau khi hoàn thiện, tôi chạy kiểm tra trên 24 paper sạch và xác nhận sinh đúng 10 câu, ID duy nhất, đủ bốn nhóm và mọi ground truth đều hợp lệ.

### Nếu có thêm thời gian

- Thêm unit test cho DataFrame thiếu cột, thiếu 10 dòng hợp lệ, DOI trùng và ngày không hợp lệ.
- Mở rộng cách encode title để hỗ trợ title chứa dấu nháy đơn thay vì loại khỏi candidate pool.
- Tăng độ phủ câu hỏi hoặc chia benchmark theo corruption scenario để đo tác động chi tiết hơn.

## 10. Cam kết của thành viên

Sinh viên tự đánh dấu sau khi kiểm tra và có thể tự giải thích nội dung:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích hàm `build_test_set` và vai trò của benchmark trong pipeline.
- [x] Mọi kết luận về kết quả đều có commit, artifact hoặc metric để đối chiếu.
- [x] Tôi không nhận ownership cho phần việc của thành viên khác.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Tôi đã đọc và chỉnh lại báo cáo bằng lời của mình trước khi nộp.

**Họ và tên:** Trần Nguyễn Trí Dũng  
**Ngày xác nhận:** 26/09/2026
