# ── Stage 1: Builder (install Python dependencies) ──
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a virtual environment
RUN python3 -m venv /opt/agent-venv
COPY agent/requirements.txt /tmp/requirements.txt
RUN /opt/agent-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# Install Playwright's Chromium browser binaries
RUN /opt/agent-venv/bin/playwright install chromium --with-deps

# ── Stage 2: Runtime ──
FROM debian:bookworm-slim

# System-level hardening
RUN groupadd -r agent && useradd -r -g agent agent \
    && mkdir -p /home/agent/workspace /home/agent/.cache \
    && chown -R agent:agent /home/agent

# Minimal runtime packages
# See CLAUDE.md §4 Package Allow-List for justifications
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    jq \
    python3 \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual environment from builder
COPY --from=builder /opt/agent-venv /opt/agent-venv

# Copy Playwright browser binaries from builder
COPY --from=builder /root/.cache/ms-playwright /home/agent/.cache/ms-playwright

# Install Chromium's system library dependencies in the runtime stage
RUN /opt/agent-venv/bin/playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Fix ownership of browser cache after root-level install
RUN chown -R agent:agent /home/agent/.cache

# Copy agent application code
COPY agent/ /opt/agent/

# Make venv python the default
ENV PATH="/opt/agent-venv/bin:$PATH"
ENV PYTHONPATH="/opt/agent:$PYTHONPATH"
# Point Playwright to the copied browser cache
ENV PLAYWRIGHT_BROWSERS_PATH=/home/agent/.cache/ms-playwright

# Drop to non-root user
USER agent
WORKDIR /home/agent/workspace

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["tini", "--"]
CMD ["python", "/opt/agent/agent.py", "watch"]
