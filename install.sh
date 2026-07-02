#!/usr/bin/env bash
# toxi one-shot installer. Detects what's already present and installs or upgrades:
#   libtoxcore -> pipx -> toxi engine -> identity/daemon -> Claude Code plugin.
#
#   curl -fsSL https://raw.githubusercontent.com/JefferyLee/toxi/master/install.sh | bash
set -euo pipefail

REPO="JefferyLee/toxi"
REPO_URL="https://github.com/${REPO}"
PLUGINS_DIR="${HOME}/.claude/plugins"
MARKETPLACE_DIR="${PLUGINS_DIR}/marketplaces/toxi"
CACHE_ROOT="${PLUGINS_DIR}/cache/toxi/toxi"

info() { printf '\033[1;34m→\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m⚠\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$1" >&2; exit 1; }

OS="$(uname -s)"
have() { command -v "$1" >/dev/null 2>&1; }

# 1. libtoxcore -----------------------------------------------------------------
if pkg-config --exists toxcore 2>/dev/null \
   || ls /opt/homebrew/lib/libtoxcore* /usr/local/lib/libtoxcore* /usr/lib/libtoxcore* >/dev/null 2>&1; then
  ok "libtoxcore present"
elif [ "$OS" = "Darwin" ] && have brew; then
  info "Installing libtoxcore (brew install toxcore)…"; brew install toxcore
else
  die "libtoxcore not found. Install it first (macOS: brew install toxcore; Linux: your distro's libtoxcore)."
fi

# 2. pipx -----------------------------------------------------------------------
if have pipx; then
  ok "pipx present"
elif [ "$OS" = "Darwin" ] && have brew; then
  info "Installing pipx…"; brew install pipx; pipx ensurepath || true
else
  info "Installing pipx via pip…"; python3 -m pip install --user pipx && python3 -m pipx ensurepath || true
fi
export PATH="${HOME}/.local/bin:${PATH}"
have pipx || die "pipx still not on PATH — open a new shell and re-run."

# 3. toxi engine (install or upgrade) -------------------------------------------
if have toxi; then
  info "toxi present ($(toxi --version 2>/dev/null || echo '?')) — upgrading…"
  pipx upgrade toxi >/dev/null 2>&1 || pipx install --force "toxi[mcp] @ git+${REPO_URL}"
  pipx inject toxi mcp >/dev/null 2>&1 || true
else
  info "Installing toxi engine from ${REPO_URL}…"
  pipx install "toxi[mcp] @ git+${REPO_URL}"
fi
export PATH="${HOME}/.local/bin:${PATH}"
have toxi || die "toxi still not on PATH — open a new shell and re-run."
ok "engine: $(toxi --version 2>/dev/null)"

# 4. identity + daemon (refresh so the running daemon picks up the new engine) --
info "Setting up identity + daemon…"
toxi daemon stop >/dev/null 2>&1 || true
toxi setup-engine

# 5. Claude Code present? -------------------------------------------------------
if ! have claude && [ ! -d "${HOME}/.claude" ]; then
  warn "Claude Code not detected — engine is ready. Install Claude Code, then re-run this to add the plugin."
  ok "Done (engine only)."
  exit 0
fi
ok "Claude Code detected"

# 6. plugin: clone-or-update the marketplace, deploy to cache, write the registry
if [ -d "${MARKETPLACE_DIR}/.git" ]; then
  info "Updating plugin from GitHub…"
  git -C "${MARKETPLACE_DIR}" fetch --quiet origin
  git -C "${MARKETPLACE_DIR}" reset --quiet --hard origin/HEAD
else
  info "Cloning plugin marketplace…"
  rm -rf "${MARKETPLACE_DIR}"; mkdir -p "$(dirname "${MARKETPLACE_DIR}")"
  git clone --quiet --depth 1 "${REPO_URL}" "${MARKETPLACE_DIR}"
fi

PLUGIN_SRC="${MARKETPLACE_DIR}/claude-code-plugin"
VERSION="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "${PLUGIN_SRC}/.claude-plugin/plugin.json")"
SHA="$(git -C "${MARKETPLACE_DIR}" rev-parse HEAD)"
HAD_PLUGIN="no"
if grep -q '"toxi@toxi"' "${PLUGINS_DIR}/installed_plugins.json" 2>/dev/null; then HAD_PLUGIN="yes"; fi

# Deploy fresh files into the versioned cache; drop stale version dirs.
DEST="${CACHE_ROOT}/${VERSION}"
rm -rf "${DEST}"; mkdir -p "${DEST}"; cp -R "${PLUGIN_SRC}/." "${DEST}/"
for d in "${CACHE_ROOT}"/*/; do
  [ -d "$d" ] || continue
  if [ "$(basename "$d")" != "${VERSION}" ]; then rm -rf "$d"; fi
done

# Update the three registry files (idempotent; preserves other plugins/keys).
python3 - "${VERSION}" "${SHA}" "${DEST}" "${MARKETPLACE_DIR}" "${REPO}" <<'PY'
import json, os, sys, time
version, sha, install_path, marketplace, repo = sys.argv[1:6]
home = os.path.expanduser("~"); plugins = os.path.join(home, ".claude", "plugins")
now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

def load(p):
    try:
        with open(p) as f: return json.load(f)
    except (FileNotFoundError, ValueError): return {}

def dump(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: json.dump(d, f, indent=2)

ip = os.path.join(plugins, "installed_plugins.json")
inst = load(ip) or {"version": 2, "plugins": {}}
inst.setdefault("plugins", {})
entries = inst["plugins"].get("toxi@toxi") or []
entry = entries[0] if entries else {"scope": "user", "installedAt": now}
entry.update({"version": version, "gitCommitSha": sha,
              "installPath": install_path, "lastUpdated": now})
inst["plugins"]["toxi@toxi"] = [entry]
dump(ip, inst)

km = os.path.join(plugins, "known_marketplaces.json")
known = load(km)
known.setdefault("toxi", {"source": {"source": "github", "repo": repo},
                          "installLocation": marketplace, "lastUpdated": now})
dump(km, known)

sp = os.path.join(home, ".claude", "settings.json")
st = load(sp)
st.setdefault("enabledPlugins", {})["toxi@toxi"] = True

# statusLine: wrap an existing command-type line so toxi composes instead of
# clobbering it (mirrors bootstrap.ensure_statusline). Saves the original to
# ~/.config/toxi/statusline_wrapped, which `toxi statusline` re-runs and appends to.
toxi_cmd = "toxi statusline"
cfg = os.environ.get("TOXI_HOME") or os.path.join(home, ".config", "toxi")
wrapped = os.path.join(cfg, "statusline_wrapped")
sl = st.get("statusLine")
if isinstance(sl, dict) and sl.get("command") == toxi_cmd:
    pass  # already ours
elif isinstance(sl, dict) and sl.get("type") == "command" and isinstance(sl.get("command"), str):
    os.makedirs(cfg, exist_ok=True)
    with open(wrapped, "w") as f:
        f.write(sl["command"])
    st["statusLine"] = {"type": "command", "command": toxi_cmd}
elif sl is None:
    if os.path.exists(wrapped):
        os.remove(wrapped)
    st["statusLine"] = {"type": "command", "command": toxi_cmd}
# else: a non-command statusLine we can't re-run — leave it untouched.
dump(sp, st)
PY

if [ "${HAD_PLUGIN}" = "yes" ]; then
  ok "Plugin upgraded to ${VERSION} (${SHA:0:7})"
else
  ok "Plugin installed: ${VERSION} (${SHA:0:7})"
fi

# 7. inside Claude Code? --------------------------------------------------------
if [ -n "${CLAUDECODE:-}" ]; then
  warn "You're inside Claude Code — run /reload-plugins to load it now."
else
  ok "Start (or restart) Claude Code to load the plugin."
fi
ok "Done."
