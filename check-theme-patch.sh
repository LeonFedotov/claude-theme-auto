#!/usr/bin/env bash
# Claude Code SessionStart hook: detect when binary was updated and theme patch is missing.
# Stdout goes to Claude as context — Claude handles the fix using CLAUDE.md instructions.

CLAUDE_DIR="${HOME}/.claude"
MARKER="${CLAUDE_DIR}/.patched-version"

# Get current version
CURRENT=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
[ -z "$CURRENT" ] && exit 0

# First run — no marker yet, assume patched
if [ ! -f "$MARKER" ]; then
  echo "$CURRENT" > "$MARKER"
  exit 0
fi

# Same version — patch is still applied
PREVIOUS=$(cat "$MARKER" 2>/dev/null || echo "")
[ "$CURRENT" = "$PREVIOUS" ] && exit 0

# Version changed — patch was overwritten by the update
echo "$CURRENT" > "$MARKER"
cat << EOF
IMPORTANT: Claude Code was updated from $PREVIOUS to $CURRENT. The theme auto-switch binary patch was overwritten.

To fix: follow the instructions in ~/.claude/CLAUDE.md or https://github.com/antonioacg/claude-code-theme-patch/blob/main/CLAUDE.md to extract the new version's minified names, update patch-theme.py, and re-apply the patch.

The files at ~/.claude/tw.js and ~/.claude/detect-theme are still intact — only the binary patch needs re-applying.
EOF
