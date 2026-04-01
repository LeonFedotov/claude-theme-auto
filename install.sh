#!/usr/bin/env bash
set -euo pipefail

# Claude Code Theme Auto-Switch — one-click installer
#
# Install (ANSI themes, recommended):
#   curl -fsSL https://raw.githubusercontent.com/antonioacg/claude-code-theme-patch/main/install.sh | bash
#
# Install (standard RGB themes):
#   curl -fsSL .../install.sh | THEME_STYLE=standard bash
#
# Check status:
#   curl -fsSL .../install.sh | bash -s -- --check
#
# Restore original:
#   curl -fsSL .../install.sh | bash -s -- --restore

REPO="https://raw.githubusercontent.com/antonioacg/claude-code-theme-patch/main"
THEME_STYLE="${THEME_STYLE:-ansi}"
CLAUDE_DIR="${HOME}/.claude"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

info()  { printf '\033[1;34m>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m>\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m>\033[0m %s\n' "$*" >&2; }

# Check deps
if ! command -v python3 &>/dev/null; then
  err "python3 is required but not found"
  exit 1
fi

if ! command -v claude &>/dev/null; then
  err "Claude Code is not installed"
  exit 1
fi

# Download files
info "Downloading..."
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/patch-theme.py" -o "$TMPDIR/patch-theme.py"
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/detect-theme-${THEME_STYLE}" -o "$TMPDIR/detect-theme"
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/tw.js" -o "$TMPDIR/tw.js"
chmod +x "$TMPDIR/detect-theme"

if [ "${1:-}" = "--check" ]; then
  python3 "$TMPDIR/patch-theme.py" --check
  [ -f "$CLAUDE_DIR/tw.js" ] && echo "tw.js: installed" || echo "tw.js: NOT installed"
  [ -f "$CLAUDE_DIR/theme-watcher" ] && echo "theme-watcher: installed" || echo "theme-watcher: not installed (optional)"
  exit 0
fi

if [ "${1:-}" = "--restore" ]; then
  info "Restoring original binary..."
  python3 "$TMPDIR/patch-theme.py" --restore
  exit 0
fi

# Install tw.js (event-driven theme watcher module)
mkdir -p "$CLAUDE_DIR"
cp "$TMPDIR/tw.js" "$CLAUDE_DIR/tw.js"
info "Installed tw.js (event-driven theme watcher)"

# Configure theme names
if [ "$THEME_STYLE" != "standard" ]; then
  cat > "$CLAUDE_DIR/tw.config.json" << 'CONF'
{"dark": "dark-ansi", "light": "light-ansi"}
CONF
  info "Theme style: ANSI (uses terminal palette)"
else
  cat > "$CLAUDE_DIR/tw.config.json" << 'CONF'
{"dark": "dark", "light": "light"}
CONF
  info "Theme style: standard (hardcoded RGB)"
fi

# Apply binary patch
info "Patching binary..."
python3 "$TMPDIR/patch-theme.py"

# macOS: compile Swift watcher for 0ms latency
if [ "$(uname)" = "Darwin" ] && command -v swiftc &>/dev/null; then
  info "Compiling Swift theme watcher..."
  curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/theme-watcher.swift" -o "$TMPDIR/theme-watcher.swift"

  DARK_ARG="dark-ansi"
  LIGHT_ARG="light-ansi"
  if [ "$THEME_STYLE" = "standard" ]; then
    DARK_ARG="dark"
    LIGHT_ARG="light"
  fi

  if swiftc -O -o "$CLAUDE_DIR/theme-watcher" "$TMPDIR/theme-watcher.swift" 2>/dev/null; then
    ok "Swift watcher compiled"

    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST="$PLIST_DIR/com.claude.theme-watcher.plist"
    mkdir -p "$PLIST_DIR"
    cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.theme-watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>${CLAUDE_DIR}/theme-watcher</string>
        <string>--dark</string>
        <string>${DARK_ARG}</string>
        <string>--light</string>
        <string>${LIGHT_ARG}</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>/tmp/claude-theme-watcher.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/claude-theme-watcher.log</string>
</dict>
</plist>
PLISTEOF

    launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
    launchctl bootstrap gui/$(id -u) "$PLIST" 2>/dev/null && \
      ok "Swift watcher running (0ms theme detection)" || \
      warn "Could not start launchd agent — tw.js will use plist watcher (~100ms)"
  else
    warn "Swift compilation failed — tw.js will use plist watcher (~100ms)"
  fi
fi

# Install update detection hook
info "Installing SessionStart hook..."
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/check-theme-patch.sh" -o "$CLAUDE_DIR/check-theme-patch.sh"
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/CLAUDE.md" -o "$CLAUDE_DIR/CLAUDE.md"
chmod +x "$CLAUDE_DIR/check-theme-patch.sh"

# Record current version
CLAUDE_VER=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
[ -n "$CLAUDE_VER" ] && echo "$CLAUDE_VER" > "$CLAUDE_DIR/.patched-version"

# Add hook to settings.json
SETTINGS="$CLAUDE_DIR/settings.json"
python3 -c "
import json, sys, os
p = '$SETTINGS'
try:
    with open(p) as f: s = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    s = {}
h = s.setdefault('hooks', {})
ss = h.setdefault('SessionStart', [])
hook_cmd = 'bash \$HOME/.claude/check-theme-patch.sh'
for entry in ss:
    for hk in entry.get('hooks', []):
        if 'check-theme-patch' in hk.get('command', ''):
            sys.exit(0)
ss.append({
    'matcher': 'startup',
    'hooks': [{
        'type': 'command',
        'command': hook_cmd,
        'timeout': 10
    }]
})
with open(p, 'w') as f: json.dump(s, f, indent=2); f.write('\n')
" && ok "SessionStart hook installed (detects updates, Claude fixes the patch)"

echo
ok "Done! Restart Claude Code to activate."
ok "Theme switches automatically when OS appearance changes."
ok "After Claude Code updates, the patch re-applies automatically on next session."
