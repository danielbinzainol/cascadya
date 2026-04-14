FROM python:3.12-slim-bookworm AS builder

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.27 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Copy application code and static assets.
COPY src ./src
COPY static ./static
COPY app.py ./app.py
COPY plots.py ./plots.py
COPY config.yml ./config.yml

# Install project into the virtual environment.
RUN uv sync --locked --no-dev


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Create an unprivileged runtime user.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Copy only runtime artifacts from builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/static /app/static
COPY --from=builder /app/app.py /app/app.py
COPY --from=builder /app/plots.py /app/plots.py
COPY --from=builder /app/config.yml /app/config.yml

# Ensure runtime writable directories exist.
RUN mkdir -p /app/data /app/reports && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# The app currently has no dedicated /health route; /docs is a lightweight fallback.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=3)" || exit 1

CMD ["uvicorn", "src.backoffice.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
