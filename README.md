# Claude Code Theme Auto-Switch Patch

Patches the Claude Code binary so the `"auto"` theme reactively follows terminal dark/light mode **during a running session** — on macOS, Linux, through SSH, and through tmux.

Without this patch, Claude Code's built-in `"auto"` theme only checks the OS appearance at startup. If you switch from light to dark mode mid-session, the UI stays on the old theme until you restart.

## How it works

Two components:

### 1. Binary patch — polling interval

The theme provider's React `useEffect` hook is patched from a no-op to a 5-second polling interval:

```javascript
// Original — empty, does nothing
WDT.useEffect(() => {}, [z]);

// Patched — polls terminal theme every 5 seconds when theme is "auto"
WDT.useEffect(() => {
  let t = z == "auto" && setInterval(() => H(pPR()), 5e3);
  return () => clearInterval(t);
}, [z]);
```

`pPR()` now calls `~/.claude/detect-theme` via `execSync` instead of the macOS-only `defaults read` command.

### 2. detect-theme script — OSC 11 terminal query

A small shell script at `~/.claude/detect-theme` that:
1. Opens `/dev/tty` and sends the [OSC 11](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands) escape sequence (`\033]11;?\033\\`)
2. The terminal responds with its current background color as `rgb:RRRR/GGGG/BBBB`
3. Computes luminance from the RGB values
4. Prints `dark` (luminance < 128) or `light` to stdout

This queries the **terminal directly** — not the OS. It works:
- **macOS** — Ghostty, iTerm2, WezTerm, Kitty, Terminal.app
- **Linux** — any terminal with OSC 11 support
- **Through SSH** — escape sequences travel through the PTY
- **Through tmux** — tmux 3.4+ natively forwards OSC 11 to the outer terminal

### Byte-budget technique

The Bun-compiled binary embeds JS source at a fixed offset. The replacement must be exactly the same byte length. Compressions used:

| Compression | Bytes saved |
|---|---|
| `===` → `==` (8 string comparisons) | 8 |
| `!==null` → `!=null` (2 occurrences) | 2 |
| `spawnSync` + result parsing → `execSync` of external script | 46 |
| `Pu_===void 0` → `??=` operator | 22 |
| `function $k6(){return pPR()}` → `var $k6=pPR;` | 16 |
| **Total saved** | **94** |
| Interval code + script path added | −78 |
| **Net surplus (padded with spaces)** | **16** |

After patching, the binary is ad-hoc re-signed with `codesign -s -` on macOS.

## Requirements

- Python 3.10+
- A terminal with OSC 11 support (most modern terminals)
- Claude Code installed as a compiled binary (mise, standalone download). For npm installations, edit `cli.js` directly.

## Usage

```bash
# Apply the patch (patches binary + installs detect-theme script)
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
2. Installs `~/.claude/detect-theme` (OSC 11 detection script)
3. Creates a backup (`.backup` alongside the binary)
4. Applies the same-length byte replacement
5. Re-signs the binary (macOS only)
6. Sets `"theme": "auto"` in `~/.claude.json`

### After Claude Code updates

Updates replace the binary, removing the patch. Re-run `python3 patch-theme.py` after each update. The `detect-theme` script persists across updates.

### Remote servers

To patch Claude Code on a remote machine:

```bash
# Copy the patcher and detect-theme script
scp -r . user@remote:/tmp/claude-theme-patch/

# SSH in and apply
ssh user@remote 'cd /tmp/claude-theme-patch && python3 patch-theme.py'
```

The `detect-theme` script uses OSC 11, so theme detection works through SSH + tmux — it queries the terminal on your local machine, not the remote OS.

## Tested versions

| Claude Code | Platform | Status | Date | Notes |
|---|---|---|---|---|
| 2.1.76 | macOS arm64 (mise) | Tested | 2026-03-29 | Bun Mach-O, `defaults read` detection |
| 2.1.86 | Linux aarch64 (mise) | Tested | 2026-03-30 | Bun ELF, `COLORFGBG` detection |
| 2.1.87 | macOS arm64 (mise) | Tested | 2026-03-30 | Same structure as 2.1.86, different function names |
| 2.1.87 | Linux aarch64 (mise) | Tested | 2026-03-30 | Different names than macOS build of same version |

### Version differences

The minified JS uses different function names across versions. The patcher maintains patterns for each supported version and auto-detects which one matches.

| | v2.1.76 | v2.1.86 | v2.1.87 |
|---|---|---|---|
| Theme provider | `MDT` | `EGq` | `E0_` |
| Cached detect | `Jfq` | `Cd8` | `IFH` |
| Raw detect | `pPR` / `$k6` | `_k5` | `MR4` |
| Original method | `defaults read` | `COLORFGBG` | `COLORFGBG` |
| React import | `WDT`, `Ak6`, `fm` | `zA` | `KG` |
| useEffect deps | `[z]` | `[j, J]` | `[f, w]` |

## How the original code works

Claude Code already supports `"auto"` as a theme value (not documented). The detection logic:

```
~/.claude.json: "theme": "auto"
        ↓
    Jfq() — cached detection (runs once at startup)
    Wfq() — fresh detection (runs when user opens /theme picker)
        ↓
    $k6() → pPR() — calls `defaults read -g AppleInterfaceStyle` (macOS only)
        ↓
    Returns "dark" or "light"
```

The gap: `Wfq()` only fires when the user interacts with the theme picker. There is no listener for theme changes mid-session. This patch fills that gap with polling, and replaces the macOS-only `defaults` detection with cross-platform OSC 11.

## Context

- [Issue #2990](https://github.com/anthropics/claude-code/issues/2990) — Automatic light/dark theme selection
- [Issue #11813](https://github.com/anthropics/claude-code/issues/11813) — System theme support (134+ upvotes)
- [OSC 11 comment](https://github.com/anthropics/claude-code/issues/2990#issuecomment-4150099587) — Suggested approach using terminal background query
- [Helix implementation](https://github.com/helix-editor/helix/pull/14356) — Same OSC 11 approach
- Inspired by [claude-code-patches](https://github.com/aleks-apostle/claude-code-patches)

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
