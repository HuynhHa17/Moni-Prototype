# Kiểm thử nghiệm thu toàn luồng (TST-01)

Áp dụng cho lab cá nhân hai VM: VM1 monitoring, VM2 workload. Mỗi lượt chạy
ghi một biên bản theo mẫu ở mục 2. Kết quả unit test hoặc promtool chỉ chứng
minh luật đúng trên dữ liệu giả, không thay cho lượt nghiệm thu này.

## 1. Test case

### TC-SVC: Dịch vụ web ngừng (TST-02)

| Mục | Nội dung |
|---|---|
| Điều kiện trước | Mọi service trên VM1 Up, webhook healthy; `probe_success{job="http"}` = 1 và `up{job="http"}` = 1; không có alert đang firing |
| Gây lỗi | VM2: `docker compose stop nginx` trong `workload/` |
| Kỳ vọng | `probe_success` = 0 trong khi `up{job="http"}` vẫn = 1; `ServiceHttpDown` pending rồi firing sau `for: 1m`; webhook nhận `new` sau thêm `group_wait` 30s |
| Khôi phục | VM2: `docker compose start nginx`; `probe_success` = 1; alert hết; webhook nhận `resolve` cùng episode |
| Giới hạn | Chỉ dừng container nginx, không tắt VM2; Node Exporter vẫn chạy |

### TC-CPU: CPU cao (TST-03)

| Mục | Nội dung |
|---|---|
| Điều kiện trước | CPU VM2 dưới 85%; `up{job="node"}` = 1; không có `HostHighCpu` firing |
| Gây lỗi | VM2: `workload/scripts/cpu-load.sh -d 420` (worker = nproc, `nice -n 10`) |
| Kỳ vọng | CPU > 85% đủ `for: 3m` thì `HostHighCpu` firing; webhook nhận `new`; HTTP được ghi riêng trong cùng khoảng |
| Khôi phục | Tải tự dừng sau 420 giây; CPU giảm dưới 85%; alert hết; webhook nhận `resolve` |
| Giới hạn | Chỉ chạy trên `workload-vm2`; không suy ra HTTP bị ảnh hưởng nếu probe vẫn tốt |

### TC-DSK: Filesystem gần đầy (TST-04)

| Mục | Nội dung |
|---|---|
| Điều kiện trước | Mọi filesystem VM2 dưới 90%; ghi lại `df -h /` |
| Gây lỗi | VM2: `disktest.sh setup`, đối chiếu `df -B1` với `node_filesystem_*`, rồi `disktest.sh fill 95` |
| Kỳ vọng | Filesystem thử > 90% đủ `for: 2m` thì `FilesystemAlmostFull` firing với đúng mountpoint; webhook nhận `new` |
| Khôi phục | `disktest.sh clean` rồi `teardown`; mức dùng giảm; alert hết; webhook nhận `resolve`; `/` trở về như trước |
| Giới hạn | Chỉ ghi vào `/mnt/moni-disktest`; không làm đầy phân vùng hệ thống |

## 2. Mẫu biên bản

```
Mã TC:            TC-...
Ngày, người chạy:
Commit đang chạy: (git rev-parse --short HEAD trên VM1 và VM2)
Lab:              VM1 monitoring, VM2 workload-vm2
Rule:             tên, ngưỡng, for; group_wait/group_interval/repeat_interval

Trước:   trạng thái metric và alert, ảnh/lệnh
Gây lỗi: lệnh, giờ UTC
Trong:   pending, firing (startsAt), webhook nhận new; HTTP nếu có
Khôi phục: lệnh, giờ UTC
Sau:     alert hết (endsAt), webhook nhận resolve, episode trong lịch sử

Kết quả: PASS | FAIL | NOT_RUN
Ghi chú: sai lệch so với kỳ vọng, giới hạn
```

Mục chưa chạy ghi `NOT_RUN`. Giờ ghi theo UTC; lịch sử CLI hiển thị UTC+7.

## 3. Biên bản

| TC | Ngày (UTC) | Commit | Kết quả | Chi tiết |
|---|---|---|---|---|
| TC-SVC | 23/11/2026 | 87ba02d (VM1), 3e2388c (VM2) | PASS | Mục 4 |
| TC-CPU | 21/11/2026 | ef696a4 | PASS | `docs/cpu-e2e-check.md` |
| TC-DSK | 21/11/2026 | c51cd06 | PASS | `docs/disk-e2e-check.md` |

## 4. Biên bản TC-SVC

```
Mã TC:            TC-SVC (TST-02)
Ngày:             23/11/2026
Commit đang chạy: VM1 87ba02d, VM2 3e2388c (khác nhau chỉ ở docs/disk-e2e-check.md)
Lab:              VM1 monitoring, VM2 workload-vm2
Rule:             ServiceHttpDown, probe_success == 0 và up == 1, for 1m;
                  group_wait 30s, group_interval 2m, repeat_interval 15m

Trước:   5 service Up, webhook healthy; probe_success = 1, up = 1; không có alert
Gây lỗi: docker compose stop nginx, 19:49:21
Trong:   probe_success = 0, up = 1 từ 19:49:34; pending 19:49:49;
         firing startsAt 19:50:45; webhook nhận new 19:51:22 (episode 6)
Khôi phục: docker compose start nginx, 19:56:28
Sau:     probe_success = 1 từ 19:56:38; endsAt 19:56:45;
         webhook nhận resolve 19:57:22 cùng startsAt và fingerprint; episode 6 resolved

Kết quả: PASS
Ghi chú: từ lúc dừng nginx đến firing 1 phút 24 giây, đến webhook 2 phút 1 giây.
```
