# ==========================================
# GIAI ĐOẠN 1: Builder - Cài đặt dependencies
# ==========================================
FROM python:3.11-slim-bookworm AS builder

# Thiết lập thư mục làm việc
WORKDIR /app

# Tận dụng công cụ 'uv' (Astral) để cài đặt dependency với tốc độ cực nhanh
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Sao chép các tệp định nghĩa dependency trước để tối ưu hóa bộ nhớ đệm (build cache)
COPY pyproject.toml uv.lock ./

# Tạo requirements.txt từ pyproject.toml và cài đặt dependencies vào hệ thống
# --no-dev giúp loại bỏ pytest và các thư viện phát triển khác, làm nhẹ container
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt


# ==========================================
# GIAI ĐOẠN 2: Runtime - Chạy ứng dụng chính
# ==========================================
FROM python:3.11-slim-bookworm

# Cài đặt thư viện hệ thống cần thiết (libgomp1 cho LightGBM / XGBoost)
# --no-install-recommends để tối ưu hóa dung lượng nhẹ nhất cho Docker Image
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc chính
WORKDIR /app

# Sao chép các package Python đã cài đặt từ giai đoạn builder sang
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Sao chép mã nguồn chính và module của dự án vào container
COPY src/ /app/src/
COPY main.py /app/main.py

# Sao chép file cấu hình làm fallback mặc định cho ứng dụng
COPY .env.example /app/.env

# Đặt biến môi trường mặc định (Có thể dễ dàng ghi đè bằng tham số -e khi khởi chạy Docker)
ENV PYTHONUNBUFFERED=1

# Khởi chạy pipeline chính
CMD ["python", "main.py"]
