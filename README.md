# rdt-cli

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

> Reddit in your terminal 📖

A command-line tool for browsing Reddit — read feeds, search posts, view comments, upvote, save, and subscribe, all from the terminal.

## More Tools

| Tool | Description |
|------|-------------|
| [boss-cli](https://github.com/jackwener/boss-cli) | BOSS 直聘 CLI |
| [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) | 小红书 CLI |
| [twitter-cli](https://github.com/jackwener/twitter-cli) | Twitter/X CLI |
| [bilibili-cli](https://github.com/jackwener/bilibili-cli) | 哔哩哔哩 CLI |
| [discord-cli](https://github.com/jackwener/discord-cli) | Discord CLI |
| [tg-cli](https://github.com/jackwener/tg-cli) | Telegram CLI |

## Features

- 🔐 **Auth** — Browser cookie extraction (Chrome, Firefox, Edge, Brave)
- 🏠 **Feed** — Browse home feed, popular, and /r/all
- 📋 **Subreddits** — Browse any subreddit with sort/time filters
- 📰 **Posts** — Read posts and comment trees with syntax highlighting
- 🔢 **Short-Index** — `rdt show 3` to quickly read result #3
- 🔍 **Search** — Full-text search with subreddit, sort, and time filters
- 📤 **Export** — Export search results to CSV or JSON
- 👤 **Users** — View user profiles and post history
- ⬆️ **Upvote** — Vote on posts and comments
- 💾 **Save** — Save/unsave posts
- 📡 **Subscribe** — Subscribe/unsubscribe to subreddits
- 🛡️ **Anti-Detection** — Gaussian jitter, exponential backoff, Chrome 133 fingerprint
- 📊 **Structured Output** — `--json` / `--yaml` for all commands

## Installation

```bash
# Install with uv (recommended)
uv tool install rdt-cli

# Or with pip
pip install rdt-cli

# Development
git clone git@github.com:jackwener/rdt-cli.git
cd rdt-cli
uv sync
```

## Usage

### Authentication

```bash
# Extract cookies from browser (must be logged into reddit.com)
rdt login

# Check auth status
rdt status

# Clear saved cookies
rdt logout
```

### Browsing

```bash
# Home feed (requires login)
rdt feed

# Popular posts
rdt popular

# Browse a subreddit
rdt sub python
rdt sub programming -s top -t week
rdt sub rust -s new -n 10

# Subreddit info
rdt sub-info python
```

### Reading Posts

```bash
# Read a post by ID
rdt read 1abc123

# Read by short-index (after browsing)
rdt sub python        # browse → see numbered list
rdt show 3            # read post #3

# Sort comments
rdt read 1abc123 -s top
rdt show 1 -s new
```

### Search

```bash
# Global search
rdt search "python async"

# Search within subreddit
rdt search "error handling" -r rust

# Sort by top, last year
rdt search "machine learning" -s top -t year
```

### Export

```bash
# Export to CSV
rdt export "python tips" -n 100 -o tips.csv

# Export to JSON
rdt export "rust vs go" --format json -o comparison.json
```

### Users

```bash
# View user profile
rdt user spez

# View user's posts
rdt user-posts spez
```

### Interactions (require login)

```bash
# Upvote
rdt upvote 3              # upvote result #3
rdt upvote 1abc123        # upvote by ID
rdt upvote 3 --down       # downvote
rdt upvote 3 --undo       # remove vote

# Save
rdt save 3                # save result #3
rdt save 3 --undo         # unsave

# Subscribe
rdt subscribe python      # subscribe to r/python
rdt subscribe python --undo  # unsubscribe
```

### Utilities

```bash
# Verbose mode (show API requests)
rdt -v sub python

# Version
rdt --version

# JSON output
rdt sub python --json

# YAML output
rdt sub python --yaml
```

## Authentication

rdt-cli uses browser cookie extraction to authenticate with Reddit:

1. Login to [reddit.com](https://reddit.com) in your browser
2. Run `rdt login` — cookies are extracted automatically
3. Cookies are saved to `~/.config/rdt-cli/credential.json` (0600 permissions)
4. Auto-refresh: if cookies are older than 7 days, browser extraction is retried automatically

**Supported browsers**: Chrome, Firefox, Edge, Brave (via [browser-cookie3](https://github.com/borisbabic/browser_cookie3))

## Rate Limiting & Anti-Detection

| Strategy | Implementation |
|----------|---------------|
| Chrome 133 UA + sec-ch-ua | Consistent browser fingerprint |
| Gaussian jitter | ~1s mean delay with σ=0.3 between requests |
| 5% long pause | Random 2-5s pause to mimic reading |
| Exponential backoff | 2^attempt + random on 429/5xx |
| Cookie merge | Set-Cookie headers merged back into session |

## Project Structure

```
rdt_cli/
├── __init__.py           # Version
├── cli.py                # Click entry point
├── client.py             # API client (rate-limit, retry)
├── auth.py               # Cookie authentication + TTL refresh
├── constants.py          # URLs, headers, sort options
├── exceptions.py         # Error hierarchy
├── index_cache.py        # Short-index cache for show command
└── commands/
    ├── _common.py        # Shared helpers (handle_command, output routing)
    ├── auth.py           # login, logout, status
    ├── browse.py         # feed, popular, sub, sub-info, user, user-posts
    ├── post.py           # read, show
    ├── search.py         # search, export
    └── social.py         # upvote, save, subscribe
```

## Development

```bash
# Run tests
uv run pytest tests/test_cli.py -v

# Run smoke tests (requires login)
uv run pytest tests/test_smoke.py -v -m smoke

# Lint
uv run ruff check .
```

## Use as AI Agent Skill

See [SKILL.md](SKILL.md) for AI agent integration.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No Reddit cookies found` | Login to reddit.com in browser, then retry `rdt login` |
| `database is locked` | Close browser, then retry |
| `Session expired` | Run `rdt logout && rdt login` |
| `Rate limited` | Wait and retry; built-in backoff handles this automatically |

## License

Apache License 2.0
