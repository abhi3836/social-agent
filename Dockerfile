# ── Stage 1: Builder (install Python dependencies) ──
FROM alpine:3.20 AS builder

RUN apk add --no-cache python3 py3-pip build-base

# Install Python deps into a virtual environment
RUN python3 -m venv /opt/agent-venv
COPY agent/requirements.txt /tmp/requirements.txt
RUN /opt/agent-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# ── Stage 2: Runtime ──
FROM alpine:3.20

# System-level hardening
RUN addgroup -S agent && adduser -S agent -G agent \
    && mkdir -p /home/agent/workspace /home/agent/.cache \
    && chown -R agent:agent /home/agent

# Minimal runtime packages (no py3-pip — not needed at runtime)
# See CLAUDE.md §4 Package Allow-List for justifications
RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    jq \
    python3 \
    tini

# Copy the pre-built virtual environment from builder
COPY --from=builder /opt/agent-venv /opt/agent-venv

# Copy agent application code
COPY agent/ /opt/agent/

# Make venv python the default
ENV PATH="/opt/agent-venv/bin:$PATH"
ENV PYTHONPATH="/opt/agent:$PYTHONPATH"

# Drop to non-root user
USER agent
WORKDIR /home/agent/workspace

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["tini", "--"]
CMD ["sleep", "infinity"]
