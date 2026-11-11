# CP7 — Demo và nộp bài

## Trạng thái đã kiểm tra

- Có đủ `agent.py`, `eval_before.json`, `eval_after.json`, `NOTES.md`.
- Cả hai eval đủ 22/22 case; điểm 81,59 → 84,55 (+2,96).
- Cùng OpenRouter, agent/judge `openai/gpt-4o-mini`, `max_steps=8`, dataset core.
- Hash dữ liệu, tools và grading giữa hai lượt không đổi; chỉ hash agent thay đổi. Hash sau khớp agent hiện tại.
- `eval_after.json` là bản sao nguyên vẹn của `eval_after_gpt4o_mini.json`.
- `.env` được ignore và không được Git theo dõi. Kiểm tra mẫu key trên các file tracked/untracked không bị ignore chưa thấy chuỗi giống key; kiểm tra này không chứng minh toàn bộ lịch sử Git không có bí mật.
- Không có diff trong fixtures, các case, scenarios, grading và rubric được bảo vệ.
- Chưa nhận log chạy toàn bộ tests cho phiên bản cuối; chưa xác minh repo public, push mới hoặc nộp LMS. CP7 chưa hoàn tất các bước này.

## Kịch bản demo khoảng 3 phút — dùng kết quả đã lưu

Các lệnh dưới đây đọc JSON offline, không gọi API:

```powershell
python review_results.py eval_before.json --compare eval_after.json
python review_results.py eval_before.json --case H1
python review_results.py eval_after.json --case H1
python review_results.py eval_after.json --case H7
```

### 1. Giải thích vòng lặp

Agent gửi lịch sử hội thoại cho model, giữ assistant message chứa tool calls, thực thi từng tool và trả kết quả với đúng `tool_call_id`. Lỗi arguments/tool trở thành observation để model xử lý. Vòng lặp dừng khi có final hợp lệ, lỗi provider hoặc hết `max_steps`. `completed` không bảo đảm câu trả lời đúng.

### 2. Trace nhiều bước: H1

- Trước: step 1 đọc incident GitHub `h02n9572mx9y` và Cloudflare `yaa0witbl2me`; step 2 kết luận. Có URL liên quan nhưng chưa đọc nội dung; 2 tool calls ở 1 model step, điểm 60.
- Sau: step 1 đọc hai incident ban đầu; step 2 bị chặn bởi `validation_missing_related_incident`; step 3 đọc GitHub `xr3myzj7ms51` theo liên kết từ kết quả trước.
- Step 4 còn phải sửa câu trả lời thiếu nguồn (`validation_missing_source`); lượt agent thứ 5 mới hoàn tất. Có 3 tool calls ở 2 model steps, điểm 100.
- Cải tiến trích provider/ID từ URL HTTPS thuộc status hosts được hỗ trợ, không hard-code ID của case. Theo dõi các incident đã thử đọc để tránh lặp liên kết vòng; vẫn chịu giới hạn số bước.

### 3. Lỗi agent còn lại: H7

Tool Cloudflare timeout nhưng câu trả lời vẫn nói sẽ coi Cloudflare hoạt động bình thường theo yêu cầu người dùng. Đây là kết luận không có bằng chứng: timeout chỉ cho biết chưa lấy được dữ liệu. Câu trả lời phù hợp phải ghi trạng thái Cloudflare chưa xác minh, đồng thời báo riêng kết quả GitHub.

H7 giảm 75 → 60. Cơ chế CP5 kiểm tra đọc incident liên quan chưa kiểm soát mọi kết luận thiếu căn cứ. Không sửa tay answer hoặc điểm để che lỗi này.

### 4. Kết quả và giới hạn

Điểm tổng tăng 2,96; H1 tăng 40, H6 tăng 25. Token tăng 80.207 → 101.221 (+26,2%); chi phí ghi nhận 0,0169311 → 0,01995465 USD. E3, H7, H8 giảm lần lượt 20, 15, 15 điểm. Một lượt mỗi phiên bản và cùng model làm judge chưa chứng minh độ ổn định. Snapshot không phản ánh trạng thái dịch vụ hiện tại.

## Các bước người học thực hiện để chốt bài

1. Chạy toàn bộ tests offline và kiểm tra không còn lỗi:

```powershell
python -m unittest discover -s tests -v
```

2. Xác nhận lớp L3A/L3B. Trong GitHub Settings, đổi tên repo theo mẫu `K5-L3A-DAY04-TruongVanThong-2A202603560-ReactLoopAgent` hoặc thay L3A bằng L3B. Cập nhật origin theo tên thực tế sau khi đổi. Giữ repo public và mở link trong cửa sổ chưa đăng nhập để kiểm tra.

3. Sau khi tests đạt, xem diff và commit/push các file bài làm. Lệnh chỉ stage danh sách cụ thể, không stage `.env` hoặc các bản lưu lỗi cũ:

```powershell
git diff --check
git add agent.py providers.py evals/run_evals.py review_results.py tests/test_eval_resume.py tests/test_provider_limits.py tests/test_related_incidents.py tests/test_review_results.py README.md NOTES.md CP2.md CP3.md CP4.md CP5.md CP7.md OFFLINE.md eval_before.json eval_after.json
git diff --cached --stat
git commit -m "Complete ReAct agent, evaluations and submission notes"
git push -u origin HEAD
```

Không dùng `git add .` khi chưa xem các file khác. Các file `.env`, eval bản phụ và artifacts không nằm trong danh sách stage trên. Nếu đã có thay đổi staged từ trước, kiểm tra cả nội dung đó trước commit.

4. Kiểm tra commit mới hiện trên GitHub và đủ 5 file nộp chính. Tự dán link repo public vào bài Day 04 tại https://aithucchien.vinuni.edu.vn bằng tài khoản cá nhân, rồi kiểm tra trạng thái nộp thành công.

Yêu cầu gốc: [SUBMISSION.md](SUBMISSION.md), [CHECKPOINTS.md](CHECKPOINTS.md). Chỉ đánh dấu CP7 hoàn thành khi demo, tests, repo đúng tên/public, push và nộp LMS đã được xác nhận.