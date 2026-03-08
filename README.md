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

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  macOS Host                                                         │
│                                                                     │
│  agent-workspace/  ◄──────────────────────────────────────────┐    │
│  agent-config/     ◄── bind mounts (read-only for config)     │    │
│                                                                │    │
│  ┌──────────────────────────────────────┐  ┌───────────────┐  │    │
│  │  agent-sandbox (agent-internal net)  │  │  egress-proxy │  │    │
│  │                                      │  │  (Squid)      │  │    │
│  │  ┌────────────────────────────────┐  │  │               │  │    │
│  │  │  agent.py (CLI entry point)    │  │  │  allow-list:  │  │    │
│  │  │                                │  │  │  anthropic    │  │    │
│  │  │  ┌──────────────────────────┐  │  │  │  openai       │  │    │
│  │  │  │  chains/                 │  │──┼──►               ├──►Internet│
│  │  │  │  style_analyzer.py       │  │  │  │               │  │    │
│  │  │  │  post_writer.py          │  │  │  └───────────────┘  │    │
│  │  │  │  image_generator.py      │  │  │                     │    │
│  │  │  │  post_suggester.py       │  │  │  (proxy-external    │    │
│  │  │  └──────────────────────────┘  │  │   bridge net)       │    │
│  │  │                                │  │                     │    │
│  │  │  Security: non-root user,      │  └─────────────────────┘    │
│  │  │  read-only rootfs, ALL caps    │                             │
│  │  │  dropped, 2G mem limit         │                             │
│  │  └────────────────────────────────┘                             │
│  │                │ bind mounts                                     │
│  └────────────────┼─────────────────────────────────────────────────┘
│                   ▼
│           /home/agent/workspace  ──────────────────────────────────►┘
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
 USER                          AGENT                         EXTERNAL APIs
  │                              │                                │
  │  input/style-reference/      │                                │
  │  twitter-samples.md    ─────►│                                │
  │  linkedin-samples.md         │  1. StyleAnalyzer              │
  │                              │     ─────────────────────────►│ Claude API
  │                              │     ◄───── StyleProfile JSON ──│
  │                              │                                │
  │  input/raw-thoughts/         │                                │
  │  YYYY-MM-DD-topic.md   ─────►│  2. PostWriter                 │
  │                              │     ─────────────────────────►│ Claude API
  │                              │     ◄─── Twitter draft ────────│
  │                              │     ─── self-critique ────────►│ Claude API
  │                              │     ◄─── refined draft ─────── │
  │                              │     ─────────────────────────►│ Claude API
  │                              │     ◄─── LinkedIn draft ───────│
  │                              │                                │
  │                              │  3. ImageGenerator (optional)  │
  │                              │     ─── image brief ──────────►│ Claude API
  │                              │     ─── generate image ───────►│ DALL·E 3 /
  │                              │     ◄─── PNG (resized) ─────── │ Stable Diffusion
  │                              │                                │
  │                              │  4. PostSuggester              │
  │                              │     ─────────────────────────►│ Claude API
  │                              │     ◄─── ranked ideas ──────── │
  │                              │                                │
  │  output/drafts/              │                                │
  │  ├── twitter-draft.md  ◄─────│                                │
  │  ├── linkedin-draft.md ◄─────│                                │
  │  ├── image-twitter.png ◄─────│                                │
  │  ├── image-linkedin.png◄─────│                                │
  │  └── metadata.json     ◄─────│                                │
  │                              │                                │
  │  output/suggestions/         │                                │
  │  YYYY-MM-DD-suggestions◄─────│                                │
  │                              │                                │
  │  [review & edit]             │                                │
  │  approved/           ──────► (human posts manually)          │
  │  archive/                    │                                │
```

### Agent Processing Pipeline

```
agent.py CLI
│
├── write [--input FILE | --all]
│   │
│   ├── FileReader.read_style_reference()
│   │     └── loads twitter-samples.md + linkedin-samples.md
│   │
│   ├── StyleAnalyzer.analyze()
│   │     ├── prompt: prompts/style_analysis.txt
│   │     └── returns: StyleProfile { twitter: PlatformStyle, linkedin: PlatformStyle }
│   │
│   ├── FileReader.read_raw_thought(file)
│   │     └── validates: min 20 chars
│   │
│   ├── PostWriter.write(thought, style_profile)
│   │     ├── Twitter chain
│   │     │   ├── prompt: prompts/twitter_writer.txt
│   │     │   ├── self-critique: prompts/self_critique.txt
│   │     │   └── returns: Draft (single tweet or thread)
│   │     └── LinkedIn chain
│   │         ├── prompt: prompts/linkedin_writer.txt
│   │         ├── self-critique: prompts/self_critique.txt
│   │         └── returns: Draft
│   │
│   ├── ImageGenerator.generate(drafts)   [if image API configured]
│   │     ├── prompt: prompts/image_brief.txt  → visual brief
│   │     ├── ImageAPIClient.generate()        → DALL·E 3 / SD
│   │     └── Pillow resize → 1200×675 (Twitter) / 1200×627 (LinkedIn)
│   │
│   └── FileWriter.write_drafts(drafts)
│         └── output/drafts/YYYY-MM-DD-topic/{twitter,linkedin}-draft.md
│                                              image-{twitter,linkedin}.png
│                                              metadata.json
│
├── suggest
│   │
│   ├── FileReader.read_recent_thoughts(n=5)
│   ├── PostSuggester.suggest(thoughts, style_profile)
│   │     ├── prompt: prompts/suggestion.txt
│   │     └── returns: SuggestionSet [ PostSuggestion × SUGGESTION_COUNT ]
│   └── FileWriter.write_suggestions()
│         └── output/suggestions/YYYY-MM-DD-suggestions.md
│
├── image --draft PATH
│   └── ImageGenerator.generate(existing_draft)
│
├── run
│   └── write --all  +  suggest  (full pipeline)
│
└── watch --interval N
      └── polls input/raw-thoughts/ every N seconds → triggers write
```

### Directory Layout

```
social-agent/
├── Dockerfile                   # Multi-stage Alpine 3.20 build
├── docker-compose.yml           # agent-sandbox + egress-proxy services
├── CLAUDE.md                    # Platform security spec & design decisions
│
├── agent/                       # All Python application code
│   ├── agent.py                 # CLI entry point (Click)
│   ├── config.py                # Settings loader (Pydantic, from .env)
│   ├── requirements.txt
│   ├── chains/                  # LLM processing pipelines
│   │   ├── style_analyzer.py    # Voice extraction from style samples
│   │   ├── post_writer.py       # Raw thought → Twitter + LinkedIn drafts
│   │   ├── image_generator.py   # Draft → image brief → PNG
│   │   └── post_suggester.py    # Recent themes → ranked post ideas
│   ├── models/                  # Pydantic data models
│   │   ├── style_profile.py     # PlatformStyle, StyleProfile
│   │   ├── draft.py             # Draft (content, type, platform, source)
│   │   └── suggestion.py        # PostSuggestion, SuggestionSet
│   ├── tools/                   # I/O and API integrations
│   │   ├── file_reader.py       # Reads from input/ workspace
│   │   ├── file_writer.py       # Writes to output/ workspace
│   │   └── image_api.py         # DALL·E 3 / Stable Diffusion wrapper
│   ├── prompts/                 # LLM system prompts (plain text)
│   │   ├── style_analysis.txt
│   │   ├── twitter_writer.txt
│   │   ├── linkedin_writer.txt
│   │   ├── self_critique.txt
│   │   ├── image_brief.txt
│   │   └── suggestion.txt
│   └── tests/                   # Unit tests per module
│
├── agent-workspace/             # Shared read-write volume (host ↔ container)
│   ├── input/
│   │   ├── raw-thoughts/        # ← YOU write here
│   │   └── style-reference/     # ← YOU write here (style samples)
│   ├── output/
│   │   ├── drafts/              # ← AGENT writes here
│   │   └── suggestions/         # ← AGENT writes here
│   ├── approved/                # ← YOU move drafts here when ready
│   └── archive/                 # ← YOU move here after posting
│
├── agent-config/                # Read-only config volume
│   └── .env.example             # Copy to .env and fill in API keys
│
├── proxy-config/
│   └── squid.conf               # Egress allow-list (anthropic + openai only)
│
└── scripts/
    ├── build.sh / start.sh / stop.sh
    ├── shell.sh                 # bash into agent-sandbox for debugging
    └── logs.sh
```

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
