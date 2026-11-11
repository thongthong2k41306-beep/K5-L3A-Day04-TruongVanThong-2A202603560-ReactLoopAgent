# CP5 — Đọc incident liên quan trước khi kết luận

**Trạng thái:** đã triển khai code và chuẩn bị tests offline; học viên chưa gửi kết quả tests cho phiên bản này. Học viên đã chạy eval sau đủ 22/22: 84,55/100, tăng 2,96 điểm. H1 tăng 60 → 100; H6 tăng 60 → 85 và đã đọc incident liên quan. Xem kết quả, token và các case giảm trong [NOTES.md](NOTES.md).

## Vấn đề từ baseline thật

Baseline GPT-4o mini đạt 81,59/100, đủ 22 case. H1 và H6 cùng đạt 60/100. Trong hai case này, tool result chỉ tới một incident tổng hợp, nhưng agent dừng trước khi gọi tool để đọc incident được liên kết. Cả hai bị mechanical checks áp trần 60 vì chỉ có tool calls ở một model step.

Xem dữ liệu gốc và phân tích trong [NOTES.md](NOTES.md). Các file baseline được giữ nguyên.

## Thay đổi trong agent.py

1. Bổ sung hướng dẫn đọc incident liên quan khi câu hỏi yêu cầu theo liên kết hoặc điều tra nguyên nhân.
2. Trích provider/incident ID từ URL HTTPS dạng `/incidents/<id>` trong `updates.body` của tool chi tiết đã thành công. Chỉ nhận hostname của các status providers có trong bộ tools đang dùng.
3. Theo dõi incident đã thử tra cứu. Các incident đã đọc trong cùng một batch hoặc liên kết vòng không buộc đọc lặp lại.
4. Nếu model trả final answer trong khi vẫn còn incident liên quan chưa tra cứu, ghi `validation_missing_related_incident` rồi yêu cầu model đọc tiếp bằng tool calling trong `max_steps` còn lại.
5. Nếu hết bước, trả `max_steps`; nếu tool lỗi, trả lỗi làm observation để model báo phần chưa xác minh. Arguments sai định dạng vẫn cần được sửa và gọi lại.

Logic dùng URL/ID nhận từ dữ liệu, không hard-code case ID, incident ID hay số bước tối thiểu để tối ưu rubric. Một batch đã đọc đủ các incident liên quan không bị ép gọi thêm tool chỉ để tăng số bước.

## Kiểm thử offline — học viên tự chạy

```powershell
python -m unittest discover -s tests -p test_related_incidents.py -v
python -m unittest discover -s tests -v
```

Tests mới dùng IDs và dữ liệu giả lập để kiểm tra:

- Final answer bị yêu cầu đọc tiếp incident liên quan trước khi được chấp nhận.
- Hết budget thì không báo `completed`.
- Các calls song song đã đọc đủ, liên kết vòng và yêu cầu không theo liên kết.
- Bỏ qua domain ngoài danh sách, URL có user/password, port lạ, HTTP và đường dẫn ngoài `/incidents/`.
- Tool timeout, arguments sai định dạng và liên kết sang provider khác được hỗ trợ.

Các lệnh trên không gọi API model. Trợ lý chưa chạy chúng theo quy ước học viên tự chạy chương trình/tests.

## Giới hạn còn lại

- Việc nhận diện yêu cầu theo liên kết dựa trên các mẫu tiếng Việt/Anh; không bao phủ mọi cách diễn đạt.
- Không tự giải mã URL rút gọn hay URL không có incident ID. Không truy cập trực tiếp URL trong tool output; việc đọc vẫn qua tools đã đăng ký.
- Một lần gọi tool thất bại được ghi nhận để tránh yêu cầu lại vô hạn. Chất lượng câu trả lời về phần chưa xác minh vẫn cần đọc trace để đánh giá.
- Kiểm tra này không xác minh mọi nhận định hoặc tự chứng minh quan hệ nhân quả.

## Sau khi tests đạt

CP6 cần một lượt eval **mới** cho phiên bản đã sửa, cùng model/judge/max steps/dataset như baseline. Học viên tự chạy API:

```powershell
python evals/run_evals.py --model openai/gpt-4o-mini --judge-model openai/gpt-4o-mini --output eval_after_gpt4o_mini.json
```

Không dùng `--seed` từ baseline hoặc resume file trước cải tiến: hash agent đã đổi. Khi cần tiếp tục chính lượt eval sau, dùng `--resume --output eval_after_gpt4o_mini.json` với cùng cấu hình.

Đọc/so sánh kết quả offline sau khi đủ 22/22 ở cả hai file:

```powershell
python review_results.py eval_before.json --compare eval_after_gpt4o_mini.json
```

Chỉ cập nhật điểm sau và kết luận cải tiến trong NOTES.md khi có dữ liệu thật.
