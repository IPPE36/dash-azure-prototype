FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY src/ /app/src/

# make /app/src importable: "import shared", "import web"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8050

# default = web; compose overrides for worker
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server", "--workers", "2", "--threads", "4"]