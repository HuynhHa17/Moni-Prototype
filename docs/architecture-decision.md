# Quyết định kiến trúc

Cập nhật ngày 12/11/2026 theo mô tả điều chỉnh của nhóm. Quyết định thiết kế
không đồng nghĩa đã triển khai trên VM; xem docs/validation.md.

## ADR-01 — Hai VM cá nhân, ba VM tích hợp ở M3

Mỗi thành viên dùng VM1 Monitoring và VM2 Workload để làm việc độc lập.
VM1 tập trung các thành phần giám sát/lịch sử, tách khỏi nơi gây lỗi.
VM3 chỉ thêm tại lab tích hợp để kiểm thử nhiều host, cô lập nhãn/cảnh báo
và khả năng tiếp tục quan sát workload còn lại khi tắt một VM.

VM3 dùng cùng `workload/compose.yaml`, inventory/IP/host riêng. Không tách
Grafana sang VM riêng hoặc sao chép stack thành cấu hình khác. Cả ba VM
có thể vẫn chia sẻ laptop nên không tạo HA; thêm VM tăng tài nguyên cần cấp.

## ADR-02 — Lịch sử CLI/CSV, Webhook nội bộ

Alertmanager POST các alert vào Webhook trong Docker network VM1; receiver
ghi SQLite trên volume. HIS-07 cung cấp CLI xem/xuất CSV cho người quản trị.
Ô lịch sử trên sơ đồ là chức năng CLI/CSV, không phải trang HTML cho Viewer.
Không publish cổng Webhook/SQLite; quyền và đường mạng thật phải kiểm chứng
tại ALT-09/SEC-01 khi thêm thành phần.

Một lần phát sinh nhận dạng bằng fingerprint/bộ nhãn và startsAt. Tách
thời điểm nguồn/nhận, xử lý firing/resolved từng alert, notification lặp
không tạo episode mới và sự kiện đến muộn không làm lùi trạng thái đã biết.
Không tự tạo thời điểm khôi phục hoặc suy healthy vì mất dữ liệu.

## ADR-03 — Job chung, kiểm tra theo tầng và ức chế có bằng chứng

Job `node`/`http` dùng nhãn host/environment, HTTP thêm service. `.env` riêng
được render thành file_sd JSON; Compose không nội suy file Prometheus khác.
M0 cập nhật đồng thời config, rule và dashboard; label cũ không được viết
lại trong lịch sử. cAdvisor/podinfo/host probe sẽ dùng cùng quy tắc nhãn.

HTTP probe phải thể hiện hợp đồng endpoint thật: health tĩnh Nginx chỉ
chứng minh Nginx trả nội dung đó. M2 thêm endpoint ứng dụng qua Nginx và
metric podinfo, dùng module Blackbox riêng khi body/điều kiện khác nhau.
Dashboard mục tiêu gồm Tổng quan, Host, Container và Service (traffic,
errors, latency, saturation); no-data là unknown.

HostDown cần reachability độc lập đã kiểm tra, không đồng nhất node up=0
với VM tắt. INH-01 chỉ thêm quan hệ ức chế sau test, giới hạn đúng host/
environment/service/container; lỗi riêng ở host khác không bị che.
Alert bị ức chế vẫn có thể firing, không phải bằng chứng đã phục hồi.

CPU/disk/for khởi đầu là provisional, bắt đầu baseline từ M0/M1 và chốt
ở BSL-01 với mentor/UTH. `predict_linear` minh họa ngoại suy disk với guard
dữ liệu/xu hướng; NAB ngoại tuyến tùy chọn, không thay metric lab thật.

## ADR-04 — Nâng cấp nền tảng chuẩn Production và lộ trình Pha A → Pha B (28/11/2026)

Nhằm đáp ứng nghiệm thu UTH–VNPT (giữa tháng 01/2027) mà không tạo ngõ cụt khi
mở rộng lên hạ tầng doanh nghiệp, nhóm chốt 6 quyết định bổ sung:

1. **ADR-04.1 — Inventory & bộ nhãn chuẩn:** Tách `inventory.yml` (gitignored,
   mẫu ở `inventory.example.yml`) khai báo target theo profile (`node`, `http`,
   `cadvisor`, `snmp`, `redfish`); giữ tương thích ngược `.env` qua
   `scripts/render_targets.py`. Mọi target đều có bộ nhãn `environment`, `site`,
   `rack`, `team`, `host`, `target_id`. Luật `TargetMissing` so khớp theo
   `(job, host, target_id)` để không bị che khi một host có nhiều target cùng job.
2. **ADR-04.2 — Kho lịch sử PostgreSQL 16 (chốt):** Triển khai `postgres:16-alpine`
   nội bộ trong Docker network VM1 cho `webhook` (`WEBHOOK_DSN`) và Grafana
   native PostgreSQL datasource (`postgres-history`), bỏ giới hạn khóa file của
   SQLite. Giữ nguyên schema `episodes`/`events` (khóa `fingerprint + starts_at`),
   CLI `history.py` hỗ trợ cả `--dsn` và `--db`, và giữ backend SQLite nhẹ cho
   unit test cục bộ không cần dịch vụ ngoài.
3. **ADR-04.3 — Tách Pha A (2 VM lõi) → Pha B (VM Cloud & DC giả lập):** Hoàn
   thiện trọn vẹn toàn bộ lớp lõi trên 2 VM cục bộ (nền, `podinfo` + SLO burn
   rate, Container, Dự báo Disk 4-guard, Alertmanager Telegram + Inhibition +
   Watchdog, Dashboard Lịch sử, Fault Harness, SEC-01, Backup/Restore) trước khi
   mở rộng sang `VM Cloud` (qua WireGuard/Tailscale, cấm mở public `9100`, đặt
   dịch vụ nhận Heartbeat khác miền lỗi vật lý) và `DC giả lập` (SNMP UPS/PDU +
   Redfish BMC).
4. **ADR-04.4 — Tự giám sát VM1 & TSDB có trần:** Bổ sung `node-exporter` nội
   bộ trên VM1 (`host="monitoring-vm1"`), scrape `/metrics` của `webhook` và
   `alertmanager`, đặt giới hạn tài nguyên container (`mem_limit`/`cpus`) và giữ
   TSDB `60d` kèm trần `5GB`.
5. **ADR-04.5 — Cảnh báo 4 tầng:** Ngưỡng tĩnh/lỗi cứng → Mất dữ liệu &
   Self-Health → Triệu chứng dịch vụ (SLO Burn Rate có low-traffic guard) → Dự
   báo cạn kiệt (`predict_linear` 4-guard).
6. **ADR-04.6 — Kiểm chứng CI tự động:** Mọi commit/PR chạy tự động `unittest`,
   `docker compose config -q`, `promtool check/test rules` và `amtool check-config`.
