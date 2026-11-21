# Kiểm tra filesystem gần đầy toàn luồng (DSK-01..05)

Ngày chạy: 21/11/2026, giờ UTC. Công cụ: `workload/scripts/disktest.sh` trên
VM2; rule `FilesystemAlmostFull` trong `monitoring/prometheus/rules/resources.yml`.

## Thiết kế

- Filesystem thử riêng: image 256 MiB tại `/var/lib/moni-disktest/disk.img`,
  ext4 `-m 0`, mount loop `nodev,nosuid,noexec` tại `/mnt/moni-disktest`, có
  file đánh dấu `.moni-disktest`. Không ghi vào `/etc/fstab`; không làm đầy
  phân vùng hệ thống.
- Mọi lệnh ghi/xóa kiểm tra mount là loop của đúng image và có file đánh dấu;
  sai thì dừng. `fill` chỉ cho mục tiêu 1–98%.
- Rule: `100 * (1 - avail / size) > 90` trong `2m`, bỏ `tmpfs|devtmpfs|overlay|
  squashfs|nsfs|ramfs|fuse.*` (filesystem ảo hoặc lớp container), chỉ đánh giá
  khi `up{job="node"} == 1`. Dùng `avail` vì đó là dung lượng ứng dụng thường
  còn ghi được. Ngưỡng/for là giá trị khởi đầu cho lab, chốt ở BSL-01.

## Kết quả

| Mốc | Giờ (UTC) |
|---|---|
| `setup`: nền `/` còn 6628 MiB, tạo image và mount `/dev/loop3` | 20:30:11 |
| `fill 95`: ghi 208 MiB | 20:33:03–20:33:06 |
| Prometheus thấy 95,3%, alert pending | ~20:33:31 |
| Alert firing (`startsAt`) | 20:35:31 |
| Webhook nhận `new` | 20:36:01 |
| `clean`: xóa dữ liệu thử, 96% → 1% | 20:39:00 |
| Alert hết (`endsAt`) | 20:39:16 |
| Webhook nhận `resolve` | 20:40:01 |
| `teardown`: unmount, xóa image | 20:40:40 |

- Trước khi ghi, `df -B1` trên VM2 và `node_filesystem_*` trên Prometheus khớp
  từng byte cho `/mnt/moni-disktest` (size 234594304, avail 229199872) và `/`.
  Ổ thử trống dùng 2,3% do metadata/journal của ext4. Mọi filesystem khác
  dưới 90%.
- Ba cách hiển thị cùng thời điểm: `findmnt` 93% (used/size), `df` 96%
  (used/(used+avail), làm tròn lên), Prometheus 95,3% (1 − avail/size).
- `fill 99` bị từ chối. Sau khi `umount` (mô phỏng reboot): `status` báo lỗi,
  `fill 95` từ chối ghi, `remount` gắn lại đúng image theo nhãn.
- Sau `teardown`: `/` trở về 6,5G trống (51%), như trước khi tạo.
- Lịch sử: 1 episode `FilesystemAlmostFull` (`new` → `resolve`), firing 3 phút 45 giây.

## Đối chiếu tiêu chí

| Issue | Tiêu chí | Kết quả |
|---|---|---|
| #52 DSK-01 | Filesystem riêng giới hạn; kiểm tra chỗ trống nền, không ghi đè; mục đích rõ | Đạt |
| #53 DSK-02 | Kiểm tra mount/fstype/backing image/dung lượng; đối chiếu metric trước khi ghi; sai mount thì dừng | Đạt |
| #54 DSK-03 | Query theo size/avail, loại fs ảo; ngưỡng/for, nhãn mountpoint; promtool; xử lý mất scrape | Đạt |
| #55 DSK-04 | Chỉ ghi vào filesystem đã xác minh, có giới hạn; dừng khi mount sai; ghi thời điểm | Đạt |
| #56 DSK-05 | Chỉ xóa dữ liệu thử; mức dùng giảm; unmount/xóa image; xử lý mất mount sau reboot | Đạt |

Không có ứng dụng nào ghi vào `/mnt/moni-disktest`, nên phép thử không chứng
minh lỗi ghi của ứng dụng; chỉ chứng minh phát hiện filesystem gần đầy.
