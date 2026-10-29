# Playwright's image already has Node, Chromium and its system libraries.
# Match this tag to the @playwright/test version in templates/react-vite/package.json.
FROM mcr.microsoft.com/playwright:v1.64.1-noble
# yarn for the generated apps
RUN corepack enable

# uv for the Python backend; it installs the Python version from pyproject.toml
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the backend code
COPY . .

# Job folders live here inside the container
ENV WORKSPACES_DIR=/data/workspaces
RUN mkdir -p /data/workspaces

EXPOSE 8000

# Railway sets PORT; 8000 is the local default
CMD ["sh", "-c", "uv run --no-dev uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]