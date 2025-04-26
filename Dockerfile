# Sử dụng image Python chính thức
FROM python:3.9-slim

# Đặt thư mục làm việc
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho requests-kerberos
RUN apt-get update && apt-get install -y \
    gcc \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ project vào container
COPY . .

# Đặt biến môi trường cho proxy
ENV HTTP_PROXY=http://rb-proxy-apac.bosch.com:8080
ENV HTTPS_PROXY=http://rb-proxy-apac.bosch.com:8080
ENV NO_PROXY=localhost,127.0.0.1

# Lệnh mặc định để chạy ExcelBackupExtractor.py
CMD ["python", "ExcelBackupExtractor.py"]