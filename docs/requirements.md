# Yêu cầu và tiêu chí kiểm chứng

Nguồn: đề bài N4 người dùng cung cấp và bản điều chỉnh 12/11/2026. Bảng
này là nơi tra mã REQ, không tạo các issue giả REQ-02/03/04. REQ-00 quản lý
bảng; code task/issue và milestone nằm trong [kế hoạch](project-plan.md).

| Mã | Yêu cầu và nguồn | Tiêu chí/bằng chứng | Task chính |
| --- | --- | --- | --- |
| <a id="req-01"></a>REQ-01 | N4: prototype lab; nhóm: hai VM cá nhân, thêm VM3 tích hợp M3 | Sơ đồ triển khai/luồng metric-alert-history, inventory, quyết định và giới hạn. Không yêu cầu Cloud/GPU/DC thật | DES-02/03, VM3-01, DOC-01 |
| <a id="req-02"></a>REQ-02 | N4: CPU, RAM, disk, network, uptime, endpoint; phạm vi nhóm thêm container | Query, đơn vị, đúng host/mount/interface/container và đối chiếu Linux. up là scrape, uptime từ boot time; metric hiển thị theo thời gian | WKL-05/07, COL-07/08, DSH-04–09 |
| <a id="req-03"></a>REQ-03 | N4: luật cảnh báo kiểm thử được; nhóm: phân biệt lỗi dịch vụ/thu thập | Ngưỡng/for có cơ sở, pending/firing/resolved, thông báo đủ đối tượng/điều kiện/ảnh hưởng/bước kiểm tra; HTTP mất scrape là unknown | ALT-01–10, CPU-01/02, DSK-03, BSL-01 |
| <a id="req-04"></a>REQ-04 | N4: ít nhất ba demo và đánh giá thời gian phát hiện | CPU cao, filesystem gần đầy/đầy giả lập, service down; ghi trước/trong/sau, metric, firing, nhận thông báo, lịch sử và phục hồi. Lặp 3–5 lần cho ca đo toàn luồng; so lý thuyết và sai số | TST-01–11, CPU-03/04, DSK-01–05 |
| <a id="req-05"></a>REQ-05 | N4: dashboard theo host/service và lịch sử; nhóm chọn CLI/CSV | Dashboard version control; episode/sự kiện SQLite, fingerprint+startsAt, source/received time, chống trùng, đúng thứ tự firing/resolved, còn dữ liệu qua restart. CLI đọc/xuất, không yêu cầu HTML | HIS-01–09, DES-05, TST-08–10 |
| <a id="req-06"></a>REQ-06 | N4: runbook và tái lập | Repo, cấu hình theo lab/commit, sơ đồ nguồn, test/kết quả, hướng dẫn; người nhận tự dựng hai VM sạch và chạy demo. Mục mở rộng ba VM riêng | STD-01/02, DOC-01–03, HND-01–03, DES-01 |
| <a id="req-07"></a>REQ-07 | N4: môi trường được quản lý/cấp phép, không credential production | Secret/runtime ngoài Git; filesystem thử riêng và dừng khi mount sai; tải giới hạn; cổng/quyền thật được kiểm tra, Webhook không publish | SEC-01, DSK-01/02/04/05, ALT-09 |
| <a id="req-08"></a>REQ-08 | Nhóm bổ sung M2: ứng dụng thực và tầng container/service | Nginx → podinfo; probe chức năng và scrape ứng dụng; ContainerDown, ContainerHighMemory, ServiceHighErrorRate; bốn dashboard Tổng quan/Host/Container/Service | SVC-01–03, CTN-01/02, DSH-10/11, TST-12–15 |
| <a id="req-09"></a>REQ-09 | Nhóm bổ sung M3: nhiều host và tương quan cảnh báo | VM3 dùng Compose chung, giám sát VM1, HostDown có reachability độc lập; inhibition chỉ bật từng quan hệ có test, không che lỗi host khác | VM3-01, MON-01, HST-01, INH-01, TST-16 |
| <a id="req-10"></a>REQ-10 | Nhóm bổ sung M3: minh họa dự báo disk | predict_linear có cửa sổ, chân trời, guard dữ liệu/xu hướng và kết quả ghi đều có giới hạn; không thay bằng dữ liệu mô phỏng rồi gọi là metric lab | FCT-01, BSL-01, TST-17 |
| <a id="req-11"></a>REQ-11 | Tùy chọn: NAB ngoại tuyến, CI; vận hành mở rộng tùy tiến độ | Chỉ NAB khi mentor xác nhận, tách kết quả ngoại tuyến với VM. Backup/restore nếu hoãn phải ghi hạn chế, không tuyên bố đã kiểm chứng | NAB-01, OPT-01, OPS-01/02 |

## Ngưỡng và KPI

Đề bài yêu cầu chỉ tiêu định lượng thống nhất với UTH và mentor sau khi
chốt dữ liệu. Chưa có phản hồi đó thì ghi **chưa thống nhất**, không tự
ghi SLA. `for: 1m` của rule HTTP hiện tại là tham số lab khởi đầu.
CPU/disk dùng provisional khi triển khai M1. Baseline bắt đầu ghi từ M0/M1,
không đợi M3; BSL-01 tổng kết, đề xuất và ghi phê duyệt/điều chỉnh ở M3.

Mỗi ca ghi commit, lab/inventory, ngưỡng, cửa sổ rate, scrape/evaluation
interval, group_wait/group_interval, lệnh thử và các timestamp đồng bộ giờ:

1. Gây lỗi/tín hiệu bất thường.
2. Quan sát metric, pending và firing.
3. Webhook thực sự nhận (khác thời điểm alert startsAt).
4. Thao tác khôi phục, tín hiệu kiểm tra mới đạt và resolved nhận/lưu.

Tổng hợp min/median/max và sai số 3–5 lượt của ca đo. Ca retry/sai thứ tự
đánh giá tính đúng lịch sử riêng. Thử rule bằng dữ liệu synthetic chưa
chứng minh latency hay gửi cảnh báo trên VM thật.

## Giới hạn diễn giải

HTTP 200 của health tĩnh Nginx chưa chứng minh podinfo/nghiệp vụ; điều kiện
endpoint ứng dụng phải được xác định ở SVC-02. ExporterDown chưa chứng minh
host tắt. Alert resolved vì mất dữ liệu/thay config chưa chứng minh phục hồi.
Cả ba VM chung laptop không có HA; stack không tự báo khi VM1 đã tắt.
Phân tích NAB/AI hoặc Cloud/GPU không phải điều kiện bắt buộc của ba demo N4.
