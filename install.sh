#!/usr/bin/env bash
set -euo pipefail

# Claude Theme Auto — one-click installer
#
# Install (ANSI themes, recommended):
#   curl -fsSL https://raw.githubusercontent.com/antonioacg/claude-code-theme-patch/main/install.sh | bash
#
# Install (standard RGB themes):
#   curl -fsSL https://raw.githubusercontent.com/antonioacg/claude-code-theme-patch/main/install.sh | THEME_STYLE=standard bash
#
# Check status:
#   curl -fsSL .../install.sh | bash -s -- --check
#
# Restore original:
#   curl -fsSL .../install.sh | bash -s -- --restore

REPO="https://raw.githubusercontent.com/antonioacg/claude-code-theme-patch/main"
THEME_STYLE="${THEME_STYLE:-ansi}"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

info()  { printf '\033[1;34m>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m>\033[0m %s\n' "$*"; }
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

info "Downloading claude-theme-auto..."
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/patch-theme.py" -o "$TMPDIR/patch-theme.py"
curl -fsSL --max-time 15 --connect-timeout 5 "$REPO/detect-theme-${THEME_STYLE}" -o "$TMPDIR/detect-theme"
chmod +x "$TMPDIR/detect-theme"

if [ "${1:-}" = "--check" ]; then
  python3 "$TMPDIR/patch-theme.py" --check
  exit 0
fi

if [ "${1:-}" = "--restore" ]; then
  info "Restoring original binary..."
  python3 "$TMPDIR/patch-theme.py" --restore
  exit 0
fi

info "Applying patch (theme style: $THEME_STYLE)..."
python3 "$TMPDIR/patch-theme.py"
echo
ok "Restart Claude Code to activate."
