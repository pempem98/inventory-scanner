#!/bin/bash

# ====================================================================
# SCRIPT TỰ ĐỘNG BUILD VÀ DEPLOY ỨNG DỤNG DJANGO BẰNG DOCKER (Nâng cao)
#
# Cho phép chạy từng bước hoặc chạy từ một bước nhất định.
#
# Hướng dẫn sử dụng: ./deploy.sh [tham_số]
#   - Không có tham số: Chạy tất cả các bước (clean -> build -> run).
#   - clean:         Chỉ dọn dẹp container cũ.
#   - build:         Chỉ build image.
#   - run:           Chỉ chạy container (phải có image đã build).
#   - from-build:    Chạy từ bước build đến hết (build -> run).
# ====================================================================

# --- Cấu hình ---
IMAGE_NAME="saleadmintoolkit"
CONTAINER_NAME="saleadmintoolkit-container"
HOST_PORT="8888"
CONTAINER_PORT="8000"
# ---------------------------------------------------------

# Dừng script ngay khi có lỗi
set -e

# Hàm hiển thị hướng dẫn sử dụng
show_usage() {
    echo "Sử dụng không hợp lệ!"
    echo "Cách dùng: $0 [clean|build|run|from-build]"
    echo "  (để trống)    - Chạy tất cả các bước: Dọn dẹp, Build và Chạy."
    echo "  clean         - Bước 1: Chỉ dừng và xóa container cũ."
    echo "  build         - Bước 2: Chỉ build Docker image."
    echo "  run           - Bước 3: Chỉ chạy container mới (yêu cầu image đã tồn tại)."
    echo "  from-build    - Chạy từ Bước 2: Build image rồi chạy container."
    exit 1
}

# Bước 1: Dọn dẹp container cũ
cleanup() {
    echo "--- Bước 1: Dọn dẹp container cũ ---"
    if [ "$(docker ps -a -q -f name=${CONTAINER_NAME})" ]; then
        echo "Phát hiện container cũ '${CONTAINER_NAME}'. Đang dừng và xóa..."
        docker stop ${CONTAINER_NAME}
        docker rm ${CONTAINER_NAME}
        echo "Đã xóa container cũ."
    else
        echo "Không tìm thấy container cũ. Bỏ qua."
    fi
}

# Bước 2: Build Docker image
build_image() {
    echo "--- Bước 2: Build Docker image ---"
    echo "Đang build image '${IMAGE_NAME}:latest'..."
    docker build -t ${IMAGE_NAME}:latest .
    echo "Build image thành công!"
}

# Bước 3: Chạy container mới
run_container() {
    echo "--- Bước 3: Chạy container mới ---"
    echo "Đang chạy container '${CONTAINER_NAME}'..."
    docker run -d -p ${HOST_PORT}:${CONTAINER_PORT} --env-file .env --name ${CONTAINER_NAME} ${IMAGE_NAME}:latest
    echo ""
    echo "--- HOÀN TẤT! ---"
    echo "Container của bạn đang chạy."
    echo "Truy cập ứng dụng tại: http://localhost:${HOST_PORT}"
    echo "Kiểm tra trạng thái: docker ps | grep ${CONTAINER_NAME}"
    echo "Xem log: docker logs ${CONTAINER_NAME}"
}


echo "================================================="
# $1 là tham số đầu tiên được truyền vào script
case "$1" in
    "") # Nếu không có tham số, chạy tất cả
        echo "Không có tham số. Chạy tất cả các bước..."
        cleanup
        build_image
        run_container
        ;;
    "clean") # Chỉ chạy bước dọn dẹp
        cleanup
        ;;
    "build") # Chỉ chạy bước build
        build_image
        ;;
    "run") # Chỉ chạy bước chạy container
        run_container
        ;;
    "from-build") # Chạy từ bước build đến hết
        echo "Chạy từ bước build đến hết..."
        build_image
        run_container
        ;;
    *) # Nếu tham số không hợp lệ, hiển thị hướng dẫn
        show_usage
        ;;
esac

echo "================================================="
echo "Script đã thực thi xong."