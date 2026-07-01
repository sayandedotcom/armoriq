FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

# Install mcp-bank first (agent spawns it as a stdio subprocess)
COPY apps/mcp-bank/ ./mcp-bank/
RUN pip install --no-cache-dir ./mcp-bank

# Install agent dependencies via uv
COPY apps/agent/pyproject.toml apps/agent/uv.lock ./agent/
RUN cd agent && uv sync --frozen --no-dev

# Copy agent source and MCP server config
COPY apps/agent/src ./agent/src
COPY apps/agent/servers.json ./agent/servers.json

ENV PYTHONUNBUFFERED=1

WORKDIR /app/agent

EXPOSE 8000

CMD ["uv", "run", "python", "src/main.py"]
