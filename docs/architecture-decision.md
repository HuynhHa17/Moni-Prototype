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
