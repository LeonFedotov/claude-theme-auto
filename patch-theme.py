#!/usr/bin/env python3
"""
Claude Theme Auto — reactive dark/light theme switching for Claude Code

Patches the Claude Code binary so the "auto" theme reactively follows the
terminal's dark/light mode while a session is running. Without this patch,
the built-in "auto" theme only detects the OS theme once at startup.

The patch rewrites the theme provider's useEffect hook so that when the
theme setting is "auto", it requires ~/.claude/tw.js which owns all
reactive theme-switching logic (no byte budget constraints).

On macOS this uses `defaults read -g AppleInterfaceStyle` (instant).
On Linux/SSH/tmux it uses OSC 11 to query the terminal's background color.

Byte-budget technique: the replacement must be exactly the same length as
the original to avoid shifting offsets in the binary. We achieve this by
compressing nearby code (=== to ==, ??= operator, etc.) and padding with
whitespace.

Based on https://github.com/antonioacg/claude-code-theme-patch

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
# Patch definitions — each entry is (original, patched_core, pad_marker)
# The pad_marker is the string before which spaces are inserted to match length.
# ---------------------------------------------------------------------------

VERSIONS = [
    {
        "label": "2.1.76",
        "original": (
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
        ),
        "patched": (
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
            b'WDT.useEffect(()=>{try{if(z=="auto")return require(process.env.HOME+"/.claude/tw")(H)}catch{}},[z]);'
            b'let j=z=="auto"?A:z,'
            b'D=Ak6.useMemo(()=>({themeSetting:R,'
            b'setThemeSetting:(f)=>{if(K(f),O(null),f=="auto")H(Wfq());q?.(f)},'
            b'setPreviewTheme:(f)=>{if(O(f),f=="auto")H(Wfq())},'
            b'savePreview:()=>{if($!=null)K($),O(null),q?.($)},'
            b'cancelPreview:()=>{if($!=null)O(null)},'
            b'currentTheme:j}),[R,$,j,q]);'
            b'return WDT.default.createElement(XDT.Provider,{value:D},_)}'
        ),
        "pad_before": b"]);return WDT",
    },
    {
        "label": "2.1.86",
        "original": (
            b'function Cd8(){if(qR6===void 0)qR6=_k5()??"dark";return qR6}'
            b'function Wg(q){if(q==="auto")return Cd8();return q}'
            b'function _k5(){let q=process.env.COLORFGBG;if(!q)return;'
            b'let _=q.split(";"),K=_[_.length-1];'
            b'if(K===void 0||K==="")return;'
            b'let O=Number(K);if(!Number.isInteger(O)||O<0||O>15)return;'
            b'return O<=6||O===8?"dark":"light"}'
            b'var qR6;'
            b'function Kk5(){return $q().theme}'
            b'function Ok5(q){Iq((_)=>({..._,theme:q}))}'
            b'function EGq({children:q,initialState:_,onThemeSave:K=Ok5}){'
            b'let[O,z]=zA.useState(_??Kk5),[Y,H]=zA.useState(null),'
            b'[$,w]=zA.useState(()=>(_??O)==="auto"?Cd8():"dark"),'
            b'j=Y??O,{internal_querier:J}=yq8();'
            b'zA.useEffect(()=>{},[j,J]);'
            b'let T=j==="auto"?$:j,'
            b'X=zA.useMemo(()=>({themeSetting:O,'
            b'setThemeSetting:(D)=>{if(z(D),H(null),D==="auto")w(Cd8());K?.(D)},'
            b'setPreviewTheme:(D)=>{if(H(D),D==="auto")w(Cd8())},'
            b'savePreview:()=>{if(Y!==null)z(Y),H(null),K?.(Y)},'
            b'cancelPreview:()=>{if(Y!==null)H(null)},'
            b'currentTheme:T}),[O,Y,T,K]);'
            b'return zA.default.createElement(SGq.Provider,{value:X},q)}'
        ),
        "patched": (
            b'function Cd8(){return qR6??=_k5()??"dark"}'
            b'function Wg(q){if(q=="auto")return Cd8();return q}'
            b'function _k5(){try{return(""+require("child_process").execSync('
            b'process.env.HOME+"/.claude/detect-theme"'
            b',{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}'
            b'var qR6;'
            b'function Kk5(){return $q().theme}'
            b'function Ok5(q){Iq((_)=>({..._,theme:q}))}'
            b'function EGq({children:q,initialState:_,onThemeSave:K=Ok5}){'
            b'let[O,z]=zA.useState(_??Kk5),[Y,H]=zA.useState(null),'
            b'[$,w]=zA.useState(()=>(_??O)=="auto"?Cd8():"dark"),'
            b'j=Y??O,{internal_querier:J}=yq8();'
            b'zA.useEffect(()=>{try{if(j=="auto")return require(process.env.HOME+"/.claude/tw")(w,J)}catch{}},[j,J]);'
            b'let T=j=="auto"?$:j,'
            b'X=zA.useMemo(()=>({themeSetting:O,'
            b'setThemeSetting:(D)=>{if(z(D),H(null),D=="auto")w(Cd8());K?.(D)},'
            b'setPreviewTheme:(D)=>{if(H(D),D=="auto")w(Cd8())},'
            b'savePreview:()=>{if(Y!=null)z(Y),H(null),K?.(Y)},'
            b'cancelPreview:()=>{if(Y!=null)H(null)},'
            b'currentTheme:T}),[O,Y,T,K]);'
            b'return zA.default.createElement(SGq.Provider,{value:X},q)}'
        ),
        "pad_before": b"]);return zA",
    },
    {
        "label": "2.1.87",
        "original": (
            b'function IFH(){if($k6===void 0)$k6=MR4()??"dark";return $k6}'
            b'function Rg(H){if(H==="auto")return IFH();return H}'
            b'function MR4(){let H=process.env.COLORFGBG;if(!H)return;'
            b'let _=H.split(";"),q=_[_.length-1];'
            b'if(q===void 0||q==="")return;'
            b'let $=Number(q);if(!Number.isInteger($)||$<0||$>15)return;'
            b'return $<=6||$===8?"dark":"light"}'
            b'var $k6;'
            b'function JR4(){return z_().theme}'
            b'function PR4(H){u_((_)=>({..._,theme:H}))}'
            b'function E0_({children:H,initialState:_,onThemeSave:q=PR4}){'
            b'let[$,K]=KG.useState(_??JR4),[O,T]=KG.useState(null),'
            b'[z,A]=KG.useState(()=>(_??$)==="auto"?IFH():"dark"),'
            b'f=O??$,{internal_querier:w}=E_H();'
            b'KG.useEffect(()=>{},[f,w]);'
            b'let Y=f==="auto"?z:f,'
            b'D=KG.useMemo(()=>({themeSetting:$,'
            b'setThemeSetting:(j)=>{if(K(j),T(null),j==="auto")A(IFH());q?.(j)},'
            b'setPreviewTheme:(j)=>{if(T(j),j==="auto")A(IFH())},'
            b'savePreview:()=>{if(O!==null)K(O),T(null),q?.(O)},'
            b'cancelPreview:()=>{if(O!==null)T(null)},'
            b'currentTheme:Y}),[$,O,Y,q]);'
            b'return KG.default.createElement(S0_.Provider,{value:D},H)}'
        ),
        "patched": (
            b'function IFH(){return $k6??=MR4()??"dark"}'
            b'function Rg(H){if(H=="auto")return IFH();return H}'
            b'function MR4(){try{return(""+require("child_process").execSync('
            b'process.env.HOME+"/.claude/detect-theme"'
            b',{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}'
            b'var $k6;'
            b'function JR4(){return z_().theme}'
            b'function PR4(H){u_((_)=>({..._,theme:H}))}'
            b'function E0_({children:H,initialState:_,onThemeSave:q=PR4}){'
            b'let[$,K]=KG.useState(_??JR4),[O,T]=KG.useState(null),'
            b'[z,A]=KG.useState(()=>(_??$)=="auto"?IFH():"dark"),'
            b'f=O??$,{internal_querier:w}=E_H();'
            b'KG.useEffect(()=>{try{if(f=="auto")return require(process.env.HOME+"/.claude/tw")(A,w)}catch{}},[f,w]);'
            b'let Y=f=="auto"?z:f,'
            b'D=KG.useMemo(()=>({themeSetting:$,'
            b'setThemeSetting:(j)=>{if(K(j),T(null),j=="auto")A(IFH());q?.(j)},'
            b'setPreviewTheme:(j)=>{if(T(j),j=="auto")A(IFH())},'
            b'savePreview:()=>{if(O!=null)K(O),T(null),q?.(O)},'
            b'cancelPreview:()=>{if(O!=null)T(null)},'
            b'currentTheme:Y}),[$,O,Y,q]);'
            b'return KG.default.createElement(S0_.Provider,{value:D},H)}'
        ),
        "pad_before": b"]);return KG",
    },
    {
        "label": "2.1.87-linux",
        "original": (
            b'function Cd8(){if(qR6===void 0)qR6=_k5()??"dark";return qR6}'
            b'function Wg(q){if(q==="auto")return Cd8();return q}'
            b'function _k5(){let q=process.env.COLORFGBG;if(!q)return;'
            b'let _=q.split(";"),K=_[_.length-1];'
            b'if(K===void 0||K==="")return;'
            b'let O=Number(K);if(!Number.isInteger(O)||O<0||O>15)return;'
            b'return O<=6||O===8?"dark":"light"}'
            b'var qR6;'
            b'function Kk5(){return $q().theme}'
            b'function Ok5(q){Iq((_)=>({..._,theme:q}))}'
            b'function EGq({children:q,initialState:_,onThemeSave:K=Ok5}){'
            b'let[O,z]=OA.useState(_??Kk5),[Y,H]=OA.useState(null),'
            b'[$,w]=OA.useState(()=>(_??O)==="auto"?Cd8():"dark"),'
            b'j=Y??O,{internal_querier:J}=Vq8();'
            b'OA.useEffect(()=>{},[j,J]);'
            b'let T=j==="auto"?$:j,'
            b'X=OA.useMemo(()=>({themeSetting:O,'
            b'setThemeSetting:(D)=>{if(z(D),H(null),D==="auto")w(Cd8());K?.(D)},'
            b'setPreviewTheme:(D)=>{if(H(D),D==="auto")w(Cd8())},'
            b'savePreview:()=>{if(Y!==null)z(Y),H(null),K?.(Y)},'
            b'cancelPreview:()=>{if(Y!==null)H(null)},'
            b'currentTheme:T}),[O,Y,T,K]);'
            b'return OA.default.createElement(SGq.Provider,{value:X},q)}'
        ),
        "patched": (
            b'function Cd8(){return qR6??=_k5()??"dark"}'
            b'function Wg(q){if(q=="auto")return Cd8();return q}'
            b'function _k5(){try{return(""+require("child_process").execSync('
            b'process.env.HOME+"/.claude/detect-theme"'
            b',{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}'
            b'var qR6;'
            b'function Kk5(){return $q().theme}'
            b'function Ok5(q){Iq((_)=>({..._,theme:q}))}'
            b'function EGq({children:q,initialState:_,onThemeSave:K=Ok5}){'
            b'let[O,z]=OA.useState(_??Kk5),[Y,H]=OA.useState(null),'
            b'[$,w]=OA.useState(()=>(_??O)=="auto"?Cd8():"dark"),'
            b'j=Y??O,{internal_querier:J}=Vq8();'
            b'OA.useEffect(()=>{try{if(j=="auto")return require(process.env.HOME+"/.claude/tw")(w,J)}catch{}},[j,J]);'
            b'let T=j=="auto"?$:j,'
            b'X=OA.useMemo(()=>({themeSetting:O,'
            b'setThemeSetting:(D)=>{if(z(D),H(null),D=="auto")w(Cd8());K?.(D)},'
            b'setPreviewTheme:(D)=>{if(H(D),D=="auto")w(Cd8())},'
            b'savePreview:()=>{if(Y!=null)z(Y),H(null),K?.(Y)},'
            b'cancelPreview:()=>{if(Y!=null)H(null)},'
            b'currentTheme:T}),[O,Y,T,K]);'
            b'return OA.default.createElement(SGq.Provider,{value:X},q)}'
        ),
        "pad_before": b"]);return OA",
    },
    {
        "label": "2.1.89",
        "original": (
            b'function rUH(){if(Xv6===void 0)Xv6=uG4()??"dark";return Xv6}'
            b'function Ad(H){if(H==="auto")return rUH();return H}'
            b'function uG4(){let H=process.env.COLORFGBG;if(!H)return;'
            b'let _=H.split(";"),q=_[_.length-1];'
            b'if(q===void 0||q==="")return;'
            b'let K=Number(q);if(!Number.isInteger(K)||K<0||K>15)return;'
            b'return K<=6||K===8?"dark":"light"}'
            b'var Xv6;'
            b'function pG4(){return z_().theme}'
            b'function gG4(H){S_((_)=>({..._,theme:H}))}'
            b'function pG_({children:H,initialState:_,onThemeSave:q=gG4}){'
            b'let[K,$]=UG.useState(_??pG4),[O,T]=UG.useState(null),'
            b'[z,A]=UG.useState(()=>(_??K)==="auto"?rUH():"dark"),'
            b'w=O??K,{internal_querier:f}=W6H();'
            b'UG.useEffect(()=>{},[w,f]);'
            b'let Y=w==="auto"?z:w,'
            b'j=UG.useMemo(()=>({themeSetting:K,'
            b'setThemeSetting:(D)=>{if($(D),T(null),D==="auto")A(rUH());q?.(D)},'
            b'setPreviewTheme:(D)=>{if(T(D),D==="auto")A(rUH())},'
            b'savePreview:()=>{if(O!==null)$(O),T(null),q?.(O)},'
            b'cancelPreview:()=>{if(O!==null)T(null)},'
            b'currentTheme:Y}),[K,O,Y,q]);'
            b'return UG.default.createElement(mG_.Provider,{value:j},H)}'
        ),
        "patched": (
            b'function rUH(){return Xv6??=uG4()??"dark"}'
            b'function Ad(H){if(H=="auto")return rUH();return H}'
            b'function uG4(){try{return(""+require("child_process").execSync('
            b'process.env.HOME+"/.claude/detect-theme"'
            b',{stdio:"pipe",timeout:3e3})).trim()}catch{return"dark"}}'
            b'var Xv6;'
            b'function pG4(){return z_().theme}'
            b'function gG4(H){S_((_)=>({..._,theme:H}))}'
            b'function pG_({children:H,initialState:_,onThemeSave:q=gG4}){'
            b'let[K,$]=UG.useState(_??pG4),[O,T]=UG.useState(null),'
            b'[z,A]=UG.useState(()=>(_??K)=="auto"?rUH():"dark"),'
            b'w=O??K,{internal_querier:f}=W6H();'
            b'UG.useEffect(()=>{try{if(w=="auto")return require(process.env.HOME+"/.claude/tw")(A,f)}catch{}},[w,f]);'
            b'let Y=w=="auto"?z:w,'
            b'j=UG.useMemo(()=>({themeSetting:K,'
            b'setThemeSetting:(D)=>{if($(D),T(null),D=="auto")A(rUH());q?.(D)},'
            b'setPreviewTheme:(D)=>{if(T(D),D=="auto")A(rUH())},'
            b'savePreview:()=>{if(O!=null)$(O),T(null),q?.(O)},'
            b'cancelPreview:()=>{if(O!=null)T(null)},'
            b'currentTheme:Y}),[K,O,Y,q]);'
            b'return UG.default.createElement(mG_.Provider,{value:j},H)}'
        ),
        "pad_before": b"]);return UG",
    },
]


def find_matching_version(data: bytes) -> dict | None:
    """Find which version's original pattern matches the binary."""
    for v in VERSIONS:
        if v["original"] in data:
            return v
    return None


def find_patched_version(data: bytes) -> dict | None:
    """Find which version's patched pattern matches the binary."""
    for v in VERSIONS:
        padded = build_patched(v)
        if padded in data:
            return v
    return None


def build_patched(version: dict) -> bytes:
    """Build the patched version, padded to exactly match original length."""
    original = version["original"]
    patched = version["patched"]
    pad_before = version["pad_before"]
    diff = len(original) - len(patched)
    if diff < 0:
        raise ValueError(
            f"Patched code for {version['label']} is {abs(diff)} bytes longer than original"
        )
    if diff == 0:
        return patched
    return patched.replace(pad_before, b"]);" + b" " * diff + pad_before[3:])


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def find_claude_binary() -> str | None:
    """Locate the Claude Code binary using multiple strategies."""

    # 1. ~/.local/share/claude/versions (official install)
    versions_path = os.path.expanduser("~/.local/share/claude/versions")
    if os.path.isdir(versions_path):
        # Check for versioned files (e.g., 2.1.89)
        versions = sorted(
            [v for v in os.listdir(versions_path) if os.path.isfile(os.path.join(versions_path, v)) and not v.endswith('.backup')],
            reverse=True,
        )
        for v in versions:
            candidate = os.path.join(versions_path, v)
            if os.path.isfile(candidate):
                return candidate

    # 2. mise
    mise_path = os.path.expanduser("~/.local/share/mise/installs/claude")
    if os.path.isdir(mise_path):
        versions = sorted(os.listdir(mise_path), reverse=True)
        for v in versions:
            candidate = os.path.join(mise_path, v, "claude")
            if os.path.isfile(candidate):
                return candidate

    # 3. which
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

    # 4. Common locations
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
        print(f"DRY RUN: Would install {source} -> {DETECT_THEME_PATH}")
        return True

    os.makedirs(os.path.dirname(DETECT_THEME_PATH), exist_ok=True)
    shutil.copy2(source, DETECT_THEME_PATH)
    os.chmod(DETECT_THEME_PATH, 0o755)
    print(f"Installed detect-theme -> {DETECT_THEME_PATH}")
    return True


# ---------------------------------------------------------------------------
# Patch operations
# ---------------------------------------------------------------------------

def check_status(data: bytes) -> tuple[str, dict | None]:
    """Return ('original'|'patched'|'unknown', matched_version)."""
    v = find_matching_version(data)
    if v:
        return "original", v
    v = find_patched_version(data)
    if v:
        return "patched", v
    return "unknown", None


def apply_patch(binary_path: str, dry_run: bool = False) -> bool:
    with open(binary_path, "rb") as f:
        data = f.read()

    status, version = check_status(data)
    if status == "patched":
        install_detect_theme(dry_run)
        print(f"Binary already patched (v{version['label']}). Nothing to do.")
        return True
    if status == "unknown":
        print("ERROR: Could not find the expected code pattern in this binary.")
        print("This version of Claude Code may not be compatible with this patch.")
        print("Run with --check for details.")
        return False

    print(f"Matched pattern: v{version['label']}")
    count = data.count(version["original"])
    patched_bytes = build_patched(version)
    assert len(patched_bytes) == len(version["original"])

    if dry_run:
        print(f"DRY RUN: Would patch {count} occurrence(s) in {binary_path}")
        print(f"  Pattern length: {len(version['original'])} bytes (same-length replacement)")
        print(f"  Detection: ~/.claude/detect-theme")
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
    new_data = data.replace(version["original"], patched_bytes)
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
    print("Theme follows the terminal via ~/.claude/tw.js")
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
    status, version = check_status(data)
    vlabel = f" (v{version['label']})" if version else ""
    print(f"Status: {status}{vlabel}")

    if args.check:
        if status == "original":
            print("Binary has the original (unpatched) theme code.")
        elif status == "patched":
            print("Binary is already patched with reactive theme switching.")
        else:
            print("Binary does not match known patterns. Possibly a different version.")
            supported = ", ".join(v["label"] for v in VERSIONS)
            print(f"Supported versions: {supported}")
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
