# Architecture Decision

## Quyết định

Prototype sử dụng hai VM.

VM1 chứa toàn bộ thành phần monitoring và lưu lịch sử sự kiện.

VM2 chứa workload, exporter và môi trường tạo lỗi.

## Lý do

- Cô lập máy giám sát khỏi máy thử lỗi.
- Blackbox kiểm tra dịch vụ từ một máy khác.
- Giảm độ phức tạp so với ba VM.
- Đủ để chứng minh thu thập, trực quan hóa, cảnh báo, lưu lịch sử và phục hồi.

## Giới hạn

Hai VM vẫn có thể dùng chung tài nguyên laptop và có điểm lỗi chung ở máy chủ VMware.
Mô hình này là prototype trong môi trường lab, chưa phải kiến trúc production high availability.
