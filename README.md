# youtube-automator

Automated Blender 4.2 LTS 2D-on-3D stickman diorama studio, 20-gate quality assurance pipeline, smart quota-aware TTS voice manager, and Playwright YouTube Shorts publisher for `@Fivestackkk`.

## Architecture
- `blender_studio/` — Modular Blender 4.2 EEVEE Next stickman rig (`cartoon_blender_kit.py`), miniature 3D diorama builder library (`diorama_library.py`), Pillow sprite/infographic generators (`generate_cartoon_faces.py`, `generate_episode_diagrams.py`), and multi-worker JSON renderer (`render_cartoon_episode.py`).
- `automation/` — ElevenLabs -> `edge-tts` automatic voice failover (`voice_manager.py`), lockfile-safe queue publisher (`publish_next_short.py`), iteration benchmark tracker (`log_iteration.py`), and secret-checked repo sync (`sync_to_github.py`).
- `uploader/` — Env-configured Playwright desktop Chrome YouTube Studio Shorts uploader (`upload_short.mjs`).

## Iteration Benchmarks

| Iteration | Episode | Render Profile | Shots (Clips) | Render Wall Time | Audio & QA |
| :--- | :--- | :--- | :--- | :--- | :--- |
| v1 | `ep04_jackscrew_hotel` | `720x1280 @ 24fps` | 39 (38) | 80.0 min | 210 WPM / 95% recall / `20/20` |
| v2 | `ep05_ghost_army_tanks` | `576x1024 @ 15fps` | 40 (38) | 21.86 min | 205 WPM / 94% recall / `20/20` |
| v3 | `ep06_dazzle_warships` | `576x1024 @ 15fps` | 44 (40) | 15.33 min | 210 WPM / 95% recall / `20/20` |
| v4 | `ep06_dazzle_warships_v4` | `720x1280 @ 24fps` | 44 (40) | 43.34 min | 210 WPM / 95% recall / `20/20` |
| v5 | `ep07_deadliest_paper_map` | `720x1280 @ 24fps` | 41 (36) | 49.2 min | 204 WPM / 91% recall / `20/20` |
| v6 | `ep08_concrete_ships_ww2` | `720x1280 @ 24fps` | 40 (39) | 26.8 min | 197 WPM / 87% recall / `20/20` |

## Local Setup
1. Copy `.env.example` to `.env` and fill your local credentials (never commit `.env`).
2. Install Python dependencies + `edge-tts`, Pillow, FFmpeg, and Blender 4.2 LTS.
3. Render an episode via multi-worker `render_cartoon_episode.py` -> assemble -> run strict 20-gate QA -> enqueue & publish with `publish_next_short.py`.
