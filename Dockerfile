# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder
WORKDIR /app

ENV PIP_CACHE_DIR=/root/.cache/pip \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    pkg-config \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

COPY requirements/ /tmp/requirements/

# Build all local/offline wheels up front.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /wheels && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/base.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/web.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/ml.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/test.txt

# Build a reusable torch wheelhouse separately so the worker stage
# does not need to hit the network during its own install step.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /torch-wheels && \
    pip wheel \
      --wheel-dir /torch-wheels \
      --index-url https://download.pytorch.org/whl/cpu \
      torch

FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    PIP_CACHE_DIR=/home/app/.cache/pip \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    libffi8 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && \
    adduser --system --ingroup app --home /home/app app && \
    mkdir -p /home/app/.cache/pip && \
    chown -R app:app /home/app

COPY --from=builder /wheels /wheels
COPY --from=builder /torch-wheels /torch-wheels
COPY requirements/ /tmp/requirements/

# Install the stable shared base dependencies first.
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/base.txt

# Copy code after dependency installation for better layer reuse.
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/
COPY src/ /app/src/

RUN chown -R app:app /app /home/app && \
    chmod +x /app/src/worker/entrypoint.sh /app/src/web/entrypoint.sh

################
# Web image    
################
FROM base AS web
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/web.txt
USER app
EXPOSE 8050
ENTRYPOINT ["/app/src/web/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]

################
# Torch layer  
################
# Separate stage so the expensive torch install is cached independently
# from app code and model artifact copies.
FROM base AS worker-deps
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/torch-wheels torch
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/ml.txt

################
# Worker image 
################
FROM worker-deps AS worker
# Put frequently changing artifacts as late as possible so they do not
# invalidate dependency installation layers.
COPY ml/models/artifacts/ /app/ml/models/artifacts/
RUN chown -R app:app /app/ml /home/app
USER app
ENTRYPOINT ["/app/src/worker/entrypoint.sh"]

################
# Test image   
################
FROM base AS test
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/test.txt
USER app