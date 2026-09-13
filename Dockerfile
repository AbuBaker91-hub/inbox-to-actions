FROM python:3.12-slim

# git is needed to install the pinned aiforge-core tag from GitHub
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/inbox-to-actions

COPY . .
RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

# entrypoint runs migrations + seeds the sample inbox idempotently, then serves
CMD ["sh", "scripts/entrypoint.sh"]
