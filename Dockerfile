# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ pkg-config libpq-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

COPY requirements/ /tmp/requirements/

RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /wheels && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/base.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/web.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/ml.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/test.txt

FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client libpq5 libffi8 libssl3 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

COPY --from=builder /wheels /wheels
COPY requirements/ /tmp/requirements/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/base.txt

COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/
COPY src/ /app/src/

RUN mkdir -p /home/app && \
    chown -R app:app /app /home/app && \
    chmod +x /app/src/worker/entrypoint.sh /app/src/web/entrypoint.sh

FROM base AS web
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/web.txt
USER app
EXPOSE 8050
ENTRYPOINT ["/app/src/web/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]

FROM base AS worker
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/ml.txt
USER app
ENTRYPOINT ["/app/src/worker/entrypoint.sh"]

FROM base AS test
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/test.txt
USER app