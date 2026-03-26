FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS=requirements/web.txt
ARG MODEL_DIR=ml/models/artifacts
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r $REQUIREMENTS

# run app processes as non-root (Celery warns when started as root)
RUN addgroup --system app && adduser --system --ingroup app app

# copy code
COPY --chown=app:app src/ /app/src/
# copy trained models (baked into image)
COPY --chown=app:app ${MODEL_DIR}/ /app/models/

RUN chown -R app:app /app
RUN chmod +x /app/src/worker/entrypoint.sh
RUN chmod +x /app/src/web/entrypoint.sh

# make /app/src importable: "import shared", "import web"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8050

# bootsrapping
ENTRYPOINT ["/app/src/web/entrypoint.sh"]

# default = web; compose overrides for worker
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]
