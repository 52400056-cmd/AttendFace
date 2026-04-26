# FaceAttend - Hệ thống Điểm danh bằng Nhận diện Khuôn mặt

FaceAttend là một hệ thống quản lý lớp học và điểm danh tự động bằng nhận diện khuôn mặt ứng dụng mô hình MobileNetV6. Hệ thống cho phép điểm danh theo thời gian thực thông qua Camera, quản lý số buổi vắng, và tự động cảnh báo/cấm thi sinh viên vượt quá số buổi quy định.

---

## Yêu cầu
Trước khi chạy dự án, hãy đảm bảo máy tính đã cài đặt sẵn:
- **[Docker](https://www.docker.com/products/docker-desktop/)**

---

## Hướng dẫn cài đặt và khởi chạy

Dự án đã được đóng gói hoàn toàn bằng docker.

### Khởi chạy hệ thống bằng Docker
Mở Terminal tại thư mục source:

```bash
docker-compose up -d --build