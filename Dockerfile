# HN Pulse — MCP Server container
#
# Builds a single image that can run either MCP server:
#   docker run hn-pulse                             # HN Pulse (default, stdio)
#   docker run -p 8000:8000 hn-pulse http           # HN Pulse HTTP
#   docker run -p 8001:8001 hn-pulse http-fetch     # HN Fetch HTTP
#
# See docker-compose.yml for the full multi-service setup.

FROM python:3.12-slim

WORKDIR /app

# Install uv — faster than pip for dependency resolution
RUN pip install --no-cache-dir uv

# Copy only what's needed for install (cache layer)
COPY pyproject.toml ./

# Copy source
COPY src/ src/

# Install server deps (no agent/dev extras needed in container)
RUN uv pip install --system -e "."

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000 8001

# Default: run HN Pulse in HTTP mode on all interfaces
# Override CMD in docker-compose for the fetch server
CMD ["python", "src/hn_pulse/server.py", "http", "--host", "0.0.0.0", "--port", "8000"]
