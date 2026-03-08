# Social Media Agent

A sandboxed AI agent that transforms raw thoughts into polished Twitter/X and LinkedIn posts. Runs inside a hardened Docker container — no host access, controlled API egress, human-in-the-loop before anything gets posted.

---

## How it works

```
You write a raw thought  →  Agent drafts posts + images  →  You review & post manually
  input/raw-thoughts/           output/drafts/                 approved/ → archive/
```

The agent never publishes. You copy-paste from the output.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (latest stable)
- An Anthropic API key (`sk-ant-...`)
- Optional: an OpenAI API key for DALL·E 3 image generation

---

## 1. Configure your API key

Copy the example config and fill in your key:

```bash
cp agent-config/.env.example agent-config/.env
```

Edit `agent-config/.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
CLAUDE_MODEL=claude-sonnet-4-6

# Optional — enables image generation
# OPENAI_API_KEY=sk-YOUR_OPENAI_KEY

# Agent behaviour
POST_PLATFORMS=["twitter","linkedin"]
SUGGESTION_COUNT=5
LOG_LEVEL=INFO

# Leave these — set automatically by docker-compose
HTTP_PROXY=http://egress-proxy:3128
HTTPS_PROXY=http://egress-proxy:3128
```

> `agent-config/.env` is mounted read-only into the container. It is git-ignored — never commit it.

---

## 2. Add your style references

The agent learns your voice from sample posts. Add 5–10 of your real posts to:

```
agent-workspace/input/style-reference/twitter-samples.md
agent-workspace/input/style-reference/linkedin-samples.md
```

Format — just paste your posts under `## Sample N` headers:

```markdown
## Sample 1
Hot take: most AI agent tutorials skip the part where they give the agent root access.

## Sample 2
Three things I wish someone had told me about Docker networking.
...
```

The more samples you provide, the better the agent matches your voice.

---

## 3. Build and start the platform

```bash
./scripts/build.sh   # builds the Docker image (~2–3 min first time)
./scripts/start.sh   # starts agent-sandbox + egress-proxy
```

Verify both containers are running:

```bash
docker compose ps
```

You should see `agent-sandbox` and `egress-proxy` both with status `Up`.

---

## 4. Write a raw thought

Create a file in `agent-workspace/input/raw-thoughts/`. Name it with today's date and a slug:

```
agent-workspace/input/raw-thoughts/2026-03-08-your-topic.md
```

Format:

```markdown
# Topic: Your topic in one line

- bullet point capturing the core idea
- supporting argument or anecdote
- another angle or example
- what makes this relevant now

Tone: practical, opinionated        ← optional hints for the agent
Audience: developers and builders   ← optional hints for the agent
```

Keep it rough — these are notes, not prose. The agent does the writing.

---

## 5. Run the agent

All commands run inside the container via `docker exec`.

### Process a specific raw thought

```bash
docker exec agent-sandbox python /opt/agent/agent.py write --input 2026-03-08-your-topic.md
```

### Process all unprocessed thoughts at once

```bash
docker exec agent-sandbox python /opt/agent/agent.py write --all
```

### Generate post ideas (no input file needed)

```bash
docker exec agent-sandbox python /opt/agent/agent.py suggest
```

Reads your recent raw thoughts and style profile, outputs 5 ranked post ideas.

### Full pipeline — write + suggest in one shot

```bash
docker exec agent-sandbox python /opt/agent/agent.py run
```

### Watch mode — auto-process new files as you drop them in

```bash
docker exec -it agent-sandbox python /opt/agent/agent.py watch --interval 30
```

Polls `input/raw-thoughts/` every 30 seconds. Keep this running in a terminal while you write.

---

## 6. Read the output

After running `write`, the agent creates a folder per raw thought:

```
agent-workspace/output/drafts/2026-03-08-your-topic/
├── twitter-draft.md      ← tweet or thread, ready to copy-paste
├── linkedin-draft.md     ← LinkedIn post, ready to copy-paste
├── image-twitter.png     ← generated image (if OpenAI key set)
├── image-linkedin.png    ← generated image (if OpenAI key set)
└── metadata.json         ← model used, timestamp, source file
```

After running `suggest`:

```
agent-workspace/output/suggestions/2026-03-08-suggestions.md
```

Ranked list of post ideas with topics, timing rationale, and outlines.

---

## 7. Review and post

1. Open the draft files in `output/drafts/your-topic/`
2. Edit as needed — the drafts are yours to change
3. Move the folder to `approved/` when ready:
   ```bash
   mv agent-workspace/output/drafts/2026-03-08-your-topic agent-workspace/approved/
   ```
4. Copy-paste from the draft and post manually on Twitter/LinkedIn
5. Move to `archive/` after posting:
   ```bash
   mv agent-workspace/approved/2026-03-08-your-topic agent-workspace/archive/
   ```

The agent never has credentials for any social platform. Posting is always your action.

---

## Helper scripts

| Script | What it does |
|---|---|
| `./scripts/build.sh` | Build / rebuild the Docker image |
| `./scripts/start.sh` | Start the platform (`docker compose up -d`) |
| `./scripts/stop.sh` | Stop the platform (`docker compose down`) |
| `./scripts/shell.sh` | Open a bash shell inside the container |
| `./scripts/logs.sh` | Tail container logs (`docker compose logs -f`) |

---

## Troubleshooting

**`POST_PLATFORMS` parse error on startup**
The value must be JSON-formatted: `POST_PLATFORMS=["twitter","linkedin"]` — not comma-separated.

**Style analysis fails with "No style reference files found"**
Add at least one sample file to `agent-workspace/input/style-reference/` before running.

**Image generation is skipped**
Expected when `OPENAI_API_KEY` is not set. Drafts are still written — images are optional.

**API call blocked / timeout**
The container routes all traffic through the Squid egress proxy. Only `api.anthropic.com` and `api.openai.com` are allowed. Check `proxy-config/squid.conf` to add other endpoints.

**Container won't start after `docker compose up`**
Run `./scripts/logs.sh` to see errors. Most common cause: `.env` missing or malformed.

**Need to update agent code or prompts**
The agent code is baked into the image (read-only rootfs). After any change to `agent/`, run:
```bash
./scripts/build.sh && ./scripts/start.sh
```
