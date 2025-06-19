# Sử dụng image Python chính thức
FROM python:3.12.6

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    gcc \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt trước để tận dụng cache của Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của project vào thư mục làm việc
COPY . .

# Đặt biến môi trường cho proxy (giữ nguyên)
# ENV HTTP_PROXY=http://rb-proxy-apac.bosch.com:8080
# ENV HTTPS_PROXY=http://rb-proxy-apac.bosch.com:8080
# ENV NO_PROXY=localhost,127.0.0.1

# Cấp quyền thực thi cho entry point script
RUN chmod +x /app/entry_point.sh

# Lệnh mặc định để chạy ứng dụng
ENTRYPOINT ["/app/entry_point.sh"]