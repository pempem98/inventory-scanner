#!/bin/bash

# Script triển khai ứng dụng sử dụng Docker Compose.
# Dừng các container cũ, xây dựng lại image và khởi động lại toàn bộ hệ thống.

echo "==== Pulling latest changes from Git... ===="
# (Tùy chọn) Lấy code mới nhất từ repository của bạn
git pull origin production

echo "==== Stopping and removing old containers... ===="
# Dừng và xóa tất cả các container được định nghĩa trong docker-compose.yml
# Lệnh này sẽ không xóa database volume của bạn.
docker-compose down

echo "==== Building new images and starting services... ===="
# Xây dựng lại image cho các dịch vụ có tag 'build' và khởi động toàn bộ hệ thống
# ở chế độ nền (-d).
docker-compose up --build -d

echo "==== Deployment complete. Application is running. ===="
echo "To view logs, run: docker-compose logs -f"
