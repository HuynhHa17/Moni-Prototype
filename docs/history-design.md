# Thiết kế nhận dạng episode cảnh báo (HIS-01)

Cập nhật ngày 13/11/2026. Tài liệu này chốt cách Webhook lịch sử (HIS-03→HIS-05)
nhận biết **một lần phát sinh cảnh báo** (episode) từ notification của
Alertmanager. Đây là thiết kế dựa trên payload đo thật trên lab cá nhân hai
VM; Webhook/SQLite chưa được triển khai. Bổ sung cho ADR-02 trong
`docs/architecture-decision.md`.

## 1. Cách thu payload

- Lab: VM1 (Prometheus v3.5.0, Alertmanager v0.28.1), VM2 (Nginx).
  Rule `ServiceHttpDown`, `for: 1m`, `evaluation_interval: 15s`.
  Route ALT-07: `group_wait: 30s`, `group_interval: 2m`, `repeat_interval: 15m`.
- Tạm thêm `webhook_configs` (`send_resolved: true`) trỏ tới container
  `mendhak/http-https-echo` trong network `moni-monitoring_default`, không
  publish cổng. Sau khi đo đã gỡ container và `git restore` cấu hình;
  receiver thật thuộc ALT-09.
- Gây lỗi bằng `docker compose stop nginx` trên VM2, phục hồi bằng
  `docker compose start nginx`. Đồng hồ VM2 chạy UTC nên so trực tiếp với
  thời gian trong payload.
- Log thô giữ trên VM1; bản đăng công khai đã thay IP lab bằng `<IP-LAB>`.

## 2. Payload thực tế (rút gọn)

Alertmanager gửi `POST /` với `Content-Type: application/json`, `version: "4"`:

```json
{
  "receiver": "bootstrap",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ServiceHttpDown",
        "environment": "lab",
        "host": "workload-vm2",
        "instance": "http://<IP-LAB>:8080/health",
        "job": "http",
        "service": "moni-nginx",
        "severity": "critical"
      },
      "annotations": { "summary": "...", "description": "...", "action": "..." },
      "startsAt": "2026-11-13T11:17:00.534Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://<container>:9090/graph?...",
      "fingerprint": "ffba5f3489ed0334"
    }
  ],
  "groupLabels": { "alertname": "ServiceHttpDown", "environment": "lab", "host": "workload-vm2" },
  "commonLabels": { "...": "..." },
  "groupKey": "{}:{alertname=\"ServiceHttpDown\", environment=\"lab\", host=\"workload-vm2\"}",
  "truncatedAlerts": 0
}
```

Trường Webhook cần dùng:

| Trường | Cấp | Ý nghĩa và cách dùng |
|---|---|---|
| `status` (ngoài cùng) | Nhóm | Trạng thái chung của cả notification. **Không** dùng để lưu. |
| `alerts[].status` | Từng alert | `firing` hoặc `resolved`. Lưu theo trường này vì một notification có thể chứa alert ở hai trạng thái. |
| `alerts[].fingerprint` | Từng alert | Mã băm từ bộ nhãn. Giống nhau cho mọi lần cùng loại sự cố trên cùng đối tượng. |
| `alerts[].startsAt` | Từng alert | Thời điểm nguồn lúc alert chuyển firing (xem mục 4). |
| `alerts[].endsAt` | Từng alert | Chỉ có giá trị khi `status = resolved`. |
| `alerts[].labels` | Từng alert | Lưu nguyên để CLI lọc theo `host`, `service`, `alertname`, `severity`. |
| `groupKey`, `truncatedAlerts` | Nhóm | Ghi kèm để điều tra; `truncatedAlerts > 0` nghĩa là notification bị cắt bớt alert. |

## 3. Kết quả đo

Bốn episode của cùng `ServiceHttpDown` trên `workload-vm2`, tất cả cùng
`fingerprint = ffba5f3489ed0334`. Thời gian UTC.

| Episode | Dừng Nginx | `startsAt` | Nhận firing | Nhắc lại | Bật Nginx | `endsAt` | Nhận resolved |
|---|---|---|---|---|---|---|---|
| A (12/11) | — | 22:40:00.534 | 22:40:30 | — | 22:45:49 | 22:46:00.534 | 22:46:30 |
| D (12/11) | 22:59:16 | 23:00:30.534 | 23:01:00 | — | 23:01:17 | 23:01:30.534 | 23:03:00 |
| E (12/11) | tắt VM2 | 23:05:15.534 | 23:05:45 | — | — | — | **không có** |
| B (13/11) | 11:15:52 | 11:17:00.534 | 11:17:30 | 11:33:30 | 11:44:46 | 11:45:00.534 | 11:45:30 |

Giờ dừng Nginx ở episode A không được ghi lại; episode E phát sinh khi tắt
VM2 trước VM1 cuối phiên làm việc, không phải ca gây lỗi có chủ đích.

Quan sát:

1. **Notification lặp giữ nguyên khóa.** Episode B nhận firing lúc 11:17:30 và
   nhắc lại lúc 11:33:30 với cùng `fingerprint` và `startsAt`.
2. **Tái phát đổi `startsAt`.** A, D, E, B cùng `fingerprint` nhưng mỗi
   episode có `startsAt` riêng.
3. **Resolved mang đúng khóa của firing.** A, D, B: bản resolved giữ
   nguyên `fingerprint` và `startsAt` của bản firing.
4. **`endsAt` của firing là giá trị rỗng** `0001-01-01T00:00:00Z`, không phải
   giờ kết thúc dự kiến.
5. **Có thể mất resolved.** Episode E firing nhưng VM1 tắt ngay sau đó;
   Alertmanager giữ alert trong bộ nhớ nên không bao giờ gửi resolved.
6. **Nhắc lại sau 16 phút**, không đúng 15 phút: Alertmanager chỉ xét gửi lại
   tại mốc `group_interval` (2 phút) đầu tiên sau khi đủ `repeat_interval`.
7. **Resolved cũng đi theo nhịp `group_interval`.** Mọi notification sau thư
   đầu của nhóm rơi đúng các mốc cách nhau 2 phút (A: 22:40:30 → 22:46:30;
   D: 23:01:00 → 23:03:00; B: 11:17:30 → 11:33:30 → 11:45:30). Vì vậy độ trễ
   từ `endsAt` tới lúc nhận resolved dao động 0–120 s (đo được 30 s ở A, B và
   90 s ở D).

## 4. Ý nghĩa các mốc thời gian

| Mốc | Nguồn | Kết quả đo | Diễn giải |
|---|---|---|---|
| `startsAt` | Prometheus | Sau lúc dừng Nginx 68–74 s (D, B) | Thời điểm alert **chuyển firing**, tức sau khi điều kiện đúng liên tục `for: 1m`. Không phải thời điểm lỗi bắt đầu. |
| `endsAt` (resolved) | Prometheus | Sau lúc bật Nginx 11–14 s (A, D, B) | Vòng đánh giá rule đầu tiên thấy điều kiện hết đúng. |
| `received_at` | Webhook tự ghi | Firing: sau `startsAt` 30 s. Resolved: sau `endsAt` 30–90 s | Payload không có trường thời điểm gửi nên Webhook phải tự ghi giờ nhận. Firing chờ `group_wait`; resolved chờ mốc `group_interval` kế tiếp. |

- `startsAt` và `endsAt` cùng phần lẻ `.534` vì đều là thời điểm của vòng
  đánh giá rule. Độ phân giải của thời gian nguồn bị giới hạn bởi
  `evaluation_interval` 15 s.
- Ước lượng lúc lỗi bắt đầu xấp xỉ `startsAt − for`, sai số khoảng một
  `scrape_interval` cộng một `evaluation_interval`. Đây chỉ là ước lượng,
  không lưu như dữ liệu đo.
- Thời gian phát hiện tính từ lịch sử phải ghi rõ mốc dùng: `startsAt`
  (Prometheus firing) hay `received_at` (Webhook nhận).

## 5. Quyết định thiết kế

### 5.1. Khóa episode

**Episode = (`fingerprint`, `startsAt`).**

- Chỉ `fingerprint` không đủ: mọi lần tái phát đều trùng (A, D, E, B).
- Không dùng `groupKey`: nó nhận dạng nhóm notification, không nhận dạng
  alert; một nhóm có thể chứa nhiều alert khác nhau.
- Lưu kèm `labels` đầy đủ để không phụ thuộc cách băm `fingerprint`.

### 5.2. Episode và sự kiện

- **Episode**: một dòng cho mỗi khóa, giữ trạng thái hiện biết, `startsAt`,
  `endsAt` (nếu có), nhãn, lần nhận đầu và lần nhận cuối.
- **Sự kiện**: một dòng cho mỗi alert trong mỗi notification nhận được, gồm
  `status`, `endsAt` gốc và `received_at`. Giữ lại để đếm notification lặp
  và điều tra thứ tự đến.

Schema cụ thể và ràng buộc thuộc HIS-02.

### 5.3. Quy tắc xử lý từng alert

| Tình huống | Xử lý |
|---|---|
| Firing, khóa chưa có | Tạo episode trạng thái `firing`. |
| Firing, khóa đã có và đang firing | Notification lặp: chỉ ghi sự kiện, cập nhật lần nhận cuối; **không** tạo episode mới. |
| Resolved, khóa đã có | Đóng episode: lưu `endsAt` và trạng thái `resolved`. |
| Resolved, khóa chưa có (thiếu firing, ví dụ Webhook ngừng lúc firing) | Tạo episode trạng thái `resolved`, đánh dấu thiếu bản firing. |
| Firing đến sau khi khóa đã resolved | Bản tin cũ đến muộn: ghi sự kiện, **không** mở lại episode. Tái phát thật luôn có `startsAt` mới. |
| Resolved lặp | Chỉ ghi sự kiện; giữ `endsAt` đã lưu. |
| Không bao giờ nhận resolved (episode E) | Giữ `firing`, `endsAt` để trống. **Không** tự tạo thời điểm khôi phục, không suy là đã healthy. |
| `endsAt = 0001-01-01T00:00:00Z` | Coi là không có giá trị, lưu rỗng. |

Thời gian lưu theo UTC như payload; CLI chuyển sang Asia/Saigon khi hiển thị.

## 6. Ngoài phạm vi

- Không có người xử lý, phân công hay quản lý sự cố (HIS-02).
- Không gom nhiều alert khác `fingerprint` thành một sự cố chung.
- Chưa đo trường hợp Prometheus khởi động lại giữa episode; cần kiểm tra
  ở HIS-09 vì `startsAt` có thể đổi khi trạng thái rule bị mất.

## 7. Liên quan

- HIS-02 schema SQLite, HIS-03→HIS-05 Webhook, HIS-07 CLI, DES-05 ERD.
- ALT-07 cấu hình route, ALT-09 receiver Webhook thật.
