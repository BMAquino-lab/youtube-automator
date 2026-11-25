#!/usr/bin/env python3
"""Universal JSON-driven Blender 4.2 LTS 2D-on-3D cartoon episode renderer (Fivestack studio kit v2).

Reads <ep_dir>/scene_plan.json (+ render/timeline_resolved.json when present) and renders every
unique shot (i001..iNNN) as a fast H.264 MP4 clip + exact Frame-0 PNG keyframe.

Usage:
  blender --background --factory-startup --python render_cartoon_episode.py -- --ep-dir <ep_dir> --check-frames
  blender --background --factory-startup --python render_cartoon_episode.py -- --ep-dir <ep_dir> --worker 0/2
  blender --background --factory-startup --python render_cartoon_episode.py -- --ep-dir <ep_dir> --only i001,i005
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import os
from pathlib import Path
import bpy
import mathutils

STUDIO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_DIR))
import cartoon_blender_kit as K  # noqa: E402
import diorama_library as D      # noqa: E402

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


def _activate_set(sets_meta: dict[str, dict], active_name: str, actors: dict[str, K.StickmanActor]) -> dict:
    for sname, meta in sets_meta.items():
        hide = sname != active_name
        col = meta["col"]
        col.hide_render = hide
        col.hide_viewport = hide
        for obj in col.objects:
            obj.hide_render = hide
            obj.hide_viewport = hide

    active_meta = sets_meta[active_name]
    sky_top, sky_hor, sky_str = active_meta["sky"]
    K.setup_world_sky(sky_top, sky_hor, strength=sky_str)

    for act in actors.values():
        act.set_visible(False)
        act.reset_animation()
    return active_meta


def _animate_prop_spec(meta: dict, prop_spec: dict, n_frames: int, ep_dir: Path) -> None:
    """Apply set-specific hero prop mode or swap diagram card texture on diagram_plane."""
    # Swap diagram image if present in spec
    diag_file = prop_spec.get("diagram_texture")
    if diag_file and "diagram_plane" in meta:
        tex_p = ep_dir / "textures" / diag_file
        if tex_p.exists():
            plane = meta["diagram_plane"]
            mat_name = f"DiagTex_{Path(diag_file).stem}"
            mat = K.make_image_mat(mat_name, tex_p, emission=0.32, roughness=0.50)
            plane.data.materials.clear()
            plane.data.materials.append(mat)

    # Interactive tank buoyancy / inflation animation
    tank = meta.get("hero_tank")
    if tank is not None:
        K.clear_object_anim(tank)
        mode = prop_spec.get("tank_mode", "bob")
        base_loc = tuple(prop_spec.get("tank_loc", (0.0, -0.35, 0.0)))
        rot_z = math.radians(float(prop_spec.get("tank_rot_z", 24.0)))
        base_s = float(prop_spec.get("tank_scale", 1.05))
        tank.rotation_euler = (0.0, 0.0, rot_z)
        if mode == "lift_overhead":
            # Held cleanly ABOVE helmets/heads so faces stay unobstructed!
            tank.location = (base_loc[0], base_loc[1], base_loc[2] + 2.55)
            tank.scale = (base_s, base_s, base_s)
            tank.keyframe_insert(data_path="location", frame=1)
            tank.keyframe_insert(data_path="scale", frame=1)
            mid = max(2, n_frames // 2)
            tank.location = (base_loc[0], base_loc[1], base_loc[2] + 2.72)
            tank.scale = (base_s * 1.02, base_s * 1.02, base_s * 0.96)
            tank.keyframe_insert(data_path="location", frame=mid)
            tank.keyframe_insert(data_path="scale", frame=mid)
            tank.location = (base_loc[0], base_loc[1], base_loc[2] + 2.58)
            tank.scale = (base_s, base_s, base_s)
            tank.keyframe_insert(data_path="location", frame=n_frames)
            tank.keyframe_insert(data_path="scale", frame=n_frames)
        elif mode == "inflate":
            tank.location = base_loc
            tank.scale = (base_s * 0.85, base_s * 0.85, base_s * 0.25)
            tank.keyframe_insert(data_path="scale", frame=1)
            tank.scale = (base_s * 1.04, base_s * 1.04, base_s * 1.06)
            tank.keyframe_insert(data_path="scale", frame=max(2, int(n_frames * 0.72)))
            tank.scale = (base_s, base_s, base_s)
            tank.keyframe_insert(data_path="scale", frame=n_frames)
        else:
            tank.location = base_loc
            tank.scale = (base_s, base_s, base_s)
            tank.keyframe_insert(data_path="scale", frame=1)
            tank.scale = (base_s * 1.02, base_s * 1.02, base_s * 0.97)
            tank.keyframe_insert(data_path="scale", frame=max(2, n_frames // 2))
            tank.scale = (base_s, base_s, base_s)
            tank.keyframe_insert(data_path="scale", frame=n_frames)

    # Expanding sonic wave rings diagonally across clearing away from lens
    rings = meta.get("wave_rings")
    if rings:
        for ri, ring in enumerate(rings):
            K.clear_object_anim(ring)
            phase = ri / max(1, len(rings))
            for step_f in (1, max(2, n_frames // 2), n_frames):
                t = (step_f - 1) / max(1, n_frames - 1)
                prog = (t + phase) % 1.0
                ring.location = (0.25 - prog * 2.2, -1.15 + prog * 1.4, 1.42 + prog * 0.20)
                ring.rotation_euler = (0.0, math.radians(82.0), math.radians(-35.0))
                sc = 0.55 + prog * 1.35
                ring.scale = (sc, sc, sc)
                ring.keyframe_insert(data_path="location", frame=step_f)
                ring.keyframe_insert(data_path="scale", frame=step_f)

    # Sliding map markers in war room
    markers = meta.get("map_markers")
    if markers:
        dx = float(prop_spec.get("marker_shift_x", -0.42))
        dy = float(prop_spec.get("marker_shift_y", -0.18))
        for mi, mk in enumerate(markers):
            K.clear_object_anim(mk)
            x0, y0, z0 = mk.location
            mk.keyframe_insert(data_path="location", frame=1)
            mk.location = (x0 + dx * (0.7 + 0.15 * mi), y0 + dy, z0)
            mk.keyframe_insert(data_path="location", frame=n_frames)

    # Flying recon plane + spinning propeller
    plane = meta.get("plane_root")
    if plane is not None:
        K.clear_object_anim(plane)
        plane.location = (-0.5, -1.5, 1.65)
        plane.rotation_euler = (math.radians(3.0), math.radians(-12.0), math.radians(-18.0))
        plane.keyframe_insert(data_path="location", frame=1)
        plane.keyframe_insert(data_path="rotation_euler", frame=1)
        plane.location = (0.65, -0.2, 1.55)
        plane.rotation_euler = (math.radians(-2.0), math.radians(8.0), math.radians(-8.0))
        plane.keyframe_insert(data_path="location", frame=n_frames)
        plane.keyframe_insert(data_path="rotation_euler", frame=n_frames)
    prop = meta.get("plane_prop")
    if prop is not None:
        K.clear_object_anim(prop)
        prop.rotation_euler = (0.0, 0.0, 0.0)
        prop.keyframe_insert(data_path="rotation_euler", frame=1)
        prop.rotation_euler = (0.0, math.radians(1440.0), 0.0)
        prop.keyframe_insert(data_path="rotation_euler", frame=n_frames)
        for fc in prop.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    # Iteration 3: Naval Dazzle Ship, Torpedo Miss Wake, Callout Arrows & Periscope Reticle
    ship = meta.get("dazzle_ship")
    if ship is not None:
        K.clear_object_anim(ship)
        smode = prop_spec.get("ship_mode", "cruise")
        x0, y0, z0 = tuple(prop_spec.get("ship_loc", ship.location))
        rz = math.radians(float(prop_spec.get("ship_rot_z", math.degrees(ship.rotation_euler.z))))
        if smode == "docked":
            ship.location = (x0, y0, z0)
            ship.rotation_euler = (0.0, 0.0, rz)
        else:
            dx = float(prop_spec.get("ship_dx", 1.15))
            mid = max(2, n_frames // 2)
            ship.location = (x0, y0, z0)
            ship.rotation_euler = (math.radians(-1.5), math.radians(1.0), rz)
            ship.keyframe_insert(data_path="location", frame=1)
            ship.keyframe_insert(data_path="rotation_euler", frame=1)
            ship.location = (x0 + dx * 0.5, y0, z0 + 0.04)
            ship.rotation_euler = (math.radians(1.8), math.radians(-1.2), rz)
            ship.keyframe_insert(data_path="location", frame=mid)
            ship.keyframe_insert(data_path="rotation_euler", frame=mid)
            ship.location = (x0 + dx, y0, z0)
            ship.rotation_euler = (math.radians(-1.0), math.radians(0.8), rz)
            ship.keyframe_insert(data_path="location", frame=n_frames)
            ship.keyframe_insert(data_path="rotation_euler", frame=n_frames)

    torp = meta.get("torpedo_root")
    if torp is not None:
        K.clear_object_anim(torp)
        tx0 = float(prop_spec.get("torpedo_x0", -1.2))
        tx1 = float(prop_spec.get("torpedo_x1", 6.2))
        ty = float(prop_spec.get("torpedo_y", -4.6))
        torp.location = (tx0, ty, 0.08)
        torp.keyframe_insert(data_path="location", frame=1)
        torp.location = (tx1, ty + 1.2, 0.08)
        torp.keyframe_insert(data_path="location", frame=n_frames)

    arrows = meta.get("callout_arrows")
    if arrows:
        show_arr = bool(prop_spec.get("show_callouts", True))
        for arr in arrows:
            for child in arr.children:
                child.hide_render = not show_arr
                child.hide_viewport = not show_arr

    reticle = meta.get("periscope_reticle")
    if reticle is not None:
        show_ret = bool(prop_spec.get("show_reticle", True))
        for child in reticle.children:
            child.hide_render = not show_ret
            child.hide_viewport = not show_ret
        if "reticle_loc" in prop_spec:
            reticle.location = tuple(prop_spec["reticle_loc"])

    # Iteration 5: Foreground silhouette framing props, crossroads store & map pin
    fg_list = meta.get("fg_framing")
    if fg_list:
        show_fg = bool(prop_spec.get("show_fg_framing", False))
        for fg_root in fg_list:
            for child in fg_root.children:
                child.hide_render = not show_fg
                child.hide_viewport = not show_fg

    store = meta.get("store_building")
    if store is not None:
        show_store = bool(prop_spec.get("show_store", False))
        for child in store.children:
            child.hide_render = not show_store
            child.hide_viewport = not show_store

    sign = meta.get("crossroads_sign")
    if sign is not None:
        show_sign = bool(prop_spec.get("show_sign", True))
        for child in sign.children:
            child.hide_render = not show_sign
            child.hide_viewport = not show_sign

    trap_pin = meta.get("trap_pin")
    if trap_pin is not None:
        K.clear_object_anim(trap_pin)
        px0, py0, pz0 = (0.12, -0.22, 1.50)
        trap_pin.location = (px0, py0, pz0)
        trap_pin.keyframe_insert(data_path="location", frame=1)
        trap_pin.location = (px0, py0, 1.16)
        trap_pin.keyframe_insert(data_path="location", frame=max(2, n_frames // 2))
        trap_pin.location = (px0, py0, 1.18)
        trap_pin.keyframe_insert(data_path="location", frame=n_frames)


def stage_shot(
    shot_spec: dict,
    n_frames: int,
    cam: bpy.types.Object,
    actors: dict[str, K.StickmanActor],
    sets_meta: dict[str, dict],
    ep_dir: Path,
) -> None:
    meta = _activate_set(sets_meta, shot_spec["set"], actors)
    _animate_prop_spec(meta, shot_spec.get("props", {}), n_frames, ep_dir)

    for ca in shot_spec.get("actors", []):
        act = actors[ca["id"]]
        act.set_visible(True)
        action = ca.get("action", "idle_talk")
        loc = tuple(ca.get("loc", (0.0, 0.0, 0.0)))
        yaw = float(ca.get("yaw_deg", 0.0))
        emo = ca.get("emotion", "NEUTRAL")
        inten = float(ca.get("intensity", 1.0))

        if action == "point":
            act.animate_point(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo, side=ca.get("side", "R"))
        elif action == "shock":
            act.animate_shock_recoil(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo)
        elif action == "laugh":
            act.animate_laugh(1, n_frames, root_loc=loc, yaw_deg=yaw)
        elif action == "lift_prop":
            act.animate_lift_prop(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo)
        elif action == "salute":
            act.animate_salute(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo)
        elif action == "peer_periscope":
            act.animate_peer_periscope(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo)
        elif action == "paint_stroke":
            act.animate_paint_stroke(1, n_frames, root_loc=loc, yaw_deg=yaw, emotion=emo)
        else:
            act.animate_idle_talk(1, n_frames, emo, root_loc=loc, yaw_deg=yaw, intensity=inten)

        for hp in ca.get("held_props", []):
            act.set_prop_visible(hp, True)

        mid_f = max(2, min(n_frames, int(round(n_frames * float(ca.get("mid_frame_frac", 0.50)))))) if ca.get("mid_emotion") else None
        if action in ("idle_talk", "point", "paint_stroke", "peer_periscope", "salute", "laugh"):
            act.animate_lip_flap(
                1,
                n_frames,
                emo,
                mid_emotion=ca.get("mid_emotion"),
                mid_frame=mid_f,
            )
        elif ca.get("mid_emotion") and mid_f is not None:
            act.set_emotion_at(mid_f, ca["mid_emotion"])

    cm = shot_spec["camera"]
    K.animate_camera(
        cam,
        1,
        n_frames,
        tuple(cm["loc0"]),
        tuple(cm["tgt0"]),
        tuple(cm["loc1"]),
        tuple(cm["tgt1"]),
        lens0=float(cm.get("lens0", 40.0)),
        lens1=float(cm.get("lens1", cm.get("lens0", 40.0))),
        fstop=float(cm.get("fstop", 3.2)),
        use_dof=bool(cm.get("use_dof", False)),
        dof_dist0=float(cm["dof_dist0"]) if "dof_dist0" in cm else None,
        dof_dist1=float(cm["dof_dist1"]) if "dof_dist1" in cm else None,
        dof_dist_mid=float(cm["dof_dist_mid"]) if "dof_dist_mid" in cm else None,
        dof_mid_frac=float(cm.get("dof_mid_frac", 0.50)),
        fstop1=float(cm["fstop1"]) if "fstop1" in cm else None,
    )


def compute_shot_durations(ep_dir: Path, fps: int, all_ids: list[str]) -> dict[str, int]:
    resolved_p = ep_dir / "render" / "timeline_resolved.json"
    if resolved_p.exists():
        tl = json.loads(resolved_p.read_text(encoding="utf-8"))
        by_img: dict[str, float] = {}
        for s in tl["shots"]:
            dur_s = float(s.get("n_frames", 45)) / 30.0
            by_img[s["image_id"]] = max(by_img.get(s["image_id"], 0.0), dur_s)
        return {img_id: max(18, math.ceil((dur_s + 0.35) * fps)) for img_id in all_ids if (dur_s := by_img.get(img_id, 2.0))}
    return {img_id: max(18, math.ceil(2.4 * fps)) for img_id in all_ids}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep-dir", required=True)
    ap.add_argument("--check-frames", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--worker", default="")
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=1280)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--samples", type=int, default=8)
    args = ap.parse_args(argv)

    ep_dir = Path(args.ep_dir).resolve()
    plan = json.loads((ep_dir / "scene_plan.json").read_text(encoding="utf-8"))
    ep_id = plan["episode_id"]

    scn = K.reset_scene(
        fps=args.fps,
        width=args.width,
        height=args.height,
        samples=args.samples,
        bloom=False,
    )

    cast_col = K.get_or_create_collection("Cast")
    actors: dict[str, K.StickmanActor] = {}
    for c in plan["cast"]:
        actors[c["id"]] = K.StickmanActor(
            c["id"].title(),
            preset=c["preset"],
            torso_hex=c.get("torso_hex"),
            col=cast_col,
        )

    sets_meta: dict[str, dict] = {}
    for sname in plan["sets"]:
        builder = D.SET_BUILDERS[sname]
        col = K.get_or_create_collection(f"Set_{sname}")
        sets_meta[sname] = builder(col, frame_end=80)

    cam = K.ensure_camera("MainCam")
    shots_map: dict[str, dict] = plan["shots"]
    all_ids = sorted(shots_map.keys())
    durations = compute_shot_durations(ep_dir, args.fps, all_ids)

    if args.check_frames:
        prev_dir = STUDIO_DIR / "previews" / ep_id
        prev_dir.mkdir(parents=True, exist_ok=True)
        check_ids = plan.get("check_shots") or [all_ids[min(len(all_ids) - 1, k)] for k in (0, 2, 6, 11, 16, len(all_ids) - 2)]
        stage_shot(shots_map[all_ids[0]], durations[all_ids[0]], cam, actors, sets_meta, ep_dir)
        blend_out = ep_dir / f"{ep_id}_blender_scene.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
        print(f"SAVED BLEND: {blend_out}", flush=True)

        scn.render.image_settings.file_format = "PNG"
        scn.render.image_settings.color_mode = "RGB"
        for sid in check_ids:
            t0 = time.time()
            nf = durations[sid]
            stage_shot(shots_map[sid], nf, cam, actors, sets_meta, ep_dir)
            scn.frame_start = 1
            scn.frame_end = nf
            scn.frame_set(1)
            out_png = prev_dir / f"check_{sid}.png"
            scn.render.filepath = str(out_png)
            bpy.ops.render.render(write_still=True)
            print(f"[check] {sid} -> {out_png.name} ({time.time() - t0:.2f}s)", flush=True)
        return

    clips_dir = ep_dir / "clips"
    kf_dir = ep_dir / "keyframes"
    clips_dir.mkdir(parents=True, exist_ok=True)
    kf_dir.mkdir(parents=True, exist_ok=True)

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    todo = [sid for sid in all_ids if not only or sid in only]
    if args.worker:
        w_idx, w_tot = (int(x) for x in args.worker.split("/"))
        todo = [sid for i, sid in enumerate(todo) if i % w_tot == w_idx]

    print(f"Rendering {len(todo)} Blender 3D clip(s) at {args.width}x{args.height} @ {args.fps}fps: {todo}", flush=True)
    for idx, sid in enumerate(todo, 1):
        t0 = time.time()
        nf = durations[sid]
        stage_shot(shots_map[sid], nf, cam, actors, sets_meta, ep_dir)
        scn.frame_start = 1
        scn.frame_end = nf
        out_mp4 = clips_dir / f"{sid}.mp4"
        out_kf = kf_dir / f"{sid}.png"
        K.configure_mp4_output(scn, out_mp4)
        bpy.ops.render.render(animation=True)
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-i", str(out_mp4), "-frames:v", "1", str(out_kf)],
            check=True,
        )
        kb = out_mp4.stat().st_size // 1024
        print(f"[{idx}/{len(todo)}] {sid}.mp4 ({nf}f @ {args.fps}fps, {kb} KB) + {out_kf.name} in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
