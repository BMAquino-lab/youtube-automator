#!/usr/bin/env python3
"""Append measured iteration metrics to iterations_log.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
import os
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "iterations_log.json"


def append_iteration(entry: dict) -> None:
    data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    iterations = [row for row in data.get("iterations", []) if row.get("episode_id") != entry.get("episode_id")]
    entry = dict(entry)
    entry.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    iterations.append(entry)
    iterations.sort(key=lambda r: int(r.get("iteration", 0)))
    data["iterations"] = iterations

    applied_titles = set(entry.get("upgrades_applied", []))
    for upg in data.get("next_iteration_upgrades", []):
        if upg.get("id") in applied_titles or upg.get("title") in applied_titles:
            upg["status"] = f"done (iter {entry.get('iteration')})"

    LOG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[log_iteration] Recorded iteration {entry.get('iteration')} ({entry.get('episode_id')})", flush=True)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: log_iteration.py <json_file_or_string>", file=sys.stderr)
        return 1
    arg = sys.argv[1]
    payload = json.loads(Path(arg).read_text(encoding="utf-8") if Path(arg).exists() else arg)
    append_iteration(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
