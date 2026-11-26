# Thiết kế cảnh báo CPU cao (CPU-01)

## 1. Cách tính CPU từ counter

Node Exporter xuất `node_cpu_seconds_total{cpu, mode}`: tổng số giây mỗi
nhân CPU đã ở từng chế độ (`idle`, `user`, `system`, `iowait`...) kể từ lúc
boot. Đây là counter, chỉ tăng, nên giá trị thô không cho biết CPU đang bận
bao nhiêu.

`rate(...[2m])` lấy độ tăng trung bình mỗi giây trong 2 phút gần nhất. Với
`mode="idle"`, kết quả là tỷ lệ thời gian rảnh của từng nhân, từ 0 đến 1.
Lấy trung bình qua mọi nhân rồi đổi sang phần trăm đã dùng:

```promql
100 * (1 - avg by(instance, host, environment) (
  rate(node_cpu_seconds_total{job="node", mode="idle"}[2m])
))
```

- Đơn vị: phần trăm CPU của **cả host** (0–100), không phải của một nhân.
  Host 2 vCPU chạy kín 1 nhân thì ra khoảng 50%.
- `iowait` được tính là bận vì không thuộc `idle`. Khi cần tách CPU tính
  toán với chờ I/O thì xem riêng `mode="iowait"` trên dashboard.
- Cửa sổ 2 phút = 8 mẫu ở `scrape_interval` 15s. Mất 1–2 lần scrape vẫn
  còn đủ mẫu; đủ ngắn để bắt tải kéo dài trong lab. Dashboard dùng cùng cửa sổ `[2m]`
  nên panel CPU và rule luôn khớp nhau (từ dashboard v6).

## 2. Ngưỡng và thời gian chờ khởi đầu

| Tham số | Giá trị | Lý do |
|---|---|---|
| Ngưỡng | `> 85` | Đủ xa mức nền của VM2 khi rảnh, để tải thử vượt rõ ràng |
| `for` | `3m` | Bỏ qua đỉnh ngắn (cập nhật gói, khởi động container) |
| `severity` | `warning` | CPU cao chưa chắc làm hỏng dịch vụ; HTTP lỗi mới là `critical` |

Thời gian phát hiện lý thuyết khi tải đẩy CPU lên gần 100%: trung bình 2
phút vượt 85% sau khoảng 1,7 phút, cộng `for` 3 phút, cộng chu kỳ đánh giá
15s, tức khoảng 5 phút. Alertmanager thêm `group_wait` 30s trước khi gửi.

Đây là giá trị **khởi đầu cho lab**, chưa phải SLA hay ngưỡng production.
Ngưỡng chính thức chốt sau khi đo baseline (BSL-01).

## 3. Mất scrape không được hiểu là CPU bình thường

Khi Node Exporter không trả lời, `up{job="node"}` = 0 và chuỗi
`node_cpu_seconds_total` bị đánh dấu stale. Vài phút sau `rate()` không còn
mẫu và biểu thức trả về rỗng; nếu đang firing thì alert sẽ **resolved**
dù CPU không hề giảm.

Cách xử lý:

- Rule chỉ đánh giá khi lần scrape gần nhất thành công:
  `and on(instance) (up{job="node"} == 1)`.
- Alert hết firing do mất dữ liệu **không** phải bằng chứng đã phục hồi.
  Phục hồi phải được xác nhận bằng mẫu CPU mới dưới ngưỡng khi `up` = 1.
- Cảnh báo mất scrape là việc của rule riêng `ExporterDown` (ALT-10).
- Dashboard đã áp dụng cùng nguyên tắc: panel CPU trống khi `up` = 0.

## 4. Rule dự kiến (CPU-02)

```yaml
- alert: HostHighCpu
  expr: |
    (100 * (1 - avg by(instance, host, environment) (
      rate(node_cpu_seconds_total{job="node", mode="idle"}[2m])
    )) > 85)
    and on(instance) (up{job="node"} == 1)
  for: 3m
  labels:
    severity: warning
```

Annotations ghi host, giá trị CPU hiện tại, ngưỡng, thời gian chờ và bước
kiểm tra đầu tiên (`top`/`ps` trên host đó). CPU cao chỉ là quan sát tài
nguyên, không tự kết luận HTTP lỗi hay nguyên nhân gốc.
