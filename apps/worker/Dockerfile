FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/cortex

COPY api /srv/cortex/api
COPY worker /srv/cortex/worker

RUN pip install --no-cache-dir /srv/cortex/api /srv/cortex/worker

RUN useradd --create-home --uid 10001 cortex
USER cortex

CMD ["python", "-m", "worker.main"]
