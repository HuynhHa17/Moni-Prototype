# Dựng và nâng cấp phần nền M0

Các lệnh dưới đây chạy trong Linux guest, tại thư mục gốc repository.
Docker Engine, Compose và Python 3 phải có sẵn. Docker chạy trong mỗi VM.
Đây là hướng dẫn cho phần nền hiện có; Alertmanager, Webhook, cAdvisor và
podinfo được bổ sung theo [kế hoạch](project-plan.md), chưa nằm trong stack này.

## Lab cá nhân và lab tích hợp

- Lab cá nhân: VM1 Monitoring và VM2 Workload.
- Lab tích hợp: thêm VM3 Workload ở M3, dùng lại `workload/compose.yaml`.
- Cùng repository nhưng IP, tài khoản và dữ liệu riêng. Docker DNS chỉ phân
  giải service trong cùng Docker network; giữa các VM dùng địa chỉ mạng lab.

## Cấu hình mỗi lab

Nếu chưa có `.env`, tạo từ mẫu; không ghi đè file đã có:

```bash
test -f .env || cp .env.example .env
nano .env
```

Điền `WORKLOAD_IP`, `WORKLOAD_HOST`, `WORKLOAD_HTTP_PORT` và `ENVIRONMENT`.
VM1 dùng các biến này để sinh target; VM2 dùng HTTP port để publish Nginx.
Giữ `WORKLOAD_VM3_IP` rỗng cho lab hai VM. Điền IP/host/port của VM3 sau khi
đã dựng VM3 ở lab tích hợp. Không điền địa chỉ VM của người khác.

`PROMETHEUS_IP` và `WEBHOOK_PORT` trong mẫu cũ không còn dùng. Datasource
Grafana truy cập `http://prometheus:9090` nội bộ; Webhook tương lai cũng chỉ
nhận nội bộ. Các khóa cũ trong `.env` có thể bỏ sau khi đối chiếu, không
copy đè mật khẩu hoặc giá trị đang dùng.

Compose không tự thay nội dung file `prometheus.yml`. Script sau đọc `.env`
và sinh hai file JSON file_sd được Prometheus mount đọc. Không truy cập VM,
không khởi tạo VM và không khởi chạy container:

```bash
python3 scripts/render_targets.py
```

Đầu ra: `.runtime/prometheus/targets/node.json` và `http.json`, ngoài Git.
Script kiểm tra IP, port và host trùng trước khi thay file; thư mục này
không chứa secret. Chạy lại sau khi đổi inventory. Khi config nền đã được
nạp, file_sd đọc lại target theo chu kỳ 15 giây mà không cần recreate.

## VM2 — Workload

```bash
sudo docker compose --env-file .env -f workload/compose.yaml config -q
sudo docker compose --env-file .env -f workload/compose.yaml up -d
sudo docker compose --env-file .env -f workload/compose.yaml ps
```

`config -q` kiểm tra Compose; `up -d` áp dụng stack; `ps` xem container.
Không xóa named volume hoặc làm đầy phân vùng hệ thống để thử lỗi.

## VM1 — Monitoring

Render trước khi chạy Compose. Bind mount đặt `create_host_path: false`
để không tự tạo một thư mục rỗng rồi chạy giám sát thiếu inventory.

```bash
python3 scripts/render_targets.py
sudo docker compose --env-file .env -f monitoring/compose.yaml config -q
sudo docker compose --env-file .env -f monitoring/compose.yaml run --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
sudo docker compose --env-file .env -f monitoring/compose.yaml up -d
sudo docker compose --env-file .env -f monitoring/compose.yaml ps
curl --fail --show-error http://localhost:9090/-/ready
```

`promtool` kiểm tra config và rules với đúng đường dẫn mount trước khi áp dụng.
`ready` kiểm tra Prometheus sẵn sàng, chưa chứng minh target hoặc cảnh báo đạt.
Đổi URL local nếu đã đổi port/bind trong `.env`. Các port publish giữ mặc
định lab cũ; giới hạn firewall/quyền truy cập là SEC-01, chưa được kiểm chứng.

## Nâng cấp job và dashboard từ phiên bản cũ

Ghi commit đang chạy, sao lưu cấu hình và `.env` trước khi đổi phiên bản.
Recreate Prometheus bằng `up -d` để nạp job mới; không dùng `down -v`.
Grafana provisioning sẽ đọc lại dashboard Host trong chu kỳ cấu hình.

- `node-vm2` đổi thành `node`, `http-vm2` đổi thành `http`.
- Mỗi target có `host` và `environment`; HTTP thêm `service`.
- Dashboard mới tên Host, chọn một host qua biến `host`; giữ UID `moni-vm2`
  để các URL dashboard cũ còn dùng được.
- Chuỗi thời gian job cũ vẫn nằm trong retention nhưng không tự đổi nhãn.
  Khi nghiệm thu dùng khoảng thời gian sau nâng cấp; sửa query/script riêng
  còn tham chiếu job cũ và lưu commit trước/sau.
- Đổi job/nhãn làm thay định danh alert và có thể bắt đầu lại thời gian `for`.
  Một resolved do thay config/mất dữ liệu không chứng minh dịch vụ phục hồi.

Trên Prometheus chạy lần lượt, thay host bằng nhãn đã điền:

```promql
up{job="node",host="workload-vm2"}
up{job="http",host="workload-vm2"}
probe_success{job="http",host="workload-vm2"}
```

Khi dừng Nginx: kỳ vọng probe=0, scrape HTTP=1, node=1. Khi bật lại,
probe=1 mới là tín hiệu HTTP phục hồi. Không có dữ liệu là chưa xác định.
Rule `ServiceHttpDown` vẫn chờ `for: 1m`; Alertmanager/lịch sử chưa có trong
bản nền, nên lượt này chỉ kiểm chứng metric/rule. Minh chứng toàn luồng ở M1.

## Kiểm tra mã nguồn

```bash
python3 -m unittest discover -s tests -v
```

Test renderer kiểm tra lab hai workload, inventory sai và giữ target cũ khi
input không hợp lệ. Các fixture dùng địa chỉ tài liệu, không gọi lab thật.
