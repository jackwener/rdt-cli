---
name: rdt-cli
description: Use rdt-cli for ALL Reddit operations — browsing feeds, reading posts, searching, viewing users, upvoting, saving, and subscribing. Invoke whenever the user requests any Reddit interaction.
author: jackwener
version: "0.1.0"
tags:
  - reddit
  - rdt
  - social-media
  - cli
---

# rdt-cli — Reddit CLI Tool

**Binary:** `rdt`
**Credentials:** browser cookies (auto-extracted via browser-cookie3)

## Setup

```bash
# Install (requires Python 3.10+)
uv tool install rdt-cli
# Or: pip install rdt-cli

# Upgrade
uv tool upgrade rdt-cli
```

## Authentication

**IMPORTANT FOR AGENTS**: Before executing ANY rdt command that requires auth, check if credentials exist.

### Step 0: Check if already authenticated

```bash
rdt status --json 2>/dev/null && echo "AUTH_OK" || echo "AUTH_NEEDED"
```

If `AUTH_OK`, skip to [Command Reference](#command-reference).
If `AUTH_NEEDED`, proceed to Step 1.

### Step 1: Guide user to authenticate

Ensure user is logged into reddit.com in a supported browser (Chrome, Firefox, Edge, Brave). Then:

```bash
rdt login
```

Verify with:

```bash
rdt status
```

### Step 2: Handle common auth issues

| Symptom | Agent action |
|---------|-------------|
| `No Reddit cookies found` | Guide user to login to reddit.com in browser |
| `Session expired` | Run `rdt logout && rdt login` |
| `database is locked` | Close browser, then retry |

## Agent Defaults

- Non-TTY stdout → auto YAML
- `--json` / `--yaml` → explicit format
- Most read commands work without auth (public Reddit JSON API)
- Write actions (upvote, save, subscribe) require auth

## Command Reference

### Browsing

| Command | Description | Example |
|---------|-------------|---------|
| `rdt feed` | Browse home feed (requires login) | `rdt feed -n 10` |
| `rdt popular` | Browse /r/popular | `rdt popular -n 5 --json` |
| `rdt sub <name>` | Browse a subreddit | `rdt sub python -s top -t week` |
| `rdt sub-info <name>` | View subreddit info | `rdt sub-info rust --json` |
| `rdt user <name>` | View user profile | `rdt user spez` |
| `rdt user-posts <name>` | View user's posts | `rdt user-posts spez -n 5` |

### Reading

| Command | Description | Example |
|---------|-------------|---------|
| `rdt read <post_id>` | Read a post + comments | `rdt read 1abc123` |
| `rdt show <index>` | Read by short-index | `rdt show 3` |

### Search & Export

| Command | Description | Example |
|---------|-------------|---------|
| `rdt search <query>` | Search posts | `rdt search "python async" -s top -t year` |
| `rdt search <query> -r <sub>` | Search in subreddit | `rdt search "error" -r rust` |
| `rdt export <query>` | Export to CSV/JSON | `rdt export "ML" -n 50 -o results.csv` |

### Interactions (require auth)

| Command | Description | Example |
|---------|-------------|---------|
| `rdt upvote <id_or_index>` | Upvote | `rdt upvote 3` |
| `rdt upvote <id> --down` | Downvote | `rdt upvote 3 --down` |
| `rdt upvote <id> --undo` | Remove vote | `rdt upvote 3 --undo` |
| `rdt save <id_or_index>` | Save post | `rdt save 3` |
| `rdt save <id> --undo` | Unsave | `rdt save 3 --undo` |
| `rdt subscribe <sub>` | Subscribe | `rdt subscribe python` |
| `rdt subscribe <sub> --undo` | Unsubscribe | `rdt subscribe python --undo` |

### Account

| Command | Description |
|---------|-------------|
| `rdt login` | Extract cookies from browser |
| `rdt logout` | Clear cached cookies |
| `rdt status` | Check authentication status |

## Agent Workflow Examples

### Browse → Read → Upvote pipeline

```bash
rdt sub python -s top -t week -n 5
rdt show 1
rdt upvote 1
```

### Search → Export pipeline

```bash
rdt search "machine learning" -s top -t year --json | jq '.data.children[:3]'
rdt export "machine learning" -n 100 -o ml_posts.csv
```

### User research

```bash
rdt user spez --json | jq '{name, link_karma, comment_karma}'
rdt user-posts spez -n 10 --json
```

### Subreddit discovery

```bash
rdt sub-info python --json | jq '{subscribers, accounts_active}'
rdt sub python -s top -t month -n 5
```

## Sort Options

- **Listing sort**: `hot`, `new`, `top`, `rising`, `controversial`, `best`
- **Search sort**: `relevance`, `hot`, `top`, `new`, `comments`
- **Time filter** (for top/controversial): `hour`, `day`, `week`, `month`, `year`, `all`
- **Comment sort**: `best`, `top`, `new`, `controversial`, `old`, `qa`

## Limitations

- **No DMs** — cannot access private messages
- **No live/streaming** — live features not supported
- **No media download** — cannot download images/videos
- **Single account** — one set of cookies at a time
- **Rate limited** — built-in Gaussian jitter (~1s) between requests
- **Public API only** — uses .json suffix API, not OAuth endpoints

## Anti-Detection Notes for Agents

- **Do NOT parallelize requests** — the built-in rate-limit delay is for account safety
- **Batch operations**: add delays between CLI calls when doing bulk work
- **Chrome 133 fingerprint**: all requests use consistent browser identity
- **Exponential backoff**: 429/5xx errors are auto-retried with backoff

## Safety Notes

- Do not ask users to share raw cookie values in chat logs
- Prefer browser cookie extraction over manual secret copy/paste
- If auth fails, ask the user to re-login via `rdt login`
- Built-in rate-limit delay protects accounts; do not bypass it
