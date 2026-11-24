# Metric container từ cAdvisor (WKL-06, WKL-07, COL-07, DSH-07)

## Cấu hình

- VM2: `ghcr.io/google/cadvisor:0.55.1`, publish `WORKLOAD_CADVISOR_PORT`
  (mặc định 8081) cho VM1. Chạy `privileged`, `/dev/kmsg`, mount chỉ đọc `/`,
  `/sys`, `/var/run`, `/var/lib/docker`, `/dev/disk`. Chỉ dùng trên VM lab.
- Cờ: `--docker_only`, `--housekeeping_interval=10s`, chỉ giữ nhãn
  `com.docker.compose.project` và `com.docker.compose.service`, tắt nhóm
  metric không dùng (percpu, sched, tcp, udp, process, hugetlb,
  referenced_memory, cpu_topology, resctrl, advtcp).
- VM1: job `cadvisor` lấy target từ `.runtime/prometheus/targets/cadvisor.json`
  do `scripts/render_targets.py` sinh; bỏ series có `name=""` (cgroup hệ
  thống). Job nằm trong inventory nên `TargetMissing` và `ExporterDown` áp dụng.

## Kiểm tra tương thích (24/11/2026, giờ UTC)

| Mục | Giá trị trên VM2 |
|---|---|
| Docker | 29.1.3, image store `io.containerd.snapshotter.v1` (driver overlayfs) |
| cgroup | v2 |
| Docker root | `/var/lib/docker` (trùng mount của cAdvisor) |
| cAdvisor log | `Registration of the docker container factory successfully`; danh sách enabled metrics không còn nhóm đã tắt |
| `/healthz` | `ok` |
| `up{job="cadvisor"}` | 1 |

## Đối chiếu với container đang chạy

Query trên VM1, so với `docker stats --no-stream` trên VM2 cùng thời điểm:

```promql
sum by(name) (container_memory_working_set_bytes{job="cadvisor",name!=""}) / 1048576
sum by(name) (rate(container_cpu_usage_seconds_total{job="cadvisor",name!=""}[1m]))
count by(name, image) (container_last_seen{job="cadvisor",name!=""})
```

| Container | Image | RAM cAdvisor (MiB) | RAM `docker stats` (MiB) |
|---|---|---|---|
| moni-workload-nginx-1 | nginx:1.28-alpine | 5,26 | 5,262 |
| moni-workload-node-exporter-1 | prom/node-exporter:v1.9.1 | 7,91 | 7,906 |
| moni-workload-cadvisor-1 | ghcr.io/google/cadvisor:0.55.1 | 26,15 | 25,79 |

CPU lúc rảnh dưới 0,001 core nên `docker stats` hiển thị 0.00%. Để so CPU,
chạy `timeout 60 yes > /dev/null` bên trong container nginx:

| Nguồn | Giá trị |
|---|---|
| cAdvisor, `rate(...[30s])` | 0,998 core |
| `docker stats` | 98,90% |

1 core tương ứng 100% của `docker stats`; hai giá trị khớp.

## Lưu ý vận hành

- cAdvisor Up chưa đủ: lần đầu `up{job="cadvisor"}` trống vì Prometheus vẫn
  đọc `prometheus.yml` cũ. File được bind mount riêng nên `git pull`/`git apply`
  thay file bằng inode mới; SIGHUP không thấy thay đổi. Sau khi sửa
  `prometheus.yml` phải `up -d --force-recreate prometheus` (xem `docs/setup.md`).
- Container dừng hoặc bị xóa không còn series mới: panel CPU/RAM dừng đường,
  bảng container chỉ liệt kê container có `container_last_seen` trong 60 giây.
