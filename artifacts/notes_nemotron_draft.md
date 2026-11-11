# Ghi chú phân tích · Day 04

Họ và tên: Trương Văn Thông
MSSV: 2A202603560

**Trạng thái bản ghi:** đang chuẩn bị phân tích từ dữ liệu thật đã lưu. `eval_before.json` hiện có 11/22 case được chấm; điểm tổng còn `null`. CP5 chưa được chốt và chưa có `eval_after.json`.

**Đổi model:** cấu hình hoạt động đã chuyển sang `openai/gpt-4o-mini` qua OpenRouter cho cả agent và judge. Các điểm và trace A1 bên dưới thuộc baseline NVIDIA cũ, được sao lưu nguyên vẹn tại `artifacts/eval_before_nemotron_partial.json`. GPT-4o mini đã có kết quả chạy riêng **E2 = 80/100** trong `eval_results_gpt4o_mini_e2.json`; chưa có baseline đầy đủ. Dùng file mới `eval_before_gpt4o_mini.json`, nạp nguyên E2 bằng `--seed` theo `CP4.md` và cập nhật phân tích sau khi hoàn tất. Hai model cần được đánh giá riêng.

## 1. Case được chọn

- ID case dự kiến: **A1**. Cần xem tiếp các case còn lại sau khi baseline đủ 22/22 trước khi chốt case cải tiến.
- Nguồn dữ liệu: `eval_before.json` → `cases` → phần tử `id: A1`.
- Câu trả lời của agent: đối chiếu GitHub Actions và Cloudflare Spectrum theo snapshot ngày 09/11/2026; nêu các incident Actions đã resolved, Spectrum tại Phoenix đang monitoring và không khẳng định hai bên có cùng nguyên nhân. Câu trả lời gồm bảng chi tiết bốn incident GitHub và một incident Cloudflare, kèm các URL nguồn.
- Điểm A1 ở lần chạy 1: **98/100**; factuality 39/40, completeness 24/25, evidence 20/20, boundaries 15/15. Phần mechanical checks không có vi phạm.
- Nhận xét của judge: trả lời đúng theo trace. Gợi ý cải thiện là tóm gọn bảng, nhấn mạnh thời điểm chụp dữ liệu và trích trạng thái cuối của incident.

Xem lại hoàn toàn offline bằng `python review_results.py eval_before.json --case A1`.

## 2. Bằng chứng trong trace

Các trường liên quan được trích từ hai tool events thật của A1 (đã lược các trường khác):

```json
[
  {
    "event": "tool",
    "step": 2,
    "name": "get_incident_details",
    "arguments": {"provider": "github", "incident_id": "xr3myzj7ms51"},
    "result": {
      "status": "resolved",
      "url": "https://stspg.io/pjgptg3cfc6n"
    }
  },
  {
    "event": "tool",
    "step": 2,
    "name": "get_incident_details",
    "arguments": {"provider": "cloudflare", "incident_id": "c60k3g4vsoc1"},
    "result": {
      "status": "monitoring",
      "url": "https://www.cloudflarestatus.com/incidents/c60k3g4vsoc1"
    }
  }
]
```

A1 dùng hai `get_status` ở step 1, rồi năm `get_incident_details` ở step 2; tổng cộng **7 tool calls**, **3 model calls của agent**. Agent trả lời ở step 3.

**Vấn đề quan sát được:** câu trả lời khá dài so với yêu cầu đối chiếu. Judge không nêu lỗi sai dữ kiện; điểm 98 không đủ để kết luận tồn tại một lỗi factuality cụ thể. Hướng cải tiến dự kiến là cách chọn và trình bày bằng chứng gọn hơn, vẫn giữ trạng thái, phạm vi, thời điểm snapshot và URL. Chưa có phép đo chứng minh hướng này sẽ tăng điểm hay giảm token.

## 3. Thay đổi đã thực hiện

- **Chưa áp dụng cải tiến CP5 vào agent.** Cần hoàn thành baseline riêng cho GPT-4o mini trước khi chốt cải tiến; A1 của bản NVIDIA hiện chỉ là phân tích tham khảo đã lưu.
- Sau khi đủ 22/22 case, đối chiếu A1 với các case còn lại rồi chốt vấn đề cần giải quyết.
- Nếu chọn A1, dự kiến điều chỉnh hướng dẫn trả lời trong `SYSTEM_PROMPT` của `agent.py`: mở đầu bằng thời điểm snapshot, dùng bảng đối chiếu ngắn theo provider, giữ trạng thái/phạm vi/URL và chỉ mở rộng timeline khi câu hỏi cần.
- Vì sao cân nhắc hướng này: dựa trên câu trả lời và gợi ý judge thực tế; cần kiểm chứng tác động bằng lần eval sau.
- Các phần hỗ trợ chạy eval đã có trước baseline này: đọc `.env`, giãn requests miễn phí, checkpoint sau từng case, dừng khi gặp 429 và `--resume`. Phần phân tích cải tiến agent ở CP5 vẫn đang chờ baseline hoàn tất.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | Chưa có (`null`), mới chấm 11/22 | Chưa chạy |
| Điểm case dự kiến A1 | 98/100 | Chưa chạy |
| Số model calls của A1 | Agent: 3; judge có usage: 1 | Chưa chạy |
| Số tool calls của A1 | 7 | Chưa chạy |
| Token của A1 | Agent: 9.118; judge: 7.468; tổng: 16.586 | Chưa chạy |
| Chi phí A1 do API ghi nhận | 0 USD | Chưa chạy |

- Lỗi đã giải quyết bằng cải tiến CP5: chưa có kết quả trước/sau để xác nhận.
- Phần còn lại: hoàn thành 11 case chưa được chấm, chốt cải tiến, chạy lại đủ 22 case với cùng model/judge/max steps/dataset và cập nhật bảng bằng số liệu thật.
- `partial_mean_0_100 = 99.82` hiện chỉ là trung bình 11 case đã chấm, không phải điểm của toàn bộ baseline.
- Tại mốc 11/22 case, học viên tự chạy công cụ đọc kết quả offline và ghi nhận: **30 lượt agent có usage, 11 lượt judge có usage, 97.999 token và 0 USD chi phí API được ghi trong file**. Các con số này chỉ phản ánh usage đã lưu, không phải tổng số yêu cầu đã gửi hay quota còn lại.

## 5. Giới hạn

- Agent và judge trong bản baseline NVIDIA đang phân tích đều dùng `nvidia/nemotron-3.5-super-vl:free`; judge có thể thiên lệch hoặc chấm sai. Cần đọc `expected`, câu trả lời và trace để đối chiếu. Cấu hình mới dùng GPT-4o mini cần kết quả đánh giá riêng.
- Chỉ một lần chạy mỗi phiên bản không chứng minh độ ổn định. Chênh lệch điểm có thể do biến thiên của model.
- Snapshot GitHub và Cloudflare được chụp ngày 09/11/2026; không xác minh tình trạng dịch vụ ở thời điểm hiện tại.
- Tools bài chính chỉ tìm chuỗi trong 50 incident gần nhất và lược bớt updates/nội dung dài. Thiếu kết quả không chứng minh thiếu sự cố.
- HTTP 429 là vấn đề giới hạn API, không phải bằng chứng GitHub/Cloudflare bị outage. Case chưa chấm phải giữ `score: null`; không sửa tay điểm.
- Các số token và chi phí ở trên lấy từ usage đã lưu; requests lỗi không trả usage có thể không được phản ánh trong các tổng này.
