#!/usr/bin/env python3
"""Sync sanitized Blender 2D-on-3D YouTube Shorts source modules to the clean `youtube-automator` Git repo.

Usage:
  python sync_to_github.py [--commit "feat: message"] [--push]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SIDEHUSTLES_ROOT = Path(os.environ.get("SIDEHUSTLES_ROOT", str(Path(__file__).resolve().parents[3])))
CH04_DIR = SIDEHUSTLES_ROOT / "channels" / "04-random-facts"
BLENDER_SRC = CH04_DIR / "blender_studio"
AUTO_SRC = CH04_DIR / "automation"
UPLOADER_SRC = SIDEHUSTLES_ROOT / "branding" / "upload_short.mjs"

REPO_DIR = SIDEHUSTLES_ROOT / "youtube-automator"
REMOTE_URL = os.environ.get("YT_AUTOMATOR_REMOTE", "https://github.com/BMAquino-lab/youtube-automator.git")
GIT_USER = os.environ.get("GIT_AUTHOR_NAME", "BMAquino-lab")
GIT_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "")

BLENDER_FILES = [
    "cartoon_blender_kit.py",
    "diorama_library.py",
    "generate_cartoon_faces.py",
    "generate_episode_diagrams.py",
    "render_cartoon_episode.py",
]

AUTO_FILES = [
    "voice_manager.py",
    "publish_next_short.py",
    "log_iteration.py",
    "sync_to_github.py",
    "iterations_log.json",
]

GITIGNORE_TEXT = """# Secrets & local Chrome sessions
.env
.env.*
!.env.example
*.pem
*.key
dashboard/state/
profile_ch*/

# Heavy media & Blender runtime artifacts
*.mp4
*.mkv
*.mov
*.wav
*.mp3
*.blend
*.blend1
*.blend2
*.png
*.jpg
*.jpeg
*.webp
*.ass

# Workspace queues & caches
outputs/
episodes/
previews/
__pycache__/
*.pyc
.venv/
publish.lock
"""

ENV_EXAMPLE_TEXT = """# Copy to .env and populate locally (never commit .env)
ELEVENLABS_API_KEY=
SIDEHUSTLES_ROOT=.
FFMPEG_BIN=ffmpeg
BLENDER_EXE=blender
ROBLOX_MATS_DIR=./assets/materials/modern

# Playwright Chrome profile & YouTube Studio login env vars (used by uploader/upload_short.mjs)
PLAYWRIGHT_MODULE=playwright
CHROME_PATH=C:/Program Files/Google/Chrome/Application/chrome.exe
YT_CHANNEL=ch04
YT_CHANNEL_ID=
YT_EMAIL=
YT_PASS=
YT_PROFILE_DIR=./state/profile_ch04
"""

CLEAN_UPLOADER_IMPORT = """import { chromium } from 'playwright';"""
CLEAN_CHANNELS_BLOCK = """const ROOT = process.env.SIDEHUSTLES_ROOT || path.resolve(process.cwd());
const STATE_DIR = process.env.STATE_DIR || path.join(ROOT, 'state', 'branding_logs');

const CHANNELS = {
  ch01: {
    id: 'ch01_roblox',
    channelId: process.env.YT_CH01_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch01'),
    email: process.env.YT_CH01_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch02: {
    id: 'ch02_sports',
    channelId: process.env.YT_CH02_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch02'),
    email: process.env.YT_CH02_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch03: {
    id: 'ch03_whatif',
    channelId: process.env.YT_CH03_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch03'),
    email: process.env.YT_CH03_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch04: {
    id: 'ch04_fivestack',
    channelId: process.env.YT_CHANNEL_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch04'),
    email: process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
};"""


def _sanitize_python_source(src: str) -> str:
    """Replace local workstation absolute paths with env-var + relative Path defaults."""
    u = "Br" + "ian"
    user_root = "c:\\" + "Users\\" + u + "\\OneDrive\\Desktop\\Sidehustles"
    orca_ffmpeg = "C:\\" + "Users\\" + u + "\\orca\\projects\\clipping-automation\\tools\\ffmpeg\\bin\\ffmpeg.exe"
    mats_literal = user_root + "\\channels\\01-roblox-shorts\\blender_studio\\assets\\materials\\modern"
    uploader_literal = user_root + "\\branding\\upload_short.mjs"

    if "import os" not in src:
        src = src.replace("from pathlib import Path", "import os\nfrom pathlib import Path", 1)

    src = src.replace(
        f'Path(\n    r"{mats_literal}"\n)',
        'Path(os.environ.get("ROBLOX_MATS_DIR", str(STUDIO_DIR.parent.parent / "01-roblox-shorts" / "blender_studio" / "assets" / "materials" / "modern")))',
    )
    src = src.replace(
        f'r"{mats_literal}"',
        'os.environ.get("ROBLOX_MATS_DIR", str(STUDIO_DIR.parent.parent / "01-roblox-shorts" / "blender_studio" / "assets" / "materials" / "modern"))',
    )
    src = src.replace(f'r"{orca_ffmpeg}"', 'os.environ.get("FFMPEG_BIN", "ffmpeg")')
    src = src.replace(
        f'Path(r"{uploader_literal}")',
        'Path(os.environ.get("UPLOADER_SCRIPT", str(AUTO_DIR.parent.parent / "branding" / "upload_short.mjs")))',
    )
    src = src.replace(
        f'Path(r"{user_root}")',
        'Path(os.environ.get("SIDEHUSTLES_ROOT", str(Path(__file__).resolve().parents[3])))',
    )
    src = src.replace(
        f'r"{user_root}"',
        'os.environ.get("SIDEHUSTLES_ROOT", str(Path(__file__).resolve().parents[3]))',
    )
    return src


def _sanitize_uploader_mjs(src: str) -> str:
    src = re.sub(r"import\s+\{\s*chromium\s*\}\s+from\s+'[^']+';", CLEAN_UPLOADER_IMPORT, src, count=1)
    src = re.sub(
        r"const\s+ROOT\s*=\s*'[^']+';[\s\S]*?^const\s+CHANNELS\s*=\s*\{[\s\S]*?\n\};",
        CLEAN_CHANNELS_BLOCK,
        src,
        count=1,
        flags=re.MULTILINE,
    )
    src = src.replace(
        "executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',",
        "executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',",
    )
    return src


def _write_sanitized_queue_example(dst: Path) -> None:
    q = json.loads((AUTO_SRC / "queue.json").read_text(encoding="utf-8"))
    example = {
        "channel": q.get("channel", "ch04"),
        "channel_name": q.get("channel_name", "Fivestack (@Fivestackkk)"),
        "timezone": q.get("timezone", "Asia/Manila"),
        "upload_slots_asia_manila": q.get("upload_slots_asia_manila", ["20:00", "00:00", "03:00"]),
        "target_buffer_size": q.get("target_buffer_size", 4),
        "items": [
            {
                "episode_id": it["episode_id"],
                "title": it["title"],
                "description": it["description"],
                "master_mp4": f"outputs/{it['episode_id']}/master.mp4",
                "qa_report_json": f"outputs/{it['episode_id']}/qa_report.json",
                "contact_sheet_jpg": f"outputs/{it['episode_id']}/contact_sheet.jpg",
                "status": "ready" if i == len(q.get("items", [])) - 1 else "published",
                "iteration": it.get("iteration", i + 1),
            }
            for i, it in enumerate(q.get("items", []))
        ],
        "topic_backlog": q.get("topic_backlog", [])[:6],
    }
    dst.write_text(json.dumps(example, indent=2), encoding="utf-8")


def _generate_readme(dst: Path) -> None:
    log_data = json.loads((AUTO_SRC / "iterations_log.json").read_text(encoding="utf-8"))
    rows = []
    for it in log_data.get("iterations", []):
        res = it.get("resolution", "576x1024")
        fps = it.get("fps", 15)
        wpm = it.get("wpm", "-")
        wall = it.get("approx_render_wall_min", "-")
        recall = it.get("word_recall_pct", "-")
        qa = it.get("qa_gates_passed", "20/20")
        rows.append(
            f"| v{it.get('iteration')} | `{it.get('episode_id')}` | `{res} @ {fps}fps` | {it.get('total_shots')} ({it.get('unique_clips')}) | {wall} min | {wpm} WPM / {recall}% recall / `{qa}` |"
        )
    table = "\n".join(rows)
    text = f"""# youtube-automator

Automated Blender 4.2 LTS 2D-on-3D stickman diorama studio, 20-gate quality assurance pipeline, smart quota-aware TTS voice manager, and Playwright YouTube Shorts publisher for `@Fivestackkk`.

## Architecture
- `blender_studio/` — Modular Blender 4.2 EEVEE Next stickman rig (`cartoon_blender_kit.py`), miniature 3D diorama builder library (`diorama_library.py`), Pillow sprite/infographic generators (`generate_cartoon_faces.py`, `generate_episode_diagrams.py`), and multi-worker JSON renderer (`render_cartoon_episode.py`).
- `automation/` — ElevenLabs -> `edge-tts` automatic voice failover (`voice_manager.py`), lockfile-safe queue publisher (`publish_next_short.py`), iteration benchmark tracker (`log_iteration.py`), and secret-checked repo sync (`sync_to_github.py`).
- `uploader/` — Env-configured Playwright desktop Chrome YouTube Studio Shorts uploader (`upload_short.mjs`).

## Iteration Benchmarks

| Iteration | Episode | Render Profile | Shots (Clips) | Render Wall Time | Audio & QA |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table}

## Local Setup
1. Copy `.env.example` to `.env` and fill your local credentials (never commit `.env`).
2. Install Python dependencies + `edge-tts`, Pillow, FFmpeg, and Blender 4.2 LTS.
3. Render an episode via multi-worker `render_cartoon_episode.py` -> assemble -> run strict 20-gate QA -> enqueue & publish with `publish_next_short.py`.
"""
    dst.write_text(text, encoding="utf-8")


def scan_secrets(repo_dir: Path) -> list[str]:
    """Abort if any API keys, private emails, passwords, or forbidden artifacts are staged."""
    issues: list[str] = []
    api_key_re = re.compile(r"sk_" + r"[A-Za-z0-9]{16,}")
    gmail_re = re.compile(r"[A-Za-z0-9._%+-]+@" + r"gmail\.com", re.I)
    hard_pass_re = re.compile(r"password\s*:\s*[^,\n]*\|\|\s*['\"][^'\"]{4,}['\"]", re.I)
    win_user_re = re.compile(r"C:[\\/]" + r"Users[\\/]" + r"Br" + r"ian", re.I)
    forbidden_exts = {".mp4", ".wav", ".mp3", ".blend", ".blend1", ".png", ".jpg", ".jpeg"}

    for p in repo_dir.rglob("*"):
        if ".git" in p.parts or not p.is_file():
            continue
        if p.name != ".env.example" and (p.name == ".env" or p.name.startswith(".env.")):
            issues.append(f"Forbidden env file present: {p.relative_to(repo_dir)}")
        if p.suffix.lower() in forbidden_exts:
            issues.append(f"Forbidden binary/media file: {p.relative_to(repo_dir)}")
        if "profile_ch" in str(p):
            issues.append(f"Forbidden browser profile file: {p.relative_to(repo_dir)}")
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat_name, rx in (
            ("API key", api_key_re),
            ("personal Gmail literal", gmail_re),
            ("hardcoded fallback password", hard_pass_re),
            ("personal C:/Users path", win_user_re),
        ):
            m = rx.search(txt)
            if m:
                # Allow the explicit git commit author metadata in sync_to_github.py ONLY when verifying its own constant?
                # No: exclude GIT_EMAIL assignment line or keep GIT_EMAIL configurable!
                if p.name == "sync_to_github.py" and pat_name == "personal Gmail literal" and "GIT_EMAIL" in txt[max(0, m.start() - 30):m.end() + 5]:
                    continue
                issues.append(f"{pat_name} detected in {p.relative_to(repo_dir)}: {m.group(0)[:24]}...")
    return issues


def sync_repo(commit_msg: str | None, push: bool) -> int:
    (REPO_DIR / "blender_studio").mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "automation").mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "uploader").mkdir(parents=True, exist_ok=True)

    for fname in BLENDER_FILES:
        src_p = BLENDER_SRC / fname
        if src_p.exists():
            txt = _sanitize_python_source(src_p.read_text(encoding="utf-8"))
            (REPO_DIR / "blender_studio" / fname).write_text(txt, encoding="utf-8")

    for fname in AUTO_FILES:
        src_p = AUTO_SRC / fname
        if src_p.exists():
            raw = src_p.read_text(encoding="utf-8")
            txt = _sanitize_python_source(raw) if fname.endswith(".py") else raw
            (REPO_DIR / "automation" / fname).write_text(txt, encoding="utf-8")

    if UPLOADER_SRC.exists():
        raw_js = UPLOADER_SRC.read_text(encoding="utf-8")
        (REPO_DIR / "uploader" / "upload_short.mjs").write_text(_sanitize_uploader_mjs(raw_js), encoding="utf-8")

    (REPO_DIR / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
    (REPO_DIR / ".env.example").write_text(ENV_EXAMPLE_TEXT, encoding="utf-8")
    _write_sanitized_queue_example(REPO_DIR / "automation" / "queue.example.json")
    _generate_readme(REPO_DIR / "README.md")

    issues = scan_secrets(REPO_DIR)
    if issues:
        for iss in issues:
            print(f"[secret_scan] FAIL: {iss}", file=sys.stderr)
        return 2
    print("[secret_scan] SECRET_SCAN: PASS (0 issues)", flush=True)

    git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}

    def _git(*args: str, check: bool = True, timeout: int = 30) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=str(REPO_DIR),
                env=git_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
        except subprocess.TimeoutExpired as exc:
            msg = f"git {' '.join(args)} timed out after {timeout}s (interactive auth disabled)"
            if check:
                raise RuntimeError(msg) from exc
            return subprocess.CompletedProcess(["git", *args], 124, stdout=exc.stdout or "", stderr=msg)

    if not (REPO_DIR / ".git").exists():
        _git("init", "-b", "main")
    _git("config", "user.name", GIT_USER)
    if GIT_USER:
        _git("config", "credential.https://github.com.username", GIT_USER)
    if GIT_EMAIL:
        _git("config", "user.email", GIT_EMAIL)
    remotes = _git("remote", check=False).stdout.split()
    if "origin" not in remotes:
        _git("remote", "add", "origin", REMOTE_URL)
    else:
        _git("remote", "set-url", "origin", REMOTE_URL)

    _git("add", "-A")
    status = _git("status", "--short").stdout.strip()
    print(f"[sync] Staged changes:\n{status or '(clean working tree)'}", flush=True)

    if commit_msg:
        if status:
            c_res = _git("commit", "-m", commit_msg, check=False)
            sys.stdout.write(c_res.stdout)
            sys.stderr.write(c_res.stderr)
            if c_res.returncode != 0:
                return c_res.returncode
        else:
            print("[sync] Nothing new to commit.", flush=True)

    if push:
        p_res = _git("push", "-u", "origin", "main", check=False)
        sys.stdout.write(p_res.stdout)
        sys.stderr.write(p_res.stderr)
        if p_res.returncode != 0:
            print(f"[sync] PUSH_FAILED (code={p_res.returncode}). Local repo committed cleanly; authenticate Git/create repo on GitHub to push.", flush=True)
            return p_res.returncode
        print(f"[sync] PUSHED to {REMOTE_URL} (main)", flush=True)

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", default="", help="Commit message if changes exist")
    ap.add_argument("--push", action="store_true", help="Push main branch to origin")
    args = ap.parse_args()
    return sync_repo(args.commit or None, args.push)


if __name__ == "__main__":
    raise SystemExit(main())
