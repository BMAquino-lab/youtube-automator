#!/usr/bin/env python3
"""Smart voiceover manager for Fivestack (ch04) Shorts.

Usage:
  python voice_manager.py <ep_dir>

Checks ElevenLabs remaining character quota first:
  - Uses ElevenLabs (`eleven_turbo_v2_5`, Liam `TX3LPaxmHKxFdv7VOQHJ`) -> narration/ai_voice_xi_cartoon.wav
    when remaining characters >= len(text) + 100.
  - Automatically falls back to `edge-tts` (`en-US-AndrewMultilingualNeural`, rate="+6%") ->
    narration/narrator_neural_fallback.wav if quota is exhausted or ElevenLabs errors out, so
    unmodified render.py accepts it as a non-TEMP neural voice and passes 20/20 QA without stopping.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("SIDEHUSTLES_ROOT", str(Path(__file__).resolve().parents[3])))
ENV_PATH = ROOT / "channels" / "01-roblox-shorts" / ".env"
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
STATUS_PATH = Path(__file__).resolve().parent / "voice_status.json"

XI_VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam
XI_MODEL = "eleven_turbo_v2_5"
EDGE_VOICE = "en-US-AndrewMultilingualNeural"
EDGE_RATE = "+6%"


def load_elevenlabs_key() -> str | None:
    if os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY"):
        return os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() in ("ELEVENLABS_API_KEY", "XI_API_KEY"):
                    return v.strip().strip('"').strip("'")
    return None


def get_elevenlabs_quota(api_key: str) -> dict | None:
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/user/subscription",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        used = int(data.get("character_count", 0))
        limit = int(data.get("character_limit", 0))
        return {
            "character_count": used,
            "character_limit": limit,
            "remaining": limit - used,
            "tier": data.get("tier", "unknown"),
        }
    except Exception as exc:
        print(f"[voice_manager] Quota check failed ({exc}); assuming exhausted.", flush=True)
        return None


def synthesize_elevenlabs(text: str, api_key: str, out_wav: Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3 = out_wav.with_suffix(".mp3")
    payload = json.dumps({
        "text": text,
        "model_id": XI_MODEL,
        "voice_settings": {
            "stability": 0.48,
            "similarity_boost": 0.80,
            "style": 0.20,
            "use_speaker_boost": True,
            "speed": 1.12,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{XI_VOICE_ID}?output_format=mp3_44100_128",
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    mp3.write_bytes(urllib.request.urlopen(req, timeout=90).read())
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)], check=True)
    mp3.unlink(missing_ok=True)


def synthesize_edge_tts(text: str, out_wav: Path) -> None:
    import edge_tts

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3 = out_wav.with_suffix(".mp3")

    async def _gen() -> None:
        comm = edge_tts.Communicate(text, voice=EDGE_VOICE, rate=EDGE_RATE, pitch="+0Hz")
        await comm.save(str(mp3))

    asyncio.run(_gen())
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)], check=True)
    mp3.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: voice_manager.py <ep_dir>", file=sys.stderr)
        return 1

    ep_dir = Path(sys.argv[1]).resolve()
    tl = json.loads((ep_dir / "timeline.json").read_text(encoding="utf-8"))
    text = " ".join(s["text"].strip() for s in tl["sentences"] if s["text"].strip())
    need_chars = len(text)
    need_credits_est = max(1, need_chars // 2)  # turbo v2.5 = 0.5 credits/char (API tracks credits under character_count or chars)

    xi_key = load_elevenlabs_key()
    quota = get_elevenlabs_quota(xi_key) if xi_key else None
    used_engine = "edge_tts"
    exhausted = True
    out_wav = ep_dir / "narration" / "narrator_neural_fallback.wav"

    if xi_key and quota and quota["remaining"] >= need_chars + 100:
        xi_wav = ep_dir / "narration" / "ai_voice_xi_cartoon.wav"
        try:
            synthesize_elevenlabs(text, xi_key, xi_wav)
            out_wav = xi_wav
            used_engine = "elevenlabs_liam"
            exhausted = False
        except Exception as exc:
            print(f"[voice_manager] ElevenLabs synth failed ({exc}); falling back to edge-tts.", flush=True)

    if used_engine == "edge_tts":
        # Remove any stale ai_voice_xi_cartoon.wav so render.py prefers narrator_neural_fallback.wav
        stale_xi = ep_dir / "narration" / "ai_voice_xi_cartoon.wav"
        if stale_xi.exists():
            stale_xi.unlink()
        synthesize_edge_tts(text, out_wav)

    post_quota = get_elevenlabs_quota(xi_key) if xi_key else None
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "episode_id": tl.get("episode_id", ep_dir.name),
        "engine_used": used_engine,
        "output_wav": str(out_wav),
        "text_chars": need_chars,
        "elevenlabs_quota_exhausted": exhausted,
        "quota_before": quota,
        "quota_after": post_quota,
        "est_elevenlabs_cost_chars_or_credits": need_credits_est if used_engine.startswith("elevenlabs") else 0,
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
    rem_str = f"{post_quota['remaining']}/{post_quota['character_limit']}" if post_quota else "unknown"
    print(f"[voice_manager] {used_engine} -> {out_wav.name} (text={need_chars} chars, ElevenLabs remaining={rem_str})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
