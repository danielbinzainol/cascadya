# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 – build wheels (c104 has a C extension, needs build tools)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Force HTTPS for apt inside the container
RUN sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null ||     sed -i 's|http://|https://|g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ cmake make libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 – lean runtime image
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Create a non-root user
RUN groupadd -r iec104 && useradd -r -g iec104 iec104

WORKDIR /app

# Install pre-built wheels from stage 1
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels \
        c104 nats-py \
 && rm -rf /wheels

COPY --chown=iec104:iec104 server.py .

# IEC 104 default port
EXPOSE 2404/tcp

USER iec104

# ──────────────────────────────────────────────────────────────────────────────
# Runtime environment variables (override with docker run -e or compose)
# ──────────────────────────────────────────────────────────────────────────────
ENV IEC104_BIND_IP=0.0.0.0 \
    IEC104_PORT=2404 \
    IEC104_CA=1 \
    NATS_URL=nats://nats:4222 \
    NATS_SUBJECT_PFX=iec104.cmd \
    LOG_LEVEL=INFO

CMD ["python", "-u", "server.py"]