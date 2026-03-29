# Claude Code Theme Auto-Switch Patch

Patches the Claude Code binary so the `"auto"` theme reactively follows macOS system appearance (dark ↔ light) **during a running session**.

Without this patch, Claude Code's built-in `"auto"` theme only checks the OS appearance at startup. If you switch macOS from light to dark mode mid-session, the Claude Code UI stays on the old theme until you restart.

## How it works

The patch modifies the theme provider's React `useEffect` hook inside the compiled binary. The original hook is a no-op:

```javascript
// Original — empty, does nothing
WDT.useEffect(() => {}, [z]);
```

The patch replaces it with a 5-second polling interval:

```javascript
// Patched — polls macOS appearance every 5 seconds when theme is "auto"
WDT.useEffect(() => {
  let t = z == "auto" && setInterval(() => H(pPR()), 5e3);
  return () => clearInterval(t);
}, [z]);
```

`pPR()` runs `defaults read -g AppleInterfaceStyle` and returns `"dark"` or `"light"`. React's `useState` deduplicates identical values, so no re-render occurs unless the theme actually changed.

### Byte-budget technique

The Bun-compiled Mach-O binary embeds JS source at a fixed offset. The replacement **must be exactly the same byte length** as the original to avoid shifting offsets. We achieve this by compressing nearby code:

| Compression | Bytes saved |
|---|---|
| `===` → `==` (8 string comparisons) | 8 |
| `!==null` → `!=null` (2 occurrences) | 2 |
| `spawnSync` with array args → `execSync` with single string + try/catch | 53 |
| `Pu_===void 0` → `??=` operator | 22 |
| **Total saved** | **85** |
| Interval code added | −76 |
| **Net surplus (padded with spaces)** | **9** |

After patching, the binary is ad-hoc re-signed with `codesign -s -`.

## Requirements

- macOS (uses `defaults read -g AppleInterfaceStyle` for detection)
- Python 3.10+
- Claude Code installed as a Mach-O binary (mise, standalone). For npm installations, edit `cli.js` directly.

## Usage

```bash
# Apply the patch
python3 patch-theme.py

# Preview without modifying
python3 patch-theme.py --dry-run

# Check current status
python3 patch-theme.py --check

# Restore original binary from backup
python3 patch-theme.py --restore

# Use a specific binary path
python3 patch-theme.py --path /path/to/claude
```

The patcher automatically:
1. Locates the Claude Code binary (mise → `which` → common paths)
2. Creates a backup (`.backup` alongside the binary)
3. Applies the same-length byte replacement
4. Re-signs the binary with an ad-hoc signature
5. Sets `"theme": "auto"` in `~/.claude.json`

### After Claude Code updates

Updates replace the binary, removing the patch. Re-run `python3 patch-theme.py` after each update.

## Tested versions

| Claude Code | Status | Date | Notes |
|---|---|---|---|
| 2.1.76 | Tested | 2026-03-29 | Initial patch, Bun binary via mise |

## How the original code works

Claude Code already supports `"auto"` as a theme value (not documented, not in `/theme` UI). The detection logic:

```
~/.claude.json: "theme": "auto"
        ↓
    Jfq() — cached detection (runs once at startup)
    Wfq() — fresh detection (runs when user opens /theme picker)
        ↓
    $k6() → pPR() — calls `defaults read -g AppleInterfaceStyle`
        ↓
    Returns "dark" or "light"
```

The gap: `Wfq()` (fresh check) only fires when the user interacts with the theme picker. There is no listener for OS theme changes mid-session. This patch fills that gap with polling.

## Context

- [Issue #2990](https://github.com/anthropics/claude-code/issues/2990) — Automatic light/dark theme selection (open since early 2025)
- [Issue #11813](https://github.com/anthropics/claude-code/issues/11813) — System theme support (134+ upvotes)
- [OSC 11 approach](https://github.com/anthropics/claude-code/issues/2990#issuecomment-4150099587) — The "right" cross-platform solution (query terminal background color). Used by Helix, bat, delta, neovim. This patch uses the simpler macOS-specific `defaults` command instead.
- Inspired by [claude-code-patches](https://github.com/aleks-apostle/claude-code-patches) (thinking display patch)

## Restoring

```bash
# Via the patcher
python3 patch-theme.py --restore

# Or manually
cp ~/.local/share/mise/installs/claude/2.1.76/claude.backup \
   ~/.local/share/mise/installs/claude/2.1.76/claude
```

## License

MIT
