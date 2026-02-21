FROM python:3.12-slim

# Install base tools
RUN apt-get update && apt-get install -y \
    git curl jq sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace
COPY docker/docker-entrypoint.sh /usr/local/bin/

# Install Python deps
COPY pyproject.toml poetry.lock* ./
RUN pip install poetry && poetry install --no-dev

EXPOSE 8080
ENTRYPOINT ["docker-entrypoint.sh"]
