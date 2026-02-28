# ── Stage 1: Builder (if compilation is needed) ──
FROM alpine:3.20 AS builder
RUN apk add --no-cache build-base curl
# ... compile any native dependencies here ...

# ── Stage 2: Runtime ──
FROM alpine:3.20

# 4a. System-level hardening
RUN addgroup -S agent && adduser -S agent -G agent \
    && mkdir -p /home/agent/workspace /home/agent/.cache \
    && chown -R agent:agent /home/agent

# 4b. Minimal runtime packages (curate this list carefully)
# See CLAUDE.md §4 Package Allow-List for justifications
RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    jq \
    python3 \
    py3-pip \
    tini

# 4c. Copy only what's needed from builder
# COPY --from=builder /usr/local/bin/mytool /usr/local/bin/mytool

# 4d. Drop to non-root user
USER agent
WORKDIR /home/agent/workspace

# 4e. Use tini as PID 1 for proper signal handling
ENTRYPOINT ["tini", "--"]
CMD ["sleep", "infinity"]
