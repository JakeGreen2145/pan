FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import pan; print('ok')" || exit 1

CMD ["python", "-m", "pan"]
