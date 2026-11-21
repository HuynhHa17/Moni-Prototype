# Kiểm tra CPU cao toàn luồng (CPU-04)

Ngày chạy: 21/11/2026, giờ UTC. Tải: `workload/scripts/cpu-load.sh -d 420`
trên VM2 (2 worker / 2 vCPU, `nice -n 10`). Số liệu HTTP và trạng thái cảnh
báo lấy lại từ Prometheus bằng `query_range`, bước 30 giây.

## Dòng thời gian

| Mốc | Giờ | Tính từ lúc bật tải |
|---|---|---|
| Bật tải (`cpu-load.log`) | 19:25:34 | 0 |
| `HostHighCpu` pending | ~19:27:16 | ~1 phút 42 giây |
| `HostHighCpu` firing (`startsAt`) | 19:30:16 | 4 phút 42 giây |
| Webhook nhận `new` | 19:30:46 | 5 phút 12 giây |
| Tắt tải | 19:32:34 | 7 phút |
| Cảnh báo hết (`endsAt`) | 19:33:16 | 42 giây sau khi tắt tải |
| Webhook nhận `resolve` | 19:34:46 | nhịp `group_interval` 2 phút |

Lịch sử: 1 episode `HostHighCpu`, sự kiện `new` → `resolve`.

## Metric so với Linux

Lúc 19:32:04 `top` trên VM2: `id` 0,0%, `ni` 83,8%, hai tiến trình `yes`
100% và 93,8%. Prometheus cùng lúc: 100%. Phần bận nằm ở `ni` vì worker chạy
với `nice`; công thức chỉ coi `idle` là rảnh nên vẫn tính là bận.

## HTTP trong cùng khoảng

| Giai đoạn | CPU | Probe thành công | Thời gian probe (ms) |
|---|---|---|---|
| Trước tải 19:24:00–19:25:30 | 2–3% | 4/4 | 2,5–5,0 |
| Tải đang lên 19:26:00–19:27:00 | 17,7–73,6% | 3/3 | 3,3–3,8 |
| Tải kín 19:27:30–19:32:30 | 100% | 11/11 | 2,5–4,1 |
| Sau tải 19:33:00–19:36:00 | 85,4% → 2,4% | 7/7 | 3,6–8,3 |

HTTP không thất bại và không chậm hơn lúc rảnh khi CPU bận kín. Kết quả phụ
thuộc cách tạo tải (`nice`, tải nằm ngoài nginx); không suy ra quan hệ nhân
quả giữa CPU và HTTP từ một lần thử.

## Đối chiếu tiêu chí #51

| Tiêu chí | Kết quả |
|---|---|
| Đối chiếu metric CPU với công cụ Linux/tải đang chạy | Đạt |
| Ghi riêng HTTP thành công/chậm/thất bại trong cùng khoảng | Đạt |
| CPU cao và HTTP lỗi chỉ là tương quan | Đạt (lần thử không có lỗi HTTP) |
