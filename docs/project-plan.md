# Kế hoạch triển khai điều chỉnh 12/11/2026

Bản điều chỉnh được người dùng yêu cầu áp dụng vào repository và GitHub.
Lab cá nhân vẫn hai VM; VM3 chỉ thêm cho lab tích hợp ở M3. Không publish
Webhook, lịch sử qua CLI/CSV. Giữ 16 issue cũ đã đóng; 64 issue đang mở được
xếp mốc và bổ sung 24 issue. Tạo/sửa task không phải bằng chứng hoàn thành.

## Các mốc

| Mốc | Hạn (Asia/Saigon) | Đầu ra |
| --- | --- | --- |
| M0 | 2026-11-15 | Cấu hình theo lab; job/host chung; sơ đồ/REQ; đo đối chiếu và minh chứng lượt thử rule. |
| M1 | 2026-11-25 | CPU, disk, service down qua Alertmanager → Webhook → SQLite, firing/resolved và minh chứng. |
| M2 | 2026-12-03 | podinfo, cAdvisor, cảnh báo tầng service/container và bốn dashboard. |
| M3 | 2026-12-10 | VM3 tích hợp, quan sát VM1, HostDown/inhibition kiểm thử, dự báo disk và kết luận baseline. |
| M4 | 2026-12-24 | Dựng lại độc lập, tài liệu/runbook, quyền/cổng, chốt phiên bản và giới hạn. |

Ngày là kế hoạch nhóm theo mô tả, chưa phải lịch nghiệm thu mentor/UTH.
NAB-01 tùy chọn gắn M4, OPT-01 tùy chọn chưa gán hạn. Không tự phân assignee.

## Thứ tự và phụ thuộc

Trong M1–M2, tổ chức rule theo `monitoring/prometheus/rules/host.yml`,
`service.yml`, `container.yml`, `collection.yml`; test tương ứng ở
`monitoring/prometheus/tests/`. M0 giữ `availability.yml` và test hiện có.
Khi chuyển rule cũ phải bỏ bản lặp, kiểm tra promtool và cập nhật runbook.
Blackbox thêm module riêng cho podinfo nếu điều kiện body khác Nginx;
không chỉ nới regex để mất khả năng phát hiện backend lỗi.

1. M0 ưu tiên STD-01/REF-01: .env → file_sd, cập nhật config/rule/dashboard
   cùng lúc; đo baseline sơ bộ từ đây. DES-02/03 vẽ hai phạm vi lab,
   REQ-00 lập bảng yêu cầu, MNT-01 ghi phản hồi vận hành của mentor.
2. M1 có ba luồng: ALT-05/06/07/09; DES-05/HIS-01 rồi HIS-02–08;
   CPU-01–04/DSK-01–05/DSH-05/06. DES-04 và TST-01 chuẩn bị xuyên suốt.
   Hội tụ ở HIS-09 rồi TST-02/03/04; không nghiệm thu chỉ vì container Up.
3. M2 thêm app/container; dùng metric phiên bản thật, baseline sơ bộ và
   ngưỡng provisional. BSL-01 ở M3 không phải phụ thuộc chặn ngược M1/M2.
4. M3 dựng VM3 trước HostDown; TST-16 thử HostDown trước khi dùng kết quả
   để chốt inhibition. Mỗi inhibit rule thử thêm lỗi độc lập host khác.
   BSL-01 chốt ngưỡng, FCT-01/TST-17 đánh giá ngoại suy disk.
5. M4 thử người nhận triển khai lại; phần nào chưa chạy ghi NOT_RUN.
   DOC-02 bao phủ cả cảnh báo mới; sơ đồ Use Case/sequence/ERD theo trạng thái cuối.

M1 gồm **30 issue cũ trong 10 ngày**. Nếu không đủ ba luồng, đề xuất dời
M1 tới 30/11 và thu gọn M2; chưa tự đổi deadline này. Giữ TST-02–04.

## Thu gọn khi trễ

Thứ tự xem xét hoãn theo mô tả: NAB-01 → OPS-01/02 → SVC-03/CTN-02 → VM3.
Hoãn một mục phải cập nhật các mục phụ thuộc: không nhận đạt TST-14/15
khi rule chưa có; VM3/HostDown/inhibition/TST-16 cần điều chỉnh cùng nhau.
Nếu hoãn backup/restore, HND-02 chỉ kiểm chứng phần lõi và công khai giới hạn.
Dự báo và KPI chỉ giữ nếu có đủ dữ liệu; không cắt minh chứng ba kịch bản.

## Issue cũ đang mở

| Mốc | Task |
| --- | --- |
| M0 | [STD-01 #68](https://github.com/HuynhHa17/Moni-Prototype/issues/68), [DES-02 #81](https://github.com/HuynhHa17/Moni-Prototype/issues/81), [DES-03 #82](https://github.com/HuynhHa17/Moni-Prototype/issues/82), [WKL-05 #9](https://github.com/HuynhHa17/Moni-Prototype/issues/9), [ALT-04 #32](https://github.com/HuynhHa17/Moni-Prototype/issues/32) |
| M1 | [ALT-05 #33](https://github.com/HuynhHa17/Moni-Prototype/issues/33), [ALT-06 #34](https://github.com/HuynhHa17/Moni-Prototype/issues/34), [ALT-07 #35](https://github.com/HuynhHa17/Moni-Prototype/issues/35), [ALT-09 #37](https://github.com/HuynhHa17/Moni-Prototype/issues/37), [HIS-01 #39](https://github.com/HuynhHa17/Moni-Prototype/issues/39), [HIS-02 #40](https://github.com/HuynhHa17/Moni-Prototype/issues/40), [HIS-03 #41](https://github.com/HuynhHa17/Moni-Prototype/issues/41), [HIS-04 #42](https://github.com/HuynhHa17/Moni-Prototype/issues/42), [HIS-05 #43](https://github.com/HuynhHa17/Moni-Prototype/issues/43), [HIS-06 #44](https://github.com/HuynhHa17/Moni-Prototype/issues/44), [HIS-07 #45](https://github.com/HuynhHa17/Moni-Prototype/issues/45), [HIS-08 #46](https://github.com/HuynhHa17/Moni-Prototype/issues/46), [HIS-09 #47](https://github.com/HuynhHa17/Moni-Prototype/issues/47), [DES-04 #83](https://github.com/HuynhHa17/Moni-Prototype/issues/83), [DES-05 #84](https://github.com/HuynhHa17/Moni-Prototype/issues/84), [CPU-01 #48](https://github.com/HuynhHa17/Moni-Prototype/issues/48), [CPU-02 #49](https://github.com/HuynhHa17/Moni-Prototype/issues/49), [CPU-03 #50](https://github.com/HuynhHa17/Moni-Prototype/issues/50), [CPU-04 #51](https://github.com/HuynhHa17/Moni-Prototype/issues/51), [DSK-01 #52](https://github.com/HuynhHa17/Moni-Prototype/issues/52), [DSK-02 #53](https://github.com/HuynhHa17/Moni-Prototype/issues/53), [DSK-03 #54](https://github.com/HuynhHa17/Moni-Prototype/issues/54), [DSK-04 #55](https://github.com/HuynhHa17/Moni-Prototype/issues/55), [DSK-05 #56](https://github.com/HuynhHa17/Moni-Prototype/issues/56), [TST-01 #57](https://github.com/HuynhHa17/Moni-Prototype/issues/57), [TST-02 #58](https://github.com/HuynhHa17/Moni-Prototype/issues/58), [TST-03 #59](https://github.com/HuynhHa17/Moni-Prototype/issues/59), [TST-04 #60](https://github.com/HuynhHa17/Moni-Prototype/issues/60), [DSH-05 #24](https://github.com/HuynhHa17/Moni-Prototype/issues/24), [DSH-06 #25](https://github.com/HuynhHa17/Moni-Prototype/issues/25) |
| M2 | [WKL-06 #10](https://github.com/HuynhHa17/Moni-Prototype/issues/10), [WKL-07 #11](https://github.com/HuynhHa17/Moni-Prototype/issues/11), [COL-07 #18](https://github.com/HuynhHa17/Moni-Prototype/issues/18), [COL-08 #19](https://github.com/HuynhHa17/Moni-Prototype/issues/19), [DSH-04 #23](https://github.com/HuynhHa17/Moni-Prototype/issues/23), [DSH-07 #26](https://github.com/HuynhHa17/Moni-Prototype/issues/26), [DSH-08 #27](https://github.com/HuynhHa17/Moni-Prototype/issues/27), [DSH-09 #28](https://github.com/HuynhHa17/Moni-Prototype/issues/28), [ALT-08 #36](https://github.com/HuynhHa17/Moni-Prototype/issues/36), [ALT-10 #38](https://github.com/HuynhHa17/Moni-Prototype/issues/38), [TST-05 #61](https://github.com/HuynhHa17/Moni-Prototype/issues/61), [TST-06 #62](https://github.com/HuynhHa17/Moni-Prototype/issues/62), [TST-07 #63](https://github.com/HuynhHa17/Moni-Prototype/issues/63) |
| M3 | [TST-08 #64](https://github.com/HuynhHa17/Moni-Prototype/issues/64), [TST-09 #65](https://github.com/HuynhHa17/Moni-Prototype/issues/65), [TST-10 #66](https://github.com/HuynhHa17/Moni-Prototype/issues/66), [TST-11 #67](https://github.com/HuynhHa17/Moni-Prototype/issues/67) |
| M4 | [STD-02 #69](https://github.com/HuynhHa17/Moni-Prototype/issues/69), [SEC-01 #70](https://github.com/HuynhHa17/Moni-Prototype/issues/70), [DOC-01 #71](https://github.com/HuynhHa17/Moni-Prototype/issues/71), [DOC-02 #72](https://github.com/HuynhHa17/Moni-Prototype/issues/72), [DOC-03 #73](https://github.com/HuynhHa17/Moni-Prototype/issues/73), [OPS-01 #74](https://github.com/HuynhHa17/Moni-Prototype/issues/74), [OPS-02 #75](https://github.com/HuynhHa17/Moni-Prototype/issues/75), [HND-01 #76](https://github.com/HuynhHa17/Moni-Prototype/issues/76), [HND-02 #77](https://github.com/HuynhHa17/Moni-Prototype/issues/77), [HND-03 #78](https://github.com/HuynhHa17/Moni-Prototype/issues/78), [DES-01 #80](https://github.com/HuynhHa17/Moni-Prototype/issues/80) |
| Tùy chọn | [OPT-01 #79](https://github.com/HuynhHa17/Moni-Prototype/issues/79) |

## 24 issue bổ sung

| Mã | Việc | Mốc | Phụ thuộc/ liên quan |
| --- | --- | --- | --- |
| [REF-01 #85](https://github.com/HuynhHa17/Moni-Prototype/issues/85) | Dùng job chung và nhãn host cho config, rule và dashboard | M0 | STD-01 |
| [REF-02 #86](https://github.com/HuynhHa17/Moni-Prototype/issues/86) | Chuẩn hóa UTF-8, LF và dọn placeholder thừa | M0 | — |
| [REQ-00 #87](https://github.com/HuynhHa17/Moni-Prototype/issues/87) | Lập bảng yêu cầu và liên kết với issue | M0 | — |
| [MNT-01 #88](https://github.com/HuynhHa17/Moni-Prototype/issues/88) | Hỏi mentor bốn vấn đề vận hành và ghi câu trả lời | M0 | — |
| [SVC-01 #89](https://github.com/HuynhHa17/Moni-Prototype/issues/89) | Thêm podinfo phía sau Nginx trên workload | M2 | WKL-01, REF-01 |
| [SVC-02 #90](https://github.com/HuynhHa17/Moni-Prototype/issues/90) | Probe endpoint ứng dụng qua Nginx và scrape podinfo | M2 | SVC-01, COL-06 |
| [SVC-03 #91](https://github.com/HuynhHa17/Moni-Prototype/issues/91) | Thêm rule ServiceHighErrorRate | M2 | SVC-02 |
| [CTN-01 #92](https://github.com/HuynhHa17/Moni-Prototype/issues/92) | Thêm rule ContainerDown theo container kỳ vọng | M2 | WKL-07, COL-07, REF-01 |
| [CTN-02 #93](https://github.com/HuynhHa17/Moni-Prototype/issues/93) | Rule ContainerHighMemory và container thử giới hạn RAM | M2 | WKL-07, COL-07 |
| [DSH-10 #94](https://github.com/HuynhHa17/Moni-Prototype/issues/94) | Dashboard Service: lưu lượng, lỗi, độ trễ và độ bão hòa | M2 | SVC-02, SVC-03, DSH-09 |
| [DSH-11 #95](https://github.com/HuynhHa17/Moni-Prototype/issues/95) | Dashboard Tổng quan và liên kết điều tra | M2 | DSH-09, DSH-10, ALT-10 |
| [TST-12 #96](https://github.com/HuynhHa17/Moni-Prototype/issues/96) | Dừng một container và xác minh ContainerDown | M2 | CTN-01, HIS-09 |
| [TST-13 #97](https://github.com/HuynhHa17/Moni-Prototype/issues/97) | Gây lỗi ứng dụng khi container vẫn chạy | M2 | SVC-02, HIS-09 |
| [TST-14 #98](https://github.com/HuynhHa17/Moni-Prototype/issues/98) | Gây lỗi một phần và kiểm tra tỷ lệ lỗi dịch vụ | M2 | SVC-03, DSH-10, HIS-09 |
| [TST-15 #99](https://github.com/HuynhHa17/Moni-Prototype/issues/99) | Vượt ngưỡng RAM container có giới hạn và khôi phục | M2 | CTN-02, HIS-09 |
| [VM3-01 #100](https://github.com/HuynhHa17/Moni-Prototype/issues/100) | Dựng VM3 workload cho lab tích hợp bằng Compose chung | M3 | REF-01, SVC-02, COL-07 |
| [MON-01 #101](https://github.com/HuynhHa17/Moni-Prototype/issues/101) | Giám sát VM1 và ghi giới hạn khi monitoring dừng | M3 | REF-01, ALT-05, HIS-08 |
| [HST-01 #102](https://github.com/HuynhHa17/Moni-Prototype/issues/102) | Định nghĩa HostDown bằng tín hiệu độc lập có kiểm chứng | M3 | VM3-01, ALT-10 |
| [INH-01 #103](https://github.com/HuynhHa17/Moni-Prototype/issues/103) | Ức chế theo tầng với từng quy tắc được kiểm thử | M3 | HST-01, CTN-01, ALT-07, TST-16 |
| [FCT-01 #104](https://github.com/HuynhHa17/Moni-Prototype/issues/104) | Dự báo filesystem gần đầy bằng predict_linear | M3 | DSK-03, BSL-01 |
| [BSL-01 #105](https://github.com/HuynhHa17/Moni-Prototype/issues/105) | Đo baseline và chốt ngưỡng với mentor/UTH | M3 | WKL-05, TST-01, MNT-01 |
| [TST-16 #106](https://github.com/HuynhHa17/Moni-Prototype/issues/106) | Tắt một workload VM và kiểm tra cảnh báo theo host | M3 | VM3-01, HST-01, HIS-09 |
| [TST-17 #107](https://github.com/HuynhHa17/Moni-Prototype/issues/107) | Ghi đầy từ từ filesystem thử để đánh giá dự báo | M3 | FCT-01, DSK-05, HIS-09 |
| [NAB-01 #108](https://github.com/HuynhHa17/Moni-Prototype/issues/108) | Phân tích NAB ngoại tuyến nếu mentor xác nhận | M4 (tùy chọn) | MNT-01, HND-03 |

## Kiểm chứng và báo cáo tiến độ

Mỗi task giữ trạng thái Open tới khi có sản phẩm và minh chứng theo tiêu chí.
PR code không đóng tự động task vận hành/sơ đồ/chuyển giao. Đối chiếu
[yêu cầu](requirements.md) và [kết quả kiểm tra](validation.md). Lưu commit,
lab, lệnh, giá trị trước/trong/sau và timestamp thực tế; không dựng lại lịch sử.
Dashboard Host ở M0 mới là nền; Container/Service/Tổng quan thuộc M2.
