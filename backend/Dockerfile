FROM python:3.11-slim

# System deps: tesseract for OCR, libgl for OpenCV/PIL
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency spec first for Docker layer caching
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Copy application code
COPY . .

EXPOSE 7860

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
