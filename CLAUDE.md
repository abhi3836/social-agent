# CLAUDE.md — Agent Platform Plan

## Overview

Build a minimal, hardened Docker container on macOS (Apple Silicon / Intel) that serves as a **sandboxed execution platform** for an AI agent. The agent will operate inside this container with restricted, auditable access — never touching the host machine directly.

---

## 1. Design Principles

- **Least Privilege** — the container runs as a non-root user with only the capabilities it needs.
- **Minimal Attack Surface** — start from a tiny base image; add only what the agent explicitly requires.
- **No Host Leakage** — no Docker socket mount, no privileged mode, no host network.
- **Auditable** — every installed package and permission is documented and intentional.
- **Reproducible** — the entire environment is defined in version-controlled Dockerfiles and compose files.

---

## 2. Host Prerequisites

| Requirement | Details |
|---|---|
| **macOS version** | 13 Ventura or later (recommended) |
| **Docker Desktop** | Latest stable (enable "Use Virtualization Framework" + "VirtioFS") |
| **Disk budget** | ~2 GB for image + volumes |
| **RAM allocation** | Assign 4–8 GB to Docker Desktop depending on agent workload |

---

## 3. Base Image Selection

```
alpine:3.20   (~7 MB)   — preferred for absolute minimalism
debian:bookworm-slim     — fallback if agent needs glibc / broader package ecosystem
```

**Decision rule:** Start with Alpine. Only switch to Debian-slim if a hard dependency requires glibc or packages unavailable in `apk`.

---

## 4. Dockerfile Blueprint

```dockerfile
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
CMD ["bash"]
```

### Package Allow-List (extend as needed)

| Package | Why |
|---|---|
| `bash` | Shell for agent command execution |
| `ca-certificates` | TLS for outbound HTTPS calls |
| `curl` | HTTP requests |
| `jq` | JSON processing |
| `python3` / `py3-pip` | Agent runtime (if Python-based) |
| `tini` | Proper PID 1 / zombie reaping |
| `git` | *Optional* — only if agent needs repo access |

> **Rule:** Every new package must be justified in this table before being added to the Dockerfile.

---

## 5. Security Restrictions

### 5a. Dropped Linux Capabilities

```yaml
cap_drop:
  - ALL           # drop everything
cap_add:          # then add back ONLY what's needed
  # - NET_BIND_SERVICE   # uncomment only if binding < 1024
```

### 5b. Read-Only Root Filesystem

```yaml
read_only: true
tmpfs:
  - /tmp:size=100M,noexec,nosuid
  - /run:size=10M,noexec,nosuid
```

The agent can only write to explicitly mounted volumes and tmpfs paths.

### 5c. Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: "2.0"
      memory: 2G
    reservations:
      cpus: "0.5"
      memory: 512M
```

### 5d. No Privilege Escalation

```yaml
security_opt:
  - no-new-privileges:true
```

### 5e. Network Policy

```yaml
# Option A: No network at all (fully offline agent)
network_mode: "none"

# Option B: Restricted outbound only (agent needs API calls)
# Use a custom bridge network + firewall rules or a proxy container
```

**Choose Option A** if the agent works on local files only.
**Choose Option B** if the agent must call external APIs — in that case, add an egress-proxy sidecar (see §7).

---

## 6. Volume Strategy

```yaml
volumes:
  # Shared workspace — the ONLY bridge between host and agent
  - type: bind
    source: ./agent-workspace
    target: /home/agent/workspace
    read_write: true     # agent reads/writes tasks here

  # Optional: read-only config injection
  - type: bind
    source: ./agent-config
    target: /home/agent/.config
    read_only: true
```

### What is NOT mounted

- ❌ Docker socket (`/var/run/docker.sock`) — never
- ❌ Host home directory
- ❌ SSH keys / cloud credentials
- ❌ Any path outside the dedicated workspace

---

## 7. Network Egress Proxy (Optional)

If the agent needs internet access, route it through a controlled proxy to allow-list domains.

```
┌──────────┐      ┌──────────────┐      ┌───────────┐
│  Agent   │─────▶│ Squid Proxy  │─────▶│ Internet  │
│ (no DNS) │      │ (allow-list) │      │           │
└──────────┘      └──────────────┘      └───────────┘
```

- Proxy container runs **Squid** or **mitmproxy** with a domain allow-list.
- Agent container's `http_proxy` / `https_proxy` env vars point to the proxy.
- All other outbound traffic is dropped at the network level.

Example allow-list (`squid.conf` snippet):

```
acl allowed_domains dstdomain .api.openai.com
acl allowed_domains dstdomain .api.anthropic.com
http_access allow allowed_domains
http_access deny all
```

---

## 8. Docker Compose — Full Platform Definition

```yaml
# docker-compose.yml
version: "3.9"

services:
  agent-platform:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: agent-sandbox
    user: "agent"
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    tmpfs:
      - /tmp:size=100M,noexec,nosuid
      - /run:size=10M,noexec,nosuid
    volumes:
      - ./agent-workspace:/home/agent/workspace
      - ./agent-config:/home/agent/.config:ro
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
    environment:
      - LANG=C.UTF-8
      # - HTTP_PROXY=http://egress-proxy:3128   # uncomment if using proxy
      # - HTTPS_PROXY=http://egress-proxy:3128
    networks:
      - agent-net
    restart: unless-stopped

  # ── Uncomment if agent needs controlled internet access ──
  # egress-proxy:
  #   image: ubuntu/squid:latest
  #   container_name: egress-proxy
  #   volumes:
  #     - ./proxy-config/squid.conf:/etc/squid/squid.conf:ro
  #   networks:
  #     - agent-net
  #   ports: []   # no host-exposed ports

networks:
  agent-net:
    driver: bridge
    internal: true   # no external access unless proxy is enabled
```

---

## 9. Directory Structure

```
agent-platform/
├── CLAUDE.md                  # ← this file (platform plan)
├── Dockerfile
├── docker-compose.yml
├── agent-workspace/           # shared read-write mount
│   └── .gitkeep
├── agent-config/              # read-only config mount
│   └── .env.example
├── proxy-config/              # optional egress proxy config
│   └── squid.conf
└── scripts/
    ├── build.sh               # docker compose build
    ├── start.sh               # docker compose up -d
    ├── stop.sh                # docker compose down
    ├── shell.sh               # docker exec -it agent-sandbox bash
    └── logs.sh                # docker compose logs -f
```

---

## 10. Build & Run Workflow

```bash
# 1. Build the image
docker compose build

# 2. Start the platform
docker compose up -d

# 3. Verify it's running
docker compose ps

# 4. Open a shell inside the sandbox (for testing / agent use)
docker exec -it agent-sandbox bash

# 5. Check resource usage
docker stats agent-sandbox

# 6. Tear down
docker compose down
```

---

## 11. Validation Checklist

Run these checks after every image change:

- [ ] `docker exec agent-sandbox whoami` → returns `agent` (not root)
- [ ] `docker exec agent-sandbox touch /etc/test` → permission denied (read-only root fs)
- [ ] `docker exec agent-sandbox ping 8.8.8.8` → fails (no network or proxy-only)
- [ ] `docker exec agent-sandbox cat /var/run/docker.sock` → no such file
- [ ] `docker inspect agent-sandbox --format '{{.HostConfig.Privileged}}'` → `false`
- [ ] `docker inspect agent-sandbox --format '{{.HostConfig.CapDrop}}'` → `[ALL]`
- [ ] Container memory stays within 2 GB limit under load

---

## 12. Maintenance & Iteration

| Task | Frequency |
|---|---|
| Rebuild image with `apk upgrade` | Weekly or on CVE alerts |
| Review agent-workspace for leftover files | After each agent session |
| Audit package allow-list | Before adding any new package |
| Rotate any API keys in agent-config | Per your org's key rotation policy |
| Check Docker Desktop updates | Monthly |

---

## 13. Future Enhancements (Backlog)

- **Seccomp profile** — custom JSON profile to restrict syscalls beyond capability drops.
- **AppArmor / SELinux** — additional MAC layer (limited on macOS Docker, but useful if deploying to Linux hosts later).
- **Image signing** — use `cosign` or Docker Content Trust to verify image integrity.
- **Logging sidecar** — ship container stdout/stderr to a local log aggregator.
- **Snapshot / rollback** — use Docker commit or volume snapshots to checkpoint agent state.
- **Multi-stage workspace** — separate `input/` (read-only) and `output/` (write) volumes for tighter control over data flow.

---

*Agent-specific configuration, tooling, and behavior are defined in a separate CLAUDE file.*
