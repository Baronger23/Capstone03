# ── Stage 1: Build dependencies ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Cài hệ thống lib cần cho psycopg2-binary và grpcio
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và install vào prefix riêng để tránh pollute system Python
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production image ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Cài runtime lib cho psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy đã-cài packages từ builder
COPY --from=builder /install /usr/local

# Patch fixable HIGH CVEs in build tooling that ships in the base image's SYSTEM
# site-packages (not covered by requirements.txt, and left behind as stale dist-info when
# the builder's patched copy is layered on top). Upgrade to the fixed versions and delete
# the old dist-info so Trivy's fixable gate sees only the patched versions.
#   wheel 0.45.1 -> 0.46.2 (CVE-2026-24049), jaraco.context 5.3.0 -> 6.1.0 (CVE-2026-23949)
RUN pip install --no-cache-dir --upgrade "wheel>=0.46.2" "jaraco.context>=6.1.0" \
    && rm -rf /usr/local/lib/python3.11/site-packages/wheel-0.45.1.dist-info \
              /usr/local/lib/python3.11/site-packages/jaraco*context-5.3.0.dist-info

# Copy toàn bộ source code của copilot
COPY src/       ./src/
COPY static/    ./static/
COPY contracts/ ./contracts/

# Tạo thư mục data cho session/cache files
RUN mkdir -p /app/data

# Port API
EXPOSE 8001

# Chạy với non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

# Entrypoint
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
