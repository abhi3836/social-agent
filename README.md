# Social Media Agent

A sandboxed AI agent that transforms raw thoughts into polished Twitter/X and LinkedIn posts. Runs inside a hardened Docker container — no host access, controlled API egress. In watch mode, the agent auto-generates a styled stat card and posts it directly to Twitter with the card as the image.

---

## How it works

```
You write a raw thought  →  Agent drafts posts + generates card  →  Auto-posts to Twitter with card image
  input/raw-thoughts/           output/drafts/                         (watch mode only)
```

In **watch mode**, the agent:
1. Picks up new raw thought files automatically
2. Generates Twitter + LinkedIn drafts
3. Renders a dark stat card (HTML → PNG via Playwright/Chromium) from your raw thought
4. Posts the tweet with the card image attached (if `TWITTER_AUTO_POST=true`)

For `write` and `run` commands, drafts are written to disk for manual review and posting.

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
│  │  │  │  chains/                 │  │──┼──►  twitter      ├──►Internet│
│  │  │  │  style_analyzer.py       │  │  │  │               │  │    │
│  │  │  │  post_writer.py          │  │  │  └───────────────┘  │    │
│  │  │  │  card_generator.py       │  │  │                     │    │
│  │  │  │  post_suggester.py       │  │  │  (proxy-external    │    │
│  │  │  └──────────────────────────┘  │  │   bridge net)       │    │
│  │  │                                │  │                     │    │
│  │  │  tools/                        │  └─────────────────────┘    │
│  │  │  twitter_publisher.py          │                             │
│  │  │  (v2 API + v1.1 media upload)  │                             │
│  │  │                                │                             │
│  │  │  Security: non-root user,      │                             │
│  │  │  read-only rootfs, ALL caps    │                             │
│  │  │  dropped, 2G mem limit         │                             │
│  │  └────────────────────────────────┘                             │
│  │                │ bind mounts                                     │
│  └────────────────┼─────────────────────────────────────────────────┘
│                   ▼
│           /home/agent/workspace  ──────────────────────────────────►┘
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow (watch mode)

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
  │  input/image-reference/      │  3. CardGenerator              │
  │  reference.png         ─────►│     ─── style ref + messages ─►│ Claude API (claude-opus-4-6)
  │                              │     ◄─── HTML stat card ────── │
  │                              │     html_to_png() via          │
  │                              │     Playwright/Chromium         │
  │                              │                                │
  │                              │  4. TwitterPublisher           │
  │                              │     ─── upload PNG ───────────►│ Twitter v1.1 API
  │                              │     ─── create tweet ─────────►│ Twitter v2 API
  │                              │     ◄─── tweet_id ─────────── │
  │                              │                                │
  │  output/drafts/              │  5. PostSuggester              │
  │  ├── twitter-draft.md  ◄─────│     ─────────────────────────►│ Claude API
  │  ├── linkedin-draft.md ◄─────│     ◄─── ranked ideas ──────── │
  │  ├── image-twitter.png ◄─────│                                │
  │  └── metadata.json     ◄─────│                                │
```

### Agent Processing Pipeline

```
agent.py CLI
│
├── write [--input FILE | --all]
│   │
│   ├── StyleAnalyzer.analyze()         → StyleProfile
│   ├── PostWriter.write(thought)       → Twitter + LinkedIn drafts
│   ├── ImageGenerator.generate()       → image-{platform}.png  [if image API configured]
│   └── FileWriter.write_drafts()       → output/drafts/
│
├── suggest
│   ├── PostSuggester.suggest()         → ranked post ideas
│   └── FileWriter.write_suggestions()  → output/suggestions/
│
├── run
│   └── write --all  +  suggest         (full pipeline, no card generation)
│
├── cards --input FILE [--reference PATH]
│   └── CardGenerator.generate()        → output/cards/cards_TIMESTAMP.html
│
└── watch --interval N                  ← card generation + auto-post live here
      │
      ├── PostWriter.write(..., skip_auto_post=True)   → drafts (no immediate post)
      ├── CardGenerator.generate(raw_thought_lines)    → HTML stat card
      ├── CardGenerator.html_to_png()                  → image-twitter.png (Playwright)
      └── TwitterPublisher.post(content, image_path)   → tweet with card attached
            ├── api_v1.media_upload()                  → Twitter v1.1 (image upload)
            └── client.create_tweet(media_ids=[...])   → Twitter v2 (post tweet)
```

### Directory Layout

```
social-agent/
├── Dockerfile                   # Multi-stage debian:bookworm-slim build (Playwright/Chromium)
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
│   │   ├── card_generator.py    # Raw thought lines → HTML stat card → PNG (watch mode)
│   │   ├── image_generator.py   # Draft → image brief → PNG (write/run commands)
│   │   └── post_suggester.py    # Recent themes → ranked post ideas
│   ├── models/                  # Pydantic data models
│   │   ├── style_profile.py     # PlatformStyle, StyleProfile
│   │   ├── draft.py             # Draft (content, type, platform, source)
│   │   └── suggestion.py        # PostSuggestion, SuggestionSet
│   ├── tools/                   # I/O and API integrations
│   │   ├── file_reader.py       # Reads from input/ workspace
│   │   ├── file_writer.py       # Writes to output/ workspace
│   │   ├── twitter_publisher.py # Tweepy v2 + v1.1 media upload
│   │   └── image_api.py         # DALL·E 3 / Stable Diffusion wrapper
│   ├── prompts/                 # LLM system prompts (plain text)
│   └── tests/                   # Unit tests per module
│
├── agent-workspace/             # Shared read-write volume (host ↔ container)
│   ├── input/
│   │   ├── raw-thoughts/        # ← YOU write here
│   │   ├── style-reference/     # ← YOU write here (style samples)
│   │   └── image-reference/     # ← YOU place reference.png here (card style)
│   └── output/
│       ├── drafts/              # ← AGENT writes here
│       ├── cards/               # ← AGENT writes HTML cards here
│       └── suggestions/         # ← AGENT writes here
│
├── agent-config/                # Read-only config volume
│   └── .env.example             # Copy to .env and fill in API keys
│
├── proxy-config/
│   └── squid.conf               # Egress allow-list
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
- Twitter Developer account with an app configured for **OAuth 1.0a User Context** (required for auto-posting and media upload)
- Optional: OpenAI API key for DALL·E 3 image generation (`write`/`run` commands only)

---

## 1. Configure your API keys

Copy the example config and fill in your keys:

```bash
cp agent-config/.env.example agent-config/.env
```

Edit `agent-config/.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
CLAUDE_MODEL=claude-sonnet-4-6

# Twitter/X — required for auto-posting and card image upload
# Create an app at https://developer.twitter.com/ with OAuth 1.0a User Context
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
# Set to true to post tweets automatically in watch mode
TWITTER_AUTO_POST=false

# Optional — enables image generation for write/run commands
# OPENAI_API_KEY=sk-YOUR_OPENAI_KEY

# Agent behaviour
POST_PLATFORMS=["twitter","linkedin"]
SUGGESTION_COUNT=5
LOG_LEVEL=INFO
```

> `agent-config/.env` is mounted read-only into the container. It is git-ignored — never commit it.

---

## 2. Add your style references

The agent learns your voice from sample posts. Add 5–10 of your real posts to:

```
agent-workspace/input/style-reference/twitter-samples.md
agent-workspace/input/style-reference/linkedin-samples.md
```

Format — paste your posts under `## Sample N` headers:

```markdown
## Sample 1
Hot take: most AI agent tutorials skip the part where they give the agent root access.

## Sample 2
Three things I wish someone had told me about Docker networking.
...
```

---

## 3. Add a card style reference image

The card generator uses a reference image to match your visual style. Place one image at:

```
agent-workspace/input/image-reference/reference.png
```

This is passed to Claude (claude-opus-4-6) alongside your raw thought to generate a matching dark stat card. Any PNG/JPG works — use a screenshot of a card aesthetic you like.

---

## 4. Build and start the platform

```bash
./scripts/build.sh   # builds the Docker image (~3–5 min first time — downloads Chromium)
./scripts/start.sh   # starts agent-sandbox + egress-proxy
```

Verify both containers are running:

```bash
docker compose ps
```

You should see `agent-sandbox` and `egress-proxy` both with status `Up`.

---

## 5. Write a raw thought

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

## 6. Run the agent

All commands run inside the container via `docker exec`.

### Watch mode — auto-process + auto-post (recommended)

```bash
docker exec -it agent-sandbox python /opt/agent/agent.py watch --interval 30
```

Polls `input/raw-thoughts/` every 30 seconds. When a new file appears:
1. Generates Twitter + LinkedIn drafts
2. Renders a stat card PNG from your raw thought
3. Posts the tweet with the card attached (if `TWITTER_AUTO_POST=true`)

Keep this running in a terminal while you write. The container itself starts watch mode automatically on launch.

### Process a specific raw thought (no auto-post)

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

### Generate a card only

```bash
docker exec agent-sandbox python /opt/agent/agent.py cards --input 2026-03-08-your-topic.md
```

Outputs an HTML stat card to `output/cards/`. Useful for previewing the card style before enabling auto-post.

### Full pipeline — write + suggest in one shot

```bash
docker exec agent-sandbox python /opt/agent/agent.py run
```

---

## 7. Read the output

After running `write`, the agent creates a folder per raw thought:

```
agent-workspace/output/drafts/2026-03-08-your-topic/
├── twitter-draft.md      ← tweet or thread, ready to copy-paste
├── linkedin-draft.md     ← LinkedIn post, ready to copy-paste
├── image-twitter.png     ← stat card PNG (watch mode) or AI-generated image (write/run)
└── metadata.json         ← model used, timestamp, source file
```

After running `suggest`:

```
agent-workspace/output/suggestions/2026-03-08-suggestions.md
```

---

## 8. Review and post

**Watch mode with `TWITTER_AUTO_POST=true`:** tweets are posted automatically with the card image. Check `metadata.json` for the posted tweet IDs.

**Manual flow (`write`/`run` commands):**

1. Open the draft files in `output/drafts/your-topic/`
2. Edit as needed
3. Copy-paste from the draft and post manually on Twitter/LinkedIn

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

**Card generation fails with `libglib-2.0.so.0` error**
The image is based on `debian:bookworm-slim` which includes Playwright's Chromium dependencies. If you see this after a rebuild, run `./scripts/build.sh` to get a clean image.

**Tweet posted but no image attached**
Check `output/drafts/<topic>/error.log`. Common cause: Twitter app does not have write permissions enabled in the Developer Portal, or the v1.1 media upload endpoint is not accessible on your API plan (requires Basic tier or above).

**`TWITTER_AUTO_POST` is set but nothing is posted**
Confirm `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, and `TWITTER_ACCESS_TOKEN_SECRET` are all set in `agent-config/.env`. All four are required.

**`POST_PLATFORMS` parse error on startup**
The value must be JSON-formatted: `POST_PLATFORMS=["twitter","linkedin"]` — not comma-separated.

**Style analysis fails with "No style reference files found"**
Add at least one sample file to `agent-workspace/input/style-reference/` before running.

**Card style reference not found**
Place a PNG or JPG at `agent-workspace/input/image-reference/reference.png`. The card generator requires this file.

**API call blocked / timeout**
The container routes all traffic through the Squid egress proxy. Only `api.anthropic.com`, `api.openai.com`, and `api.twitter.com` are allowed. Check `proxy-config/squid.conf` to add other endpoints.

**Container won't start after `docker compose up`**
Run `./scripts/logs.sh` to see errors. Most common cause: `.env` missing or malformed.

**Need to update agent code or prompts**
The agent code is baked into the image (read-only rootfs). After any change to `agent/`, run:
```bash
./scripts/build.sh && ./scripts/start.sh
```
