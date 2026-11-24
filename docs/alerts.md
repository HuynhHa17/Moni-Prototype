# Danh mục cảnh báo (ALT-08)

Mỗi cảnh báo có `summary`, `description`, `action`, `dashboard` và `runbook`.
Ngưỡng và `for` là giá trị khởi đầu cho lab, chốt lại ở BSL-01.

| Cảnh báo | Mức độ | Điều kiện | for | Đối tượng (nhãn) |
|---|---|---|---|---|
| ServiceHttpDown | critical | `probe_success == 0` và `up{job="http"} == 1` | 1m | host, service, instance |
| HostHighCpu | warning | CPU host > 85% (trung bình 2 phút) | 3m | host, instance |
| FilesystemAlmostFull | warning | `1 − avail/size` > 90% | 2m | host, mountpoint, device |
| ExporterDown | warning | `up{job=~"node\|cadvisor\|blackbox-exporter"} == 0` | 1m | job, instance, host |
| ProbeScrapeFailed | warning | `up{job="http"} == 0` | 1m | host, instance |
| TargetMissing | warning | target trong inventory không còn series `up` | 2m | job, host |

## Cách đọc một cảnh báo

- **Thời gian nguồn** là `startsAt`/`endsAt` do Prometheus gửi; Webhook lưu
  riêng **thời gian nhận**. Xem bằng
  `docker compose exec webhook python history.py --db /data/history.db episodes`
  (hiển thị UTC+7; xuất CSV giữ UTC).
- `dashboard` là đường dẫn tương đối của Grafana: ghép sau địa chỉ Grafana của
  lab, ví dụ `http://<VM1>:3000` + `/d/moni-vm2/?var-host=workload-vm2`. Không
  ghi cố định IP vào cảnh báo.
- Nội dung cảnh báo chỉ mô tả điều quan sát được. Nguyên nhân gốc được xác định
  sau khi kiểm tra, không suy ra từ cảnh báo.

## ServiceHttpDown

- **Quan sát:** kiểm tra `/health` thất bại liên tục 1 phút, trong khi
  Prometheus vẫn nhận kết quả probe. Người dùng gọi endpoint này có thể đang
  nhận lỗi.
- **Kiểm tra đầu tiên:** trên host đích `docker compose ps` trong `workload/`,
  log container Nginx, `curl` tới URL trong nhãn `instance` từ VM1.
- **Không kết luận:** host đã tắt (Node Exporter có thể vẫn chạy) hoặc
  nguyên nhân là tài nguyên khi chưa có số liệu.
- **Hết cảnh báo:** khi probe mới thành công với `up = 1`.

## HostHighCpu

- **Quan sát:** CPU toàn host trên 85% liên tục 3 phút; giá trị nằm trong
  `description`.
- **Kiểm tra đầu tiên:** `top` hoặc `ps -eo pid,comm,%cpu --sort=-%cpu | head`
  trên host; đối chiếu panel HTTP cùng khoảng thời gian.
- **Không kết luận:** dịch vụ lỗi hoặc chậm nếu probe HTTP vẫn đạt.
- **Hết cảnh báo:** khi trung bình 2 phút xuống dưới 85% với `up = 1`.

## FilesystemAlmostFull

- **Quan sát:** filesystem trong nhãn `mountpoint` đã dùng trên 90% dung lượng
  ứng dụng còn ghi được, liên tục 2 phút.
- **Kiểm tra đầu tiên:** `df -h <mountpoint>` và
  `du -xh --max-depth=1 <mountpoint> | sort -h | tail`; xác nhận đúng mount
  trước khi xóa dữ liệu.
- **Không kết luận:** ứng dụng đã lỗi ghi nếu ứng dụng không dùng mount đó.
- **Hết cảnh báo:** khi mức dùng xuống dưới 90% với `up = 1`.

## ExporterDown

- **Quan sát:** Prometheus không scrape được exporter (`up = 0`) liên tục
  1 phút. Số liệu của target ngừng cập nhật; trạng thái là chưa xác định.
- **Kiểm tra đầu tiên:** container exporter còn chạy không, cổng trong nhãn
  `instance`, đường mạng từ VM1; panel "Thu thập" trên dashboard Host.
- **Không kết luận:** host đã tắt (cần HostDown, HST-01) hoặc dịch vụ vẫn ổn.
- **Hết cảnh báo:** khi scrape thành công trở lại. Các cảnh báo CPU/disk của
  target đó không đánh giá trong lúc mất scrape.

## ProbeScrapeFailed

- **Quan sát:** không lấy được kết quả probe HTTP từ Blackbox (`up{job="http"} = 0`)
  liên tục 1 phút. Trạng thái HTTP là chưa xác định; ServiceHttpDown cố ý
  không đánh giá lúc này.
- **Kiểm tra đầu tiên:** container `blackbox` trên VM1 và log của nó; nếu
  ExporterDown của `blackbox-exporter` cũng firing thì xử lý Blackbox trước.
- **Không kết luận:** dịch vụ HTTP lỗi hoặc vẫn đạt.
- **Hết cảnh báo:** khi Prometheus nhận lại kết quả probe; xem probe mới để
  biết HTTP đạt hay lỗi.

## TargetMissing

- **Quan sát:** target có trong inventory kỳ vọng (`expected.rules.yml`, sinh
  bởi `scripts/render_targets.py`) nhưng Prometheus không còn series `up`
  liên tục 2 phút: target mất khỏi service discovery hoặc bị relabel loại.
- **Kiểm tra đầu tiên:** chạy lại `scripts/render_targets.py`, xem
  `.runtime/prometheus/targets` và trang Targets của Prometheus.
- **Không kết luận:** host hay dịch vụ ổn vì các cảnh báo khác đã hết firing;
  chúng hết vì không còn dữ liệu.
- **Hết cảnh báo:** khi series `up` của target xuất hiện lại.
