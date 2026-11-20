# Kiểm tra lịch sử cảnh báo trên hệ thống thật (HIS-09)

Ngày chạy: 21/11/2026 (giờ UTC+7). Luồng: Blackbox → Prometheus →
Alertmanager → webhook → SQLite. Sự cố giả lập bằng cách dừng container
nginx trên VM2 (`docker compose stop nginx`).

## Kết quả

| Episode | Bắt đầu | Kết thúc | Nhận firing | Nhận resolved | Ghi chú |
|---|---|---|---|---|---|
| 2 | 01:07:30 | 01:19:15 | 01:08:13 | 01:29:20 | webhook tắt ~10 phút |
| 3 | 01:36:45 | 01:53:00 | 01:37:28 | 01:55:50 | webhook tắt trước khi gỡ sự cố |

- Episode 3: `new` (01:37:28) → `resolve` (01:55:50), cùng một episode.
- Sau cả hai lượt, DB có 3 episode, mỗi sự cố đúng một episode.
- Log Alertmanager khi webhook tắt: `Notify attempt failed, will retry later`
  (`lookup webhook ... server misbehaving`), mỗi chu kỳ ~2 phút bị hủy sau
  13–14 lần thử rồi bắt đầu chu kỳ mới, không bỏ thư.
- Khi webhook chạy lại: `Notify success` lúc 01:29:20 (attempts=12) và
  01:55:50 (attempts=9); thư resolved gắn vào episode cũ theo
  `(fingerprint, startsAt)`.

## Đối chiếu tiêu chí #47

| Tiêu chí | Kết quả |
|---|---|
| Alert từ Prometheus tới webhook qua Alertmanager | Đạt |
| Truy được firing/resolved và thời điểm nhận của cùng episode | Đạt |
| Retry không tạo incident mới | Đạt (2 lượt) |

## Hạn chế

- Lượt chạy chưa ghi được thư lặp `repeat`: sự cố kéo dài 16 phút 15 giây,
  kết thúc trước nhịp gửi lặp kế tiếp (01:53:28). Thư lặp đã đo ở HIS-05
  (~16 phút); luật ghi `repeat` vào episode cũ có test trong
  `monitoring/webhook/tests/test_rules.py`.
- Thời gian nhận phụ thuộc `group_wait` 30s, `group_interval` 2m; độ trễ
  resolved lớn ở đây là do chủ động tắt webhook.
