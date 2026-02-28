# Agent Platform — Phase Plan & Execution Summary

## Phase 1: Project Scaffolding

### Plan
- Create directory structure: `agent-workspace/`, `agent-config/`, `proxy-config/`, `scripts/`
- Add placeholder files: `.gitkeep`, `.env.example`, `squid.conf`
- Initialize git repo with `.gitignore`

### Execution
- All directories created successfully
- `agent-workspace/.gitkeep` — empty placeholder to track the shared workspace directory in git
- `agent-config/.env.example` — template with API key placeholders, proxy settings, and locale
- `proxy-config/squid.conf` — Squid domain allow-list for OpenAI and Anthropic, deny-all default
- `.gitignore` — excludes `.env` secrets, workspace runtime files, `.DS_Store`, logs
- Git repo initialized, initial commit `9a94ba6`

---

## Phase 2: Core Container Build

### Plan
- Create `Dockerfile` following the §4 blueprint (multi-stage Alpine 3.20)
- Create `docker-compose.yml` per §8 with all security hardening options

### Execution
- **Dockerfile** — Multi-stage build with:
  - `alpine:3.20` base image (~7 MB)
  - Non-root `agent` user/group via `addgroup -S` / `adduser -S`
  - Allow-listed packages only: `bash`, `ca-certificates`, `curl`, `jq`, `python3`, `py3-pip`, `tini`
  - `tini` as PID 1 for proper signal handling and zombie reaping
  - `CMD ["sleep", "infinity"]` to keep container alive in detached mode (changed from `CMD ["bash"]` which exits immediately)

- **docker-compose.yml** — Full hardened service definition with:
  - `read_only: true` root filesystem
  - `cap_drop: ALL` — every Linux capability dropped
  - `no-new-privileges` — prevents privilege escalation
  - `tmpfs` for `/tmp` (100M) and `/run` (10M) with `noexec,nosuid`
  - Resource limits (initially under `deploy.resources`, later fixed in Phase 7)
  - Internal bridge network
  - Egress proxy commented out (enabled in Phase 6)

---

## Phase 3: Helper Scripts

### Plan
- Create 5 utility scripts in `scripts/`: `build.sh`, `start.sh`, `stop.sh`, `shell.sh`, `logs.sh`
- Make all scripts executable

### Execution
All scripts created with `set -euo pipefail` for safety, `cd "$(dirname "$0")/.."` to resolve project root, and `"$@"` for argument passthrough:

| Script | Command |
|---|---|
| `scripts/build.sh` | `docker compose build` |
| `scripts/start.sh` | `docker compose up -d` |
| `scripts/stop.sh` | `docker compose down` |
| `scripts/shell.sh` | `docker exec -it agent-sandbox bash` |
| `scripts/logs.sh` | `docker compose logs -f` |

All made executable with `chmod +x`.

---

## Phase 4: Configuration Files

### Plan
- Create `agent-config/.env.example` with placeholder environment variables
- Create `proxy-config/squid.conf` with domain allow-list template

### Execution
Already completed during Phase 1 — no additional work needed.

---

## Phase 5: Build & Smoke Test

### Plan
- Build the Docker image
- Start the container
- Run the full validation checklist from §11

### Execution

**Prerequisite:** Docker Desktop was not initially installed. Installed Docker Desktop (v29.2.1) before proceeding.

**Build:** Image built successfully from Alpine 3.20 — 90 MiB total with 53 packages.

**Issue encountered:** Container kept restarting because `CMD ["bash"]` exits immediately in non-interactive mode. Fixed by changing to `CMD ["sleep", "infinity"]`.

**Validation checklist results:**

| Check | Expected | Actual |
|---|---|---|
| `whoami` | `agent` | `agent` |
| `touch /etc/test` | Permission denied | `Read-only file system` |
| `ping 8.8.8.8` | Fails | `Network unreachable` |
| `cat /var/run/docker.sock` | No such file | `No such file or directory` |
| Privileged flag | `false` | `false` |
| CapDrop | `[ALL]` | `[ALL]` |

All 6 checks passed.

---

## Phase 6: Network Egress Proxy

### Plan
- Decide network mode: Option A (offline) vs Option B (proxy)
- Enable egress-proxy service in compose
- Set `HTTP_PROXY`/`HTTPS_PROXY` env vars on agent container
- Test proxy routing — allowed domains resolve, blocked domains denied

### Decision
**Option B: Proxy** — agent needs external API access (OpenAI, Anthropic).

### Execution

**Architecture deployed:**

```
agent-sandbox ──[agent-internal (isolated)]──▶ egress-proxy ──[proxy-external]──▶ Internet
```

- Dual-network design:
  - `agent-internal` — bridge with `internal: true` (no internet access)
  - `proxy-external` — bridge with internet access
- Agent container sits only on `agent-internal`, can only reach the proxy
- Proxy container bridges both networks, forwarding allowed requests to the internet
- `HTTP_PROXY` and `HTTPS_PROXY` env vars set on agent container pointing to `egress-proxy:3128`

**Proxy routing test results:**

| Test | Expected | Actual |
|---|---|---|
| `curl api.anthropic.com` via proxy | Connected | HTTP 404 (connected, no valid endpoint) |
| `curl api.openai.com` via proxy | Connected | HTTP 421 (connected, no valid endpoint) |
| `curl www.google.com` via proxy | Blocked | HTTP 403 Forbidden (Squid denied) |
| `curl www.google.com` direct (no proxy) | Fails | No route / timeout |

All proxy routing tests passed.

---

## Phase 7: Hardening & Documentation

### Plan
- Test resource limits under load
- Clean up compose file (remove obsolete `version` key)
- Add `.dockerignore` for cleaner builds
- Commit all changes

### Execution

**Resource limit fix:** The `deploy.resources` section in Compose v3 only applies in Docker Swarm mode. Replaced with top-level `mem_limit`, `mem_reservation`, and `cpus` directives so limits are enforced by `docker compose`.

**Memory stress test:**

| Test | Result |
|---|---|
| Allocate 2.5G inside container | Process OOM-killed |
| `docker inspect` memory value | `2147483648` bytes (2G) confirmed |

**Additional hardening:**
- Removed obsolete `version: "3.9"` from compose file
- Added `.dockerignore` excluding `.git`, `*.md`, `agent-workspace`, `agent-config`, `proxy-config`, `scripts` from build context

**Committed** as `4f2281e`.

---

## Final Project Structure

```
social-agent/
├── .dockerignore              # excludes non-build files from Docker context
├── .gitignore                 # excludes secrets, runtime files, .DS_Store
├── CLAUDE.md                  # platform plan and design spec
├── Dockerfile                 # multi-stage Alpine 3.20, non-root, tini
├── docker-compose.yml         # hardened services + dual-network proxy
├── agent-workspace/           # shared read-write mount
│   └── .gitkeep
├── agent-config/              # read-only config mount
│   └── .env.example
├── proxy-config/              # Squid egress proxy config
│   └── squid.conf
└── scripts/
    ├── build.sh
    ├── start.sh
    ├── stop.sh
    ├── shell.sh
    └── logs.sh
```

## Security Summary

| Control | Implementation |
|---|---|
| Non-root user | `agent` user/group, `USER agent` in Dockerfile |
| Read-only root fs | `read_only: true` in compose |
| All capabilities dropped | `cap_drop: ALL` |
| No privilege escalation | `no-new-privileges:true` |
| Memory limit | `mem_limit: 2g` (OOM-enforced) |
| CPU limit | `cpus: 2.0` |
| No Docker socket | Not mounted, verified absent |
| Network isolation | Agent on internal-only network, proxy bridges to internet |
| Egress allow-list | Squid proxy permits only `api.openai.com` and `api.anthropic.com` |
| Writable paths | Only `agent-workspace` (bind mount) + `/tmp` and `/run` (tmpfs) |
