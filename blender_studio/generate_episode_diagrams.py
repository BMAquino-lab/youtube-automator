#!/usr/bin/env python3
"""Generic JSON-driven high-DPI prop & macro diagram texture generator for Fivestack Blender episodes.

Usage:
  python generate_episode_diagrams.py <ep_dir>
Reads <ep_dir>/diagram_specs.json and renders PNG textures into <ep_dir>/textures/.
Keeps headline & key visuals cleanly above the 64%-79% caption band (and avoids white stroke text there).
"""
from __future__ import annotations

import json
import math
import sys
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(r"C:\Windows\Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in (name, "arialbd.ttf", "arial.ttf", "calibrib.ttf"):
        p = FONT_DIR / cand
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _base_card(spec: dict) -> tuple[Image.Image, ImageDraw.ImageDraw, dict]:
    w = int(spec.get("width", 1024))
    h = int(spec.get("height", 1250))
    pal_name = spec.get("palette", "parchment")
    palettes = {
        "parchment": {"bg": (244, 232, 202), "bg2": (231, 214, 178), "border": (44, 34, 24), "ink": (30, 24, 18), "accent": (176, 44, 34), "accent2": (46, 98, 148)},
        "olive": {"bg": (228, 224, 198), "bg2": (196, 194, 158), "border": (42, 48, 30), "ink": (28, 32, 20), "accent": (168, 48, 32), "accent2": (68, 92, 46)},
        "blueprint": {"bg": (24, 62, 114), "bg2": (18, 48, 90), "border": (230, 242, 255), "ink": (240, 246, 255), "accent": (255, 198, 72), "accent2": (118, 194, 248)},
        "brass": {"bg": (214, 174, 86), "bg2": (182, 142, 58), "border": (38, 28, 16), "ink": (26, 20, 12), "accent": (152, 28, 24), "accent2": (42, 68, 92)},
        "navy": {"bg": (236, 239, 244), "bg2": (212, 220, 232), "border": (22, 38, 68), "ink": (20, 32, 56), "accent": (188, 44, 38), "accent2": (38, 98, 158)},
    }
    P = palettes.get(pal_name, palettes["parchment"])
    img = Image.new("RGB", (w, h), P["bg"])
    d = ImageDraw.Draw(img)

    # Subtle paper border + double technical rule
    d.rectangle([18, 18, w - 18, h - 18], fill=P["bg"], outline=P["border"], width=10)
    d.rectangle([38, 38, w - 38, h - 38], outline=P["border"], width=3)

    # Header band (top ~20% so central art fills 22%..62%, leaving 64%..79% safe)
    d.rectangle([38, 38, w - 38, 235], fill=P["bg2"])
    d.line([38, 235, w - 38, 235], fill=P["border"], width=5)

    title = str(spec.get("title", "")).upper()
    subtitle = str(spec.get("subtitle", "")).upper()
    ft = _font("arialbd.ttf", 72 if len(title) <= 14 else 56)
    fs = _font("arialbd.ttf", 36)
    d.text((w // 2, 118), title, fill=P["ink"], font=ft, anchor="mm")
    if subtitle:
        d.text((w // 2, 192), subtitle, fill=P["accent"], font=fs, anchor="mm")

    footer = str(spec.get("footer", ""))
    if footer:
        ff = _font("arialbd.ttf", 40 if len(footer) <= 28 else 32)
        d.rectangle([38, h - 150, w - 38, h - 38], fill=P["bg2"])
        d.line([38, h - 150, w - 38, h - 150], fill=P["border"], width=4)
        d.text((w // 2, h - 94), footer.upper(), fill=P["ink"], font=ff, anchor="mm")

    return img, d, P


def _draw_tank_silhouette(d: ImageDraw.ImageDraw, cx: int, cy: int, scale: float, fill, outline) -> None:
    s = scale
    # Tracks
    d.rounded_rectangle([cx - int(145 * s), cy + int(10 * s), cx + int(145 * s), cy + int(78 * s)], radius=int(24 * s), fill=(48, 52, 44), outline=outline, width=5)
    # Hull
    d.polygon([
        (cx - int(120 * s), cy + int(18 * s)),
        (cx + int(130 * s), cy + int(18 * s)),
        (cx + int(105 * s), cy - int(28 * s)),
        (cx - int(95 * s), cy - int(28 * s)),
    ], fill=fill, outline=outline)
    # Turret + barrel
    d.rounded_rectangle([cx - int(65 * s), cy - int(84 * s), cx + int(55 * s), cy - int(26 * s)], radius=int(20 * s), fill=fill, outline=outline, width=5)
    d.rectangle([cx + int(50 * s), cy - int(66 * s), cx + int(185 * s), cy - int(48 * s)], fill=fill, outline=outline, width=4)


def render_diagram(spec: dict, out_path: Path) -> None:
    img, d, P = _base_card(spec)
    w, h = img.size
    layout = spec.get("layout", "spec_card")
    ink, acc, acc2 = P["ink"], P["accent"], P["accent2"]

    if layout == "spec_card":
        big_num = str(spec.get("big_value", "93 LBS"))
        cap = str(spec.get("caption_top", ""))
        note = str(spec.get("note", ""))
        if spec.get("icon") == "tank":
            _draw_tank_silhouette(d, w // 2, 430, 1.28, acc2, ink)
        d.text((w // 2, 585), big_num, fill=acc, font=_font("arialbd.ttf", 112), anchor="mm")
        if cap:
            d.text((w // 2, 675), cap.upper(), fill=ink, font=_font("arialbd.ttf", 40), anchor="mm")
        if note:
            d.text((w // 2, 742), note.upper(), fill=acc2, font=_font("arialbd.ttf", 34), anchor="mm")

    elif layout == "comparison":
        left_t = str(spec.get("left_title", "REAL TANK"))
        left_v = str(spec.get("left_value", "40 TONS"))
        right_t = str(spec.get("right_title", "RUBBER DECOY"))
        right_v = str(spec.get("right_value", "93 LBS"))
        d.line([w // 2, 265, w // 2, 740], fill=ink, width=5)
        d.text((w // 4, 305), left_t, fill=ink, font=_font("arialbd.ttf", 44), anchor="mm")
        d.text((3 * w // 4, 305), right_t, fill=acc2, font=_font("arialbd.ttf", 44), anchor="mm")
        _draw_tank_silhouette(d, w // 4, 465, 0.95, (92, 98, 84), ink)
        _draw_tank_silhouette(d, 3 * w // 4, 465, 0.95, (112, 146, 78), ink)
        # Draw feather/arrow lifting right tank
        d.text((w // 4, 645), left_v, fill=ink, font=_font("arialbd.ttf", 68), anchor="mm")
        d.text((3 * w // 4, 645), right_v, fill=acc, font=_font("arialbd.ttf", 72), anchor="mm")

    elif layout == "wave_range":
        val = str(spec.get("big_value", "15 MILES"))
        d.text((w // 2, 310), val, fill=acc, font=_font("arialbd.ttf", 104), anchor="mm")
        sx, sy = 190, 540
        # Speaker horn icon
        d.polygon([(sx - 40, sy - 40), (sx + 70, sy - 95), (sx + 70, sy + 95), (sx - 40, sy + 40)], fill=acc2, outline=ink)
        for r in (160, 270, 380, 490, 600):
            d.arc([sx - r + 80, sy - r, sx + r + 80, sy + r], start=-45, end=45, fill=acc if r > 350 else ink, width=10)
        d.line([sx + 80, sy + 145, sx + 680, sy + 145], fill=ink, width=5)
        d.text((sx + 380, sy + 185), "AUDIBLE PROJECTION", fill=ink, font=_font("arialbd.ttf", 36), anchor="mm")

    elif layout == "decoy_map":
        # Channel water + coastline + Pas-de-Calais fake bulge vs Normandy
        d.rectangle([70, 265, w - 70, 745], fill=(76, 134, 186), outline=ink, width=5)
        # Land mass on right/bottom
        d.polygon([(520, 265), (w - 70, 265), (w - 70, 745), (360, 745), (450, 560)], fill=(214, 198, 148), outline=ink)
        # UK coast top-left
        d.polygon([(70, 265), (340, 265), (290, 410), (70, 460)], fill=(198, 184, 138), outline=ink)
        # Big decoy bullseye at Pas-de-Calais
        px, py = 740, 410
        d.ellipse([px - 85, py - 85, px + 85, py + 85], outline=acc, width=8)
        d.ellipse([px - 45, py - 45, px + 45, py + 45], fill=acc, outline=ink, width=4)
        d.text((px, py - 115), "PAS-DE-CALAIS (DECOY)", fill=ink, font=_font("arialbd.ttf", 34), anchor="mm")
        # Real target Normandy
        nx, ny = 520, 635
        d.ellipse([nx - 26, ny - 26, nx + 26, ny + 26], fill=acc2, outline=ink, width=4)
        d.text((nx - 140, ny + 55), "NORMANDY", fill=ink, font=_font("arialbd.ttf", 34), anchor="mm")

    elif layout == "gauge":
        val = str(spec.get("big_value", "30 MIN"))
        d.text((w // 2, 305), val, fill=acc, font=_font("arialbd.ttf", 104), anchor="mm")
        cx, cy, rad = w // 2, 555, 175
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=P["bg2"], outline=ink, width=8)
        for deg in range(0, 360, 30):
            rads = math.radians(deg)
            x1, y1 = cx + int((rad - 26) * math.cos(rads)), cy + int((rad - 26) * math.sin(rads))
            x2, y2 = cx + int((rad - 6) * math.cos(rads)), cy + int((rad - 6) * math.sin(rads))
            d.line([x1, y1, x2, y2], fill=ink, width=5)
        # Red wedge sweep for 30 minutes
        d.pieslice([cx - rad + 22, cy - rad + 22, cx + rad - 22, cy + rad - 22], start=-90, end=90, fill=acc, outline=ink)
        d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=ink)

    elif layout == "naval_reticle":
        val = str(spec.get("big_value", "40° OFF COURSE"))
        d.text((w // 2, 305), val, fill=acc, font=_font("arialbd.ttf", 76), anchor="mm")
        # Coincidence split horizon box showing shifted bow/stern stripes
        bx0, by0, bx1, by1 = 120, 380, w - 120, 710
        d.rectangle([bx0, by0, bx1, by1], fill=(164, 212, 240), outline=ink, width=6)
        mid_y = (by0 + by1) // 2
        # Top half shifted left, bottom half shifted right
        for half, sx in ((0, -70), (1, 70)):
            y_top = by0 + 35 if half == 0 else mid_y + 4
            y_bot = mid_y - 4 if half == 0 else by1 - 35
            ship_x0 = w // 2 - 190 + sx
            ship_x1 = w // 2 + 190 + sx
            d.rectangle([ship_x0, y_top, ship_x1, y_bot], fill=(38, 46, 62), outline=ink, width=4)
            for si in range(6):
                stripe_x = ship_x0 + 20 + si * 60
                d.polygon([(stripe_x, y_top), (stripe_x + 32, y_top), (stripe_x + 12, y_bot), (stripe_x - 18, y_bot)], fill=(250, 250, 250) if si % 2 == 0 else acc2)
        d.line([bx0, mid_y, bx1, mid_y], fill=acc, width=5)
        d.line([w // 2, by0, w // 2, by1], fill=ink, width=3)

    elif layout == "tally_plaque":
        val = str(spec.get("big_value", "4,000+ SHIPS"))
        line2 = str(spec.get("caption_top", "DAZZLE CAMOUFLAGE"))
        d.text((w // 2, 430), val, fill=acc, font=_font("arialbd.ttf", 112), anchor="mm")
        d.text((w // 2, 545), line2.upper(), fill=ink, font=_font("arialbd.ttf", 52), anchor="mm")
        for bi in range(4):
            sx = 160 + bi * 185
            d.rounded_rectangle([sx, 600, sx + 140, 675], radius=12, fill=acc2 if bi % 2 == 0 else ink, outline=ink, width=4)

    elif layout == "initials_puzzle":
        top_lbl = str(spec.get("caption_top", "FOUNDER + ASSISTANT INITIALS"))
        d.text((w // 2, 295), top_lbl.upper(), fill=ink, font=_font("arialbd.ttf", 38), anchor="mm")
        source_letters = list(spec.get("source_letters", ["O", "G", "L", "E", "A"]))
        target_letters = list(spec.get("target_letters", ["A", "G", "L", "O", "E"]))
        box_w, gap = 130, 35
        sx0 = (w - (len(source_letters) * box_w + (len(source_letters) - 1) * gap)) // 2
        for idx, ch in enumerate(source_letters):
            bx = sx0 + idx * (box_w + gap)
            d.rounded_rectangle([bx, 345, bx + box_w, 465], radius=18, fill=P["bg2"], outline=ink, width=6)
            d.text((bx + box_w // 2, 405), ch, fill=acc2, font=_font("arialbd.ttf", 78), anchor="mm")
        d.text((w // 2, 515), "SCRAMBLED INTO FAKE TOWN", fill=acc, font=_font("arialbd.ttf", 38), anchor="mm")
        tx0 = (w - (len(target_letters) * box_w + (len(target_letters) - 1) * gap)) // 2
        for idx, ch in enumerate(target_letters):
            bx = tx0 + idx * (box_w + gap)
            d.rounded_rectangle([bx, 565, bx + box_w, 695], radius=18, fill=acc, outline=ink, width=6)
            d.text((bx + box_w // 2, 630), ch, fill=(252, 248, 240), font=_font("arialbd.ttf", 82), anchor="mm")

    elif layout == "map_trap":
        # Stylized road grid + Catskills crossroads + highlighted fake town dot
        d.rectangle([80, 265, w - 80, 725], fill=(238, 228, 198), outline=ink, width=6)
        # Highway curves / diagonal crossroads
        d.line([120, 640, w - 120, 340], fill=(196, 62, 48), width=16)
        d.line([240, 285, 760, 700], fill=(72, 118, 168), width=14)
        # Intersection circle + magnifying ring sized cleanly around text
        cx, cy = w // 2, 490
        d.ellipse([cx - 175, cy - 175, cx + 175, cy + 175], fill=(252, 246, 224), outline=ink, width=10)
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=acc, outline=ink, width=5)
        d.text((cx, cy - 82), str(spec.get("big_value", "AGLOE, N.Y.")), fill=acc, font=_font("arialbd.ttf", 46), anchor="mm")
        d.text((cx, cy + 82), str(spec.get("caption_top", "0 BUILDINGS")), fill=ink, font=_font("arialbd.ttf", 36), anchor="mm")
        if spec.get("note"):
            d.text((w // 2, 775), str(spec["note"]).upper(), fill=acc2, font=_font("arialbd.ttf", 34), anchor="mm")

    elif layout == "lawsuit_verdict":
        left_t = str(spec.get("left_title", "1930s MAP TRAP"))
        left_v = str(spec.get("left_value", "EMPTY ROAD"))
        right_t = str(spec.get("right_title", "1950s REALITY"))
        right_v = str(spec.get("right_value", "REAL STORE"))
        d.line([w // 2, 265, w // 2, 690], fill=ink, width=5)
        d.text((w // 4, 315), left_t, fill=acc2, font=_font("arialbd.ttf", 40), anchor="mm")
        d.text((3 * w // 4, 315), right_t, fill=acc, font=_font("arialbd.ttf", 40), anchor="mm")
        # Left empty crossroad X
        d.line([w // 4 - 90, 410, w // 4 + 90, 520], fill=ink, width=10)
        d.line([w // 4 - 90, 520, w // 4 + 90, 410], fill=ink, width=10)
        # Right store silhouette
        sx, sy = 3 * w // 4, 465
        d.rectangle([sx - 85, sy - 45, sx + 85, sy + 55], fill=acc2, outline=ink, width=5)
        d.polygon([(sx - 98, sy - 45), (sx + 98, sy - 45), (sx, sy - 105)], fill=acc, outline=ink)
        d.text((w // 4, 600), left_v, fill=ink, font=_font("arialbd.ttf", 48), anchor="mm")
        d.text((3 * w // 4, 600), right_v, fill=acc, font=_font("arialbd.ttf", 48), anchor="mm")
        if spec.get("big_value"):
            d.rounded_rectangle([180, 650, w - 180, 745], radius=14, fill=acc, outline=ink, width=5)
            d.text((w // 2, 698), str(spec["big_value"]).upper(), fill=(255, 248, 240), font=_font("arialbd.ttf", 46), anchor="mm")

    elif layout == "archimedes_buoyancy":
        # Cutaway waterline comparison: Solid stone block sinks vs Hollow concrete hull displaces > weight and floats!
        left_t = str(spec.get("left_title", "SOLID CONCRETE"))
        left_v = str(spec.get("left_value", "SINKS IMMEDIATELY"))
        right_t = str(spec.get("right_title", "HOLLOW HULL"))
        right_v = str(spec.get("right_value", "FLOATS ON AIR"))
        d.line([w // 2, 265, w // 2, 745], fill=ink, width=5)
        d.text((w // 4, 298), left_t, fill=ink, font=_font("arialbd.ttf", 40), anchor="mm")
        d.text((3 * w // 4, 298), right_t, fill=acc2, font=_font("arialbd.ttf", 40), anchor="mm")
        # Water boxes
        for bx0, bx1 in ((72, w // 2 - 28), (w // 2 + 28, w - 72)):
            d.rectangle([bx0, 415, bx1, 635], fill=(84, 152, 208), outline=ink, width=5)
            d.line([bx0, 415, bx1, 415], fill=(240, 250, 255), width=6)
        # Left sunken solid concrete slab at bottom
        lx = w // 4
        d.rectangle([lx - 90, 540, lx + 90, 625], fill=(138, 142, 144), outline=ink, width=6)
        d.text((lx, 582), "NO AIR", fill=(255, 255, 255), font=_font("arialbd.ttf", 32), anchor="mm")
        # Right hollow U-shaped concrete hull floating high above waterline
        rx = 3 * w // 4
        d.polygon([
            (rx - 135, 365), (rx + 135, 365), (rx + 105, 495), (rx - 105, 495)
        ], fill=(172, 176, 174), outline=ink)
        d.polygon([
            (rx - 95, 365), (rx + 95, 365), (rx + 75, 462), (rx - 75, 462)
        ], fill=(224, 238, 252), outline=ink)
        d.text((rx, 418), "TRAPPED AIR", fill=acc2, font=_font("arialbd.ttf", 28), anchor="mm")
        d.text((lx, 695), left_v, fill=acc, font=_font("arialbd.ttf", 38), anchor="mm")
        d.text((rx, 695), right_v, fill=acc2, font=_font("arialbd.ttf", 38), anchor="mm")

    elif layout == "material_ratio":
        # Two horizontal comparison bars for steel plate saved vs lightweight Haydite concrete
        val = str(spec.get("big_value", "70% LESS STEEL PLATE"))
        d.text((w // 2, 310), val, fill=acc, font=_font("arialbd.ttf", 68), anchor="mm")
        rows = [
            (str(spec.get("bar1_label", "STANDARD STEEL SHIP")), float(spec.get("bar1_frac", 0.92)), acc),
            (str(spec.get("bar2_label", "C1-S-D1 CONCRETE SHIP")), float(spec.get("bar2_frac", 0.28)), acc2),
        ]
        for idx, (lbl, frac, col_f) in enumerate(rows):
            ry = 415 + idx * 165
            d.text((90, ry - 42), lbl.upper(), fill=ink, font=_font("arialbd.ttf", 36), anchor="lm")
            track_x0, track_x1 = 90, w - 235
            d.rounded_rectangle([track_x0, ry, track_x1, ry + 74], radius=12, fill=P["bg2"], outline=ink, width=5)
            bar_w = max(60, int((track_x1 - track_x0) * min(1.0, max(0.05, frac))))
            d.rounded_rectangle([track_x0, ry, track_x0 + bar_w, ry + 74], radius=12, fill=col_f, outline=ink, width=4)
            d.text((w - 90, ry + 37), f"{int(round(frac * 100))}%", fill=col_f, font=_font("arialbd.ttf", 48), anchor="rm")

    elif layout == "depth_scale":
        # Vertical ocean cross-section: surface mining ship -> 3 miles / 16,500 ft pipe -> seabed sub
        top_lbl = str(spec.get("caption_top", "SURFACE: MINING SHIP"))
        big_val = str(spec.get("big_value", "16,500 FT"))
        bot_lbl = str(spec.get("note", "SOVIET SUB K-129"))
        d.rectangle([80, 260, w - 80, 745], fill=(32, 92, 146), outline=ink, width=6)
        # Sky band & waterline
        d.rectangle([80, 260, w - 80, 345], fill=(148, 206, 244), outline=ink, width=4)
        # Mini ship silhouette shifted slightly left, label cleanly on right
        sx = w // 2 - 120
        d.polygon([(sx - 110, 315), (sx + 110, 315), (sx + 88, 345), (sx - 88, 345)], fill=(58, 72, 94), outline=ink)
        d.rectangle([sx - 22, 275, sx + 22, 315], fill=(238, 178, 48), outline=ink, width=3)
        d.text((sx + 135, 302), top_lbl.upper(), fill=ink, font=_font("arialbd.ttf", 28), anchor="lm")
        # Vertical drill pipe + depth ticks
        d.line([sx, 345, sx, 645], fill=(238, 178, 48), width=12)
        for ty in range(385, 630, 55):
            d.line([sx - 30, ty, sx - 12, ty], fill=(230, 244, 255), width=4)
        d.rounded_rectangle([sx + 48, 430, w - 105, 560], radius=14, fill=(20, 44, 78), outline=(255, 198, 72), width=5)
        d.text(((sx + 48 + w - 105) // 2, 495), big_val, fill=(255, 198, 72), font=_font("arialbd.ttf", 64), anchor="mm")
        # Seabed & submarine silhouette
        d.rectangle([80, 685, w - 80, 745], fill=(92, 84, 68), outline=ink, width=4)
        d.rounded_rectangle([sx - 105, 642, sx + 105, 685], radius=18, fill=(44, 52, 62), outline=ink, width=4)
        d.rectangle([sx - 24, 616, sx + 20, 644], fill=(44, 52, 62), outline=ink, width=3)
        d.text((w // 2, 715), bot_lbl.upper(), fill=(246, 244, 236), font=_font("arialbd.ttf", 32), anchor="mm")
        # Subtle abyss depth rule below (kept low-contrast in caption zone 64%-79%)
        d.rectangle([80, 770, w - 80, 1055], fill=(20, 52, 92), outline=ink, width=4)
        for wy in (835, 905, 975):
            d.line([110, wy, w - 110, wy], fill=(38, 84, 138), width=3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: generate_episode_diagrams.py <ep_dir>", file=sys.stderr)
        return 1
    ep_dir = Path(sys.argv[1]).resolve()
    specs = json.loads((ep_dir / "diagram_specs.json").read_text(encoding="utf-8"))
    tex_dir = ep_dir / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs.get("diagrams", []):
        out_p = tex_dir / spec["filename"]
        render_diagram(spec, out_p)
        print(f"[diagram] {out_p.name}", flush=True)
    print(f"Generated {len(specs.get('diagrams', []))} diagram(s) in {tex_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
