#!/bin/bash

# --- Cấu hình ---
# Thư mục để lưu trữ các tệp log. Script sẽ tự động tạo thư mục này nếu chưa có.
LOG_DIR="./logs"

# Danh sách các tên container cần theo dõi log.
CONTAINERS=(
    "web-worker"
    "web-beat"
    "web-app"
)

# Tạo thư mục log nếu nó chưa tồn tại
mkdir -p "$LOG_DIR"

echo "📝 Đang bắt đầu quá trình ghi log..."

for container in "${CONTAINERS[@]}"; do
    LOG_FILE="$LOG_DIR/${container}.log"
    
    # Kiểm tra xem có tiến trình `docker logs` nào đang chạy cho container này chưa.
    if pgrep -f "docker logs -f ${container}" > /dev/null; then
        echo "🔵 Tiến trình ghi log cho container '$container' đã chạy rồi."
    else
        echo "🟢 Bắt đầu ghi log cho container '$container'. Log sẽ được lưu tại: $LOG_FILE"
        # - `nohup`: Chạy lệnh trong nền và giữ cho nó chạy ngay cả khi bạn đóng terminal.
        # - `docker logs -f`: Theo dõi (follow) và hiển thị log của container.
        # - `>> "$LOG_FILE"`: Chuyển hướng đầu ra và GHI TIẾP (append) vào tệp log.
        #   Điều này đảm bảo log cũ không bị mất khi bạn chạy lại script.
        # - `2>&1`: Chuyển hướng đầu ra lỗi tiêu chuẩn (stderr) vào cùng nơi với stdout.
        # - `&`: Chạy lệnh trong nền.
        nohup docker logs -f ${container} >> "$LOG_FILE" 2>&1 &
    fi
done

echo "--------------------------------------------------"
echo "✅ Hoàn tất! Tất cả các tiến trình ghi log đã được kiểm tra hoặc khởi động."
echo "📂 Bạn có thể tìm thấy các tệp log trong thư mục: '$LOG_DIR'"
echo ""
echo "👉 Để xem log trực tiếp, sử dụng lệnh: tail -f $LOG_DIR/web-app.log"
echo "👉 Để dừng TẤT CẢ các tiến trình ghi log, sử dụng lệnh: pkill -f 'docker logs -f'"


