"""Modular 3D miniature diorama set builders for Fivestack (@RicksClips3000 / Blender 4.2 LTS EEVEE Next).

Every builder populates an isolated Blender Collection and returns a metadata dict containing:
  - 'col': Collection
  - 'sky': (top_hex, horizon_hex, strength)
  - 'animated_props': optional named objects & mode hooks controlled by render_cartoon_episode.py
"""
from __future__ import annotations

import math
import random
import os
from pathlib import Path
import bpy
import mathutils

import cartoon_blender_kit as K


def _make_empty(name: str, loc: tuple[float, float, float], col: bpy.types.Collection) -> bpy.types.Object:
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = 0.25
    e.location = loc
    K.link_to_collection(e, col)
    return e


def _build_pine_tree(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
    trunk_mat: bpy.types.Material,
    leaf_mat: bpy.types.Material,
) -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        K.add_cylinder(
            f"{name}_Trunk",
            0.12 * scale,
            1.1 * scale,
            (x, y, z + 0.55 * scale),
            trunk_mat,
            col,
            vertices=10,
            outline=0.015,
        )
    ]
    for idx, (rz, r1, h) in enumerate(((1.25, 0.72, 1.15), (1.92, 0.54, 0.95), (2.48, 0.36, 0.75))):
        objs.append(
            K.add_cone(
                f"{name}_Tier{idx}",
                r1 * scale,
                0.03 * scale,
                h * scale,
                (x, y, z + rz * scale),
                leaf_mat,
                col,
                vertices=10,
                outline=0.018,
            )
        )
    return objs


def _build_rubber_tank(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
    *,
    rot_z_deg: float = 0.0,
    with_valve: bool = False,
) -> bpy.types.Object:
    """Stylized puffy olive-drab inflatable M4 Sherman tank rig parented under an Empty root."""
    root = _make_empty(f"{name}_Root", loc, col)
    root.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))
    root.scale = (scale, scale, scale)

    m_olive = K.make_toon_mat(f"{name}_RubberOlive", "#667A44", emission_lift=0.22, roughness=0.58)
    m_track = K.make_toon_mat(f"{name}_RubberTrack", "#2C3029", emission_lift=0.08, roughness=0.72)
    m_star = K.make_toon_mat(f"{name}_WhiteStar", "#F4F1E6", emission_lift=0.45, roughness=0.7)

    parts: list[bpy.types.Object] = []
    # Rounded puffy rubber treads (left & right)
    for sx in (-0.82, 0.82):
        tr = K.add_box(
            f"{name}_Track{'L' if sx < 0 else 'R'}",
            (0.40, 2.35, 0.58),
            (sx, 0.0, 0.30),
            m_track,
            col,
            bevel=0.14,
            outline=0.024,
        )
        parts.append(tr)

    # Rounded rubber hull
    hull = K.add_box(
        f"{name}_Hull",
        (1.42, 2.08, 0.66),
        (0.0, 0.0, 0.56),
        m_olive,
        col,
        bevel=0.16,
        outline=0.028,
    )
    parts.append(hull)

    # White Allied star badge painted on front glinting slope & sides
    badge = K.add_cylinder(
        f"{name}_StarPlate",
        0.22,
        0.03,
        (0.0, 0.96, 0.65),
        m_star,
        col,
        vertices=5,
        rot_deg=(65.0, 0.0, 0.0),
    )
    parts.append(badge)

    # Puffy rounded turret
    turret = K.add_sphere(
        f"{name}_Turret",
        0.58,
        (0.0, -0.05, 1.06),
        m_olive,
        col,
        segments=16,
        rings=12,
        scale=(1.05, 1.18, 0.72),
        outline=0.026,
    )
    parts.append(turret)

    # Rubber gun barrel angled slightly forward-up
    barrel = K.add_cylinder(
        f"{name}_Barrel",
        0.10,
        1.45,
        (0.0, 0.95, 1.12),
        m_olive,
        col,
        vertices=14,
        rot_deg=(84.0, 0.0, 0.0),
        outline=0.020,
    )
    parts.append(barrel)

    if with_valve:
        m_brass = K.make_toon_mat(f"{name}_ValveBrass", "#DFB13E", emission_lift=0.25, roughness=0.35)
        valve = K.add_cylinder(
            f"{name}_AirValve",
            0.09,
            0.22,
            (0.68, 0.45, 0.68),
            m_brass,
            col,
            vertices=12,
            rot_deg=(0.0, 90.0, 0.0),
            outline=0.015,
        )
        parts.append(valve)

    for p in parts:
        p.parent = root
    return root


# --------------------------------------------------------------------------- 1. WWII NORMANDY MEADOW
def build_wwii_meadow_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_sunlit_sky_rig(
        "MeadowSunRig",
        col,
        sun_rot_deg=(48.0, 12.0, -32.0),
        sun_energy=2.3,
        sky_top="#2164C8",
        sky_horizon="#78BAF5",
        sky_strength=0.82,
        sun_disc_loc=(-5.8, -15.0, 9.2),
    )

    m_grass = K.make_pbr_mat("Meadow_Grass", "LeafyGrass", "#9EE066", uv_scale=6.0, roughness_bias=0.12, emission_lift=0.18)
    m_grass_dk = K.make_pbr_mat("Meadow_Hill", "Grass", "#80BA54", uv_scale=5.0, roughness_bias=0.14, emission_lift=0.15)
    m_road = K.make_pbr_mat("Meadow_DirtRoad", "Ground", "#DFB888", uv_scale=5.0, roughness_bias=0.18, emission_lift=0.16)
    m_wood = K.make_pbr_mat("Meadow_FenceWood", "Wood", "#B88456", uv_scale=4.0, roughness_bias=0.12, emission_lift=0.14)
    m_trunk = K.make_toon_mat("Meadow_PineTrunk", "#5C3D26", emission_lift=0.10, roughness=0.88)
    m_pine = K.make_toon_mat("Meadow_PineLeaf", "#336B36", emission_lift=0.16, roughness=0.82)
    m_pebble = K.make_pbr_mat("Meadow_Pebble", "Cobblestone", "#BFB4A4", uv_scale=4.0, emission_lift=0.12)
    m_crate = K.make_pbr_mat("Meadow_Crate", "WoodPlanks", "#DFB87E", uv_scale=3.0, emission_lift=0.16)

    # Sunlit rolling pasture floor + leading-line dirt road
    K.add_box("Meadow_Floor", (26.0, 26.0, 0.8), (0.0, -2.0, -0.40), m_grass, col, bevel=0.04)
    K.add_box("Meadow_Road", (3.2, 24.0, 0.08), (0.2, -2.0, 0.02), m_road, col, bevel=0.02, rot_deg=(0.0, 0.0, -8.0))
    for i, (hx, hy, sx, sy, sz) in enumerate((
        (-6.2, -9.5, 8.5, 4.5, 2.2),
        (6.4, -10.5, 9.0, 4.8, 2.5),
        (0.0, -14.0, 18.0, 5.5, 3.2),
    )):
        K.add_sphere(f"Meadow_Hill{i}", 1.0, (hx, hy, -0.35), m_grass_dk, col, segments=14, rings=8, scale=(sx, sy, sz))

    # Faceted tabletop pebbles along track edge (like @RicksClips3000 ballast texture)
    rng = random.Random(42)
    for i in range(28):
        px = rng.uniform(-2.8, 3.0)
        py = rng.uniform(-6.0, 3.2)
        pr = rng.uniform(0.06, 0.14)
        K.add_sphere(
            f"Meadow_Pebble{i:02d}",
            pr,
            (px, py, 0.03),
            m_pebble if i % 2 else m_road,
            col,
            segments=7,
            rings=5,
            scale=(1.2, 0.9, 0.5),
        )

    # Rustic wooden pasture fence on both flanks
    for side_x in (-4.2, 4.4):
        for py in (-7.5, -4.5, -1.5, 1.5):
            K.add_box(f"Meadow_Post_{side_x}_{py}", (0.14, 0.14, 1.15), (side_x, py, 0.56), m_wood, col, bevel=0.02, outline=0.014)
        for rz in (0.42, 0.84):
            K.add_box(f"Meadow_Rail_{side_x}_{rz}", (0.08, 10.5, 0.10), (side_x, -3.0, rz), m_wood, col, bevel=0.015, outline=0.012)

    # Stylized pines around meadow perimeter
    for idx, (tx, ty, ts) in enumerate(((-5.8, -5.0, 1.25), (-6.8, -1.2, 1.05), (5.8, -4.4, 1.3), (6.5, -7.8, 1.15))):
        _build_pine_tree(f"Meadow_Tree{idx}", (tx, ty, 0.0), ts, col, m_trunk, m_pine)

    # Background row of inflated decoy tanks (depth perspective)
    _build_rubber_tank("Meadow_BgTank1", (-3.1, -6.2, 0.0), 0.72, col, rot_z_deg=18.0)
    _build_rubber_tank("Meadow_BgTank2", (2.9, -6.8, 0.0), 0.72, col, rot_z_deg=-15.0)

    # Hero inflatable tank (animated / liftable!) + supply air pump & wooden crate
    hero_tank = _build_rubber_tank("Meadow_HeroTank", (0.0, -0.35, 0.0), 1.05, col, rot_z_deg=24.0, with_valve=True)
    pump = K.add_cylinder("Meadow_AirPump", 0.18, 0.52, (1.45, 0.25, 0.26), K.make_toon_mat("Meadow_PumpRed", "#C84434", 0.20), col, outline=0.016)
    crate = K.add_box("Meadow_Crate", (0.85, 0.65, 0.58), (-2.1, -0.6, 0.29), m_crate, col, bevel=0.02, outline=0.018)

    # Gentle drift clouds in the sunlit sky
    m_cloud = K.make_toon_mat("Meadow_Cloud", "#EEF4FC", emission_lift=0.20, roughness=0.95)
    for ci, (cx, cy, cz) in enumerate(((-3.8, -13.5, 6.2), (3.5, -14.5, 7.1), (0.4, -15.5, 8.0))):
        cl = K.add_sphere(f"Meadow_Cloud{ci}", 1.15, (cx, cy, cz), m_cloud, col, segments=12, rings=8, scale=(2.2, 0.9, 0.65))
        if hasattr(cl, "visible_shadow"):
            cl.visible_shadow = False

    return {
        "col": col,
        "sky": ("#2164C8", "#78BAF5", 0.82),
        "hero_tank": hero_tank,
        "air_pump": pump,
        "crate": crate,
    }


# --------------------------------------------------------------------------- 2. WWII FOREST SONIC SET
def build_wwii_forest_sonic_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    # Crisp moody cobalt evening woodland + golden camp lights so stickmen still pop bright white
    K.add_sunlit_sky_rig(
        "SonicMoonRig",
        col,
        sun_rot_deg=(42.0, -18.0, -25.0),
        sun_energy=1.65,
        sun_color="#9EC4FF",
        sky_top="#192A56",
        sky_horizon="#5076B8",
        sky_strength=0.95,
        sun_disc_loc=(4.5, -14.0, 8.5),
    )

    m_earth = K.make_pbr_mat("Sonic_Earth", "Ground", "#7D7466", uv_scale=5.0, emission_lift=0.14)
    m_grass = K.make_pbr_mat("Sonic_Moss", "Grass", "#64945E", uv_scale=5.0, emission_lift=0.14)
    m_truck = K.make_toon_mat("Sonic_HalfTrack", "#53603D", emission_lift=0.22, roughness=0.65)
    m_metal = K.make_pbr_mat("Sonic_Steel", "Metal", "#7B8798", uv_scale=3.0, emission_lift=0.14)
    m_horn = K.make_toon_mat("Sonic_HornBrass", "#D6A134", emission_lift=0.28, roughness=0.32)
    m_trunk = K.make_toon_mat("Sonic_Trunk", "#48301E", emission_lift=0.08)
    m_pine = K.make_toon_mat("Sonic_Pine", "#254C2E", emission_lift=0.12)

    K.add_box("Sonic_Ground", (24.0, 24.0, 0.8), (0.0, -2.0, -0.40), m_earth, col, bevel=0.04)
    K.add_box("Sonic_RimPatch", (14.0, 12.0, 0.06), (0.0, -6.5, 0.02), m_grass, col)

    for idx, (tx, ty, ts) in enumerate((
        (-4.5, -3.5, 1.3), (-3.8, -7.2, 1.4), (4.2, -3.0, 1.25), (4.8, -6.5, 1.35), (-1.5, -8.8, 1.5), (1.8, -9.2, 1.4)
    )):
        _build_pine_tree(f"Sonic_Tree{idx}", (tx, ty, 0.0), ts, col, m_trunk, m_pine)

    # Stylized sound-truck half-track at (0.85, -2.1) rotated diagonally left so horns shine cleanly
    truck_root = _make_empty("Sonic_TruckRoot", (0.85, -2.1, 0.0), col)
    truck_root.rotation_euler = (0.0, 0.0, math.radians(-52.0))
    truck_parts = [
        K.add_box("Sonic_TruckBed", (1.65, 2.8, 0.55), (0.0, 0.0, 0.72), m_truck, col, bevel=0.08, outline=0.024),
        K.add_box("Sonic_TruckCab", (1.45, 1.1, 0.85), (0.0, -1.45, 1.05), m_truck, col, bevel=0.08, outline=0.024),
    ]
    for wx in (-0.84, 0.84):
        for wy in (-1.35, 0.75):
            truck_parts.append(
                K.add_cylinder(f"Sonic_Wheel_{wx}_{wy}", 0.34, 0.24, (wx, wy, 0.34), K.make_toon_mat("Sonic_Tire", "#1E2024", 0.06), col, rot_deg=(0.0, 90.0, 0.0), outline=0.018)
            )

    # Pair of giant 500-lb horn speakers mounted on the truck bed aiming forward-left
    for hx in (-0.42, 0.42):
        truck_parts.append(K.add_box(f"Sonic_SpkBox{hx}", (0.58, 0.52, 0.52), (hx, 0.2, 1.26), m_metal, col, bevel=0.04, outline=0.020))
        truck_parts.append(K.add_cone(f"Sonic_SpkHorn{hx}", 0.42, 0.14, 0.62, (hx, 0.72, 1.34), m_horn, col, rot_deg=(82.0, 0.0, 0.0), outline=0.020))
    for p in truck_parts:
        p.parent = truck_root

    # Sleek pulsing golden sonic wave rings radiating diagonally from speakers
    m_wave = K.make_emissive_mat("Sonic_WaveGlow", "#FFD358", strength=1.8)
    wave_rings: list[bpy.types.Object] = []
    for wi in range(5):
        ring = K.add_torus(f"Sonic_WaveRing{wi}", 0.32, 0.018, (0.25, -1.15, 1.42), m_wave, col, rot_deg=(0.0, 82.0, -35.0))
        if hasattr(ring, "visible_shadow"):
            ring.visible_shadow = False
        wave_rings.append(ring)

    K.add_warm_lantern("Sonic_CampLanternL", (-2.6, 0.6, 1.45), col, energy=95.0, radius=0.22)
    K.add_warm_lantern("Sonic_CampLanternR", (2.4, -0.5, 1.35), col, energy=85.0, radius=0.20)
    K.add_floating_motes("Sonic_Motes", (0.0, -1.0, 1.8), (3.5, 2.5, 1.2), col, count=22, frame_end=frame_end)

    return {
        "col": col,
        "sky": ("#192A56", "#5076B8", 0.95),
        "wave_rings": wave_rings,
        "truck_root": truck_root,
    }


# --------------------------------------------------------------------------- 3. WWII WAR ROOM
def build_wwii_warroom_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    # Warm timber bunker room with strong overhead skylight & lamp pool
    K.add_cinematic_3point_rig(
        "WarRoomRig",
        col,
        key_loc=(0.0, 2.2, 4.4),
        fill_loc=(-3.2, 3.8, 2.4),
        rim_loc=(0.0, -2.5, 3.0),
        key_energy=240.0,
        fill_energy=105.0,
        rim_energy=160.0,
    )

    m_floor = K.make_pbr_mat("War_FloorWood", "WoodPlanks", "#8B684E", uv_scale=4.0, emission_lift=0.14)
    m_wall = K.make_pbr_mat("War_WallTimber", "Wood", "#9B7B5C", uv_scale=4.0, emission_lift=0.18)
    m_table = K.make_pbr_mat("War_TableOak", "Wood", "#735036", uv_scale=3.0, emission_lift=0.14)
    m_sea = K.make_toon_mat("War_MapSea", "#457AA8", emission_lift=0.22, roughness=0.55)
    m_land = K.make_toon_mat("War_MapLand", "#C9B47C", emission_lift=0.20, roughness=0.72)
    m_pin_red = K.make_toon_mat("War_MarkerRed", "#D43F36", emission_lift=0.35, roughness=0.45)
    m_pin_blue = K.make_toon_mat("War_MarkerBlue", "#3478D4", emission_lift=0.35, roughness=0.45)

    K.add_box("War_Floor", (14.0, 12.0, 0.4), (0.0, 0.0, -0.20), m_floor, col)
    K.add_box("War_BackWall", (14.0, 0.5, 6.2), (0.0, -3.4, 3.1), m_wall, col)
    K.add_box("War_SideWallL", (0.5, 10.0, 6.2), (-4.8, 0.5, 3.1), m_wall, col)
    K.add_box("War_SideWallR", (0.5, 10.0, 6.2), (4.8, 0.5, 3.1), m_wall, col)

    # Central tactical map table
    K.add_box("War_TableTop", (3.6, 2.2, 0.18), (0.0, -0.3, 1.05), m_table, col, bevel=0.03, outline=0.022)
    for lx in (-1.55, 1.55):
        for ly in (-1.2, 0.6):
            K.add_cylinder(f"War_Leg_{lx}_{ly}", 0.10, 1.0, (lx, ly, 0.50), m_table, col, outline=0.015)

    # Channel sea & coastline diorama blocks atop the map table
    K.add_box("War_MapWater", (3.2, 1.8, 0.05), (0.0, -0.3, 1.16), m_sea, col, bevel=0.01)
    K.add_box("War_MapCalais", (1.25, 1.4, 0.10), (-0.78, -0.35, 1.20), m_land, col, bevel=0.02, outline=0.012)
    K.add_box("War_MapBritain", (1.10, 0.65, 0.09), (0.88, 0.18, 1.19), m_land, col, bevel=0.02, outline=0.012)

    # Sliding miniature map tank markers moving toward Pas-de-Calais
    markers: list[bpy.types.Object] = []
    for mi, (mx, my) in enumerate(((0.55, 0.10), (0.25, -0.15), (-0.25, -0.30))):
        mk = K.add_box(f"War_Marker{mi}", (0.22, 0.16, 0.16), (mx, my, 1.28), m_pin_red if mi < 2 else m_pin_blue, col, bevel=0.02, outline=0.014)
        markers.append(mk)

    # Overhead green bunker lamp shade raised above officer cap
    m_shade = K.make_toon_mat("War_LampGreen", "#265E40", emission_lift=0.22, roughness=0.45)
    K.add_cone("War_LampShade", 0.65, 0.16, 0.36, (0.0, -0.3, 3.55), m_shade, col, outline=0.018)
    K.add_warm_lantern("War_DeskLamp", (0.0, -0.3, 3.30), col, color_hex="#FFE2A4", energy=75.0, radius=0.14)

    return {
        "col": col,
        "sky": ("#2C211B", "#4B3A2E", 0.55),
        "map_markers": markers,
    }


# --------------------------------------------------------------------------- 4. WWII SKY RECON SET
def build_wwii_sky_recon_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_sunlit_sky_rig(
        "SkyReconSun",
        col,
        sun_rot_deg=(52.0, 14.0, -28.0),
        sun_energy=2.3,
        sky_top="#2164C8",
        sky_horizon="#78BAF5",
        sky_strength=0.82,
        sun_disc_loc=(-5.0, -16.0, 8.8),
    )

    m_patch1 = K.make_toon_mat("Sky_FieldLight", "#7AB24D", emission_lift=0.18, roughness=0.88)
    m_patch2 = K.make_toon_mat("Sky_FieldGold", "#C2AD5A", emission_lift=0.16, roughness=0.88)
    m_patch3 = K.make_toon_mat("Sky_FieldDark", "#558B3C", emission_lift=0.14, roughness=0.88)
    m_cloud = K.make_toon_mat("Sky_CloudWhite", "#EEF4FC", emission_lift=0.20, roughness=0.95)
    m_plane = K.make_toon_mat("Sky_ReconSilver", "#BFC8D4", emission_lift=0.28, roughness=0.42)
    m_red = K.make_toon_mat("Sky_ReconTrim", "#B8342A", emission_lift=0.28, roughness=0.52)

    # Patchwork agricultural terrain below at Z=-4.0
    mats = (m_patch1, m_patch2, m_patch3)
    for gx in range(-2, 3):
        for gy in range(-2, 2):
            K.add_box(f"Sky_Field_{gx}_{gy}", (4.8, 4.4, 0.2), (gx * 4.9, gy * 4.5 - 3.0, -4.0), mats[(gx + gy) % 3], col, bevel=0.02)

    # Neat decoy tanks far below glinting on meadow patch
    for ti, tx in enumerate((-2.2, -0.7, 0.8, 2.3)):
        _build_rubber_tank(f"Sky_TinyTank{ti}", (tx, -3.5, -3.88), 0.42, col, rot_z_deg=25.0)

    # Puffy sky clouds floating between plane & terrain
    for ci, (cx, cy, cz, sx) in enumerate((
        (-2.8, -5.0, -1.4, 1.8), (3.2, -6.5, -1.2, 2.1), (-0.4, -8.0, 0.8, 2.4), (3.6, -2.5, -0.6, 1.6)
    )):
        c = K.add_sphere(f"Sky_CloudPuff{ci}", 0.9, (cx, cy, cz), m_cloud, col, segments=12, rings=8, scale=(sx, 1.0, 0.55))
        if hasattr(c, "visible_shadow"):
            c.visible_shadow = False

    # Stylized Recon Plane
    plane_root = _make_empty("Sky_PlaneRoot", (0.0, -1.0, 1.6), col)
    p_parts = [
        K.add_cylinder("Sky_Fuselage", 0.30, 2.3, (0.0, 0.0, 0.0), m_plane, col, rot_deg=(90.0, 0.0, 0.0), outline=0.022),
        K.add_box("Sky_Wings", (3.2, 0.65, 0.10), (0.0, 0.15, 0.05), m_plane, col, bevel=0.03, outline=0.020),
        K.add_box("Sky_TailWing", (1.2, 0.38, 0.08), (0.0, -1.0, 0.10), m_red, col, bevel=0.02, outline=0.016),
        K.add_box("Sky_TailFin", (0.08, 0.42, 0.55), (0.0, -1.0, 0.34), m_red, col, bevel=0.02, outline=0.016),
        K.add_sphere("Sky_NoseSpinner", 0.24, (0.0, 1.18, 0.0), m_red, col, outline=0.016),
    ]
    for p in p_parts:
        p.parent = plane_root

    prop = K.add_box("Sky_Propeller", (1.25, 0.05, 0.14), (0.0, 1.32, 0.0), K.make_toon_mat("Sky_PropMat", "#202226", 0.12), col, bevel=0.015)
    prop.parent = plane_root

    return {
        "col": col,
        "sky": ("#2C74DC", "#C6E8FF", 1.25),
        "plane_root": plane_root,
        "plane_prop": prop,
    }


# --------------------------------------------------------------------------- 5. TACTILE 3D DIAGRAM BACKDROP SET
def build_diagram_backdrop_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_cinematic_3point_rig(
        "DiagramStudioRig",
        col,
        key_loc=(1.8, 4.2, 3.8),
        fill_loc=(-2.5, 4.0, 2.4),
        rim_loc=(0.0, -2.5, 3.2),
        key_color="#FFF3DF",
        fill_color="#B8D8FF",
        rim_color="#FFE29E",
        key_energy=210.0,
        fill_energy=95.0,
        rim_energy=150.0,
    )

    m_bench = K.make_pbr_mat("Diag_OakBench", "WoodPlanks", "#BD8E60", uv_scale=3.5, emission_lift=0.16)
    m_wall = K.make_pbr_mat("Diag_WarmWall", "Slate", "#6A7C96", uv_scale=2.5, emission_lift=0.20)
    m_frame = K.make_pbr_mat("Diag_FrameWood", "Wood", "#735036", uv_scale=3.0, emission_lift=0.12)
    m_brass = K.make_toon_mat("Diag_BrassAcc", "#D8A842", emission_lift=0.24, roughness=0.35)
    m_red = K.make_toon_mat("Diag_FolderRed", "#B54132", emission_lift=0.20, roughness=0.65)
    m_paper = K.make_toon_mat("Diag_DefaultPaper", "#F0E5CC", emission_lift=0.25, roughness=0.60)

    K.add_box("Diag_Table", (10.0, 6.0, 0.4), (0.0, 0.0, -0.20), m_bench, col, bevel=0.03)
    K.add_box("Diag_BackWall", (14.0, 0.5, 8.0), (0.0, -2.8, 3.5), m_wall, col)

    # Framed poster board mounted upright at Y=-0.1, centered at Z=1.55 (top ~2.7 BU, bottom ~0.4 BU)
    frame_box = K.add_box("Diag_EaselBoard", (2.06, 0.10, 2.48), (0.0, -0.10, 1.56), m_frame, col, bevel=0.025, outline=0.020)
    plane = K.add_uv_plane("Diag_CardPlane", 1.88, 2.30, (0.0, -0.04, 1.56), m_paper, col)
    if hasattr(plane, "visible_shadow"):
        plane.visible_shadow = False

    # Tactile miniature drafting desk accents in corners (never blocking the chart!)
    K.add_box("Diag_DeskFolderL", (0.75, 0.55, 0.08), (-1.45, 0.55, 0.04), m_red, col, bevel=0.015, rot_deg=(0.0, 0.0, 18.0), outline=0.014)
    K.add_cylinder("Diag_BrassWeight", 0.14, 0.16, (1.42, 0.48, 0.08), m_brass, col, outline=0.014)

    return {
        "col": col,
        "sky": ("#2C3A4E", "#526682", 0.85),
        "diagram_plane": plane,
        "diagram_frame": frame_box,
    }


# --------------------------------------------------------------------------- 6-9. WWI NAVAL DAZZLE SETS (Iteration 3)
def _build_dazzle_warship(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
    *,
    rot_z_deg: float = 0.0,
) -> bpy.types.Object:
    """Stylized 3D WWI warship wrapped in high-contrast angled geometric Dazzle zebra armor blocks."""
    root = _make_empty(f"{name}_Root", loc, col)
    root.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))
    root.scale = (scale, scale, scale)

    m_blk = K.make_toon_mat(f"{name}_DazzleBlk", "#181C24", emission_lift=0.06, roughness=0.65)
    m_wht = K.make_toon_mat(f"{name}_DazzleWht", "#EFEFE9", emission_lift=0.22, roughness=0.68)
    m_cyn = K.make_toon_mat(f"{name}_DazzleCyn", "#2AA2C8", emission_lift=0.22, roughness=0.65)
    m_cor = K.make_toon_mat(f"{name}_DazzleCor", "#D45E45", emission_lift=0.22, roughness=0.65)
    m_deck = K.make_pbr_mat(f"{name}_ShipDeck", "WoodPlanks", "#D0A676", uv_scale=3.5, emission_lift=0.14)
    m_redhull = K.make_toon_mat(f"{name}_LowerHull", "#822A22", emission_lift=0.14, roughness=0.72)

    parts: list[bpy.types.Object] = [
        K.add_box(f"{name}_Keel", (5.8, 1.30, 0.36), (0.0, 0.0, 0.16), m_redhull, col, bevel=0.08, outline=0.024),
        K.add_box(f"{name}_HullCore", (5.6, 1.24, 0.62), (0.0, 0.0, 0.56), m_wht, col, bevel=0.08, outline=0.026),
        K.add_box(f"{name}_BowProw", (1.2, 0.72, 0.72), (2.75, 0.0, 0.58), m_blk, col, bevel=0.08, rot_deg=(0.0, -14.0, 0.0), outline=0.024),
        K.add_box(f"{name}_WoodDeck", (5.2, 1.14, 0.06), (0.0, 0.0, 0.89), m_deck, col, bevel=0.01),
    ]

    # Stylized ship mast & crow's nest lookout
    parts.append(K.add_cylinder(f"{name}_MastMain", 0.048, 1.65, (0.25, 0.0, 2.05), m_blk, col, outline=0.014))
    parts.append(K.add_box(f"{name}_MastYard", (0.04, 0.72, 0.04), (0.25, 0.0, 2.48), m_blk, col, outline=0.010))

    # Geometric angled Dazzle zebra stripes along both port (+Y) and starboard (-Y) sides
    stripe_mats = (m_blk, m_cyn, m_blk, m_cor, m_wht, m_blk, m_cyn, m_blk)
    for si, sx in enumerate((-2.1, -1.5, -0.9, -0.3, 0.3, 0.9, 1.5, 2.0)):
        mat_s = stripe_mats[si % len(stripe_mats)]
        tilt = 22.0 if si % 2 == 0 else -24.0
        parts.append(
            K.add_box(f"{name}_Stripe{si}", (0.42, 1.32, 0.58), (sx, 0.0, 0.58), mat_s, col, bevel=0.02, rot_deg=(0.0, tilt, 0.0), outline=0.014)
        )

    # Bridge superstructure, twin dazzle funnels & gun turrets
    parts.append(K.add_box(f"{name}_Bridge", (1.35, 0.86, 0.72), (0.55, 0.0, 1.24), m_cyn, col, bevel=0.05, outline=0.022))
    parts.append(K.add_box(f"{name}_BridgeBand", (0.55, 0.92, 0.68), (0.65, 0.0, 1.24), m_blk, col, bevel=0.02, rot_deg=(0.0, 18.0, 0.0)))
    for fi, fx in enumerate((-0.45, -1.10)):
        parts.append(K.add_cylinder(f"{name}_Funnel{fi}", 0.22, 0.95, (fx, 0.0, 1.48), m_blk if fi == 0 else m_wht, col, rot_deg=(0.0, -8.0, 0.0), outline=0.020))
        parts.append(K.add_cylinder(f"{name}_FunnelCap{fi}", 0.24, 0.14, (fx - 0.06, 0.0, 1.92), m_cor if fi == 0 else m_blk, col))

    for ti, (tx, dir_x) in enumerate(((1.75, 1.0), (-1.95, -1.0))):
        parts.append(K.add_box(f"{name}_Turret{ti}", (0.56, 0.52, 0.30), (tx, 0.0, 1.06), m_wht if ti == 0 else m_blk, col, bevel=0.04, outline=0.018))
        parts.append(K.add_cylinder(f"{name}_Barrel{ti}", 0.055, 0.75, (tx + 0.45 * dir_x, 0.0, 1.10), m_blk, col, rot_deg=(0.0, 84.0 * dir_x, 0.0), outline=0.014))

    for p in parts:
        p.parent = root
    return root


def build_wwi_shipyard_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_sunlit_sky_rig(
        "ShipyardSun",
        col,
        sun_rot_deg=(48.0, 14.0, -30.0),
        sun_energy=2.3,
        sky_top="#2164C8",
        sky_horizon="#78BAF5",
        sky_strength=0.82,
        sun_disc_loc=(-5.5, -15.0, 9.0),
    )

    m_pier = K.make_pbr_mat("Dock_WoodPier", "WoodPlanks", "#C89864", uv_scale=4.5, emission_lift=0.14)
    m_stone = K.make_pbr_mat("Dock_BrickQuay", "Brick", "#D06C58", uv_scale=3.2, emission_lift=0.15)
    m_roof = K.make_pbr_mat("Dock_SlateRoof", "Slate", "#546272", uv_scale=3.0, emission_lift=0.12)
    m_win = K.make_toon_mat("Dock_GlassWin", "#243B4E", emission_lift=0.18, roughness=0.25)
    m_water = K.make_toon_mat("Dock_HarborSea", "#296998", emission_lift=0.16, roughness=0.22)
    m_crane = K.make_pbr_mat("Dock_CraneYellow", "Metal", "#F0B83C", uv_scale=2.5, emission_lift=0.16)
    m_scaf = K.make_pbr_mat("Dock_Scaffold", "Wood", "#986F46", uv_scale=3.0, emission_lift=0.12)
    m_crate = K.make_pbr_mat("Dock_CargoCrate", "WoodPlanks", "#D9AF76", uv_scale=2.5, emission_lift=0.14)

    K.add_box("Dock_SeaFloor", (28.0, 22.0, 0.4), (0.0, -5.0, -0.30), m_water, col)
    K.add_box("Dock_PierDeck", (24.0, 7.0, 0.6), (0.0, 2.2, -0.30), m_pier, col, bevel=0.03)
    K.add_box("Dock_BrickBuilding", (12.0, 3.2, 4.4), (-6.5, -6.5, 2.0), m_stone, col, bevel=0.04, outline=0.022)
    K.add_box("Dock_BrickRoof", (12.4, 3.5, 0.28), (-6.5, -6.5, 4.28), m_roof, col, bevel=0.02, outline=0.018)
    for wx in (-9.0, -6.4, -3.8):
        K.add_box(f"Dock_Win_{wx}", (1.15, 0.14, 1.15), (wx, -4.88, 2.65), m_win, col, bevel=0.02, outline=0.016)
    # Harbor bollards & cargo crates on wharf flanks
    for bx in (-2.9, 2.85):
        K.add_cylinder(f"Dock_Bollard_{bx}", 0.14, 0.42, (bx, -0.95, 0.21), m_roof, col, outline=0.016)
    K.add_box("Dock_CrateStack1", (0.72, 0.72, 0.56), (-2.65, 0.40, 0.28), m_crate, col, bevel=0.02, outline=0.016)
    K.add_box("Dock_CrateStack2", (0.58, 0.58, 0.48), (2.65, 0.35, 0.24), m_crate, col, bevel=0.02, outline=0.016)
    K.add_box("Dock_CranePost", (0.45, 0.45, 4.2), (3.8, -1.8, 2.0), m_crane, col, bevel=0.02, outline=0.018)
    K.add_box("Dock_CraneBoom", (3.6, 0.34, 0.34), (2.3, -1.8, 3.8), m_crane, col, bevel=0.02, rot_deg=(0.0, -14.0, 0.0), outline=0.018)

    # Scaffolding & open paint cans by the docked dazzle ship
    for sx in (-1.2, 1.2):
        K.add_box(f"Dock_Scaf{sx}", (0.14, 0.14, 1.9), (sx, -1.0, 0.95), m_scaf, col, outline=0.014)
    K.add_box("Dock_ScafPlank", (3.1, 0.36, 0.08), (0.0, -1.0, 1.32), m_pier, col, outline=0.014)

    for bx, b_hex in ((-1.9, "#2AA2C8"), (-1.45, "#EFEFE9"), (-1.0, "#D45E45"), (1.6, "#181C24")):
        K.add_cylinder(f"Dock_PaintCan_{bx}", 0.16, 0.30, (bx, 0.25, 0.15), K.make_toon_mat(f"Dock_Paint_{b_hex}", b_hex, 0.22), col, outline=0.014)

    ship = _build_dazzle_warship("Dock_DazzleShip", (0.0, -3.2, -0.05), 0.92, col, rot_z_deg=6.0)

    # Animated miniature painter crew along dock
    K.spawn_background_crew(
        "DockCrew",
        [
            (-2.35, -1.1, 0.0, -20.0, "#D9D2C4", "#2B4162", 0.56),
            (2.25, -1.0, 0.0, 22.0, "#384E68", "#D89E2B", 0.56),
            (-0.15, -1.05, 1.36, 175.0, "#D9D2C4", "#242834", 0.52),
        ],
        col,
        frame_end=frame_end,
    )

    return {
        "col": col,
        "sky": ("#2164C8", "#78BAF5", 0.82),
        "dazzle_ship": ship,
        "fg_framing": [
            K.add_foreground_framing_prop("Dock_FgRailingL", "railing", (-2.6, 2.9, 0.25), col, scale=0.85, rot_deg=(0.0, 0.0, 14.0)),
            K.add_foreground_framing_prop("Dock_FgRivetsR", "rivets", (2.8, 2.7, 1.35), col, scale=0.90, rot_deg=(0.0, 0.0, -10.0)),
        ],
    }


def build_wwi_ocean_dazzle_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_sunlit_sky_rig(
        "OceanSun",
        col,
        sun_rot_deg=(46.0, 16.0, -28.0),
        sun_energy=2.3,
        sky_top="#1E5EC2",
        sky_horizon="#7ABDF5",
        sky_strength=0.84,
        sun_disc_loc=(-5.2, -16.0, 8.8),
    )

    m_sea1 = K.make_toon_mat("Ocean_Blue1", "#256496", emission_lift=0.16, roughness=0.22)
    m_sea2 = K.make_toon_mat("Ocean_Blue2", "#2F78AD", emission_lift=0.18, roughness=0.20)
    m_foam = K.make_toon_mat("Ocean_Foam", "#EAF4FA", emission_lift=0.22, roughness=0.70)

    K.add_box("Ocean_Base", (36.0, 32.0, 0.6), (0.0, -4.0, -0.30), m_sea1, col)
    # Stylized low-poly ocean wave ridges
    for wi in range(-3, 4):
        K.add_box(f"Ocean_Wave{wi}", (32.0, 1.15, 0.24), (0.0, wi * 2.4 - 3.5, 0.04 if wi % 2 else -0.02), m_sea2, col, bevel=0.08, rot_deg=(8.0, 0.0, 0.0))

    ship = _build_dazzle_warship("Ocean_DazzleShip", (0.0, -4.2, -0.04), 0.95, col, rot_z_deg=12.0)
    wake = K.add_box("Ocean_FoamWake", (2.6, 0.48, 0.08), (-3.8, -4.4, 0.06), m_foam, col, bevel=0.04)
    wake.parent = ship

    # Pulsing 3D heading-angle confusion arrows (crimson right, gold angled left!)
    arr_r = K.add_3d_callout_arrow("Ocean_ArrowFalseBow", (2.8, -3.5, 1.4), (4.3, -2.5, 1.7), "#FF4B3E", col, frame_end=frame_end)
    arr_l = K.add_3d_callout_arrow("Ocean_ArrowTrueCourse", (-2.6, -3.5, 1.4), (-4.2, -4.9, 1.6), "#FFD447", col, frame_end=frame_end)

    return {
        "col": col,
        "sky": ("#1E5EC2", "#7ABDF5", 0.84),
        "dazzle_ship": ship,
        "callout_arrows": [arr_r, arr_l],
    }


def build_wwi_uboat_interior_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_cinematic_3point_rig(
        "SubRig",
        col,
        key_loc=(1.8, 3.6, 3.2),
        fill_loc=(-2.4, 3.8, 2.2),
        rim_loc=(0.0, -2.2, 2.8),
        key_color="#9EE0E8",
        fill_color="#FFCC80",
        rim_color="#FF7B58",
        key_energy=185.0,
        fill_energy=85.0,
        rim_energy=165.0,
    )

    m_hull = K.make_pbr_mat("Sub_HullSteel", "Metal", "#567A92", uv_scale=3.0, emission_lift=0.18)
    m_floor = K.make_pbr_mat("Sub_DeckPlate", "Slate", "#435564", uv_scale=3.5, emission_lift=0.14)
    m_brass = K.make_pbr_mat("Sub_Brass", "Metal", "#F0BE4A", uv_scale=2.0, emission_lift=0.22)
    m_chrome = K.make_pbr_mat("Sub_Chrome", "Metal", "#C6D6E4", uv_scale=2.0, emission_lift=0.22)
    m_pipe = K.make_toon_mat("Sub_CopperPipe", "#B8663C", emission_lift=0.18, roughness=0.40)
    m_dial = K.make_toon_mat("Sub_DialGlow", "#BCEAF2", emission_lift=0.60)

    K.add_box("Sub_Floor", (10.0, 8.0, 0.4), (0.0, 0.0, -0.20), m_floor, col)
    K.add_box("Sub_BackBulkhead", (10.0, 0.5, 5.4), (0.0, -2.6, 2.6), m_hull, col)
    # Overhead steel submarine pipework & red hatch wheel
    for pz in (2.55, 2.90):
        K.add_cylinder(f"Sub_Pipe_{pz}", 0.075, 8.5, (0.0, -2.28, pz), m_pipe, col, rot_deg=(0.0, 90.0, 0.0), outline=0.012)
    K.add_torus("Sub_ValveWheel", 0.30, 0.036, (-1.85, -2.24, 1.55), K.make_toon_mat("Sub_ValveRed", "#C84036", 0.20), col, rot_deg=(90.0, 0.0, 0.0), outline=0.014)
    K.add_box("Sub_Console", (1.6, 0.8, 1.15), (1.35, -1.65, 0.58), m_floor, col, bevel=0.04, outline=0.020)
    for gx in (0.95, 1.35, 1.75):
        K.add_cylinder(f"Sub_Gauge_{gx}", 0.15, 0.06, (gx, -1.24, 1.05), m_brass, col, rot_deg=(90.0, 0.0, 0.0), outline=0.012)
        K.add_cylinder(f"Sub_Dial_{gx}", 0.11, 0.07, (gx, -1.23, 1.05), m_dial, col, rot_deg=(90.0, 0.0, 0.0))

    # Central vertical steel periscope shaft & twin grip handles
    K.add_cylinder("Sub_PeriscopeCol", 0.14, 4.0, (-0.15, 0.45, 2.2), m_chrome, col, outline=0.020)
    K.add_box("Sub_PeriscopeHead", (0.58, 0.28, 0.28), (-0.15, 0.55, 1.85), m_brass, col, bevel=0.03, outline=0.018)
    K.add_box("Sub_Handles", (0.76, 0.08, 0.08), (-0.15, 0.65, 1.55), m_chrome, col, bevel=0.02, outline=0.014)
    K.add_warm_lantern("Sub_RedBeacon", (-2.1, -1.8, 2.65), col, color_hex="#FF5A44", energy=55.0, radius=0.16)

    return {
        "col": col,
        "sky": ("#162632", "#284052", 0.65),
    }


def build_wwi_periscope_view_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    K.add_sunlit_sky_rig(
        "ScopeSun",
        col,
        sun_rot_deg=(48.0, 14.0, -28.0),
        sun_energy=2.3,
        sky_top="#2164C8",
        sky_horizon="#78BAF5",
        sky_strength=0.82,
        sun_disc_loc=(-5.0, -16.0, 8.8),
    )

    m_sea = K.make_toon_mat("Scope_Sea", "#235B8C", emission_lift=0.16, roughness=0.22)
    m_wave = K.make_toon_mat("Scope_Wave", "#2D74A8", emission_lift=0.18, roughness=0.20)
    m_foam = K.make_toon_mat("Scope_Foam", "#F4FAFF", emission_lift=0.40, roughness=0.70)
    m_torp = K.make_toon_mat("Scope_TorpedoSteel", "#2C3540", emission_lift=0.10, roughness=0.35)
    m_brass = K.make_toon_mat("Scope_TorpedoNose", "#E4B238", emission_lift=0.22, roughness=0.32)
    m_ret = K.make_toon_mat("Scope_ReticleDark", "#121418", emission_lift=0.04, roughness=0.80)

    K.add_box("Scope_SeaFloor", (40.0, 36.0, 0.6), (0.0, -6.0, -0.30), m_sea, col)
    for wi in range(-3, 4):
        K.add_box(f"Scope_Wave{wi}", (36.0, 1.1, 0.22), (0.0, wi * 2.5 - 6.0, 0.03), m_wave, col, bevel=0.06, rot_deg=(6.0, 0.0, 0.0))

    ship = _build_dazzle_warship("Scope_DazzleShip", (-0.8, -8.5, -0.04), 0.90, col, rot_z_deg=14.0)

    # Torpedo + blazing white foam wake streaking wide past the bow!
    torp_root = _make_empty("Scope_TorpedoRoot", (0.0, -4.8, 0.08), col)
    t_parts = [
        K.add_cylinder("Scope_TorpedoBody", 0.14, 1.35, (0.0, 0.0, 0.0), m_torp, col, rot_deg=(0.0, 90.0, 0.0), outline=0.018),
        K.add_sphere("Scope_TorpedoHead", 0.145, (0.68, 0.0, 0.0), m_brass, col, outline=0.014),
        K.add_box("Scope_TorpedoWake1", (3.8, 0.28, 0.08), (-2.3, 0.0, -0.02), m_foam, col, bevel=0.03, outline=0.012),
        K.add_box("Scope_TorpedoWake2", (2.2, 0.42, 0.06), (-1.4, 0.0, -0.03), m_foam, col, bevel=0.02),
    ]
    for tp in t_parts:
        if hasattr(tp, "visible_shadow"):
            tp.visible_shadow = False
        tp.parent = torp_root

    # Subtle optical coincidence reticle crosshairs hovering cleanly in midground lens plane
    ret_root = _make_empty("Scope_Reticle", (0.0, 0.5, 1.48), col)
    r_parts = [
        K.add_torus("Scope_ReticleRing", 1.15, 0.028, (0.0, 0.0, 0.0), m_ret, col, rot_deg=(90.0, 0.0, 0.0)),
        K.add_box("Scope_CrossH", (2.2, 0.02, 0.022), (0.0, 0.0, 0.0), m_ret, col),
        K.add_box("Scope_CrossV", (0.022, 0.02, 2.2), (0.0, 0.0, 0.0), m_ret, col),
    ]
    for rp in r_parts:
        if hasattr(rp, "visible_shadow"):
            rp.visible_shadow = False
        rp.parent = ret_root

    return {
        "col": col,
        "sky": ("#2164C8", "#78BAF5", 0.82),
        "dazzle_ship": ship,
        "torpedo_root": torp_root,
        "periscope_reticle": ret_root,
    }


# --------------------------------------------------------------------------- 10-12. CARTOGRAPHY & PAPER TOWN SETS (Iteration 5)
def build_drafting_office_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """1930s sunlit cartographer studio with oak drafting table, road map layout, brass loupe & rolled map racks."""
    K.add_cinematic_3point_rig(
        "DraftingRig",
        col,
        key_loc=(1.6, 3.8, 4.2),
        fill_loc=(-2.8, 4.2, 2.6),
        rim_loc=(0.0, -2.2, 3.2),
        key_color="#FFF3DC",
        fill_color="#BFD8FA",
        rim_color="#FFE09C",
        key_energy=235.0,
        fill_energy=105.0,
        rim_energy=165.0,
    )

    m_floor = K.make_pbr_mat("Draft_FloorWood", "WoodPlanks", "#9B724E", uv_scale=4.0, emission_lift=0.14)
    m_wall = K.make_pbr_mat("Draft_WallBrick", "Brick", "#C8A682", uv_scale=3.2, emission_lift=0.18)
    m_wood = K.make_pbr_mat("Draft_OakTable", "Wood", "#7A5234", uv_scale=3.0, emission_lift=0.14)
    m_paper = K.make_toon_mat("Draft_MapPaper", "#F4EAD0", emission_lift=0.28, roughness=0.62)
    m_ink_blue = K.make_toon_mat("Draft_MapRiver", "#3878B4", emission_lift=0.20)
    m_ink_red = K.make_toon_mat("Draft_TrapPin", "#D83A2E", emission_lift=0.35)
    m_brass = K.make_toon_mat("Draft_Brass", "#E2B23E", emission_lift=0.24, roughness=0.30)
    m_green = K.make_toon_mat("Draft_BankerGreen", "#266844", emission_lift=0.26, roughness=0.35)

    K.add_box("Draft_Floor", (14.0, 12.0, 0.4), (0.0, 0.0, -0.20), m_floor, col)
    K.add_box("Draft_BackWall", (14.0, 0.5, 6.4), (0.0, -3.3, 3.1), m_wall, col)
    K.add_box("Draft_SideWallL", (0.5, 10.0, 6.4), (-4.8, 0.5, 3.1), m_wall, col)
    K.add_box("Draft_SideWallR", (0.5, 10.0, 6.4), (4.8, 0.5, 3.1), m_wall, col)

    # Framed reference map on back wall
    K.add_box("Draft_WallFrame", (3.6, 0.10, 2.2), (0.0, -3.02, 2.75), m_wood, col, bevel=0.02, outline=0.018)
    K.add_box("Draft_WallMap", (3.3, 0.06, 1.92), (0.0, -2.98, 2.75), m_paper, col)
    K.add_box("Draft_WallGrid1", (2.8, 0.04, 0.06), (0.0, -2.94, 2.85), m_ink_blue, col, rot_deg=(0.0, 12.0, 0.0))
    K.add_box("Draft_WallGrid2", (2.6, 0.04, 0.06), (0.0, -2.94, 2.60), m_ink_red, col, rot_deg=(0.0, -14.0, 0.0))

    # Central cartographer's drafting desk
    K.add_box("Draft_TableTop", (3.4, 2.0, 0.16), (0.0, -0.25, 1.02), m_wood, col, bevel=0.03, outline=0.022)
    for lx in (-1.45, 1.45):
        for ly in (-1.05, 0.55):
            K.add_cylinder(f"Draft_Leg_{lx}_{ly}", 0.09, 0.96, (lx, ly, 0.48), m_wood, col, outline=0.014)

    # Large parchment New York map spread across desk + ink roads + pulsing red copyright trap pin!
    K.add_box("Draft_DeskSheet", (2.65, 1.55, 0.04), (0.0, -0.25, 1.12), m_paper, col, bevel=0.01, outline=0.014)
    K.add_box("Draft_RoadA", (2.20, 0.06, 0.03), (0.0, -0.20, 1.145), m_ink_red, col, rot_deg=(0.0, 0.0, 16.0))
    K.add_box("Draft_RoadB", (0.06, 1.25, 0.03), (0.12, -0.25, 1.145), m_ink_red, col, rot_deg=(0.0, 0.0, -14.0))
    K.add_box("Draft_River", (2.35, 0.11, 0.025), (-0.10, -0.58, 1.14), m_ink_blue, col, rot_deg=(0.0, 0.0, -8.0))

    trap_pin = _make_empty("Draft_TrapPinRoot", (0.12, -0.22, 1.18), col)
    pin_shaft = K.add_cylinder("Draft_PinStem", 0.022, 0.24, (0.0, 0.0, 0.12), m_brass, col, outline=0.010)
    pin_head = K.add_sphere("Draft_PinHead", 0.095, (0.0, 0.0, 0.26), m_ink_red, col, outline=0.014)
    pin_shaft.parent = trap_pin
    pin_head.parent = trap_pin

    # Rolled map tubes bin on left + brass banker lamp on right
    K.add_cylinder("Draft_MapBin", 0.28, 0.72, (-2.2, -1.6, 0.36), m_wood, col, outline=0.016)
    for ti, (tx, ty, rot_x, col_hex) in enumerate(((-2.26, -1.58, 10.0, "#EFE2BF"), (-2.12, -1.62, -12.0, "#D8E4F0"), (-2.20, -1.52, 6.0, "#F6E8C8"))):
        K.add_cylinder(f"Draft_Tube{ti}", 0.06, 0.88, (tx, ty, 0.68), K.make_toon_mat(f"Draft_TubeM{ti}", col_hex, 0.18), col, rot_deg=(rot_x, 0.0, 0.0), outline=0.012)

    K.add_cylinder("Draft_LampBase", 0.18, 0.08, (1.28, -0.78, 1.14), m_brass, col, outline=0.012)
    K.add_cylinder("Draft_LampPost", 0.035, 0.44, (1.28, -0.78, 1.38), m_brass, col, outline=0.010)
    K.add_box("Draft_LampShade", (0.42, 0.22, 0.14), (1.18, -0.78, 1.60), m_green, col, bevel=0.02, rot_deg=(0.0, -14.0, 0.0), outline=0.014)
    K.add_warm_lantern("Draft_WarmLamp", (1.18, -0.78, 1.48), col, color_hex="#FFE2A4", energy=65.0, radius=0.14)

    return {
        "col": col,
        "sky": ("#2C221A", "#4E3C2D", 0.58),
        "trap_pin": trap_pin,
        "fg_framing": [
            K.add_foreground_framing_prop("Draft_FgEdgeL", "drafting_edge", (1.60, 2.35, 0.45), col, scale=0.72, rot_deg=(0.0, 0.0, 14.0)),
            K.add_foreground_framing_prop("Draft_FgRulerR", "railing", (-1.65, 2.45, 0.12), col, scale=0.68, rot_deg=(0.0, 0.0, -14.0)),
        ],
    }


def build_catskills_crossroads_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Sunlit Catskill Mountains dirt-road intersection with toggleable Agloe General Store & signpost."""
    K.add_sunlit_sky_rig(
        "CatskillsSun",
        col,
        sun_rot_deg=(48.0, 14.0, -32.0),
        sun_energy=2.35,
        sky_top="#2164C8",
        sky_horizon="#78BAF5",
        sky_strength=0.84,
        sun_disc_loc=(-5.5, -15.5, 9.2),
    )

    m_grass = K.make_pbr_mat("Cat_Grass", "LeafyGrass", "#8FD85A", uv_scale=6.0, roughness_bias=0.12, emission_lift=0.18)
    m_hill = K.make_pbr_mat("Cat_Hill", "Grass", "#70AE4C", uv_scale=5.0, roughness_bias=0.14, emission_lift=0.14)
    m_road = K.make_pbr_mat("Cat_DirtRoad", "Ground", "#DEB582", uv_scale=5.0, roughness_bias=0.18, emission_lift=0.16)
    m_wood = K.make_pbr_mat("Cat_Wood", "Wood", "#B27E4E", uv_scale=3.5, emission_lift=0.14)
    m_trunk = K.make_toon_mat("Cat_Trunk", "#5C3D26", emission_lift=0.10, roughness=0.88)
    m_pine = K.make_toon_mat("Cat_Pine", "#2E6A36", emission_lift=0.16, roughness=0.82)
    m_plank = K.make_pbr_mat("Cat_StoreWood", "WoodPlanks", "#D9B98C", uv_scale=3.5, emission_lift=0.16)
    m_roof = K.make_pbr_mat("Cat_RoofSlate", "Slate", "#4C5C6E", uv_scale=3.0, emission_lift=0.12)
    m_red = K.make_toon_mat("Cat_SignRed", "#C6382E", emission_lift=0.22, roughness=0.60)
    m_cream = K.make_toon_mat("Cat_AwningCream", "#F6EFE0", emission_lift=0.22, roughness=0.72)

    # Rolling Catskill valley + crossed dirt roads
    K.add_box("Cat_Floor", (28.0, 28.0, 0.8), (0.0, -2.0, -0.40), m_grass, col)
    K.add_box("Cat_RoadNS", (2.6, 26.0, 0.06), (0.0, -2.0, 0.02), m_road, col, bevel=0.02, rot_deg=(0.0, 0.0, 8.0))
    K.add_box("Cat_RoadEW", (26.0, 2.4, 0.06), (0.0, -1.6, 0.022), m_road, col, bevel=0.02, rot_deg=(0.0, 0.0, -10.0))

    for i, (hx, hy, sx, sy, sz) in enumerate((
        (-6.8, -10.5, 9.2, 4.8, 2.6),
        (6.8, -11.0, 9.4, 4.9, 2.8),
        (0.0, -15.0, 20.0, 5.8, 3.6),
    )):
        K.add_sphere(f"Cat_Hill{i}", 1.0, (hx, hy, -0.35), m_hill, col, segments=14, rings=8, scale=(sx, sy, sz))

    # Pine woodland framing the intersection
    for idx, (tx, ty, ts) in enumerate((
        (-5.2, -4.6, 1.3), (-6.4, -0.8, 1.1), (-4.0, -7.8, 1.4),
        (5.4, -4.2, 1.3), (6.5, -7.4, 1.2), (4.6, 0.8, 1.05),
    )):
        _build_pine_tree(f"Cat_Tree{idx}", (tx, ty, 0.0), ts, col, m_trunk, m_pine)

    # Split-rail country fence along far road edges
    for side_x in (-3.8, 3.8):
        for py in (-6.5, -4.0):
            K.add_box(f"Cat_FPost_{side_x}_{py}", (0.14, 0.14, 1.05), (side_x, py, 0.52), m_wood, col, outline=0.014)
        K.add_box(f"Cat_FRail_{side_x}", (0.08, 3.2, 0.10), (side_x, -5.25, 0.72), m_wood, col, outline=0.012)

    # Roadside intersection signpost (toggleable via show_sign)
    sign_root = _make_empty("Cat_SignRoot", (-1.55, -0.35, 0.0), col)
    s_parts = [
        K.add_cylinder("Cat_SignPost", 0.075, 2.15, (0.0, 0.0, 1.07), m_wood, col, outline=0.015),
        K.add_box("Cat_SignBlade1", (1.15, 0.07, 0.24), (0.35, 0.0, 1.95), m_cream, col, bevel=0.015, rot_deg=(0.0, 0.0, -10.0), outline=0.014),
        K.add_box("Cat_SignBlade2", (0.95, 0.07, 0.22), (-0.25, 0.0, 1.66), m_red, col, bevel=0.015, rot_deg=(0.0, 0.0, 14.0), outline=0.014),
    ]
    for sp in s_parts:
        sp.parent = sign_root

    # Toggleable "Agloe General Store" clapboard cabin (hidden when intersection is empty, visible in Act 2 payoff!)
    store_root = _make_empty("Cat_AgloeStoreRoot", (0.4, -4.8, 0.0), col)
    st_parts = [
        K.add_box("Cat_StoreBody", (3.8, 2.6, 2.35), (0.0, 0.0, 1.18), m_plank, col, bevel=0.04, outline=0.024),
        K.add_box("Cat_StoreFalseFront", (3.9, 0.24, 0.95), (0.0, 1.22, 2.75), m_plank, col, bevel=0.03, outline=0.022),
        K.add_box("Cat_StoreSignBand", (3.3, 0.10, 0.56), (0.0, 1.36, 2.78), m_red, col, bevel=0.02, outline=0.016),
        K.add_box("Cat_StoreRoof", (4.1, 2.9, 0.22), (0.0, -0.05, 2.42), m_roof, col, bevel=0.02, outline=0.018),
        K.add_box("Cat_StorePorch", (3.9, 1.1, 0.18), (0.0, 1.80, 0.09), m_wood, col, bevel=0.02, outline=0.016),
        K.add_box("Cat_StoreDoor", (0.85, 0.10, 1.65), (0.0, 1.30, 0.95), m_wood, col, bevel=0.02, outline=0.016),
        K.add_box("Cat_StoreAwning", (3.7, 0.95, 0.08), (0.0, 1.72, 1.98), m_red, col, bevel=0.02, rot_deg=(18.0, 0.0, 0.0), outline=0.016),
    ]
    for wx in (-1.15, 1.15):
        st_parts.append(K.add_box(f"Cat_StoreWin_{wx}", (0.78, 0.10, 0.85), (wx, 1.30, 1.25), K.make_toon_mat(f"Cat_WinGlow_{wx}", "#FFE8A6", 0.55), col, bevel=0.02, outline=0.016))
        st_parts.append(K.add_cylinder(f"Cat_PorchPost_{wx}", 0.065, 1.90, (wx * 1.35, 2.22, 1.04), m_cream, col, outline=0.014))
    for stp in st_parts:
        stp.parent = store_root

    # Drift clouds in sunlit Catskills sky
    m_cloud = K.make_toon_mat("Cat_Cloud", "#EEF4FC", emission_lift=0.20, roughness=0.95)
    for ci, (cx, cy, cz) in enumerate(((-4.0, -14.0, 6.4), (3.6, -15.0, 7.2), (0.2, -16.0, 8.2))):
        cl = K.add_sphere(f"Cat_Cloud{ci}", 1.15, (cx, cy, cz), m_cloud, col, segments=12, rings=8, scale=(2.2, 0.9, 0.65))
        if hasattr(cl, "visible_shadow"):
            cl.visible_shadow = False

    return {
        "col": col,
        "sky": ("#2164C8", "#78BAF5", 0.84),
        "store_building": store_root,
        "crossroads_sign": sign_root,
        "fg_framing": [
            K.add_foreground_framing_prop("Cat_FgBranchL", "branches", (1.45, 2.85, 2.75), col, scale=0.85, rot_deg=(0.0, 0.0, 12.0)),
            K.add_foreground_framing_prop("Cat_FgFenceR", "fence_corner", (-1.55, 2.75, 0.28), col, scale=0.75, rot_deg=(0.0, 0.0, -18.0)),
        ],
    }


def build_courtroom_office_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Rival publisher / legal boardroom with mahogany table, stacked atlas volumes, and framed evidence map."""
    K.add_cinematic_3point_rig(
        "CourtRig",
        col,
        key_loc=(-1.5, 3.8, 4.2),
        fill_loc=(2.8, 4.0, 2.5),
        rim_loc=(0.0, -2.2, 3.2),
        key_color="#FFF5E4",
        fill_color="#B8D4FA",
        rim_color="#FFE4A8",
        key_energy=230.0,
        fill_energy=100.0,
        rim_energy=160.0,
    )

    m_floor = K.make_pbr_mat("Court_Floor", "WoodPlanks", "#7D563B", uv_scale=4.0, emission_lift=0.14)
    m_wall = K.make_pbr_mat("Court_WallSlate", "Slate", "#5A6B7E", uv_scale=3.0, emission_lift=0.18)
    m_mahog = K.make_pbr_mat("Court_Mahogany", "Wood", "#5E3222", uv_scale=3.0, emission_lift=0.14)
    m_paper = K.make_toon_mat("Court_Paper", "#F4EAD2", emission_lift=0.25)
    m_red = K.make_toon_mat("Court_FolderRed", "#B8342A", emission_lift=0.22)
    m_brass = K.make_toon_mat("Court_Brass", "#DEAE3A", emission_lift=0.22)

    K.add_box("Court_Floor", (14.0, 12.0, 0.4), (0.0, 0.0, -0.20), m_floor, col)
    K.add_box("Court_BackWall", (14.0, 0.5, 6.4), (0.0, -3.3, 3.1), m_wall, col)
    K.add_box("Court_SideL", (0.5, 10.0, 6.4), (-4.8, 0.5, 3.1), m_wall, col)
    K.add_box("Court_SideR", (0.5, 10.0, 6.4), (4.8, 0.5, 3.1), m_wall, col)

    # Central legal conference desk
    K.add_box("Court_DeskTop", (3.6, 2.0, 0.18), (0.0, -0.25, 1.02), m_mahog, col, bevel=0.03, outline=0.022)
    for lx in (-1.55, 1.55):
        for ly in (-1.05, 0.55):
            K.add_cylinder(f"Court_Leg_{lx}_{ly}", 0.10, 0.96, (lx, ly, 0.48), m_mahog, col, outline=0.015)

    # Twin competing unfolded road maps on desk + painted highway lines + gavel/folders
    m_blue = K.make_toon_mat("Court_MapBlue", "#3878B4", emission_lift=0.20)
    K.add_box("Court_EssoMap", (1.25, 0.95, 0.03), (-0.78, -0.20, 1.13), m_paper, col, rot_deg=(0.0, 0.0, 8.0), outline=0.014)
    K.add_box("Court_EssoRd1", (1.05, 0.045, 0.02), (-0.78, -0.18, 1.15), m_red, col, rot_deg=(0.0, 0.0, 22.0))
    K.add_box("Court_EssoRd2", (0.045, 0.78, 0.02), (-0.74, -0.20, 1.15), m_blue, col, rot_deg=(0.0, 0.0, -10.0))

    K.add_box("Court_RivalMap", (1.25, 0.95, 0.03), (0.78, -0.20, 1.13), m_paper, col, rot_deg=(0.0, 0.0, -7.0), outline=0.014)
    K.add_box("Court_RivalRd1", (1.05, 0.045, 0.02), (0.78, -0.18, 1.15), m_red, col, rot_deg=(0.0, 0.0, 8.0))
    K.add_box("Court_RivalRd2", (0.045, 0.78, 0.02), (0.82, -0.20, 1.15), m_blue, col, rot_deg=(0.0, 0.0, -24.0))

    K.add_box("Court_LawFolder", (0.52, 0.68, 0.07), (0.0, -0.55, 1.15), m_red, col, bevel=0.015, outline=0.014)
    K.add_cylinder("Court_Gavel", 0.06, 0.22, (0.0, -0.05, 1.18), m_brass, col, rot_deg=(0.0, 90.0, 20.0), outline=0.012)

    # Framed state map + law books shelf on back wall
    K.add_box("Court_WallBoard", (3.8, 0.12, 2.2), (0.0, -3.02, 2.80), m_mahog, col, bevel=0.02, outline=0.018)
    K.add_box("Court_WallSheet", (3.4, 0.06, 1.88), (0.0, -2.97, 2.80), m_paper, col)
    K.add_box("Court_WallLine1", (2.8, 0.04, 0.06), (0.0, -2.93, 2.90), m_blue, col, rot_deg=(0.0, 10.0, 0.0))
    K.add_box("Court_WallLine2", (2.5, 0.04, 0.06), (0.0, -2.93, 2.68), m_red, col, rot_deg=(0.0, -14.0, 0.0))
    K.add_warm_lantern("Court_CeilingLamp", (0.0, -0.25, 3.60), col, color_hex="#FFF0CC", energy=115.0, radius=0.18)

    return {
        "col": col,
        "sky": ("#1E2634", "#3B4A62", 0.60),
        "fg_framing": [
            K.add_foreground_framing_prop("Court_FgRailingL", "railing", (1.60, 2.55, 0.12), col, scale=0.70, rot_deg=(0.0, 0.0, 16.0)),
            K.add_foreground_framing_prop("Court_FgRivetsR", "rivets", (-1.92, 2.45, 1.25), col, scale=0.72, rot_deg=(0.0, 0.0, -10.0)),
        ],
    }


# --------------------------------------------------------------------------- 13-15. WWII CONCRETE CARGO SHIPS (Iteration 6)
def _build_concrete_cargo_ship(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
    *,
    rot_z_deg: float = 0.0,
    with_rebar_cage: bool = False,
) -> dict[str, bpy.types.Object]:
    """Stylized WWII C1-S-D1 concrete Liberty cargo ship with grey concrete hull, cargo hatches, wheelhouse & optional rebar/formwork."""
    root = _make_empty(f"{name}_Root", loc, col)
    root.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))
    root.scale = (scale, scale, scale)

    m_conc = K.make_pbr_mat(f"{name}_HullConcrete", "Concrete", "#A8ACA8", uv_scale=3.8, emission_lift=0.18)
    m_keel = K.make_toon_mat(f"{name}_Waterline", "#2A3038", emission_lift=0.08, roughness=0.72)
    m_deck = K.make_pbr_mat(f"{name}_DeckConcrete", "Concrete", "#8C9296", uv_scale=4.0, emission_lift=0.14)
    m_bridge = K.make_toon_mat(f"{name}_BridgeHouse", "#DCDAD2", emission_lift=0.20, roughness=0.68)
    m_funnel = K.make_toon_mat(f"{name}_Funnel", "#323A44", emission_lift=0.10, roughness=0.55)
    m_rust = K.make_toon_mat(f"{name}_RebarRust", "#7B442A", emission_lift=0.12, roughness=0.60)
    m_crate = K.make_pbr_mat(f"{name}_CargoCrate", "WoodPlanks", "#D9AC72", uv_scale=2.5, emission_lift=0.14)
    m_form = K.make_pbr_mat(f"{name}_FormWood", "WoodPlanks", "#BA8C58", uv_scale=3.2, emission_lift=0.14)

    parts: list[bpy.types.Object] = [
        K.add_box(f"{name}_Keel", (5.9, 1.38, 0.34), (0.0, 0.0, 0.16), m_keel, col, bevel=0.08, outline=0.024),
        K.add_box(f"{name}_Hull", (5.7, 1.32, 0.68), (0.0, 0.0, 0.60), m_conc, col, bevel=0.08, outline=0.026),
        K.add_box(f"{name}_Bow", (1.25, 0.78, 0.76), (2.78, 0.0, 0.62), m_conc, col, bevel=0.08, rot_deg=(0.0, -14.0, 0.0), outline=0.024),
        K.add_box(f"{name}_Deck", (5.3, 1.22, 0.07), (0.0, 0.0, 0.96), m_deck, col, bevel=0.01),
        # Central Liberty-style superstructure, wheelhouse, mast & funnel
        K.add_box(f"{name}_Bridge", (1.25, 0.96, 0.72), (-0.15, 0.0, 1.32), m_bridge, col, bevel=0.04, outline=0.022),
        K.add_box(f"{name}_Wheelhouse", (0.72, 0.82, 0.42), (0.05, 0.0, 1.82), m_bridge, col, bevel=0.03, outline=0.018),
        K.add_cylinder(f"{name}_Funnel", 0.22, 0.85, (-0.52, 0.0, 1.72), m_funnel, col, rot_deg=(0.0, -6.0, 0.0), outline=0.020),
        K.add_cylinder(f"{name}_FunnelBand", 0.23, 0.14, (-0.54, 0.0, 1.98), m_rust, col),
        K.add_cylinder(f"{name}_ForeMast", 0.045, 1.55, (1.45, 0.0, 1.72), m_funnel, col, outline=0.014),
        K.add_box(f"{name}_ForeYard", (0.04, 0.68, 0.04), (1.45, 0.0, 2.20), m_funnel, col, outline=0.010),
        # Cargo hatches & stacked wooden supply crates
        K.add_box(f"{name}_HatchF", (0.95, 0.72, 0.22), (1.35, 0.0, 1.08), m_keel, col, bevel=0.02, outline=0.016),
        K.add_box(f"{name}_HatchA", (0.95, 0.72, 0.22), (-1.65, 0.0, 1.08), m_keel, col, bevel=0.02, outline=0.016),
        K.add_box(f"{name}_Crate1", (0.48, 0.46, 0.36), (1.35, 0.12, 1.36), m_crate, col, bevel=0.02, rot_deg=(0.0, 0.0, 8.0), outline=0.014),
        K.add_box(f"{name}_Crate2", (0.44, 0.42, 0.32), (-1.60, -0.10, 1.34), m_crate, col, bevel=0.02, rot_deg=(0.0, 0.0, -10.0), outline=0.014),
    ]
    for p in parts:
        p.parent = root

    form_root = _make_empty(f"{name}_FormworkRoot", (0.0, 0.0, 0.0), col)
    form_root.parent = root
    if with_rebar_cage:
        f_parts: list[bpy.types.Object] = []
        # Wooden timber mold ribs + exposed steel rebar mesh along sides
        for sx in (-2.0, -1.0, 0.0, 1.0, 2.0):
            for sy in (-0.76, 0.76):
                f_parts.append(K.add_box(f"{name}_FormRib_{sx}_{sy}", (0.14, 0.10, 0.92), (sx, sy, 0.56), m_form, col, bevel=0.01, outline=0.012))
        for rz in (0.35, 0.62, 0.88):
            f_parts.append(K.add_box(f"{name}_RebarLongF_{rz}", (4.6, 0.04, 0.04), (0.0, 0.72, rz), m_rust, col))
            f_parts.append(K.add_box(f"{name}_RebarLongB_{rz}", (4.6, 0.04, 0.04), (0.0, -0.72, rz), m_rust, col))
        for fp in f_parts:
            fp.parent = form_root

    return {"root": root, "formwork": form_root}


def build_concrete_drydock_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Sunlit WWII Tampa / Hookers Point graving basin where steel rebar + lightweight concrete hulls are poured."""
    K.add_sunlit_sky_rig(
        "ConcreteDockSun",
        col,
        sun_rot_deg=(48.0, 14.0, -30.0),
        sun_energy=2.35,
        sky_top="#2164C8",
        sky_horizon="#7AC0F6",
        sky_strength=0.84,
        sun_disc_loc=(-5.5, -15.5, 9.2),
    )

    m_quay = K.make_pbr_mat("CDock_QuayConc", "Concrete", "#C4BFA8", uv_scale=4.5, emission_lift=0.16)
    m_pier = K.make_pbr_mat("CDock_PierWood", "WoodPlanks", "#C29462", uv_scale=4.2, emission_lift=0.14)
    m_water = K.make_toon_mat("CDock_BasinWater", "#2A6B98", emission_lift=0.16, roughness=0.22)
    m_crane = K.make_pbr_mat("CDock_CraneYellow", "Metal", "#EEB63A", uv_scale=2.5, emission_lift=0.16)
    m_silo = K.make_pbr_mat("CDock_CementSilo", "Concrete", "#B4B6B2", uv_scale=2.8, emission_lift=0.16)
    m_rebar = K.make_toon_mat("CDock_RebarBundle", "#764228", emission_lift=0.10, roughness=0.55)
    m_sack = K.make_toon_mat("CDock_CementBag", "#EAE2CE", emission_lift=0.20, roughness=0.80)

    K.add_box("CDock_SeaFloor", (30.0, 24.0, 0.4), (0.0, -5.2, -0.30), m_water, col)
    K.add_box("CDock_BasinDeck", (24.0, 7.5, 0.6), (0.0, 2.2, -0.30), m_quay, col, bevel=0.03)
    K.add_box("CDock_TimberEdge", (24.0, 0.45, 0.20), (0.0, -1.45, 0.04), m_pier, col, bevel=0.02, outline=0.016)

    # Cement batching silo & pouring gantry crane on right
    K.add_cylinder("CDock_CementSilo", 0.95, 3.6, (-4.8, -5.0, 1.8), m_silo, col, outline=0.022)
    K.add_cone("CDock_SiloRoof", 1.05, 0.08, 0.85, (-4.8, -5.0, 4.02), m_crane, col, outline=0.018)
    K.add_box("CDock_CranePost", (0.46, 0.46, 4.4), (3.8, -2.0, 2.1), m_crane, col, bevel=0.02, outline=0.018)
    K.add_box("CDock_CraneBoom", (3.8, 0.34, 0.34), (2.2, -2.0, 4.0), m_crane, col, bevel=0.02, rot_deg=(0.0, -14.0, 0.0), outline=0.018)

    # Stacked cement sacks & steel rebar rods on the pier foreground flanks
    for bi, (bx, by, bz) in enumerate(((-2.5, 0.25, 0.14), (-2.1, 0.30, 0.14), (-2.3, 0.28, 0.38))):
        K.add_box(f"CDock_Sack{bi}", (0.44, 0.32, 0.22), (bx, by, bz), m_sack, col, bevel=0.04, rot_deg=(0.0, 0.0, 10.0 * bi), outline=0.014)
    for ri in range(3):
        K.add_cylinder(f"CDock_RebarRod{ri}", 0.032, 1.8, (2.55 + ri * 0.09, 0.25, 0.08), m_rebar, col, rot_deg=(90.0, 0.0, 12.0), outline=0.010)

    ship_meta = _build_concrete_cargo_ship("CDock_ConcreteShip", (0.0, -3.5, -0.05), 0.94, col, rot_z_deg=6.0, with_rebar_cage=True)

    K.spawn_background_crew(
        "CDockCrew",
        [
            (-2.65, -0.95, 0.0, -18.0, "#D9D2C4", "#E8B838", 0.56),
            (2.35, -0.95, 0.0, 22.0, "#2B5B84", "#E8B838", 0.56),
        ],
        col,
        frame_end=frame_end,
    )

    return {
        "col": col,
        "sky": ("#2164C8", "#7AC0F6", 0.84),
        "concrete_ship": ship_meta["root"],
        "concrete_formwork": ship_meta["formwork"],
        "fg_framing": [
            K.add_foreground_framing_prop("CDock_FgRailingL", "railing", (-2.6, 2.9, 0.25), col, scale=0.85, rot_deg=(0.0, 0.0, 14.0)),
            K.add_foreground_framing_prop("CDock_FgRivetsR", "rivets", (2.8, 2.7, 1.35), col, scale=0.90, rot_deg=(0.0, 0.0, -10.0)),
        ],
    }


def build_concrete_ocean_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Sunlit Pacific / Atlantic ocean with floating concrete Liberty ship, foam wake & Archimedes buoyancy callouts."""
    K.add_sunlit_sky_rig(
        "ConcOceanSun",
        col,
        sun_rot_deg=(46.0, 16.0, -28.0),
        sun_energy=2.35,
        sky_top="#1E5EC2",
        sky_horizon="#7ABDF5",
        sky_strength=0.84,
        sun_disc_loc=(-5.2, -16.0, 8.8),
    )

    m_sea1 = K.make_toon_mat("COcean_Blue1", "#256496", emission_lift=0.16, roughness=0.22)
    m_sea2 = K.make_toon_mat("COcean_Blue2", "#2F78AD", emission_lift=0.18, roughness=0.20)
    m_foam = K.make_toon_mat("COcean_Foam", "#F0F8FE", emission_lift=0.24, roughness=0.70)

    K.add_box("COcean_Base", (36.0, 32.0, 0.6), (0.0, -4.0, -0.34), m_sea1, col)
    for wi in range(-4, 2):
        K.add_box(f"COcean_Wave{wi}", (32.0, 1.15, 0.22), (0.0, wi * 2.4 - 4.0, 0.02 if wi % 2 else -0.04), m_sea2, col, bevel=0.08, rot_deg=(8.0, 0.0, 0.0))

    ship_meta = _build_concrete_cargo_ship("COcean_ConcreteShip", (0.0, -4.2, -0.02), 0.96, col, rot_z_deg=10.0, with_rebar_cage=False)
    wake = K.add_box("COcean_FoamWake", (2.8, 0.50, 0.08), (-3.8, -4.4, 0.06), m_foam, col, bevel=0.04)
    wake.parent = ship_meta["root"]

    # Toggleable foreground wooden harbor pier for ocean character shots
    m_pier = K.make_pbr_mat("COcean_PierWood", "WoodPlanks", "#C29462", uv_scale=4.2, emission_lift=0.14)
    pier_root = _make_empty("COcean_PierRoot", (0.0, 0.0, 0.0), col)
    p_deck = K.add_box("COcean_PierDeck", (20.0, 4.2, 0.55), (0.0, 1.9, -0.24), m_pier, col, bevel=0.03)
    p_trim = K.add_box("COcean_PierEdge", (20.0, 0.35, 0.16), (0.0, -0.20, 0.06), m_pier, col, bevel=0.02, outline=0.016)
    p_bol1 = K.add_cylinder("COcean_BollardL", 0.13, 0.38, (-2.6, -0.05, 0.21), m_sea1, col, outline=0.014)
    p_bol2 = K.add_cylinder("COcean_BollardR", 0.13, 0.38, (2.6, -0.05, 0.21), m_sea1, col, outline=0.014)
    for pp in (p_deck, p_trim, p_bol1, p_bol2):
        pp.parent = pier_root

    # Pulsing 3D Archimedes upward buoyancy vs weight arrows
    arr_up = K.add_3d_callout_arrow("COcean_BuoyancyUp", (-0.45, -3.2, 0.25), (-0.45, -3.2, 1.85), "#3AE080", col, frame_end=frame_end)
    arr_dn = K.add_3d_callout_arrow("COcean_GravityDown", (1.25, -3.2, 1.85), (1.25, -3.2, 0.30), "#FF5B4A", col, frame_end=frame_end)

    return {
        "col": col,
        "sky": ("#1E5EC2", "#7ABDF5", 0.84),
        "concrete_ship": ship_meta["root"],
        "ocean_pier": pier_root,
        "callout_arrows": [arr_up, arr_dn],
    }


def build_concrete_breakwater_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Post-war coastal harbor breakwater formed by sunken WWII concrete hulls blocking ocean swells."""
    K.add_sunlit_sky_rig(
        "BreakwaterSun",
        col,
        sun_rot_deg=(42.0, 18.0, -34.0),
        sun_energy=2.25,
        sky_top="#2462BA",
        sky_horizon="#9AD0F5",
        sky_strength=0.84,
        sun_disc_loc=(-5.0, -16.0, 8.5),
    )

    m_sea = K.make_toon_mat("CBreak_Sea", "#235E8E", emission_lift=0.16, roughness=0.22)
    m_foam = K.make_toon_mat("CBreak_Foam", "#F4FAFF", emission_lift=0.28, roughness=0.70)
    m_sand = K.make_pbr_mat("CBreak_BeachSand", "Ground", "#DFC698", uv_scale=5.0, emission_lift=0.16)

    K.add_box("CBreak_SeaFloor", (40.0, 34.0, 0.6), (0.0, -5.0, -0.30), m_sea, col)
    K.add_box("CBreak_Shore", (36.0, 6.0, 0.45), (0.0, 2.8, -0.08), m_sand, col, bevel=0.05)

    # Line of 3 iconic concrete hulls settled nose-to-stern as an offshore breakwater
    hulls: list[bpy.types.Object] = []
    for hi, (hx, hy, hz, r_z) in enumerate(((-4.2, -5.2, -0.24, 16.0), (0.2, -4.8, -0.22, 8.0), (4.6, -5.4, -0.26, 12.0))):
        sm = _build_concrete_cargo_ship(f"CBreak_Hulk{hi}", (hx, hy, hz), 0.78, col, rot_z_deg=r_z, with_rebar_cage=False)
        hulls.append(sm["root"])
        K.add_box(f"CBreak_Foam{hi}", (4.4, 0.35, 0.08), (hx, hy + 0.85, 0.05), m_foam, col, bevel=0.03, rot_deg=(0.0, 0.0, r_z))

    return {
        "col": col,
        "sky": ("#2462BA", "#9AD0F5", 0.84),
        "concrete_ship": hulls[1],
        "fg_framing": [
            K.add_foreground_framing_prop("CBreak_FgRailing", "railing", (-1.8, 2.5, 0.25), col, scale=0.80, rot_deg=(0.0, 0.0, 14.0)),
        ],
    }


def _build_giant_claw(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
) -> dict:
    """Articulated multi-piece mechanical capture claw ('Clementine') with hinged left/right jaws."""
    root = _make_empty(name, loc, col)
    root.scale = (scale, scale, scale)

    m_steel = K.make_pbr_mat(f"{name}_Steel", "Metal", "#4A5868", uv_scale=2.2, emission_lift=0.16)
    m_yellow = K.make_pbr_mat(f"{name}_HazardYel", "Metal", "#E8B030", uv_scale=2.2, emission_lift=0.20)
    m_dark = K.make_toon_mat(f"{name}_DarkMech", "#222832", emission_lift=0.10, roughness=0.45)

    pipe = K.add_cylinder(f"{name}_DrillPipe", 0.14, 5.2, (0.0, 0.0, 2.9), m_steel, col, vertices=14, outline=0.018)
    head = K.add_box(f"{name}_Crosshead", (1.65, 0.90, 0.48), (0.0, 0.0, 0.35), m_yellow, col, bevel=0.03, outline=0.020)
    hub = K.add_cylinder(f"{name}_CenterHub", 0.34, 0.72, (0.0, 0.0, 0.15), m_dark, col, vertices=14, rot_deg=(90.0, 0.0, 0.0), outline=0.016)
    for part in (pipe, head, hub):
        part.parent = root

    jaws: list[bpy.types.Object] = []
    for side_lbl, sx in (("L", -1.0), ("R", 1.0)):
        pivot = _make_empty(f"{name}_JawPivot{side_lbl}", (sx * 0.62, 0.0, 0.15), col)
        pivot.parent = root
        arm = K.add_box(f"{name}_Arm{side_lbl}", (0.24, 0.56, 1.15), (sx * 0.20, 0.0, -0.52), m_yellow, col, bevel=0.02, rot_deg=(0.0, sx * 14.0, 0.0), outline=0.018)
        tip = K.add_box(f"{name}_Tip{side_lbl}", (0.48, 0.52, 0.22), (sx * 0.02, 0.0, -1.04), m_steel, col, bevel=0.02, rot_deg=(0.0, sx * -22.0, 0.0), outline=0.016)
        for p in (arm, tip):
            p.parent = pivot
        jaws.append(pivot)

    return {"root": root, "jaw_l": jaws[0], "jaw_r": jaws[1]}


def _build_soviet_sub(
    name: str,
    loc: tuple[float, float, float],
    scale: float,
    col: bpy.types.Collection,
    *,
    rot_z_deg: float = 8.0,
) -> dict:
    """Two-piece Soviet Golf-II ballistic submarine K-129 (bow + separable aft section)."""
    root = _make_empty(name, loc, col)
    root.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))
    root.scale = (scale, scale, scale)

    m_hull = K.make_pbr_mat(f"{name}_SubHull", "Metal", "#28313D", uv_scale=2.5, emission_lift=0.14)
    m_rust = K.make_toon_mat(f"{name}_SubRust", "#6E4234", emission_lift=0.12, roughness=0.72)
    m_star = K.make_toon_mat(f"{name}_RedStar", "#D6362E", emission_lift=0.28, roughness=0.45)

    bow = _make_empty(f"{name}_Bow", (0.0, 0.0, 0.0), col)
    aft = _make_empty(f"{name}_Aft", (0.0, 0.0, 0.0), col)
    bow.parent = root
    aft.parent = root

    # Bow + sail conning tower (front half recovered)
    bow_cyl = K.add_cylinder(f"{name}_BowCyl", 0.52, 2.8, (0.95, 0.0, 0.0), m_hull, col, vertices=18, rot_deg=(0.0, 90.0, 0.0), outline=0.020)
    bow_nose = K.add_sphere(f"{name}_BowNose", 0.52, (2.35, 0.0, 0.0), m_hull, col, segments=16, rings=10, scale=(1.35, 0.96, 0.96), outline=0.020)
    sail = K.add_box(f"{name}_Sail", (1.05, 0.34, 0.72), (0.65, 0.0, 0.72), m_hull, col, bevel=0.04, outline=0.018)
    dive_planes = K.add_box(f"{name}_DivePlanes", (0.36, 1.15, 0.08), (0.72, 0.0, 0.76), m_hull, col, bevel=0.02, outline=0.014)
    mast = K.add_cylinder(f"{name}_Periscope", 0.045, 0.65, (0.82, 0.0, 1.32), m_rust, col, vertices=10, outline=0.012)
    star = K.add_box(f"{name}_SailStar", (0.24, 0.37, 0.24), (0.68, 0.0, 0.78), m_star, col, bevel=0.01)
    for p in (bow_cyl, bow_nose, sail, dive_planes, mast, star):
        p.parent = bow

    # Aft missile hull (breaks away during hoist)
    aft_cyl = K.add_cylinder(f"{name}_AftCyl", 0.50, 2.5, (-1.65, 0.0, 0.0), m_hull, col, vertices=18, rot_deg=(0.0, 90.0, 0.0), outline=0.020)
    aft_tail = K.add_cone(f"{name}_AftTail", 0.50, 0.14, 0.85, (-3.30, 0.0, 0.0), m_rust, col, vertices=16, rot_deg=(0.0, -90.0, 0.0), outline=0.018)
    fin_v = K.add_box(f"{name}_TailFinV", (0.42, 0.08, 0.78), (-3.15, 0.0, 0.12), m_hull, col, bevel=0.01, outline=0.014)
    for p in (aft_cyl, aft_tail, fin_v):
        p.parent = aft

    return {"root": root, "bow": bow, "aft": aft}


def build_glomar_ship_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Sunlit 1974 ocean set featuring the Hughes Glomar Explorer mining ship, sliding moon-pool doors & giant claw."""
    K.add_sunlit_sky_rig(
        "GlomarSun",
        col,
        sun_rot_deg=(46.0, 14.0, -32.0),
        sun_energy=2.35,
        sky_top="#1F5FC4",
        sky_horizon="#7DC2F6",
        sky_strength=0.85,
        sun_disc_loc=(-5.5, -15.5, 9.2),
    )

    m_sea1 = K.make_toon_mat("Glomar_Sea1", "#246496", emission_lift=0.16, roughness=0.22)
    m_sea2 = K.make_toon_mat("Glomar_Sea2", "#2F7AAD", emission_lift=0.18, roughness=0.20)
    m_hull = K.make_pbr_mat("Glomar_Hull", "Metal", "#3B4A5E", uv_scale=3.0, emission_lift=0.14)
    m_boot = K.make_toon_mat("Glomar_BootRed", "#A63A2E", emission_lift=0.16, roughness=0.55)
    m_white = K.make_toon_mat("Glomar_SuperWhite", "#F2F4F8", emission_lift=0.22, roughness=0.55)
    m_derrick = K.make_pbr_mat("Glomar_Derrick", "Metal", "#EAA828", uv_scale=2.5, emission_lift=0.18)
    m_pool = K.make_emissive_mat("Glomar_MoonPoolGlow", "#3AC8EC", strength=1.45)
    m_pier = K.make_pbr_mat("Glomar_PierWood", "WoodPlanks", "#BD9060", uv_scale=4.0, emission_lift=0.14)

    K.add_box("Glomar_OceanFloor", (40.0, 34.0, 0.6), (0.0, -4.5, -0.34), m_sea1, col)
    for wi in range(-4, 2):
        K.add_box(f"Glomar_Wave{wi}", (36.0, 1.15, 0.22), (0.0, wi * 2.4 - 4.0, 0.02 if wi % 2 else -0.04), m_sea2, col, bevel=0.08, rot_deg=(8.0, 0.0, 0.0))

    # Hughes Glomar Explorer vessel root
    ship_root = _make_empty("Glomar_ShipRoot", (0.0, -4.2, -0.04), col)
    ship_root.rotation_euler = (0.0, 0.0, math.radians(10.0))
    hull = K.add_box("Glomar_HullBox", (7.4, 2.15, 0.95), (0.0, 0.0, 0.42), m_hull, col, bevel=0.06, outline=0.022)
    boot = K.add_box("Glomar_BootLine", (7.48, 2.20, 0.22), (0.0, 0.0, 0.04), m_boot, col, bevel=0.02)
    bow = K.add_cone("Glomar_Bow", 1.10, 0.14, 1.55, (4.35, 0.0, 0.44), m_hull, col, vertices=4, rot_deg=(0.0, 90.0, 45.0), outline=0.020)
    bridge = K.add_box("Glomar_Bridge", (1.65, 1.55, 1.25), (2.25, 0.0, 1.48), m_white, col, bevel=0.04, outline=0.018)
    stern_helipad = K.add_box("Glomar_Helipad", (1.45, 1.65, 0.35), (-2.65, 0.0, 1.04), m_white, col, bevel=0.02, outline=0.016)
    # Central A-frame gimballed lifting derrick
    derrick_l = K.add_box("Glomar_DerrickL", (0.28, 0.28, 2.85), (-0.45, -0.62, 2.25), m_derrick, col, bevel=0.02, rot_deg=(-12.0, 8.0, 0.0), outline=0.016)
    derrick_r = K.add_box("Glomar_DerrickR", (0.28, 0.28, 2.85), (-0.45, 0.62, 2.25), m_derrick, col, bevel=0.02, rot_deg=(12.0, 8.0, 0.0), outline=0.016)
    derrick_top = K.add_box("Glomar_DerrickTop", (1.15, 1.25, 0.28), (-0.30, 0.0, 3.60), m_derrick, col, bevel=0.02, outline=0.016)
    # Moon-pool opening & sliding doors (animated multi-piece reveal!)
    pool_glow = K.add_box("Glomar_MoonPoolOpening", (1.75, 1.15, 0.10), (-0.35, 0.0, 0.90), m_pool, col, bevel=0.01)
    door_l = K.add_box("Glomar_MoonDoorL", (0.88, 1.18, 0.14), (-0.80, 0.0, 0.96), m_derrick, col, bevel=0.02, outline=0.014)
    door_r = K.add_box("Glomar_MoonDoorR", (0.88, 1.18, 0.14), (0.10, 0.0, 0.96), m_derrick, col, bevel=0.02, outline=0.014)

    for p in (hull, boot, bow, bridge, stern_helipad, derrick_l, derrick_r, derrick_top, pool_glow, door_l, door_r):
        p.parent = ship_root

    claw_meta = _build_giant_claw("Glomar_Claw", (-0.35, 0.0, 2.05), 0.72, col)
    claw_meta["root"].parent = ship_root

    # Toggleable foreground harbor pier + manganese nodule crates
    pier_root = _make_empty("Glomar_PierRoot", (0.0, 0.0, 0.0), col)
    p_deck = K.add_box("Glomar_PierDeck", (20.0, 4.4, 0.55), (0.0, 1.9, -0.24), m_pier, col, bevel=0.03)
    p_trim = K.add_box("Glomar_PierEdge", (20.0, 0.38, 0.18), (0.0, -0.22, 0.06), m_pier, col, bevel=0.02, outline=0.016)
    p_bol1 = K.add_cylinder("Glomar_BollardL", 0.13, 0.40, (-2.6, -0.04, 0.22), m_hull, col, outline=0.014)
    p_bol2 = K.add_cylinder("Glomar_BollardR", 0.13, 0.40, (2.6, -0.04, 0.22), m_hull, col, outline=0.014)
    for pp in (p_deck, p_trim, p_bol1, p_bol2):
        pp.parent = pier_root

    K.spawn_background_crew(
        "GlomarCrew",
        [
            (-3.45, -1.10, 0.04, -18.0, "#D9D2C4", "#E8B838", 0.52),
            (3.45, -1.10, 0.04, 22.0, "#2B5B84", "#E8B838", 0.52),
        ],
        col,
        frame_end=frame_end,
    )

    return {
        "col": col,
        "sky": ("#1F5FC4", "#7DC2F6", 0.85),
        "glomar_ship": ship_root,
        "moonpool_doors": [door_l, door_r],
        "glomar_claw": claw_meta,
        "ocean_pier": pier_root,
        "fg_framing": [
            K.add_foreground_framing_prop("Glomar_FgRailing", "railing", (-2.2, 2.8, 0.25), col, scale=0.85, rot_deg=(0.0, 0.0, 14.0)),
            K.add_foreground_framing_prop("Glomar_FgRivets", "rivets", (2.6, 2.7, 1.35), col, scale=0.88, rot_deg=(0.0, 0.0, -10.0)),
        ],
    }


def build_azorian_abyss_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """Deep-Pacific seabed 3 miles (16,500 ft) down: Soviet K-129 wreck, manganese nodules & giant claw."""
    K.add_sunlit_sky_rig(
        "AbyssLight",
        col,
        sun_rot_deg=(34.0, 8.0, -18.0),
        sun_energy=2.20,
        sun_color="#C6EEFF",
        sky_top="#0F4670",
        sky_horizon="#2C89BA",
        sky_strength=0.88,
        sun_disc_loc=None,
    )

    m_floor = K.make_pbr_mat("Abyss_Seabed", "Ground", "#52788A", uv_scale=5.0, emission_lift=0.18)
    m_ridge = K.make_toon_mat("Abyss_Ridge", "#3C6278", emission_lift=0.16, roughness=0.85)
    m_nod = K.make_toon_mat("Abyss_Manganese", "#2B303A", emission_lift=0.14, roughness=0.45)

    K.add_box("Abyss_Floor", (36.0, 32.0, 0.6), (0.0, -3.0, -0.32), m_floor, col, bevel=0.05)
    for ri, (rx, ry, rw, rh) in enumerate(((-4.2, -5.8, 3.6, 0.9), (3.8, -6.2, 4.2, 1.1), (0.0, -8.8, 12.0, 1.6))):
        K.add_box(f"Abyss_Ridge{ri}", (rw, 2.2, rh), (rx, ry, rh * 0.4), m_ridge, col, bevel=0.18, rot_deg=(0.0, 0.0, 8.0 * ri))

    # Manganese nodules scattered across ocean floor
    nodules: list[bpy.types.Object] = []
    for ni, (nx, ny, nr) in enumerate(((-2.4, -2.6, 0.22), (-1.4, -2.0, 0.18), (1.8, -2.4, 0.24), (2.7, -3.2, 0.20), (-0.6, -1.8, 0.16))):
        nd = K.add_sphere(f"Abyss_Nodule{ni}", nr, (nx, ny, nr * 0.72), m_nod, col, segments=10, rings=8, scale=(1.2, 0.95, 0.78), outline=0.014)
        nodules.append(nd)

    sub_meta = _build_soviet_sub("Abyss_K129", (0.0, -4.0, 0.56), 0.98, col, rot_z_deg=8.0)
    claw_meta = _build_giant_claw("Abyss_Clementine", (0.35, -4.0, 2.95), 0.96, col)

    # Depth arrows & floating ROV dust motes
    arr_dn = K.add_3d_callout_arrow("Abyss_DepthArrow", (-2.8, -3.4, 3.3), (-2.8, -3.4, 0.4), "#4BE0FF", col, frame_end=frame_end)
    K.add_floating_motes("Abyss_MarineSnow", (0.0, -3.6, 1.8), (3.2, 2.4, 1.4), col, count=22, color_hex="#A8E8FF", frame_end=frame_end, seed=29)

    return {
        "col": col,
        "sky": ("#0F4670", "#2C89BA", 0.88),
        "abyss_sub": sub_meta,
        "abyss_claw": claw_meta,
        "abyss_nodules": nodules,
        "callout_arrows": [arr_dn],
    }


def build_cia_briefing_set(col: bpy.types.Collection, frame_end: int = 60) -> dict:
    """1970s CIA & Hughes command briefing room with Pacific chart, spinning tape-reel mainframes & handoff space."""
    K.add_cinematic_3point_rig(
        "CIABriefRig",
        col,
        key_loc=(0.0, 3.0, 4.4),
        fill_loc=(-3.4, 4.0, 2.5),
        rim_loc=(0.0, -2.4, 3.2),
        key_energy=235.0,
        fill_energy=105.0,
        rim_energy=155.0,
    )

    m_floor = K.make_pbr_mat("CIA_FloorWood", "WoodPlanks", "#7A583E", uv_scale=4.0, emission_lift=0.14)
    m_wall = K.make_pbr_mat("CIA_WallSlate", "Concrete", "#646E7C", uv_scale=3.8, emission_lift=0.16)
    m_table = K.make_pbr_mat("CIA_Mahogany", "Wood", "#5C3222", uv_scale=2.8, emission_lift=0.14)
    m_rack = K.make_pbr_mat("CIA_Mainframe", "Metal", "#2C3542", uv_scale=2.4, emission_lift=0.14)
    m_reel = K.make_toon_mat("CIA_TapeReel", "#D8DFE8", emission_lift=0.22, roughness=0.32)
    m_chart = K.make_toon_mat("CIA_ChartSea", "#3C76A4", emission_lift=0.22, roughness=0.55)
    m_pin = K.make_toon_mat("CIA_TargetPin", "#E23D32", emission_lift=0.45, roughness=0.40)

    K.add_box("CIA_Floor", (14.0, 12.0, 0.4), (0.0, 0.0, -0.20), m_floor, col)
    K.add_box("CIA_BackWall", (14.0, 0.5, 6.2), (0.0, -3.2, 3.1), m_wall, col)
    K.add_box("CIA_SideWallL", (0.5, 10.0, 6.2), (-4.6, 0.5, 3.1), m_wall, col)
    K.add_box("CIA_SideWallR", (0.5, 10.0, 6.2), (4.6, 0.5, 3.1), m_wall, col)

    # Briefing table positioned cleanly at Y=-0.75 so actors can stand in front (Y=0.75) for handoffs!
    K.add_box("CIA_TableTop", (3.6, 1.5, 0.16), (0.0, -0.85, 0.98), m_table, col, bevel=0.03, outline=0.020)
    for lx in (-1.55, 1.55):
        for ly in (-1.45, -0.25):
            K.add_cylinder(f"CIA_Leg_{lx}_{ly}", 0.08, 0.92, (lx, ly, 0.46), m_table, col, outline=0.012)

    # Pacific Ocean target chart on wall & table
    K.add_box("CIA_WallChartFrame", (3.4, 0.10, 2.0), (0.0, -2.88, 2.25), m_table, col, bevel=0.02, outline=0.018)
    K.add_box("CIA_WallChartSea", (3.1, 0.12, 1.72), (0.0, -2.84, 2.25), m_chart, col)
    pin = K.add_sphere("CIA_TargetK129", 0.12, (0.25, -2.72, 2.18), m_pin, col, segments=12, rings=8, outline=0.012)

    # Spinning IBM-style mainframe tape reels in corners
    reels: list[bpy.types.Object] = []
    for sx in (-2.9, 2.9):
        K.add_box(f"CIA_Rack_{sx}", (1.1, 0.75, 2.9), (sx, -2.45, 1.45), m_rack, col, bevel=0.03, outline=0.018)
        for rx_off in (-0.26, 0.26):
            rl = K.add_cylinder(f"CIA_Reel_{sx}_{rx_off}", 0.22, 0.08, (sx + rx_off, -2.04, 2.25), m_reel, col, vertices=16, rot_deg=(90.0, 0.0, 0.0), outline=0.012)
            reels.append(rl)

    K.add_warm_lantern("CIA_LampL", (-2.6, -1.8, 4.15), col, color_hex="#FFE2A4", energy=72.0, radius=0.14)
    K.add_warm_lantern("CIA_LampR", (2.6, -1.8, 4.15), col, color_hex="#FFE2A4", energy=72.0, radius=0.14)

    return {
        "col": col,
        "sky": ("#242B38", "#434E62", 0.62),
        "map_markers": [pin],
        "tape_reels": reels,
        "fg_framing": [
            K.add_foreground_framing_prop("CIA_FgEdge", "drafting_edge", (-2.1, 2.6, 0.45), col, scale=0.80, rot_deg=(0.0, 0.0, 12.0)),
        ],
    }


SET_BUILDERS = {
    "meadow": build_wwii_meadow_set,
    "forest_sonic": build_wwii_forest_sonic_set,
    "warroom": build_wwii_warroom_set,
    "sky_recon": build_wwii_sky_recon_set,
    "diagram_stage": build_diagram_backdrop_set,
    "shipyard": build_wwi_shipyard_set,
    "ocean_dazzle": build_wwi_ocean_dazzle_set,
    "uboat_interior": build_wwi_uboat_interior_set,
    "periscope_view": build_wwi_periscope_view_set,
    "drafting_office": build_drafting_office_set,
    "catskills_crossroads": build_catskills_crossroads_set,
    "courtroom_office": build_courtroom_office_set,
    "concrete_drydock": build_concrete_drydock_set,
    "concrete_ocean": build_concrete_ocean_set,
    "concrete_breakwater": build_concrete_breakwater_set,
    "glomar_ship": build_glomar_ship_set,
    "azorian_abyss": build_azorian_abyss_set,
    "cia_briefing": build_cia_briefing_set,
}
