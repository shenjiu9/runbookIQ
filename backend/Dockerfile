FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.8.4
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY runbookiq ./runbookiq

EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "runbookiq.runtime:app", "--host", "0.0.0.0", "--port", "8000"]
