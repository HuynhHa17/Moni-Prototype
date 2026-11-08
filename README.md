# Moni Prototype

Prototype giám sát tài nguyên máy chủ, container và dịch vụ trong môi trường lab hai VM.

## Mục tiêu

- Thu thập metrics của host và container.
- Kiểm tra khả năng truy cập của dịch vụ HTTP.
- Trực quan hóa trạng thái theo host và service.
- Cảnh báo CPU cao, filesystem gần đầy và service down.
- Lưu lịch sử sự kiện firing/resolved.
- Xác nhận quá trình phục hồi sau khi xử lý.

## Kiến trúc

### VM1 — Monitoring

- Prometheus
- Grafana
- Alertmanager
- Blackbox Exporter
- Python Webhook
- SQLite

### VM2 — Workload

- Nginx/API mẫu
- Node Exporter
- cAdvisor
- Filesystem thử nghiệm
- Công cụ tạo lỗi CPU, disk và service

## Cấu trúc repository

- monitoring/: cấu hình chạy trên VM1
- workload/: cấu hình chạy trên VM2
- scripts/: script kiểm thử và khôi phục
- docs/: thiết kế, sơ đồ và hướng dẫn
- evidence/: minh chứng kiểm thử

## Trạng thái

Đang khởi tạo repository và chuẩn bị môi trường VMware.
