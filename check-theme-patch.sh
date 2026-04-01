#!/usr/bin/env bash
# Claude Code hook: check if theme patch needs re-applying after an update.
# Installed as a SessionStart hook. Runs on every session start.
#
# If the binary was updated (patch missing), auto-applies the patch.
# Stdout goes to Claude as context so the user sees what happened.

set -euo pipefail

CLAUDE_DIR="${HOME}/.claude"
PATCHER="${CLAUDE_DIR}/patch-theme.py"
MARKER="${CLAUDE_DIR}/.patched-version"

# Skip if patcher not installed
[ -f "$PATCHER" ] || exit 0

# Get current Claude version
CURRENT=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
[ -z "$CURRENT" ] && exit 0

# Check if version changed since last patch
if [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$CURRENT" ]; then
  exit 0  # Same version, patch is still applied
fi

# Version changed or first run — check patch status
STATUS=$(python3 "$PATCHER" --check 2>&1 | grep -oE 'original|patched|unknown' | head -1 || echo "unknown")

if [ "$STATUS" = "patched" ]; then
  echo "$CURRENT" > "$MARKER"
  exit 0
fi

if [ "$STATUS" = "original" ]; then
  echo "Claude Code was updated to $CURRENT — re-applying theme patch..."
  if python3 "$PATCHER" 2>&1; then
    echo "$CURRENT" > "$MARKER"
    echo "Theme patch re-applied successfully. Restart Claude Code for the new version."
  else
    echo "Theme patch failed for $CURRENT. The binary may have new minified names."
    echo "Run: python3 $PATCHER --check"
  fi
  exit 0
fi

# Unknown version — can't auto-patch
echo "Claude Code $CURRENT has unknown theme code patterns."
echo "The theme auto-switch patch needs updating for this version."
echo "See: https://github.com/LeonFedotov/claude-theme-auto"
exit 0
