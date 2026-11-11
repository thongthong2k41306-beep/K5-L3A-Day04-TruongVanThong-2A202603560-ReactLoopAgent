# CP3 — Xử lý lỗi và trace

Phần logic CP3 đã có trong [agent.py](agent.py). Tài liệu này giúp giải thích code và tự kiểm tra offline.

## Hành vi cần hiểu

| Tình huống | Cách xử lý | Test liên quan |
|---|---|---|
| Hết `max_steps` | Trả `max_steps`; mỗi lượt gọi model tính một bước | `test_max_steps` |
| JSON arguments lỗi/không phải object | Tạo tool observation `INVALID_ARGUMENTS`, gắn đúng ID để model sửa | `test_invalid_json_sent_back_to_model`, `test_non_object_arguments_are_observations` |
| Một call lỗi giữa nhiều calls | Trả lỗi cho call đó và vẫn xử lý các calls còn lại | `test_bad_call_does_not_skip_another_call` |
| Tool timeout hoặc exception | Ghi lỗi vào tool result và trả lại model | `test_tool_exception_is_returned_to_model` |
| Tool trả dữ liệu không gửi được thành JSON | Chuyển thành observation `INVALID_TOOL_RESULT` | `test_invalid_tool_results_are_returned_as_errors` |
| Provider lỗi | Trả `error`, giữ trace/usage đã có và che key trong thông báo lỗi | `test_provider_failure_keeps_usage_and_redacts_key` |
| Model bị cắt (`finish=length`) | Trả `error`, không thực thi calls từ response bị cắt | `test_truncated_response_does_not_execute_tools` |
| Model trả nội dung rỗng/response sai | Trả `error` | `test_invalid_or_empty_model_output_is_not_completed` |

Lỗi tool thường là dữ liệu để model quyết định bước tiếp theo. Lỗi provider có thể khiến lượt chạy kết thúc vì không nhận được response model hợp lệ.

## Đọc trace

- `event=model`: số bước, finish reason và số tool calls.
- `event=tool`: bước chạy, tên tool, arguments, `tool_call_id` và result.
- `event=error`: lỗi khiến agent không tiếp tục được.
- `event=max_steps`: đã hết giới hạn lượt gọi model.
- `validation_missing_tool`, `validation_missing_source` và `validation_missing_related_incident`: các kiểm tra bằng chứng bổ sung.

Kết quả `completed` cho biết agent kết thúc bình thường và qua các kiểm tra đã viết; vẫn phải đọc bằng chứng để đánh giá câu trả lời có đúng hay không.

## Lệnh kiểm tra do học viên chạy

```powershell
python -m unittest discover -s tests -v
```

Các tests dùng provider giả lập/mocking. Chúng không gọi API model và không dùng quota OpenRouter.

Ở lượt kiểm tra trước đã ghi nhận **69 tests đạt**. Sau khi thêm công cụ `review_results.py`, học viên đã tự chạy riêng `test_review_results.py`: **12/12 tests đạt**, kết quả `OK` (0,035 giây). Đây là kết quả của hai phạm vi kiểm tra riêng; dùng log của lần chạy toàn bộ gần nhất để xác nhận toàn bộ bộ tests hiện tại.

Đọc checkpoint hiện có mà không gọi API:

```powershell
python review_results.py eval_before.json
python review_results.py eval_before.json --case A1
```

Các giới hạn của kiểm thử offline: xác minh được hợp đồng xử lý message/tool/lỗi, nhưng không chứng minh model thật luôn chọn đúng tool hoặc đưa ra kết luận đúng.
