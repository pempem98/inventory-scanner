#!/bin/bash

# ====================================================================
# SCRIPT TỰ ĐỘNG BUILD VÀ DEPLOY ỨNG DỤNG DJANGO BẰNG DOCKER
#
# Hướng dẫn sử dụng:
# 1. Lưu file này với tên deploy.sh trong thư mục gốc của project
#    (cùng cấp với Dockerfile).
# 2. Mở terminal, cấp quyền thực thi cho file: chmod +x deploy.sh
# 3. Chạy script: ./deploy.sh
# ====================================================================

# --- CẤU HÌNH (Bạn có thể thay đổi các giá trị này) ---
IMAGE_NAME="saleadmintoolkit"
CONTAINER_NAME="saleadmintoolkit-container"
HOST_PORT="8888"
CONTAINER_PORT="8000"
# ---------------------------------------------------------

# Dòng này đảm bảo script sẽ dừng ngay lập tức nếu có bất kỳ lệnh nào thất bại
set -e

echo "--- Bắt đầu quy trình deploy ---"

# Bước 1: Dừng và xóa container cũ nếu nó tồn tại
# '-q' chỉ lấy ID container, '-f name=' lọc theo tên chính xác.
# '[ ... ]' kiểm tra xem lệnh bên trong có trả về output hay không.
if [ "$(docker ps -a -q -f name=${CONTAINER_NAME})" ]; then
    echo "Phát hiện container cũ '${CONTAINER_NAME}'. Đang dừng và xóa..."
    docker stop ${CONTAINER_NAME}
    docker rm ${CONTAINER_NAME}
    echo "Đã xóa container cũ."
else
    echo "Không tìm thấy container cũ. Bỏ qua bước xóa."
fi

# Bước 2: Build Docker image mới
# '-t' đặt tên cho image. '.' chỉ định build từ thư mục hiện tại.
echo "=========================================="
echo "Đang build Docker image mới: ${IMAGE_NAME}:latest"
echo "=========================================="
docker build -t ${IMAGE_NAME}:latest .
echo "Build image thành công!"

# Bước 3: Chạy container mới từ image vừa build
# '-d' chạy ở chế độ nền (detached)
# '-p' ánh xạ cổng (port mapping)
# '--name' đặt tên cho container
echo "=========================================="
echo "Đang chạy container mới: ${CONTAINER_NAME}"
echo "=========================================="
docker run -d -p ${HOST_PORT}:${CONTAINER_PORT} --name ${CONTAINER_NAME} ${IMAGE_NAME}:latest

echo ""
echo "--- HOÀN TẤT! ---"
echo "Container của bạn đang chạy."
echo "Truy cập ứng dụng tại: http://localhost:${HOST_PORT}"
echo ""
echo "Sử dụng lệnh sau để xem trạng thái: docker ps"
echo "Sử dụng lệnh sau để xem log: docker logs ${CONTAINER_NAME}"