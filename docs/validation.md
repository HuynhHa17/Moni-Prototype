# Kiểm tra thay đổi nền M0 — 12/11/2026

Nền so sánh: `origin/main` tại `d8356ec` (PR service-down alert đã merge).
Nhánh: `chore/align-project-scope`. Đây là kiểm tra mã nguồn trên Windows,
không phải nghiệm thu triển khai Linux VM.

| Hạng mục | Kết quả |
| --- | --- |
| Renderer file_sd | 7 unittest đạt: inventory cá nhân, hai workload, IPv6, IP/port/host không hợp lệ và trùng, giữ file cũ khi input sai, không thực thi biểu thức, không xuất secret không liên quan |
| Compose | `docker compose --env-file .env.example -f monitoring/compose.yaml config -q` và workload đạt, không khởi chạy container |
| Prometheus | promtool v3.5.0 check config đạt trên fixture tạm; chỉ đổi đường dẫn mount Linux sang đường dẫn local, dùng IP tài liệu trong inventory |
| Rule | promtool check rules đạt; 3 bài synthetic đạt: hai host với một lỗi và đủ for, scrape lỗi không quy HTTP down, probe mới thành công thì alert hết firing |
| Dashboard | 8 biểu thức được promtool parse/evaluate trên fixture rỗng, gồm unknown fallback; JSON Host có biến host và UID cũ |
| Định dạng | UTF-8 không BOM, LF theo .gitattributes; git diff --check đạt |
| Yêu cầu/kế hoạch | Đối chiếu 64 issue cũ đang mở và 24 task bổ sung; giữ 16 issue cũ đã đóng, không dùng PR để tự đóng task VM |

## Chạy lại

```bash
python3 -m unittest discover -s tests -v
docker compose --env-file .env.example -f monitoring/compose.yaml config -q
docker compose --env-file .env.example -f workload/compose.yaml config -q
promtool check rules monitoring/prometheus/rules/availability.yml
promtool test rules monitoring/prometheus/tests/availability.test.yml
```

Trong Linux chạy promtool check config với container như setup.md để kiểm
tra đúng bind mount. `.env.example` có CHANGE_ME cố ý, cần `.env` thật
và render trước khởi chạy; không triển khai fixture `192.0.2.*`.

## Chưa kiểm chứng

- Chưa áp dụng bản M0 này lên VM1/VM2; chưa kiểm tra quyền file_sd trên
  filesystem Linux thật hoặc giao diện dashboard Grafana sau nâng cấp.
- Chưa dựng VM3, podinfo, cAdvisor, Alertmanager, Webhook/SQLite trong nhánh
  này; nội dung M1–M4 là kế hoạch và issue có tiêu chí, không phải code đã chạy.
- CPU/disk/service toàn luồng, retry/lịch sử, HostDown/inhibition, dự báo,
  baseline, bàn giao và các kênh thông báo vẫn NOT_RUN nếu chưa có bằng chứng.
- Chưa có phê duyệt ngưỡng/KPI từ mentor/UTH hoặc kết quả đo baseline để tự
  ghi đạt. MNT-01 là task người dùng trao đổi, không tự gửi tin tới mentor.
- Cổng lab vẫn theo mặc định ban đầu; SEC-01 phải kiểm tra firewall/auth/
  đường mạng thực tế. Không mô tả hạn chế truy cập dự kiến là đã áp dụng.

Thay job/nhãn có thể bắt đầu lại thời gian for và tạo chuỗi thời gian mới.
Xác nhận phục hồi bằng metric mới; alert hết firing do đổi cấu hình không
phải bằng chứng dịch vụ đã phục hồi. Không xóa volume khi nâng cấp.
