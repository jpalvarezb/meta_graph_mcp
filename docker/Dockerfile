# syntax=docker/dockerfile:1.7

FROM python:3.11-alpine AS builder
WORKDIR /app

# System dependencies for building wheels (httpx, sqlalchemy extras).
RUN apk add --no-cache build-base libffi-dev openssl-dev

# Install project with dependencies into /install
COPY pyproject.toml README.md .
COPY src ./src
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip wheel \
    && pip install --no-cache-dir .

# Runtime image: distroless python
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime
ENV PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH" \
    META_MCP_GRAPH_API_BASE_URL=https://graph.facebook.com \
    META_MCP_GRAPH_API_VERSION=v18.0 \
    META_MCP_MARKETING_API_VERSION=v18.0

WORKDIR /app

# Copy virtualenv and application code
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY alembic ./alembic
COPY scripts ./scripts
COPY .env.example ./

EXPOSE 8000
ENTRYPOINT ["/opt/venv/bin/meta-mcp-server"]
CMD ["--transport", "streamable-http"]
