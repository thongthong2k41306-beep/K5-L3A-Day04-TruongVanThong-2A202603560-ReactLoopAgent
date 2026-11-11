# Những việc làm được mà không gọi API

Các lệnh dưới đây do học viên tự chạy trong thư mục dự án. Công cụ đọc kết quả chỉ dùng Python standard library, không import provider, không đọc `.env` và không kết nối mạng.

## Đọc kết quả đã có

```powershell
python review_results.py eval_before.json
python review_results.py eval_before.json --case A1
```

Công cụ hiển thị tiến độ, case chưa chấm, lỗi đã lưu, token/chi phí có trong usage và gợi ý case điểm thấp để đọc trace. Nó không sửa JSON, không chấm điểm mới và không sử dụng quota API.

Điểm trung bình của các case đã chấm không thay cho điểm toàn bộ dataset. Một file chạy riêng E2 cũng không đủ để hoàn thành CP4.

## Kiểm thử offline

```powershell
python -m unittest discover -s tests -v
```

Chỉ kiểm tra công cụ đọc kết quả mới:

```powershell
python -m unittest discover -s tests -p test_review_results.py -v
```

Kiểm tra agent với tools bonus bằng provider giả lập:

```powershell
python -m unittest discover -s bonus -p 'test_*.py' -v
```

Đọc [CP2.md](CP2.md) và [CP3.md](CP3.md) để giải thích vòng lặp, tool-call ID, giới hạn bước và cách xử lý lỗi.

## Chuẩn bị phân tích và nộp bài

- [NOTES.md](NOTES.md) đã có bản ghi tạm dựa trên A1 và trace thật. Hoàn thành baseline trước khi chốt case cải tiến.
- Kiểm tra họ tên, MSSV, tên repo theo lớp L3A/L3B và danh sách file trong [SUBMISSION.md](SUBMISSION.md).
- Chọn một trace nhiều bước và một tình huống lỗi để trình bày. Có thể dùng A1 cho nhiều tool calls và bản lưu `artifacts/eval_before_baidu_http429.json` để giải thích lỗi hạ tầng.
- Giữ nguyên `agent.py`, `providers.py`, tools, dataset và grading cho đến khi resume baseline đủ 22/22. Tài liệu, công cụ đọc JSON và tests mới không thuộc danh sách hash mà runner đang kiểm tra.

## So sánh trước/sau khi đã có đủ hai file

Chỉ dùng sau khi cả `eval_before.json` và `eval_after.json` đã được chạy thật, đủ dataset và cùng cấu hình:

```powershell
python review_results.py eval_before.json --compare eval_after.json
```

Công cụ từ chối so sánh điểm tổng nếu thiếu case hoặc khác cấu hình. Nó đọc các điểm đã có, không gọi judge hay sửa kết quả. Phần đánh giá bằng chứng và nguyên nhân thay đổi vẫn cần được ghi vào `NOTES.md`.

## Các lệnh có gọi API model

`run.py`, `evals/run_evals.py` và lệnh có `--resume` vẫn gọi API. `--mode snapshot` chỉ thay nguồn dữ liệu status bằng file đã lưu; model vẫn là API thật. Khi chạy các lệnh đó, học viên tự quyết định thời điểm và quota sử dụng.
