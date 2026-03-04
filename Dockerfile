FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# run app processes as non-root (Celery warns when started as root)
RUN addgroup --system app && adduser --system --ingroup app app

# copy code
COPY --chown=app:app src/ /app/src/
RUN chown -R app:app /app

# make /app/src importable: "import shared", "import web"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

USER app

EXPOSE 8050

# default = web; compose overrides for worker
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]
