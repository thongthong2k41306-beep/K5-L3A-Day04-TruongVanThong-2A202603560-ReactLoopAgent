# CP2 — Hoàn thiện agent loop

**Kết quả:** đã kiểm tra đạt yêu cầu CP2 bằng kiểm thử offline và một lượt gọi OpenRouter thật.

## Phần code cần hiểu

Hàm `run_agent()` nằm trong [agent.py](agent.py). Vòng lặp thực hiện:

1. Tạo `messages` chứa system prompt và câu hỏi của người dùng.
2. Gọi `provider.complete(messages, schemas)` để model chọn tool hoặc trả lời.
3. Append **nguyên vẹn assistant message** vào lịch sử trước các tool results.
4. Với từng tool call, đọc JSON arguments rồi gọi `tools.execute(name, arguments)`.
5. Append một message `role: tool` với đúng `tool_call_id` và kết quả được chuyển thành JSON string.
6. Xử lý hết các calls trong response trước khi gọi model tiếp.
7. Chỉ chấp nhận câu trả lời cuối khi `finish == 'stop'`, không còn calls và đã qua kiểm tra bằng chứng.
8. Trả về `status`, `answer`, `trace` và `usage`.

Mỗi lần gọi model tính là một step. Một response có hai tool calls vẫn chỉ dùng một model step.

## Vì sao phải giữ assistant message và tool-call ID?

Assistant message ghi model đã yêu cầu những tools nào, với arguments và ID nào. Các trường riêng của provider cũng cần được giữ nguyên.

`tool_call_id` gắn từng kết quả với đúng yêu cầu của model. Ví dụ, nếu model yêu cầu hai truy vấn có ID khác nhau, Python phải gửi lại hai tool messages với hai ID tương ứng. Thiếu kết quả, sai ID hoặc bỏ assistant message có thể làm provider từ chối lịch sử hoặc khiến model không nhận đúng kết quả.

Trace ghi lại các bước và kết quả tools để kiểm tra, không yêu cầu model in suy nghĩ nội bộ.

## Bằng chứng chạy qua OpenRouter

File đầy đủ: [artifacts/cp2_github_actions.json](artifacts/cp2_github_actions.json).

- Câu hỏi: `GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây.`
- Dữ liệu status: `snapshot`.
- Giới hạn: `max_steps=6`.
- Kết quả: `status=completed`.
- Model calls: **2**.
- Tool calls: **2**, đều ở model step 1.
- Tools: `get_status(provider="github")` và `get_status(provider="github", component="GitHub Actions")`.
- Model step 2: `finish=stop`, không có tool call mới.
- Tổng token do provider báo: **2398**.
- Thời điểm snapshot GitHub: `2026-11-09T03:50:47.065020+00:00`.

Đây là một lần kiểm tra cơ chế agent. Kết quả mô tả dữ liệu tại thời điểm snapshot, không xác minh trạng thái GitHub ở thời điểm hiện tại. Lần chạy này chưa gọi `get_incident_details`; đường đi qua tool chi tiết đã được kiểm tra bằng test offline bên dưới.

## Kiểm thử offline cho CP2

Ba tests đã chạy và đều đạt:

- `test_tool_result_is_returned_with_id`: model nhận tool result với ID chính xác.
- `test_multiple_tool_calls`: trả đủ kết quả của nhiều tool calls trước lần gọi model tiếp theo.
- `test_two_tools_and_final_with_real_snapshot`: chạy status tool, đọc chi tiết incident, rồi trả lời dựa trên snapshot bằng provider giả lập.

Lệnh kiểm tra:

```powershell
python -m unittest discover -s tests -p test_lab.py -k test_tool_result_is_returned_with_id -k test_multiple_tool_calls -k test_two_tools_and_final_with_real_snapshot -v
```

Để chạy lại câu hỏi qua model thật:

```powershell
python run.py "GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây."
```

Kết quả và số lần gọi tool có thể thay đổi giữa các lần chạy. Kiểm tra `trace` để xác nhận tools thực sự được gọi, và đọc bằng chứng trước khi tin các nhận định trong `answer`.
