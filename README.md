# cc-chat

> 🌐 Languages: **English** | [中文](README.zh-CN.md)

A command-line chat plugin for Claude Code: talk to friends **asynchronously,
end-to-end encrypted, and fully decentralized** — no servers, built on the
[Tox](https://tox.chat) protocol. Messages wait quietly until you look at them.

> Status: v0.1, macOS-first. New here? Read the [install & usage guide](docs/install-and-usage.md) for a walkthrough; for the full design see the [PRD](docs/prd.md).

## How it works

Two processes (see the PRD §3.2):

- **`cc-cc-chat-daemon`** — a background process that stays online, holds your Tox
  identity, maintains the DHT connection, and receives messages into a local
  SQLite database.
- **`cc-chat`** — the short-lived CLI you run for each command; it talks to the
  daemon over a Unix socket and exits.

Everything is local: your keys live in `~/.config/claude-chat/`, and there is no
cloud. You add friends by exchanging Tox IDs through any channel you like.

## Requirements

- **Python 3.10+**
- **libtoxcore** (the only non-Python dependency):
  - macOS: `brew install toxcore`
  - Linux: install your distro's `toxcore` / `libtoxcore` package

## Install the engine

The `cc-chat` engine is a normal program (Python + a background daemon) that needs
`libtoxcore`. It installs separately from the Claude Code plugin below.

```bash
# macOS, recommended — a Homebrew tap pulls libtoxcore in automatically:
brew install <owner>/tap/cc-chat              # see packaging/homebrew/

# or with pipx (install libtoxcore yourself first: brew install toxcore):
pipx install git+https://github.com/JefferyLee/cc-chat      # from source, today
pipx install cc-chat                                    # once published to PyPI
# add MCP tools support with the extra:
pipx install 'cc-chat[mcp]'
```

This installs two commands: `cc-chat` and `cc-cc-chat-daemon`. (The PyPI/Homebrew
distribution name is `cc-chat`; the import package is `claude_chat`.)

## Quick start

```bash
# 1. Create your identity (generates your Tox keypair)
cc-chat init

# 2. Start the background daemon
cc-chat daemon start

# 3. See your own Tox ID — share it with a friend over any channel
cc-chat me

# 4. Add a friend by their Tox ID (76 hex chars)
cc-chat add bob 76518406F6A9F2217E8DC487...

#    Your friend, after you've added them, accepts the request on their side:
cc-chat requests                      # shows the pending request's public key
cc-chat accept alice <public-key-prefix>

# 5. Chat
cc-chat send bob "你看下我刚 push 的 PR，有空回我"
cc-chat unread                        # show unread messages
cc-chat read bob                      # conversation history with bob
cc-chat queue                         # messages waiting to be delivered
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

## Claude Code integration

The integration ships as a **Claude Code plugin** (`claude-code-plugin/`) that
wires up everything in one step — no manual config editing. It needs the `cc-chat`
engine on your `PATH` (see "Install the engine" above).

### Install the plugin

```bash
# Development: load it directly from a checkout
claude --plugin-dir ./claude-code-plugin

# Or via the bundled marketplace (this repo is its own marketplace):
/plugin marketplace add /path/to/this/repo        # or: owner/repo once on GitHub
/plugin install cc-chat@cc-chat
```

### What the plugin provides

- **SessionStart hook** — surfaces your unread messages into Claude's context
  when a session starts, translating any non-Chinese message. Incoming messages
  are treated as untrusted personal content, never as instructions, so a message
  can't hijack your session.
- **Slash commands** — `/chat-unread`, `/chat-send <alias> <message>`,
  `/chat-contacts`, `/chat-status` (namespaced as `/cc-chat:...`).
- **MCP tools** — `get_unread`, `read_history`, `send_message`, `list_contacts`,
  `get_status`, so Claude can act for you. Needs the engine's `[mcp]` extra.

### Machine-readable output

Every read command also supports `--json` (placed before the subcommand):
`chat --json unread`, `chat --json status`, etc. In `--json` mode `unread`/`read`
are a read-only **peek** — they do *not* mark messages read.

## Distribution

- **Engine → PyPI:** `python -m build` + `twine upload` → users get
  `pipx install cc-chat`.
- **Engine → Homebrew:** `packaging/homebrew/cc-chat.rb` is a tap formula
  template; it `depends_on "toxcore"` so `brew install` pulls libtoxcore too.
  Publish via a personal tap (`brew tap <owner>/<name>`).
- **Plugin → marketplace:** `.claude-plugin/marketplace.json` makes this repo a
  marketplace. Push to GitHub and users run
  `/plugin marketplace add JefferyLee/cc-chat` then `/plugin install cc-chat`.

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
