# claude-chat

A command-line chat plugin for Claude Code: talk to friends **asynchronously,
end-to-end encrypted, and fully decentralized** — no servers, built on the
[Tox](https://tox.chat) protocol. Messages wait quietly until you look at them.

> Status: v0.1, macOS-first. See [the PRD](tox-chat-plugin-prd.md) for the full design.

## How it works

Two processes (see the PRD §3.2):

- **`chat-daemon`** — a background process that stays online, holds your Tox
  identity, maintains the DHT connection, and receives messages into a local
  SQLite database.
- **`chat`** — the short-lived CLI you run for each command; it talks to the
  daemon over a Unix socket and exits.

Everything is local: your keys live in `~/.config/claude-chat/`, and there is no
cloud. You add friends by exchanging Tox IDs through any channel you like.

## Requirements

- **Python 3.10+**
- **libtoxcore** (the only non-Python dependency):
  - macOS: `brew install toxcore`
  - Linux: install your distro's `toxcore` / `libtoxcore` package

## Install

From a checkout of this repo:

```bash
# recommended: isolated install with pipx
pipx install .

# or with pip
pip install .
```

This installs two commands: `chat` and `chat-daemon`.

## Quick start

```bash
# 1. Create your identity (generates your Tox keypair)
chat init

# 2. Start the background daemon
chat daemon start

# 3. See your own Tox ID — share it with a friend over any channel
chat me

# 4. Add a friend by their Tox ID (76 hex chars)
chat add bob 76518406F6A9F2217E8DC487...

#    Your friend, after you've added them, accepts the request on their side:
chat requests                      # shows the pending request's public key
chat accept alice <public-key-prefix>

# 5. Chat
chat send bob "你看下我刚 push 的 PR，有空回我"
chat unread                        # show unread messages
chat read bob                      # conversation history with bob
chat queue                         # messages waiting to be delivered
```

If you message a friend who is offline, the message is queued locally and sent
automatically when they next come online.

## Commands

| Command | What it does |
|---|---|
| `chat init` | Generate your identity (one time) |
| `chat me` | Show your Tox ID, name, connection state |
| `chat set-name <name>` | Set your display name |
| `chat status` | Daemon status, DHT connection, contacts, queue, stats |
| `chat add <alias> <tox_id>` | Add a friend by their Tox ID |
| `chat requests` | Show pending friend requests |
| `chat accept <alias> <pubkey-prefix>` | Accept a friend request, naming them locally |
| `chat contacts [--online]` | List contacts |
| `chat send <alias> <message>` | Send a message (`-` reads from stdin) |
| `chat unread [alias]` | Show (and mark read) unread messages |
| `chat read <alias> [--limit N]` | Show conversation history |
| `chat queue` | Show messages waiting to be delivered |
| `chat introduce <to> <whom>` | Share one contact's details with another |
| `chat introductions` | Show contacts others have introduced to you |
| `chat accept-intro <from> <whom> [--alias]` | Accept an introduction |
| `chat daemon start` / `stop` | Manage the background daemon |

## Configuration

Optional `~/.config/claude-chat/config.toml`:

```toml
[retry]
ack_timeout_minutes = 5    # resend an un-acked message after this long
fail_after_hours = 24      # give up (mark failed) after this long
```

## Files

Everything lives under `~/.config/claude-chat/` (override with the
`CLAUDE_CHAT_HOME` environment variable — useful for running two daemons on one
machine during testing):

```
tox_state.bin   your Tox keys + friend list
chat.db         SQLite: contacts, messages, queue
daemon.sock     IPC socket    daemon.pid   process id    daemon.log   log
config.toml     optional configuration
```

## Limitations (v1)

- macOS-first (Linux should work given libtoxcore; not yet a tested target).
- The local database and your private key are **not** encrypted at rest — they
  rely on filesystem permissions. Don't use on a shared/untrusted machine.
- Your IP is visible to people you chat with (a property of the Tox protocol).
- No group chat, voice/video, file transfer, or multi-device sync.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -m "not dht"   # fast offline tests
.venv/bin/python -m pytest -m dht          # slow tests that use the real Tox DHT
```
