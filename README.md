# Moni Prototype

Prototype giám sát host, container và dịch vụ trong môi trường lab VMware.
Hệ thống giúp người vận hành nhận biết ảnh hưởng, phân biệt lỗi dịch vụ với
mất thu thập, nhận cảnh báo và đối chiếu lịch sử khi khôi phục.

## Phạm vi và kiến trúc

- **Lab cá nhân: hai VM.** VM1 Monitoring, VM2 Workload.
- **Lab tích hợp: ba VM từ M3.** VM3 là workload thứ hai, dùng lại
  `workload/compose.yaml`; chưa được dựng bởi thay đổi cấu hình nền này.
- VM1 theo thiết kế: Prometheus, Grafana, Alertmanager, Blackbox, Python
  Webhook và SQLite; thêm quan sát sức khỏe VM1 ở MON-01.
- Workload theo thiết kế: Nginx proxy podinfo, Node Exporter, cAdvisor,
  filesystem thử giới hạn và công cụ gây lỗi có thời lượng.
- Lịch sử dùng **CLI/CSV**. Webhook nhận trong Docker network VM1, không
  publish cổng. Không có trang HTML quản lý sự cố trong phạm vi này.

Luồng: metrics/probe → Prometheus → dashboard/rules → Alertmanager →
Webhook → SQLite → CLI/CSV. Khôi phục được xác nhận bằng tín hiệu mới,
không chỉ vì alert hết firing hoặc dữ liệu biến mất.

## Trạng thái ngày 12/11/2026

Nền GitHub main đã đối chiếu tại `d8356ec`: Nginx, Node Exporter,
Prometheus, Blackbox, Grafana và rule `ServiceHttpDown`; có PR đã merge.
16/80 issue ban đầu đã đóng. Đây không phải bằng chứng toàn bộ luồng
Alertmanager/Webhook/lịch sử hoặc CPU/disk đã được nghiệm thu.

Đợt M0 này bỏ IP ghi cứng khỏi Prometheus bằng `.env` → file_sd JSON,
đổi job thành `node`/`http`, cập nhật rule và dashboard Host theo biến
`host`, chuẩn hóa UTF-8/LF và lập bảng yêu cầu/kế hoạch.
Thay đổi trên VM, Alertmanager, Webhook/SQLite, cAdvisor, podinfo, ba
dashboard còn lại, VM3 và luật nâng cao vẫn chờ triển khai/kiểm thử.

## Bắt đầu

Đọc [dựng/nâng cấp lab](docs/setup.md) trước khi cập nhật VM đang chạy.
Trên VM1, sau khi tạo `.env` từ mẫu và sửa IP/host của lab:

```bash
python3 scripts/render_targets.py
sudo docker compose --env-file .env -f monitoring/compose.yaml config -q
sudo docker compose --env-file .env -f monitoring/compose.yaml run --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
sudo docker compose --env-file .env -f monitoring/compose.yaml up -d
```

Trên mỗi workload VM dùng `workload/compose.yaml` và HTTP port của chính VM.
Không copy `.env`, volume, DB hay credential của người khác vào repo.

## Tài liệu

- [Yêu cầu và tiêu chí kiểm chứng](docs/requirements.md)
- [Kế hoạch M0–M4 và danh sách task](docs/project-plan.md)
- [Kiến trúc và luồng dữ liệu](docs/architecture.md)
- [Các quyết định thiết kế](docs/architecture-decision.md)
- [Kiểm tra mã nguồn và phần chưa chạy trên VM](docs/validation.md)
- [GitHub Issues](https://github.com/HuynhHa17/Moni-Prototype/issues)
- [Milestones](https://github.com/HuynhHa17/Moni-Prototype/milestones)

## Phiên bản hiện tại trong cấu hình

| Thành phần | Image |
| --- | --- |
| Nginx | `nginx:1.28-alpine` |
| Node Exporter | `prom/node-exporter:v1.9.1` |
| Prometheus | `prom/prometheus:v3.5.0` |
| Blackbox | `prom/blackbox-exporter:v0.26.0` |
| Grafana | `grafana/grafana:12.3.0` |

Phiên bản cAdvisor, Alertmanager, Python và podinfo sẽ pin khi thêm cấu hình
ở task tương ứng, không ghi như đã triển khai. CPU/disk/for và dự báo phải
có baseline/lý do; giá trị lab khởi đầu chưa phải SLA hoặc KPI đã thống nhất.

## Làm nhóm

Mỗi người có lab hai VM độc lập. Chủ lab triển khai/gây lỗi ở lab tích hợp;
thành viên xem Grafana bằng Viewer riêng khi có đường mạng được phép.
Làm nhánh → kiểm tra lab riêng → PR → một thành viên khác review → merge.
Các deadline trong milestone là kế hoạch nhóm, chưa phải cam kết mentor/UTH.

Không suy HA từ ba VM cùng laptop. Khi VM1 hoặc laptop tắt, stack này
không thể tự phát thông báo độc lập; ghi giới hạn đó trong báo cáo và demo.
