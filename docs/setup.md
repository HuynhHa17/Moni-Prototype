# Hướng dẫn dựng và nâng cấp Lab (M2a — Nền Production)

Các lệnh dưới đây chạy bên trong Linux guest (`VM1` và `VM2`), tại thư mục gốc của repository. Yêu cầu mỗi VM đã cài sẵn **Docker Engine**, **Docker Compose plugin** và **Python 3**.

## 1. Cấu hình `.env` và `inventory.yml`

Tạo file cấu hình cục bộ từ file mẫu (không ghi đè nếu đã có `.env` đang dùng):

```bash
test -f .env || cp .env.example .env
test -f inventory.yml || cp inventory.example.yml inventory.yml
```

Cả `.env` và `inventory.yml` đều đã nằm trong `.gitignore` — **tuyệt đối không commit IP thật hoặc mật khẩu lên Git**.

1. **Trong `.env` (trên cả `VM1` và `VM2`):**
   - Điền `WORKLOAD_IP` (IP thực của `VM2`), `WORKLOAD_HOST=workload-vm2`, `WORKLOAD_HTTP_PORT=8080`, `WORKLOAD_CADVISOR_PORT=8081`.
   - Trên `VM1`, đặt mật khẩu thật cho Grafana và PostgreSQL 16:
     ```dotenv
     GF_SECURITY_ADMIN_USER=admin
     GF_SECURITY_ADMIN_PASSWORD=<mật_khẩu_mạnh_grafana>
     POSTGRES_DB=moni_history
     POSTGRES_USER=moni
     POSTGRES_PASSWORD=<mật_khẩu_mạnh_postgres>
     ```
2. **Trong `inventory.yml` (trên `VM1`):**
   - Thay `address: CHANGE_ME` của `workload-vm2` bằng IP thực của `VM2`.

---

## 2. Sinh danh sách target cho Prometheus trên `VM1`

Chạy script sinh `file_sd` và recording rules `expected.rules.yml` trước khi bật Prometheus:

```bash
# Khuyến nghị (dùng inventory.yml theo ADR-04.1):
python3 scripts/render_targets.py --inventory-file inventory.yml

# Hoặc chế độ tương thích ngược đọc trực tiếp từ .env:
python3 scripts/render_targets.py --env-file .env
```

Đầu ra tạo nguyên tử tại `.runtime/prometheus/targets/` gồm `node.json`, `http.json`, `cadvisor.json` (kèm bộ nhãn chuẩn `environment`, `site`, `rack`, `team`, `host`, `target_id`) và `expected.rules.yml`.

---

## 3. Khởi chạy `VM2` — Workload

```bash
sudo docker compose --env-file .env -f workload/compose.yaml config -q
sudo docker compose --env-file .env -f workload/compose.yaml up -d
sudo docker compose --env-file .env -f workload/compose.yaml ps
```

> **Lưu ý tường lửa (`ufw`) trên `VM2`:** nếu `VM2` bật `ufw`, cần cho phép IP của `VM1` truy cập cổng `8080` (Nginx), `9100` (Node Exporter), `8081` (cAdvisor) — và thêm cổng `9898` khi triển khai `podinfo` ở `M2b` (`#89` / `#90`).

---

## 4. Khởi chạy `VM1` — Monitoring Stack

```bash
python3 scripts/render_targets.py --inventory-file inventory.yml
sudo docker compose --env-file .env -f monitoring/compose.yaml config -q

# Kiểm tra cú pháp cấu hình Prometheus trước khi chạy
sudo docker compose --env-file .env -f monitoring/compose.yaml run --rm --no-deps \
  --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml

# Build image webhook (có psycopg cho PostgreSQL 16) và khởi chạy toàn bộ stack
sudo docker compose --env-file .env -f monitoring/compose.yaml up -d --build
sudo docker compose --env-file .env -f monitoring/compose.yaml ps
```

---

## 5. Quy trình nâng cấp `VM1` từ bản cũ (M0/M1) lên M2a

> [!IMPORTANT]
> **Hai bẫy bắt buộc tránh khi `git pull` nhánh `main` mới lên `VM1` đang chạy bản cũ:**
> 1. **Phải chạy lại `render_targets.py` trước khi reload Prometheus:** Luật `TargetMissing` mới đối chiếu theo `(job, host, target_id)`. Nếu giữ file `expected.rules.yml` cũ chưa có nhãn `target_id`, Prometheus sẽ báo `TargetMissing` hàng loạt.
> 2. **Phải có cờ `--build` và `--force-recreate prometheus`:**
>    - `--build` để Docker build lại image `moni-webhook:local` cài thư viện `psycopg` kết nối `postgres:16-alpine` (nếu thiếu `--build`, container `webhook` cũ sẽ lỗi thiếu module).
>    - `--force-recreate prometheus` vì `prometheus.yml` được bind mount theo file đơn lẻ (`git pull` tạo inode mới nên chỉ gửi `SIGHUP` sẽ vẫn đọc nội dung cũ). Tuyệt đối **không** dùng `down -v` để tránh xóa dữ liệu volume.

Chạy đúng chuỗi lệnh nâng cấp sau trên `VM1`:

```bash
git pull origin main

# 1. Bổ sung các biến mới (GF_SECURITY_*, POSTGRES_*) từ .env.example vào .env nếu chưa có
nano .env

# 2. Sinh lại targets và expected.rules.yml có target_id mới
python3 scripts/render_targets.py --inventory-file inventory.yml

# 3. Build lại webhook, nạp postgres:16-alpine, node-exporter VM1 và recreate prometheus
sudo docker compose --env-file .env -f monitoring/compose.yaml up -d --build --force-recreate prometheus
```

---

## 6. Kiểm tra nhanh sau khi lên Stack

```bash
# 1. Prometheus sẵn sàng
curl --fail --show-error http://127.0.0.1:9090/-/ready

# 2. Webhook khỏe và kết nối thành công tới PostgreSQL 16
sudo docker compose --env-file .env -f monitoring/compose.yaml exec webhook \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"

# 3. Xem bảng lịch sử sự cố từ PostgreSQL 16 (giờ UTC+7)
sudo docker compose --env-file .env -f monitoring/compose.yaml exec webhook \
  python history.py episodes --limit 10
```

Trên giao diện Prometheus (`http://<VM1_IP>:9090/targets`), xác nhận các job `prometheus`, `alertmanager`, `webhook`, `blackbox-exporter`, `node` (gồm cả `monitoring-vm1` và `workload-vm2`), `cadvisor` và `http` đều ở trạng thái **`UP`**.

## 7. Chạy bộ kiểm thử tự động trong mã nguồn

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s monitoring/webhook/tests -v
```
