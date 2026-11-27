# Danh mục cảnh báo (ALT-08)

Mỗi cảnh báo có `summary`, `description`, `action`, `dashboard` và `runbook`.
Ngưỡng và `for` là giá trị khởi đầu cho lab, chốt lại ở BSL-01.

| Cảnh báo | Mức độ | Điều kiện | for | Đối tượng (nhãn) |
|---|---|---|---|---|
| ServiceHttpDown | critical | `probe_success == 0` và `up{job="http"} == 1` | 1m | host, service, instance |
| HostHighCpu | warning | CPU host > 85% (trung bình 2 phút) | 3m | host, instance |
| HostHighMemory | warning | RAM đã dùng (`1 − MemAvailable/MemTotal`) > 90% | 3m | host, instance |
| FilesystemAlmostFull | warning | `1 − avail/size` > 90% | 2m | host, mountpoint, device |
| FilesystemInodesAlmostFull | warning | `1 − files_free/files` > 90% | 2m | host, mountpoint, device |
| ExporterDown | warning | `up{job=~"node\|cadvisor\|blackbox-exporter\|webhook"} == 0` | 1m | job, instance, host |
| ProbeScrapeFailed | warning | `up{job="http"} == 0` | 1m | host, instance |
| TargetMissing | warning | target trong inventory không còn series `up` theo `(job, host, target_id)` | 2m | job, host, target_id |
| PrometheusConfigReloadFailed | warning | `prometheus_config_last_reload_successful == 0` | 1m | instance |
| PrometheusRuleEvaluationFailures | warning | `increase(prometheus_rule_evaluation_failures_total[5m]) > 0` | 2m | instance |
| AlertmanagerNotificationFailed | critical | `increase(alertmanager_notifications_failed_total[5m]) > 0` | 2m | integration |
| PrometheusTSDBNearCap | warning | TSDB blocks + WAL > 85% trần 5GB | 5m | instance |

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

## HostHighMemory

- **Quan sát:** RAM khả dụng trên host giảm dưới 10% (đã dùng trên 90%) liên tục 3 phút.
- **Kiểm tra đầu tiên:** chạy `free -h`, `ps -eo pid,comm,%mem --sort=-%mem | head` hoặc `docker stats --no-stream` trên host đích.
- **Không kết luận:** dịch vụ đã chết OOM nếu container và probe HTTP vẫn bình thường.
- **Hết cảnh báo:** khi mức sử dụng RAM xuống dưới 90% với `up = 1`.

## FilesystemInodesAlmostFull

- **Quan sát:** tỷ lệ inode đã cấp phát trên `mountpoint` vượt 90% liên tục 2 phút.
- **Kiểm tra đầu tiên:** chạy `df -i <mountpoint>` và tìm thư mục chứa nhiều file nhỏ (log/cache/tmp) để xử lý an toàn.
- **Không kết luận:** dung lượng byte cũng đã đầy; hai chỉ số độc lập nhau.
- **Hết cảnh báo:** khi tỷ lệ sử dụng inode xuống dưới 90% với `up = 1`.

## PrometheusConfigReloadFailed

- **Quan sát:** lần tải lại cấu hình gần nhất của Prometheus thất bại (`prometheus_config_last_reload_successful == 0`).
- **Kiểm tra đầu tiên:** chạy `promtool check config` và `promtool check rules`, kiểm tra log container `prometheus` trên VM1.
- **Không kết luận:** Prometheus đã dừng; Prometheus vẫn chạy với bản cấu hình hợp lệ trước đó.
- **Hết cảnh báo:** sau khi sửa lỗi cú pháp và reload cấu hình thành công.

## PrometheusRuleEvaluationFailures

- **Quan sát:** Prometheus gặp lỗi khi đánh giá rule trong 5 phút gần nhất.
- **Kiểm tra đầu tiên:** mở trang Rules của Prometheus và xem log container `prometheus` để tìm biểu thức PromQL lỗi (thường do xung đột nhãn `many-to-many`).
- **Không kết luận:** toàn bộ cảnh báo bị mất; chỉ rule lỗi không đánh giá được.
- **Hết cảnh báo:** khi không còn lượt đánh giá lỗi trong cửa sổ 5 phút.

## AlertmanagerNotificationFailed

- **Quan sát:** Alertmanager không gửi được thông báo tới kênh tích hợp (`webhook`, `telegram`, ...) trong 5 phút gần nhất.
- **Kiểm tra đầu tiên:** kiểm tra log `alertmanager`, trạng thái `webhook` (`/health`), sức khỏe PostgreSQL hoặc kết nối mạng/token Telegram.
- **Không kết luận:** sự cố đã được xử lý; người trực hoặc kho lịch sử có thể đang bị thiếu bản ghi.
- **Hết cảnh báo:** khi không còn lượt gửi thất bại trong cửa sổ 5 phút.

## PrometheusTSDBNearCap

- **Quan sát:** tổng dung lượng blocks + WAL của Prometheus TSDB vượt 85% mức trần `5GB`.
- **Kiểm tra đầu tiên:** mở trang TSDB Status của Prometheus kiểm tra số series và cardinality của các nhãn; kiểm tra dung lượng đĩa còn lại trên VM1.
- **Không kết luận:** Prometheus đã ngừng ghi; TSDB sẽ tự cắt dữ liệu cũ sớm hơn 60 ngày khi chạm trần.
- **Hết cảnh báo:** khi dung lượng TSDB giảm xuống dưới 85% mức trần.
