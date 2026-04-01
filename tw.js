// ~/.claude/tw.js — Theme watcher module for Claude Code
//
// Called by the patched binary: require("~/.claude/tw")(setSystemTheme)
// Must return a cleanup function (called on useEffect unmount).
//
// Platform detection:
//   macOS:   fs.watch on GlobalPreferences.plist + defaults read (~100ms)
//            Optional: Swift watcher daemon for 0ms via ~/.claude/.current-theme
//   Linux:   gdbus monitor on freedesktop portal (event-driven, 0ms)
//   Windows: PowerShell RegNotifyChangeKeyValue (event-driven, 0ms)
//   Other:   setInterval polling with detect-theme script (1s)

'use strict';

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = os.homedir();
const CLAUDE_DIR = path.join(HOME, '.claude');

// Read theme name config — defaults to ANSI themes
let DARK = 'dark-ansi';
let LIGHT = 'light-ansi';
try {
  const cfg = JSON.parse(fs.readFileSync(path.join(CLAUDE_DIR, 'tw.config.json'), 'utf8'));
  if (cfg.dark) DARK = cfg.dark;
  if (cfg.light) LIGHT = cfg.light;
} catch {}

function themeName(isDark) {
  return isDark ? DARK : LIGHT;
}

// ---------------------------------------------------------------------------
// macOS
// ---------------------------------------------------------------------------

function macOSDetect() {
  try {
    execSync('defaults read -g AppleInterfaceStyle', { stdio: 'pipe' });
    return true; // key exists = Dark
  } catch {
    return false; // key missing = Light
  }
}

function watchDarwin(setState) {
  // Check if Swift watcher is running (writes ~/.claude/.current-theme)
  const swiftThemeFile = path.join(CLAUDE_DIR, '.current-theme');
  let useSwiftWatcher = false;
  try {
    const content = fs.readFileSync(swiftThemeFile, 'utf8').trim();
    if (content) useSwiftWatcher = true;
  } catch {}

  if (useSwiftWatcher) {
    // Swift watcher mode: just watch the file it maintains
    setState(fs.readFileSync(swiftThemeFile, 'utf8').trim());
    const watcher = fs.watch(swiftThemeFile, () => {
      try {
        const theme = fs.readFileSync(swiftThemeFile, 'utf8').trim();
        if (theme) setState(theme);
      } catch {}
    });
    return () => watcher.close();
  }

  // Plist watch mode: watch GlobalPreferences.plist for any change
  setState(themeName(macOSDetect()));
  const plist = path.join(HOME, 'Library', 'Preferences', '.GlobalPreferences.plist');
  let debounce = null;
  let prev = macOSDetect();

  const watcher = fs.watch(plist, () => {
    if (debounce) return;
    debounce = setTimeout(() => {
      debounce = null;
      const isDark = macOSDetect();
      if (isDark !== prev) {
        prev = isDark;
        setState(themeName(isDark));
      }
    }, 100);
  });

  return () => {
    if (debounce) clearTimeout(debounce);
    watcher.close();
  };
}

// ---------------------------------------------------------------------------
// Linux — gdbus monitor on freedesktop portal
// ---------------------------------------------------------------------------

function linuxDetect() {
  try {
    const out = execSync(
      'gdbus call --session --dest org.freedesktop.portal.Desktop ' +
      '--object-path /org/freedesktop/portal/desktop ' +
      '--method org.freedesktop.portal.Settings.Read ' +
      'org.freedesktop.appearance color-scheme',
      { stdio: 'pipe', timeout: 3000 }
    ).toString();
    const m = out.match(/uint32\s+(\d)/);
    return m ? m[1] === '1' : false; // 1=dark, 2=light, 0=no-pref
  } catch {
    return false;
  }
}

function watchLinux(setState) {
  // Initial detection
  let hasBus = true;
  try {
    setState(themeName(linuxDetect()));
  } catch {
    hasBus = false;
  }

  if (!hasBus) return watchFallback(setState);

  // Spawn gdbus monitor
  const proc = spawn('gdbus', [
    'monitor', '--session',
    '--dest', 'org.freedesktop.portal.Desktop',
    '--object-path', '/org/freedesktop/portal/desktop'
  ], { stdio: ['ignore', 'pipe', 'ignore'] });

  let buf = '';
  proc.stdout.on('data', (data) => {
    buf += data.toString();
    const lines = buf.split('\n');
    buf = lines.pop() || '';
    for (const line of lines) {
      const m = line.match(
        /SettingChanged\s*\(\s*'org\.freedesktop\.appearance',\s*'color-scheme',\s*<uint32\s+(\d)>/
      );
      if (m) {
        setState(themeName(m[1] === '1'));
      }
    }
  });

  proc.on('error', () => {}); // gdbus not found — silent
  return () => proc.kill();
}

// ---------------------------------------------------------------------------
// Windows — PowerShell registry watcher
// ---------------------------------------------------------------------------

function windowsDetect() {
  try {
    const out = execSync(
      'reg query "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme',
      { stdio: 'pipe', timeout: 3000 }
    ).toString();
    return out.includes('0x0'); // 0x0 = dark, 0x1 = light
  } catch {
    return false;
  }
}

function watchWindows(setState) {
  setState(themeName(windowsDetect()));

  // Write PowerShell watcher script
  const psScript = path.join(CLAUDE_DIR, 'theme-watcher.ps1');
  try {
    fs.writeFileSync(psScript, `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class RegMon {
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern int RegOpenKeyEx(IntPtr hKey, string subKey, int options, int sam, out IntPtr result);
    [DllImport("advapi32.dll", SetLastError=true)]
    public static extern int RegNotifyChangeKeyValue(IntPtr hKey, bool watchSubtree, int filter, IntPtr hEvent, bool async);
    [DllImport("advapi32.dll", SetLastError=true)]
    public static extern int RegCloseKey(IntPtr hKey);
    public static readonly IntPtr HKCU = new IntPtr(unchecked((int)0x80000001));
}
"@
$subKey = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
$prev = ""
while ($true) {
    $hKey = [IntPtr]::Zero
    $r = [RegMon]::RegOpenKeyEx([RegMon]::HKCU, $subKey, 0, 0x20019 -bor 0x0010, [ref]$hKey)
    if ($r -ne 0) { Start-Sleep -Seconds 5; continue }
    [RegMon]::RegNotifyChangeKeyValue($hKey, $false, 4, [IntPtr]::Zero, $false) | Out-Null
    [RegMon]::RegCloseKey($hKey) | Out-Null
    $v = (Get-ItemPropertyValue "HKCU:\\$subKey" -Name AppsUseLightTheme -ErrorAction SilentlyContinue)
    $t = if ($v -eq 0) { "dark" } else { "light" }
    if ($t -ne $prev) { $prev = $t; Write-Output "theme:$t"; [Console]::Out.Flush() }
}
`.trim());
  } catch {
    return watchFallback(setState);
  }

  const proc = spawn('powershell', [
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', psScript
  ], { stdio: ['ignore', 'pipe', 'ignore'] });

  let buf = '';
  proc.stdout.on('data', (data) => {
    buf += data.toString();
    const lines = buf.split('\n');
    buf = lines.pop() || '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed === 'theme:dark') setState(themeName(true));
      else if (trimmed === 'theme:light') setState(themeName(false));
    }
  });

  proc.on('error', () => {});
  return () => proc.kill();
}

// ---------------------------------------------------------------------------
// Fallback — OSC 11 via internal querier (no subprocess, async)
// ---------------------------------------------------------------------------

// OSC 11 query object — same format as Claude's internal oscColor(11)
const OSC_BG_QUERY = {
  request: '\x1b]11;?\x07',  // ESC ] 11 ; ? BEL
  match: (r) => r.type === 'osc' && r.code === 11,
};

function parseOscLuminance(data) {
  // Parse rgb:RRRR/GGGG/BBBB or #RRGGBB
  let r, g, b;
  const rgbMatch = data.match(/^rgba?:([0-9a-f]{1,4})\/([0-9a-f]{1,4})\/([0-9a-f]{1,4})/i);
  if (rgbMatch) {
    const norm = (hex) => parseInt(hex, 16) / (16 ** hex.length - 1);
    r = norm(rgbMatch[1]); g = norm(rgbMatch[2]); b = norm(rgbMatch[3]);
  } else {
    const hexMatch = data.match(/^#([0-9a-f]+)$/i);
    if (!hexMatch) return undefined;
    const h = hexMatch[1];
    const len = h.length / 3;
    const norm = (s) => parseInt(s, 16) / (16 ** s.length - 1);
    r = norm(h.slice(0, len)); g = norm(h.slice(len, len*2)); b = norm(h.slice(len*2));
  }
  // ITU-R BT.709 luminance
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.5 ? 'light' : 'dark';
}

function watchQuerier(setState, querier) {
  let prev = null;
  let timer = null;

  async function poll() {
    try {
      const resp = await Promise.race([
        (async () => {
          const r = await querier.send(OSC_BG_QUERY);
          await querier.flush();
          return r;
        })(),
        new Promise((_, reject) => setTimeout(() => reject('timeout'), 3000)),
      ]);
      if (resp && resp.data) {
        const mode = parseOscLuminance(resp.data);
        if (mode) {
          const theme = themeName(mode === 'dark');
          if (theme !== prev) { prev = theme; setState(theme); }
        }
      }
    } catch {}
  }

  poll(); // initial detection
  timer = setInterval(poll, 5000); // poll every 5s (lightweight — no subprocess)
  return () => clearInterval(timer);
}

// ---------------------------------------------------------------------------
// Fallback — poll with detect-theme script (no querier available)
// ---------------------------------------------------------------------------

function watchScript(setState) {
  const script = path.join(CLAUDE_DIR, 'detect-theme');
  function detect() {
    try {
      return execSync(script, { stdio: 'pipe', timeout: 3000 }).toString().trim();
    } catch {
      return DARK;
    }
  }

  let prev = detect();
  setState(prev);
  const timer = setInterval(() => {
    const curr = detect();
    if (curr !== prev) { prev = curr; setState(curr); }
  }, 5000);

  return () => clearInterval(timer);
}

// ---------------------------------------------------------------------------
// Entry point — called by patched binary: require("~/.claude/tw")(setState, querier?)
// ---------------------------------------------------------------------------

module.exports = function(setState, querier) {
  const platform = process.platform;
  if (platform === 'darwin') return watchDarwin(setState);
  if (platform === 'linux') return watchLinux(setState);
  if (platform === 'win32') return watchWindows(setState);
  // SSH/tmux/other: use querier if available, else shell script
  if (querier) return watchQuerier(setState, querier);
  return watchScript(setState);
};
