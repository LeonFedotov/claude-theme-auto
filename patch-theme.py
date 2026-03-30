#!/usr/bin/env python3
"""
Claude Code Theme Auto-Switch Patch

Patches the Claude Code binary to reactively follow the terminal's dark/light
mode while a session is running. Without this patch, the built-in "auto" theme
only detects the OS theme at startup.

The patch adds a 5-second polling interval inside the theme provider's
useEffect hook. When the theme setting is "auto", it periodically calls
~/.claude/detect-theme (installed by this patcher) which uses OSC 11 to
query the terminal's background color and derive dark/light from luminance.

This works on macOS, Linux, through SSH, and through tmux — anywhere the
terminal supports OSC 11 (Ghostty, iTerm2, WezTerm, Kitty, and most modern
terminal emulators).

Byte-budget technique: the replacement must be exactly the same length as
the original to avoid shifting offsets in the binary. We achieve this by
compressing nearby code (=== to ==, ??= operator, etc.) and padding with
whitespace.

Usage:
    python3 patch-theme.py              # Apply patch
    python3 patch-theme.py --restore    # Restore from backup
    python3 patch-theme.py --dry-run    # Preview without modifying
    python3 patch-theme.py --check      # Check if binary is patched
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Patch definitions
# ---------------------------------------------------------------------------

ORIGINAL = (
    b'function Jfq(){if(Pu_===void 0)Pu_=$k6();return Pu_}'
    b'function Wfq(){return Pu_=$k6(),Pu_}'
    b'function Dm(_){if(_==="auto")return Jfq();return _}'
    b'function $k6(){return pPR()}'
    b'function pPR(){let _=Kk6.spawnSync("defaults",["read","-g","AppleInterfaceStyle"],'
    b'{encoding:"utf8",timeout:1000});if(_.status===0&&_.stdout.trim()==="Dark")'
    b'return"dark";return"light"}'
    b'var Kk6,Pu_;var HP_=X(()=>{Kk6=require("child_process")});'
    b'function BPR(){return DT().theme}'
    b'function gPR(_){UT((T)=>({...T,theme:_}))}'
    b'function MDT({children:_,initialState:T,onThemeSave:q=gPR}){'
    b'let[R,K]=fm.useState(T??BPR),[$,O]=fm.useState(null),'
    b'[A,H]=fm.useState(()=>(T??R)==="auto"?Jfq():"dark"),z=$??R;'
    b'WDT.useEffect(()=>{},[z]);'
    b'let j=z==="auto"?A:z,'
    b'D=Ak6.useMemo(()=>({themeSetting:R,'
    b'setThemeSetting:(f)=>{if(K(f),O(null),f==="auto")H(Wfq());q?.(f)},'
    b'setPreviewTheme:(f)=>{if(O(f),f==="auto")H(Wfq())},'
    b'savePreview:()=>{if($!==null)K($),O(null),q?.($)},'
    b'cancelPreview:()=>{if($!==null)O(null)},'
    b'currentTheme:j}),[R,$,j,q]);'
    b'return WDT.default.createElement(XDT.Provider,{value:D},_)}'
)

PATCHED_CORE = (
    b'function Jfq(){return Pu_??=pPR()}'
    b'function Wfq(){return Pu_=pPR()}'
    b'function Dm(_){if(_=="auto")return Jfq();return _}'
    b'var $k6=pPR;'
    b'function pPR(){try{return(""+Kk6.execSync('
    b'process.env.HOME+"/.claude/detect-theme"'
    b',{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}'
    b'var Kk6,Pu_;var HP_=X(()=>{Kk6=require("child_process")});'
    b'function BPR(){return DT().theme}'
    b'function gPR(_){UT((T)=>({...T,theme:_}))}'
    b'function MDT({children:_,initialState:T,onThemeSave:q=gPR}){'
    b'let[R,K]=fm.useState(T??BPR),[$,O]=fm.useState(null),'
    b'[A,H]=fm.useState(()=>(T??R)=="auto"?Jfq():"dark"),z=$??R;'
    b'WDT.useEffect(()=>{let t=z=="auto"&&setInterval(()=>H(pPR()),5e3);'
    b'return()=>clearInterval(t)},[z]);'
    b'let j=z=="auto"?A:z,'
    b'D=Ak6.useMemo(()=>({themeSetting:R,'
    b'setThemeSetting:(f)=>{if(K(f),O(null),f=="auto")H(Wfq());q?.(f)},'
    b'setPreviewTheme:(f)=>{if(O(f),f=="auto")H(Wfq())},'
    b'savePreview:()=>{if($!=null)K($),O(null),q?.($)},'
    b'cancelPreview:()=>{if($!=null)O(null)},'
    b'currentTheme:j}),[R,$,j,q]);'
    b'return WDT.default.createElement(XDT.Provider,{value:D},_)}'
)


def build_patched(original: bytes) -> bytes:
    """Build the patched version, padded to exactly match original length."""
    diff = len(original) - len(PATCHED_CORE)
    if diff < 0:
        print(f"ERROR: patched code is {abs(diff)} bytes longer than original.")
        print("This version of Claude Code may need an updated patch.")
        sys.exit(1)
    if diff == 0:
        return PATCHED_CORE
    # Pad with spaces before the final 'return WDT'
    return PATCHED_CORE.replace(
        b"]);return WDT", b"]);" + b" " * diff + b"return WDT"
    )


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def find_claude_binary() -> str | None:
    """Locate the Claude Code binary using multiple strategies."""

    # 1. mise
    mise_path = os.path.expanduser("~/.local/share/mise/installs/claude")
    if os.path.isdir(mise_path):
        versions = sorted(os.listdir(mise_path), reverse=True)
        for v in versions:
            candidate = os.path.join(mise_path, v, "claude")
            if os.path.isfile(candidate):
                return candidate

    # 2. which
    try:
        result = subprocess.run(
            ["which", "claude"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            path = os.path.realpath(result.stdout.strip())
            if os.path.isfile(path):
                return path
    except Exception:
        pass

    # 3. Common locations
    for c in [
        os.path.expanduser("~/.claude/local/claude"),
        "/usr/local/bin/claude",
    ]:
        if os.path.isfile(c):
            return os.path.realpath(c)

    return None


def detect_binary_type(path: str) -> str:
    """Check whether the binary is Mach-O or ELF (Bun-compiled)."""
    try:
        result = subprocess.run(
            ["file", path], capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        if "Mach-O" in output:
            return "macho"
        if "ELF" in output:
            return "elf"
        if "text" in output.lower() or "script" in output.lower():
            return "script"
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Detect-theme script
# ---------------------------------------------------------------------------

DETECT_THEME_PATH = os.path.expanduser("~/.claude/detect-theme")


def install_detect_theme(dry_run: bool = False) -> bool:
    """Install the detect-theme script to ~/.claude/detect-theme."""
    source = os.path.join(SCRIPT_DIR, "detect-theme")
    if not os.path.exists(source):
        print(f"ERROR: detect-theme script not found at {source}")
        return False

    if dry_run:
        print(f"DRY RUN: Would install {source} → {DETECT_THEME_PATH}")
        return True

    os.makedirs(os.path.dirname(DETECT_THEME_PATH), exist_ok=True)
    shutil.copy2(source, DETECT_THEME_PATH)
    os.chmod(DETECT_THEME_PATH, 0o755)
    print(f"Installed detect-theme → {DETECT_THEME_PATH}")
    return True


# ---------------------------------------------------------------------------
# Patch operations
# ---------------------------------------------------------------------------

def check_status(data: bytes) -> str:
    """Return 'original', 'patched', or 'unknown'."""
    if ORIGINAL in data:
        return "original"
    patched = build_patched(ORIGINAL)
    if patched in data:
        return "patched"
    return "unknown"


def apply_patch(binary_path: str, dry_run: bool = False) -> bool:
    with open(binary_path, "rb") as f:
        data = f.read()

    status = check_status(data)
    if status == "patched":
        # Still install detect-theme in case it was deleted
        install_detect_theme(dry_run)
        print("Binary already patched. Nothing to do.")
        return True
    if status == "unknown":
        print("ERROR: Could not find the expected code pattern in this binary.")
        print("This version of Claude Code may not be compatible with this patch.")
        print("Run with --check for details.")
        return False

    count = data.count(ORIGINAL)
    patched_bytes = build_patched(ORIGINAL)
    assert len(patched_bytes) == len(ORIGINAL)

    if dry_run:
        print(f"DRY RUN: Would patch {count} occurrence(s) in {binary_path}")
        print(f"  Pattern length: {len(ORIGINAL)} bytes (same-length replacement)")
        print(f"  Detection: ~/.claude/detect-theme (OSC 11 terminal query)")
        install_detect_theme(dry_run=True)
        return True

    # Install detect-theme script first
    if not install_detect_theme():
        return False

    # Backup binary
    backup_path = binary_path + ".backup"
    if not os.path.exists(backup_path):
        shutil.copy2(binary_path, backup_path)
        print(f"Backup created: {backup_path}")
    else:
        print(f"Backup already exists: {backup_path}")

    # Patch
    new_data = data.replace(ORIGINAL, patched_bytes)
    assert len(new_data) == len(data), "Binary size changed!"

    with open(binary_path, "wb") as f:
        f.write(new_data)

    print(f"Patched {count} occurrence(s)")

    # Re-sign on macOS
    if platform.system() == "Darwin":
        subprocess.run(
            ["codesign", "--remove-signature", binary_path],
            capture_output=True,
        )
        result = subprocess.run(
            ["codesign", "-s", "-", binary_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Binary re-signed (ad-hoc)")
        else:
            print(f"WARNING: codesign failed: {result.stderr}")

    # Set theme to auto
    set_theme_auto()

    print("\nDone! Restart Claude Code to activate.")
    print("Theme follows the terminal (polls every 5s via OSC 11).")
    return True


def restore(binary_path: str) -> bool:
    backup_path = binary_path + ".backup"
    if not os.path.exists(backup_path):
        print(f"No backup found at {backup_path}")
        return False

    shutil.copy2(backup_path, binary_path)
    print(f"Restored from {backup_path}")

    if platform.system() == "Darwin":
        subprocess.run(
            ["codesign", "--remove-signature", binary_path],
            capture_output=True,
        )
        subprocess.run(
            ["codesign", "-s", "-", binary_path],
            capture_output=True,
        )
        print("Binary re-signed (ad-hoc)")

    print("Restored to original. Restart Claude Code.")
    return True


def set_theme_auto():
    """Set theme to 'auto' in ~/.claude.json if it isn't already."""
    import json

    config_path = os.path.expanduser("~/.claude.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        if config.get("theme") == "auto":
            return
        config["theme"] = "auto"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        print('Set theme to "auto" in ~/.claude.json')
    except Exception as e:
        print(f"Note: could not update ~/.claude.json: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Patch Claude Code for reactive terminal theme switching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 patch-theme.py              Apply the patch
  python3 patch-theme.py --dry-run    Preview without modifying
  python3 patch-theme.py --restore    Restore from backup
  python3 patch-theme.py --check      Check current patch status
  python3 patch-theme.py --path /path/to/claude  Use specific binary
""",
    )
    parser.add_argument(
        "--restore", action="store_true", help="Restore binary from backup"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check if binary is patched"
    )
    parser.add_argument(
        "--path", type=str, help="Path to Claude Code binary (auto-detected if omitted)"
    )
    args = parser.parse_args()

    binary_path = args.path or find_claude_binary()
    if not binary_path:
        print("ERROR: Could not find Claude Code binary.")
        print("Use --path to specify the location manually.")
        sys.exit(1)

    print(f"Binary: {binary_path}")

    btype = detect_binary_type(binary_path)
    if btype not in ("macho", "elf"):
        print(f"WARNING: Expected Mach-O or ELF binary, got: {btype}")
        print("This patcher targets Bun-compiled Claude Code binaries.")
        if not args.check:
            sys.exit(1)

    with open(binary_path, "rb") as f:
        data = f.read()
    status = check_status(data)
    print(f"Status: {status}")

    if args.check:
        if status == "original":
            print("Binary has the original (unpatched) theme code.")
        elif status == "patched":
            print("Binary is already patched with reactive theme switching.")
        else:
            print("Binary does not match known patterns. Possibly a different version.")
        dt = "installed" if os.path.exists(DETECT_THEME_PATH) else "NOT installed"
        print(f"detect-theme: {dt}")
        sys.exit(0)

    if args.restore:
        success = restore(binary_path)
        sys.exit(0 if success else 1)

    success = apply_patch(binary_path, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
