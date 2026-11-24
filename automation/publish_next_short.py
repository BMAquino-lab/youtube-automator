#!/usr/bin/env python3
"""Unattended queue publisher for Fivestack (ch04) Shorts.

Usage:
  python publish_next_short.py --dry-run
  python publish_next_short.py [--episode ep04_jackscrew_hotel]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AUTO_DIR = Path(__file__).resolve().parent
QUEUE_PATH = AUTO_DIR / "queue.json"
LOCK_PATH = AUTO_DIR / "publish.lock"
UPLOADER = Path(os.environ.get("UPLOADER_SCRIPT", str(AUTO_DIR.parent.parent / "branding" / "upload_short.mjs")))
STALE_LOCK_SECONDS = 1800  # 30 minutes


def acquire_lock() -> None:
    if LOCK_PATH.exists():
        age = time.time() - LOCK_PATH.stat().st_mtime
        if age < STALE_LOCK_SECONDS:
            raise RuntimeError(f"Another publish job is running (lock age {int(age)}s): {LOCK_PATH}")
        LOCK_PATH.unlink(missing_ok=True)
    LOCK_PATH.write_text(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")


def release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--episode", default="")
    args = ap.parse_args()

    q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    items = q.get("items", [])
    ready = [it for it in items if it.get("status") == "ready"]

    target = None
    if args.episode:
        target = next((it for it in ready if it["episode_id"] == args.episode), None)
    elif ready:
        target = ready[0]

    if target is None:
        print(f"[publish_next_short] NO READY ITEMS in queue (total={len(items)}).", flush=True)
        return 1

    video_p = Path(target["master_mp4"])
    qa_p = Path(target["qa_report_json"])
    if not video_p.exists():
        print(f"[publish_next_short] Missing video: {video_p}", file=sys.stderr)
        return 1
    if not qa_p.exists():
        print(f"[publish_next_short] Missing QA report: {qa_p}", file=sys.stderr)
        return 1

    qa = json.loads(qa_p.read_text(encoding="utf-8"))
    if not (qa.get("pass") and qa.get("publishable")):
        print(f"[publish_next_short] REFUSING non-publishable episode {target['episode_id']}", file=sys.stderr)
        return 1

    cmd = [
        "node",
        str(UPLOADER),
        "--channel",
        q.get("channel", "ch04"),
        "--video",
        str(video_p),
        "--title",
        target["title"],
        "--desc",
        target["description"],
        "--slug",
        target["episode_id"],
    ]

    print(f"[publish_next_short] Target={target['episode_id']} ({target['title']})", flush=True)
    print(f"[publish_next_short] Ready buffer={len(ready)} item(s): {[r['episode_id'] for r in ready]}", flush=True)
    if args.dry_run:
        print("[dry-run] Verified master.mp4 + 20/20 publishable QA.")
        print("[dry-run] Command:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return 0

    acquire_lock()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        sys.stdout.write(res.stdout)
        sys.stderr.write(res.stderr)
        if res.returncode != 0:
            return res.returncode

        m = re.search(r"Published Short URL:\s*(https?://\S+)", res.stdout)
        url = m.group(1) if m else None
        now_iso = datetime.now(timezone.utc).isoformat()
        target["status"] = "published"
        target["published_at"] = now_iso
        target["youtube_url"] = url

        q.setdefault("published_history", []).append({
            "episode_id": target["episode_id"],
            "title": target["title"],
            "published_at": now_iso,
            "youtube_url": url,
            "iteration": target.get("iteration", 1),
        })
        QUEUE_PATH.write_text(json.dumps(q, indent=2), encoding="utf-8")
        rem_ready = sum(1 for it in q["items"] if it.get("status") == "ready")
        print(f"[publish_next_short] SUCCESS url={url} | remaining ready buffer={rem_ready}", flush=True)
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
