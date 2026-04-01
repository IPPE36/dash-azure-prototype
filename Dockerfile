# syntax=docker/dockerfile:1.7

############################
# Wheel builder
############################
FROM python:3.11-slim AS builder
WORKDIR /build

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

# Copy requirement files individually so changing one does not invalidate all
COPY requirements/base.txt /tmp/requirements/base.txt
COPY requirements/web.txt /tmp/requirements/web.txt
COPY requirements/ml.txt /tmp/requirements/ml.txt
COPY requirements/test.txt /tmp/requirements/test.txt

# Build offline wheelhouse for normal dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /wheels && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/base.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/web.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/ml.txt && \
    pip wheel --wheel-dir /wheels -r /tmp/requirements/test.txt

# Build torch separately so worker dependency caching is more stable
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /torch-wheels && \
    pip wheel \
      --wheel-dir /torch-wheels \
      --index-url https://download.pytorch.org/whl/cpu \
      torch


############################
# Runtime OS + shared deps only
############################
FROM python:3.11-slim AS runtime-base
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

# Copy requirement files individually for better cache granularity
COPY requirements/base.txt /tmp/requirements/base.txt
COPY requirements/web.txt /tmp/requirements/web.txt
COPY requirements/ml.txt /tmp/requirements/ml.txt
COPY requirements/test.txt /tmp/requirements/test.txt

# Install only the shared base dependencies here
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/base.txt


############################
# App source layer
############################
FROM runtime-base AS app-base

# Copy app code only here, after dependency layers
COPY --chown=app:app alembic.ini /app/alembic.ini
COPY --chown=app:app alembic/ /app/alembic/
COPY --chown=app:app src/ /app/src/

RUN chmod +x /app/src/worker/entrypoint.sh /app/src/web/entrypoint.sh


############################
# Web dependency layer
############################
FROM runtime-base AS web-deps
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/web.txt


############################
# ML dependency layer
############################
FROM runtime-base AS worker-deps
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/torch-wheels torch

RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/ml.txt


############################
# Test dependency layer
############################
FROM runtime-base AS test-deps
RUN --mount=type=cache,target=/home/app/.cache/pip \
    pip install --no-index --find-links=/wheels -r /tmp/requirements/test.txt


############################
# Web image
############################
FROM web-deps AS web

COPY --from=app-base /app /app

USER app
EXPOSE 8050
ENTRYPOINT ["/app/src/web/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]


############################
# Worker image
############################
FROM worker-deps AS worker

COPY --from=app-base /app /app

# Keep frequently changing model artifacts late
COPY --chown=app:app ml/models/artifacts/ /app/ml/models/artifacts/

USER app
ENTRYPOINT ["/app/src/worker/entrypoint.sh"]


############################
# Test image
############################
FROM test-deps AS test

COPY --from=app-base /app /app

USER app