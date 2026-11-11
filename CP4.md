# CP4 — Baseline GPT-4o mini

**CP4 đã hoàn thành:** 22/22 case được chấm, 0 unscored, điểm tổng **81,59/100**. Kết quả GPT-4o mini được giữ tại `eval_before_gpt4o_mini.json` và sao chép nguyên vẹn sang tên nộp chuẩn `eval_before.json`.

## Tình trạng đã xác minh từ file

- Provider: `openrouter`.
- Agent và judge: `openai/gpt-4o-mini`.
- `eval_results_gpt4o_mini_e2.json` đã có case **E2 = 80/100**, `completed` và `scored`.
- Cấu hình và tám hash mã nguồn/dataset trong kết quả E2 khớp phiên bản baseline lúc chốt CP4. Sau thay đổi agent ở CP5, cần một lượt eval sau riêng.
- Đã xác nhận file baseline đủ 22 case đúng dataset, cùng model/judge GPT-4o mini và `max_steps=8`. Tám hash mã nguồn/dataset khớp phiên bản lúc chạy.
- 11 case của NVIDIA thuộc model khác, được lưu tại `artifacts/eval_before_nemotron_partial.json`.

H1 và H6 cùng đạt 60/100, đều thiếu bước đọc incident liên quan sau khi nhận tool result. `NOTES.md` đã ghi trace H1 làm cơ sở CP5. Code cải tiến đã được triển khai theo `CP5.md`, chờ học viên kiểm thử; chưa có eval sau.

Các lệnh bên dưới lưu lại quy trình đã dùng. Baseline hiện đã đầy đủ; dùng file đã lưu để phân tích CP5.

Các lệnh chạy chương trình và kiểm thử dưới đây do học viên tự thực hiện. Các lệnh eval có gọi API model trả phí; lệnh unittest chỉ dùng giả lập.

## 1. Kiểm thử phần dùng lại kết quả, hoàn toàn offline

```powershell
python -m unittest discover -s tests -p test_eval_resume.py -v
```

Các tests mới cho `--seed` đã được chuẩn bị nhưng chưa được trợ lý chạy. Chúng kiểm tra giữ nguyên E2 và score 80, chỉ chạy 21 case còn lại, từ chối model/phiên bản khác, bảo vệ output cũ và từ chối case trùng giữa các nguồn.

## 2. Lần đầu chạy bộ 22 case

Sau khi kiểm thử đạt, chạy:

```powershell
python evals/run_evals.py --model openai/gpt-4o-mini --judge-model openai/gpt-4o-mini --seed eval_results_gpt4o_mini_e2.json --output eval_before_gpt4o_mini.json
```

`--seed` đọc nguyên kết quả E2 đã chạy, giữ nguyên điểm và trace, không gọi lại agent/judge cho E2. Nó tạo checkpoint mới cho bộ 22 case rồi chạy 21 case chưa chấm. File E2 gốc được giữ nguyên.

Chỉ dùng `--seed` để bắt đầu output mới. Runner kiểm tra cùng model, judge, max steps, dataset, hash và nội dung case; không ghép kết quả NVIDIA vào baseline GPT-4o mini. Nếu các nguồn có case trùng nhau, runner từ chối để tránh tự chọn một điểm trong nhiều lần chạy.

## 3. Chạy tiếp nếu bị ngắt hoặc giới hạn API

Khi file output đã tồn tại, dùng:

```powershell
python evals/run_evals.py --model openai/gpt-4o-mini --judge-model openai/gpt-4o-mini --resume --output eval_before_gpt4o_mini.json
```

Các case đã chấm, kể cả điểm 0, được giữ nguyên. Nếu agent đã completed nhưng judge chưa chấm được, chỉ gọi lại judge. Không đổi model hoặc code agent trong khi baseline chưa hoàn tất.

## 4. Đọc kết quả offline

```powershell
python review_results.py eval_before_gpt4o_mini.json
python review_results.py eval_before_gpt4o_mini.json --case E2
```

CP4 hoàn thành khi có đủ **22/22 case được chấm**, `unscored_cases=0` và điểm tổng khác `null`. Sau đó đọc các case điểm thấp để chốt cải tiến CP5, không sửa tay file điểm.

Nếu API trả lỗi, xem `result.error` và `grade.reason` đã lưu. `None`/`null` là chưa chấm được, không phải 0 điểm. Giữ các kết quả đã lưu và xử lý lỗi trước khi chạy tiếp.
