FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra mcp

# Copy the application
COPY src ./src
COPY standards ./standards
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

# Default: MCP server over stdio. Override for CLI: `docker run ... hesabyar --help`
ENTRYPOINT ["hesabyar-mcp"]
