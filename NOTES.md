# Ghi chú phân tích · Day 04

Họ và tên: Trương Văn Thông
MSSV: 2A202603560

**Trạng thái:** CP4 đã hoàn thành. Baseline GPT-4o mini có 22/22 case được chấm, điểm tổng **81,59/100**, không có case unscored. `eval_before.json` là bản sao nguyên vẹn của `eval_before_gpt4o_mini.json`. CP5 đã được đánh giá bằng lượt eval sau đủ 22/22 case: **84,55/100**, tăng **2,96 điểm**. CP6 đã có dữ liệu so sánh. Tests mới vẫn chờ học viên gửi log; trợ lý không chạy tests hoặc gọi API.

Cấu hình: agent/judge đều dùng `openai/gpt-4o-mini` qua `openrouter`, `max_steps=8`, dataset `core`. Bản NVIDIA cũ và ghi chú dự thảo được giữ trong `artifacts/` để phân biệt các lần chạy.

## 1. Case được chọn

- Case được chọn cải tiến: **H1**, điểm baseline **60/100**; H6 cũng có vấn đề tương tự và được 60/100.
- Nguồn: `eval_before.json` → `cases` → `id: H1`.
- Câu hỏi yêu cầu đọc incident GitHub `h02n9572mx9y`, theo liên kết trong incident để điều tra nguyên nhân/ảnh hưởng, rồi đối chiếu với Cloudflare `yaa0witbl2me`.
- Agent đã đọc hai incident được nêu trực tiếp, trả lời và dẫn nguồn, nhưng chỉ nhắc URL incident GitHub liên quan `xr3myzj7ms51` mà chưa thực sự gọi tool để đọc incident đó.
- Judge cho điểm thô 80; kiểm tra bằng code áp trần **60** vì chỉ có tool calls ở **một model step**, trong khi yêu cầu điều tra này cần đọc tiếp bằng chứng ở bước sau.

Xem lại offline: `python review_results.py eval_before.json --case H1`.

## 2. Bằng chứng trong trace

Các trường liên quan được trích từ trace thật; các trường khác được lược bớt:

```json
[
  {"event": "model", "step": 1, "finish": "tool_calls", "tool_calls": 2},
  {
    "event": "tool",
    "step": 1,
    "name": "get_incident_details",
    "arguments": {"provider": "github", "incident_id": "h02n9572mx9y"},
    "result": {
      "updates": [{
        "status": "resolved",
        "created_at": "2026-11-04T18:16:08.361Z",
        "body": "Please refer to the combined summary in this related incident: https://www.githubstatus.com/incidents/xr3myzj7ms51",
        "truncated": false
      }]
    }
  },
  {
    "event": "tool",
    "step": 1,
    "name": "get_incident_details",
    "arguments": {"provider": "cloudflare", "incident_id": "yaa0witbl2me"}
  },
  {"event": "model", "step": 2, "finish": "stop", "tool_calls": 0}
]
```

Không có tool event đọc `xr3myzj7ms51` trong H1. `grade.mechanical` ghi:

```json
{
  "violations": ["Cần tool calls ở ít nhất 2 model steps khác nhau."],
  "score_cap": 60,
  "tool_calls": 2,
  "tool_steps": 1
}
```

**Nguyên nhân có thể xảy ra:** model dừng sau khi nhận kết quả hai tools đầu tiên. Cơ chế kiểm tra nguồn hiện tại xác nhận có URL trong final answer, nhưng chưa xác nhận yêu cầu theo incident liên quan đã được thực hiện. Việc nhắc một URL không chứng minh nội dung URL đó đã được đọc.

## 3. Thay đổi đã thực hiện

**Đã áp dụng thay đổi CP5 trong `agent.py`.** Các thay đổi chuẩn bị CP4 đã có trước baseline: đọc `.env`, checkpoint/resume, giãn requests miễn phí, dừng khi gặp 429 và nạp E2 từ kết quả thật bằng `--seed`.

Thay đổi đã thực hiện:

- `_requires_related_lookup()` nhận diện yêu cầu điều tra/theo liên kết, đồng thời giữ yêu cầu không theo liên kết.
- `_related_incidents()` chỉ trích ID từ URL HTTPS `/incidents/<id>` thuộc status providers có tools hỗ trợ trong `updates.body`; không tự truy cập URL.
- `run_agent()` theo dõi các incident đã thử tra cứu. Khi còn nguồn liên quan chưa đọc, final answer bị yêu cầu sửa bằng một lượt tool calling mới và trace ghi `validation_missing_related_incident`.
- Các incident đã tra cứu trong cùng batch và liên kết vòng không bị đọc lại. Arguments sai cần sửa; lỗi tool được trả lại model. Mọi lượt gọi model vẫn nằm trong `max_steps`.
- Đã viết `tests/test_related_incidents.py` với dữ liệu/IDs giả lập để kiểm tra bước đọc tiếp, budget, batch song song, vòng lặp liên kết, URL không hợp lệ, timeout và arguments sai. Không hard-code ID/case trong logic agent.

Lượt eval sau do học viên chạy đã xác nhận H1 và H6 thực hiện bước đọc tiếp. Cả hai trace ghi `validation_missing_related_incident` ở step 2 và gọi `get_incident_details` cho `xr3myzj7ms51` ở step 3. Mechanical checks không còn vi phạm: 3 tool calls ở 2 model steps. H1 còn cần sửa final answer vì thiếu nguồn ở step 4, nên có 5 lượt agent. Chưa có log tests mới để khẳng định toàn bộ tests đã đạt. Chi tiết ở `CP5.md`.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Số case được chấm | 22/22 | 22/22 |
| Điểm tổng | 81,59/100 | 84,55/100 |
| Điểm H1 | 60/100 | 100/100 |
| Điểm H6 | 60/100 | 85/100 |
| Lượt model H1 có usage | Agent: 2; judge: 1 | Agent: 5; judge: 1 |
| Tool calls H1 | 2, ở 1 model step | 3, ở 2 model steps |
| Token H1 | Agent: 2.130; judge: 2.136; tổng: 4.266 | Agent: 10.646; judge: 2.918; tổng: 13.564 |
| Chi phí H1 do API ghi nhận | 0,00099945 USD | 0,0024453 USD |
| Lượt model toàn bộ có usage | Agent: 50; judge: 22 | Agent: 55; judge: 22 |
| Tổng token được ghi nhận | 80.207 | 101.221 |
| Tổng chi phí do API ghi nhận | 0,0169311 USD | 0,01995465 USD |

- Trong lượt chạy này, lỗi dừng trước khi đọc incident liên quan đã được khắc phục ở H1 (60 → 100) và H6 (60 → 85). A1 cũng tăng 75 → 100. Đây là bằng chứng cho hai trace này, không bảo đảm mọi câu hỏi đều được xử lý đúng.
- Tổng điểm tăng 2,96; tổng token tăng 21.014 (+26,2%), số usage records agent tăng 50 → 55. Chi phí ghi nhận tăng khoảng 17,9%.
- Các case giảm đáng chú ý: E3 90 → 70, H7 75 → 60, H8 90 → 75, A8 100 → 90. Theo nhận xét judge, cần xem lại bằng chứng ảnh hưởng ở Việt Nam (E3), kết luận Cloudflare khi thiếu dữ liệu (H7), giới hạn 50 incidents (H8) và diễn giải nguyên nhân (A8). Nhận xét judge cần đối chiếu thủ công, không coi là sự thật đã xác minh.
- Hai file có cùng cấu hình và tập case; hashes của dữ liệu, tools và grading không đổi, chỉ `agent.py` đổi. Hash sau khớp code hiện tại. `eval_after.json` là bản sao nguyên vẹn của `eval_after_gpt4o_mini.json`.
- Không dùng kết quả NVIDIA để so sánh trước/sau với GPT-4o mini vì model/judge khác nhau.

## 5. Giới hạn

- Agent và judge cùng dùng GPT-4o mini; judge có thể thiên lệch hoặc chấm sai. Đối chiếu `expected`, câu trả lời, trace và mechanical checks.
- Một lần chạy mỗi phiên bản không chứng minh độ ổn định. Điểm thay đổi có thể chịu ảnh hưởng của tính ngẫu nhiên.
- Snapshot GitHub/Cloudflare được chụp ngày 09/11/2026, không xác nhận tình trạng dịch vụ ở thời điểm hiện tại.
- Tools chỉ tìm chuỗi trong 50 incident gần nhất và lược bớt updates/nội dung dài. Thiếu kết quả không chứng minh thiếu sự cố.
- Kiểm tra sự hiện diện của URL không chứng minh mọi nhận định đều có nguồn, hoặc mọi trang được nhắc tới đã được đọc.
- HTTP 429 là giới hạn API, không phải bằng chứng outage. Case chưa chấm cần giữ `null`; không sửa tay điểm.
- Số token/chi phí ở trên lấy từ usage đã lưu, không phản ánh các yêu cầu không trả usage và không phải số dư hay hóa đơn tài khoản.
- Điểm eval trước/sau 81,59/84,55 trên 100 và điểm bài lab là hai thang đánh giá khác nhau.
