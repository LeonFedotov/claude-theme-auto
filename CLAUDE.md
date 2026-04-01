# Claude Theme Auto

This repo patches Claude Code to reactively switch dark/light themes when the OS appearance changes mid-session.

## Quick reference

```bash
# Apply patch (run after every Claude Code update)
python3 patch-theme.py

# Check status
python3 patch-theme.py --check

# Restore original
python3 patch-theme.py --restore

# Dry run
python3 patch-theme.py --dry-run
```

## How it works

The patch modifies the Claude Code binary (same-length byte replacement) to:
1. Replace the startup-only theme detection with a call to `~/.claude/detect-theme`
2. Add a 1-second polling interval in the React theme provider's `useEffect` hook

The `detect-theme` script uses `defaults read` (macOS) or OSC 11 terminal escape sequences (Linux/SSH/tmux) to detect the current appearance.

## Theme styles

Two detect-theme variants ship in this repo:
- `detect-theme-ansi` — returns `dark-ansi`/`light-ansi` (ANSI colors only, adapts to terminal palette)
- `detect-theme-standard` — returns `dark`/`light` (hardcoded RGB colors)

The installed script at `~/.claude/detect-theme` is whichever variant was chosen at install time. To switch, copy the other variant over it.

## Adding support for a new Claude Code version

When a new version isn't recognized (`--check` says "unknown"), the minified function names have changed. To add support:

1. Find the theme code in the binary:
   ```bash
   python3 -c "
   import subprocess
   binary = subprocess.run(['which', 'claude'], capture_output=True, text=True).stdout.strip()
   import os; binary = os.path.realpath(binary)
   data = open(binary, 'rb').read()
   idx = data.find(b'COLORFGBG')
   print(data[max(0,idx-500):idx+1000].decode('utf-8', errors='replace'))
   "
   ```

2. Identify the pattern — look for:
   - `function XXX(){if(YYY===void 0)YYY=ZZZ()??"dark";return YYY}` (cached detect)
   - `function ZZZ(){let H=process.env.COLORFGBG;...}` (raw detect using COLORFGBG)
   - `RR.useEffect(()=>{},[...])` (empty useEffect — this is where polling gets injected)

3. Add a new entry to the `VERSIONS` list in `patch-theme.py` following the existing pattern:
   - Copy the nearest existing version entry
   - Replace all minified names with the new ones
   - The key transformations: `===void 0` to `??=`, `===` to `==`, `!==null` to `!=null`, COLORFGBG body to `execSync` of detect-theme, empty useEffect to `setInterval` polling

4. Verify: `python3 patch-theme.py --dry-run`

## Supported versions

Check the `VERSIONS` list in `patch-theme.py` for all supported version labels.
