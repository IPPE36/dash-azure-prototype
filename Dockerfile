FROM python:3.11-slim
# use alpine instead of slim?

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS=requirements/web.txt
ARG MODEL_DIR=ml/models/artifacts
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r $REQUIREMENTS

# run app processes as non-root (Celery warns when started as root)
RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

# copy code
COPY --chown=app:app src/ /app/src/
# copy alembic config and migrations
COPY --chown=app:app alembic.ini /app/alembic.ini
COPY --chown=app:app alembic/ /app/alembic/
# copy trained models (baked into image)
COPY --chown=app:app ${MODEL_DIR}/ /app/models/

RUN chown -R app:app /app
RUN mkdir -p /home/app && chown -R app:app /home/app
RUN chmod +x /app/src/worker/entrypoint.sh
RUN chmod +x /app/src/web/entrypoint.sh

# make /app/src importable: "import shared", "import web"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOME=/home/app

USER app

EXPOSE 8050

# bootsrapping
ENTRYPOINT ["/app/src/web/entrypoint.sh"]

# default = web; compose overrides for worker
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]
