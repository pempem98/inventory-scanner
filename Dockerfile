# Sử dụng image Python chính thức
FROM python:3.12.6-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho các thư viện Python
RUN apt-get update && apt-get install -y \
    gcc \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt trước để tận dụng cache của Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của project vào thư mục làm việc
COPY . .
