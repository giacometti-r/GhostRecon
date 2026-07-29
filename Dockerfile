FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini

RUN pip install --upgrade pip \
    && pip install "."

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin ghostrecon
USER 10001

EXPOSE 8080

CMD ["uvicorn", "ghostrecon.service_apps.runtime:app", "--host", "0.0.0.0", "--port", "8080"]
