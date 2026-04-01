# Claude Theme Auto

This repo patches Claude Code to reactively switch dark/light themes when the OS appearance changes mid-session.

## Quick reference

```bash
# Apply patch
python3 patch-theme.py

# Check status
python3 patch-theme.py --check

# Restore original
python3 patch-theme.py --restore

# Dry run
python3 patch-theme.py --dry-run
```

## How it works

The patch modifies the Claude Code binary (same-length byte replacement) to replace the empty `useEffect` in the ThemeProvider with a `require("~/.claude/tw")` call. The external `tw.js` module handles all platform-specific theme detection:

- **macOS**: `fs.watch` on GlobalPreferences.plist (~100ms) or Swift watcher daemon (0ms)
- **Linux**: `gdbus monitor` on freedesktop portal (event-driven, 0ms)
- **Windows**: PowerShell `RegNotifyChangeKeyValue` (event-driven, 0ms)
- **SSH/tmux**: Claude's internal `TerminalQuerier` for native async OSC 11 queries (500ms poll)

## Architecture

The patched useEffect calls: `require("~/.claude/tw")(setState, querier)`

- `setState` — React state setter for the resolved theme (e.g., `"dark-ansi"`)
- `querier` — Claude's internal `TerminalQuerier` instance (`internal_querier` from StdinContext). Used for native OSC 11 queries over SSH/tmux. May be `null` on older versions (2.1.76).

tw.js must export a function that takes `(setState, querier?)` and returns a cleanup function.

## Adding support for a new Claude Code version

When Claude Code updates, the binary is replaced and the patch is lost. A SessionStart hook detects this and outputs a message you'll see. To add support for the new version:

### Step 1: Find the theme code

```bash
python3 -c "
data = open('$(python3 -c "
import subprocess, os
r = subprocess.run(['which','claude'], capture_output=True, text=True)
print(os.path.realpath(r.stdout.strip()))
")', 'rb').read()
idx = data.find(b'COLORFGBG')
print(data[max(0,idx-500):idx+1000].decode('utf-8', errors='replace'))
"
```

### Step 2: Identify the minified names

Look for this pattern in the output:

```javascript
// Cached detect — runs once, caches result
function XXX(){if(YYY===void 0)YYY=ZZZ()??"dark";return YYY}

// Theme resolver — maps "auto" to detected theme  
function AAA(H){if(H==="auto")return XXX();return H}

// Raw detect — reads COLORFGBG env var
function ZZZ(){let H=process.env.COLORFGBG;if(!H)return;...}

// Variable declarations
var YYY;

// Theme provider component
function PPP({children:H,initialState:_,onThemeSave:q=SSS}){
  let[...]=RR.useState(...),[...]=RR.useState(null),
  [...,setState]=RR.useState(()=>...),
  activeSetting=...??...,{internal_querier:QQ}=HOOK();
  RR.useEffect(()=>{},[activeSetting,QQ]);   // <-- THIS IS THE EMPTY useEffect
  ...
  return RR.default.createElement(CTX.Provider,{value:...},H)}
```

You need to identify:
- `RR` — the React import variable
- `setState` — the state setter for resolved theme (3rd useState's setter)
- `QQ` — the `internal_querier` variable (destructured from the hook call)
- `activeSetting` — the variable in the useEffect deps that holds the active theme setting
- The useEffect deps array (e.g., `[activeSetting, QQ]`)

### Step 3: Add a new version entry

In `patch-theme.py`, add a new entry to the `VERSIONS` list. Copy the nearest existing version and update all minified names. The key transformations:

**For the detect function (COLORFGBG body → execSync):**
```javascript
// Original
function ZZZ(){let H=process.env.COLORFGBG;if(!H)return;...}

// Patched — calls external detect-theme script
function ZZZ(){try{return(""+require("child_process").execSync(
process.env.HOME+"/.claude/detect-theme"
,{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}
```

**For the cached detect (===void 0 → ??=):**
```javascript
// Original
function XXX(){if(YYY===void 0)YYY=ZZZ()??"dark";return YYY}

// Patched
function XXX(){return YYY??=ZZZ()??"dark"}
```

**For the useEffect (empty → require tw.js):**
```javascript
// Original
RR.useEffect(()=>{},[activeSetting,QQ]);

// Patched — passes setState AND querier to tw.js
RR.useEffect(()=>{try{if(activeSetting=="auto")return require(process.env.HOME+"/.claude/tw")(setState,QQ)}catch{}},[activeSetting,QQ]);
```

**Other compressions to fit byte budget:**
- `===` → `==` in string comparisons (e.g., `==="auto"` → `=="auto"`)
- `!==null` → `!=null`

### Step 4: Handle the querier variable

The `internal_querier` variable (`QQ` above) is passed as the second argument to tw.js. It enables native OSC 11 queries for SSH/tmux without subprocess spawning.

**If `internal_querier` is present in the new version** (look for `{internal_querier:QQ}=HOOK()` in the theme provider):
- Pass it: `require(...)(setState,QQ)`

**If `internal_querier` is NOT present** (e.g., the version removed it or restructured):
- Pass only setState: `require(...)(setState)`
- tw.js handles this gracefully — macOS/Linux/Windows watchers don't need the querier
- SSH/tmux users will get static detection only (initial detection at startup)
- **Optional fallback**: if SSH/tmux reactive switching is needed without the querier, add a `watchScript` function to tw.js that polls `~/.claude/detect-theme` via `execSync` every 1 second (the detect-theme scripts are still installed). This was previously included but removed to keep tw.js minimal. Example:
  ```javascript
  function watchScript(setState) {
    const script = require('path').join(require('os').homedir(), '.claude', 'detect-theme');
    let prev = require('child_process').execSync(script, {stdio:'pipe',timeout:3000}).toString().trim();
    setState(prev);
    const t = setInterval(() => {
      try {
        const c = require('child_process').execSync(script, {stdio:'pipe',timeout:3000}).toString().trim();
        if (c !== prev) { prev = c; setState(c); }
      } catch {}
    }, 1000);
    return () => clearInterval(t);
  }
  ```
  Wire it as the final fallback in the entry point: `if (!querier) return watchScript(setState);`

### Step 5: Verify

```bash
# Verify byte budget (patched must equal original length)
python3 patch-theme.py --dry-run

# Apply
python3 patch-theme.py

# Test: restart Claude Code, toggle OS theme, verify it switches
```

## Theme styles

Configurable via `~/.claude/tw.config.json`:

```json
{"dark": "dark-ansi", "light": "light-ansi"}
```

Valid theme values: `dark`, `light`, `dark-ansi`, `light-ansi`, `dark-daltonized`, `light-daltonized`

## Files installed

| File | Purpose |
|-|-|
| `~/.claude/tw.js` | Cross-platform theme watcher module |
| `~/.claude/tw.config.json` | Theme name configuration |
| `~/.claude/detect-theme` | Shell script fallback for initial detection |
| `~/.claude/check-theme-patch.sh` | SessionStart hook — detects binary updates |
| `~/.claude/CLAUDE.md` | This file — instructions for Claude to fix new versions |
| `~/.claude/theme-watcher` | (macOS) Compiled Swift watcher daemon |
| `~/Library/LaunchAgents/com.claude.theme-watcher.plist` | (macOS) launchd agent |

## Supported versions

Check the `VERSIONS` list in `patch-theme.py` for all supported version labels.
