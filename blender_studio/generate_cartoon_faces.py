"""Generate crisp 16-emotion 2D stickman face sprites + 4x4 4096x4096 atlas (`cartoon_face_atlas.png`)
for Fivestack's Blender 4.2 2D-on-3D Stickman Studio (@aiwithcb / @RicksClips3000 style).

Every tile is drawn at 2048x2048 and downsampled with LANCZOS to 1024x1024.
All facial ink stays strictly inside the inner 12%..88% safe box (246..1802 px) so linear
UV filtering never bleeds across tile boundaries.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent / "assets" / "faces"
INK = (20, 17, 20, 255)
WHITE = (255, 255, 255, 255)
MOUTH_DARK = (108, 22, 34, 255)
TONGUE_PINK = (242, 118, 138, 255)
SWEAT_CYAN = (112, 212, 255, 255)
BLUSH_PINK = (255, 138, 158, 165)
FURIOUS_RED = (232, 46, 56, 255)

EMOTIONS = [
    "NEUTRAL",
    "HAPPY",
    "LAUGH",
    "SMUG",
    "DEADPAN",
    "SHOCK",
    "NERVOUS_SWEAT",
    "ANGRY",
    "FURIOUS",
    "SAD",
    "CRYING",
    "SCREAM",
    "SUSPICIOUS",
    "DETERMINED",
    "SLEEPY",
    "CONFUSED",
]

EYE_L = 710
EYE_R = 1338
EYE_Y = 910
MOUTH_X = 1024
MOUTH_Y = 1380


def _draw_sweat_drop(d: ImageDraw.ImageDraw, cx: float, cy: float, scale: float = 1.0) -> None:
    w = 92 * scale
    h = 148 * scale
    pts = [
        (cx, cy - h * 0.55),
        (cx + w * 0.52, cy + h * 0.14),
        (cx, cy + h * 0.48),
        (cx - w * 0.52, cy + h * 0.14),
    ]
    d.polygon(pts, fill=SWEAT_CYAN)
    d.ellipse(
        [cx - w * 0.52, cy - h * 0.08, cx + w * 0.52, cy + h * 0.55],
        fill=SWEAT_CYAN,
        outline=INK,
        width=max(12, int(20 * scale)),
    )
    d.line([(cx, cy - h * 0.55), (cx - w * 0.48, cy + h * 0.08)], fill=INK, width=max(12, int(20 * scale)))
    d.line([(cx, cy - h * 0.55), (cx + w * 0.48, cy + h * 0.08)], fill=INK, width=max(12, int(20 * scale)))
    d.ellipse([cx - w * 0.22, cy + h * 0.05, cx - w * 0.03, cy + h * 0.28], fill=(255, 255, 255, 235))


def _draw_blush(d: ImageDraw.ImageDraw) -> None:
    for cx in (520, 1528):
        cy = 1175
        d.rounded_rectangle([cx - 120, cy - 48, cx + 120, cy + 48], radius=48, fill=BLUSH_PINK)


def _draw_d_smile(
    d: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    w: float = 460,
    h: float = 280,
    upper_teeth: bool = False,
) -> None:
    x0, y0, x1, y1 = cx - w / 2, cy - h * 0.38, cx + w / 2, cy + h * 0.62
    # Fill D-shape mouth using pie/chord geometry + crisp outline
    d.chord([x0, y0 - h * 0.58, x1, y1], start=0, end=180, fill=MOUTH_DARK)
    # Tongue arc at lower interior
    tx0, ty0, tx1, ty1 = cx - w * 0.30, cy + h * 0.18, cx + w * 0.30, y1 + h * 0.14
    d.chord([tx0, ty0, tx1, ty1], start=180, end=360, fill=TONGUE_PINK)
    # Mask bottom below chord via crisp re-outline
    d.chord([x0, y0 - h * 0.58, x1, y1], start=0, end=180, outline=INK, width=36)
    d.line([(x0, cy - h * 0.08), (x1, cy - h * 0.08)], fill=INK, width=36)
    if upper_teeth:
        d.rectangle([x0 + 34, cy - h * 0.06, x1 - 34, cy + h * 0.08], fill=WHITE)
        d.line([(x0, cy - h * 0.08), (x1, cy - h * 0.08)], fill=INK, width=36)


def _draw_open_oval_mouth(d: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float) -> None:
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    rad = min(w, h) * 0.38
    d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=MOUTH_DARK, outline=INK, width=36)
    d.rounded_rectangle([x0 + w * 0.18, y1 - h * 0.38, x1 - w * 0.18, y1 - 24], radius=rad * 0.5, fill=TONGUE_PINK)
    d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=None, outline=INK, width=36)


def _draw_oval_eye(
    d: ImageDraw.ImageDraw,
    cx: float,
    cy: float = EYE_Y,
    w: float = 175,
    h: float = 245,
    look_x: float = 0.0,
    look_y: float = 0.0,
    gloss: bool = True,
    half_lid: bool = False,
    lid_y_offset: float = -15.0,
) -> None:
    x0, y0, x1, y1 = cx - w / 2 + look_x, cy - h / 2 + look_y, cx + w / 2 + look_x, cy + h / 2 + look_y
    d.ellipse([x0, y0, x1, y1], fill=INK)
    if gloss:
        d.ellipse([cx - w * 0.24 + look_x, cy - h * 0.28 + look_y, cx + w * 0.08 + look_x, cy + h * 0.02 + look_y], fill=WHITE)
    if half_lid:
        lid_y = cy + lid_y_offset
        d.rectangle([x0 - 28, y0 - 28, x1 + 28, lid_y], fill=(0, 0, 0, 0))
        d.line([(x0 - 32, lid_y), (x1 + 32, lid_y)], fill=INK, width=38)


def _draw_crescent_eye(d: ImageDraw.ImageDraw, cx: float, cy: float = EYE_Y + 35, w: float = 260, h: float = 210) -> None:
    # Bold ^ happy eye arch matching @aiwithcb cheerful expression
    d.arc([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], start=190, end=350, fill=INK, width=42)


def _draw_circle_eye(d: ImageDraw.ImageDraw, cx: float, cy: float = EYE_Y, r: float = 148, pupil_r: float = 34) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE, outline=INK, width=36)
    d.ellipse([cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r], fill=INK)


def _draw_brows(d: ImageDraw.ImageDraw, mode: str) -> None:
    for idx, (side, cx) in enumerate(((-1, EYE_L), (1, EYE_R))):
        if mode == "calm":
            d.arc([cx - 135, 595, cx + 135, 695], start=200, end=340, fill=INK, width=34)
        elif mode == "happy":
            d.arc([cx - 140, 540, cx + 140, 650], start=195, end=345, fill=INK, width=34)
        elif mode == "shock":
            d.arc([cx - 150, 480, cx + 150, 610], start=195, end=345, fill=INK, width=38)
        elif mode == "flat":
            d.line([(cx - 135, 665), (cx + 135, 665)], fill=INK, width=36)
        elif mode == "angry":
            y_out, y_in = 570, 710
            d.line([(cx + side * 145, y_out), (cx - side * 135, y_in)], fill=INK, width=42)
        elif mode == "sad":
            y_out, y_in = 685, 560
            d.line([(cx + side * 145, y_out), (cx - side * 130, y_in)], fill=INK, width=36)
        elif mode == "smug":
            if idx == 0:
                d.line([(cx - 140, 675), (cx + 135, 645)], fill=INK, width=38)
            else:
                d.arc([cx - 140, 535, cx + 140, 650], start=195, end=345, fill=INK, width=38)
        elif mode == "suspicious":
            if idx == 0:
                d.line([(cx - 140, 685), (cx + 140, 685)], fill=INK, width=38)
            else:
                d.arc([cx - 145, 535, cx + 145, 650], start=195, end=345, fill=INK, width=38)
        elif mode == "confused":
            if idx == 0:
                d.line([(cx - 140, 695), (cx + 140, 675)], fill=INK, width=36)
            else:
                d.arc([cx - 145, 515, cx + 145, 645], start=195, end=345, fill=INK, width=36)


def render_face(emotion: str) -> Image.Image:
    S = 2048
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    if emotion == "NEUTRAL":
        _draw_oval_eye(d, EYE_L)
        _draw_oval_eye(d, EYE_R)
        _draw_brows(d, "calm")
        d.arc([MOUTH_X - 185, MOUTH_Y - 125, MOUTH_X + 185, MOUTH_Y + 60], start=14, end=166, fill=INK, width=36)

    elif emotion == "HAPPY":
        _draw_crescent_eye(d, EYE_L)
        _draw_crescent_eye(d, EYE_R)
        _draw_brows(d, "happy")
        _draw_d_smile(d, MOUTH_X, MOUTH_Y - 10, w=450, h=280)

    elif emotion == "LAUGH":
        _draw_crescent_eye(d, EYE_L, cy=EYE_Y + 45, w=270, h=220)
        _draw_crescent_eye(d, EYE_R, cy=EYE_Y + 45, w=270, h=220)
        _draw_brows(d, "happy")
        _draw_blush(d)
        _draw_d_smile(d, MOUTH_X, MOUTH_Y + 10, w=510, h=330, upper_teeth=True)

    elif emotion == "SMUG":
        _draw_oval_eye(d, EYE_L, w=185, h=220, look_x=28, half_lid=True, lid_y_offset=-18)
        _draw_oval_eye(d, EYE_R, w=185, h=220, look_x=28, half_lid=True, lid_y_offset=-18)
        _draw_brows(d, "smug")
        d.arc([MOUTH_X - 185, MOUTH_Y - 135, MOUTH_X + 215, MOUTH_Y + 55], start=18, end=142, fill=INK, width=38)

    elif emotion == "DEADPAN":
        _draw_oval_eye(d, EYE_L, w=175, h=215, half_lid=True, lid_y_offset=-10)
        _draw_oval_eye(d, EYE_R, w=175, h=215, half_lid=True, lid_y_offset=-10)
        _draw_brows(d, "flat")
        d.line([(MOUTH_X - 145, MOUTH_Y - 10), (MOUTH_X + 145, MOUTH_Y - 10)], fill=INK, width=36)

    elif emotion == "SHOCK":
        _draw_circle_eye(d, EYE_L, r=152, pupil_r=36)
        _draw_circle_eye(d, EYE_R, r=152, pupil_r=36)
        _draw_brows(d, "shock")
        _draw_open_oval_mouth(d, MOUTH_X, MOUTH_Y + 25, w=210, h=250)

    elif emotion == "NERVOUS_SWEAT":
        _draw_oval_eye(d, EYE_L, w=185, h=255)
        _draw_oval_eye(d, EYE_R, w=185, h=255)
        _draw_brows(d, "sad")
        _draw_sweat_drop(d, 1645, 700, scale=1.12)
        pts = [(790, MOUTH_Y + 15), (905, MOUTH_Y - 35), (1024, MOUTH_Y + 25), (1143, MOUTH_Y - 35), (1258, MOUTH_Y + 15)]
        d.line(pts, fill=INK, width=36, joint="curve")

    elif emotion == "ANGRY":
        _draw_oval_eye(d, EYE_L, w=175, h=225)
        _draw_oval_eye(d, EYE_R, w=175, h=225)
        _draw_brows(d, "angry")
        d.rounded_rectangle([800, 1295, 1248, 1465], radius=46, fill=WHITE, outline=INK, width=34)
        d.line([(812, 1380), (1236, 1380)], fill=INK, width=18)
        for tx in (912, 1024, 1136):
            d.line([(tx, 1306), (tx, 1454)], fill=INK, width=16)

    elif emotion == "FURIOUS":
        _draw_oval_eye(d, EYE_L, w=165, h=205)
        _draw_oval_eye(d, EYE_R, w=165, h=205)
        _draw_brows(d, "angry")
        vx, vy = 1615, 570
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            d.arc([vx - 60 + dx * 42, vy - 60 + dy * 42, vx + 60 + dx * 42, vy + 60 + dy * 42], 0, 360, fill=FURIOUS_RED, width=24)
        _draw_open_oval_mouth(d, MOUTH_X, MOUTH_Y + 35, w=430, h=290)

    elif emotion == "SAD":
        _draw_oval_eye(d, EYE_L, w=185, h=250)
        _draw_oval_eye(d, EYE_R, w=185, h=250)
        _draw_brows(d, "sad")
        d.arc([MOUTH_X - 180, MOUTH_Y - 10, MOUTH_X + 180, MOUTH_Y + 170], start=195, end=345, fill=INK, width=36)

    elif emotion == "CRYING":
        for cx in (EYE_L, EYE_R):
            d.rounded_rectangle([cx - 88, EYE_Y + 20, cx + 88, 1730], radius=44, fill=(108, 212, 255, 232))
            d.line([(cx - 38, EYE_Y + 60), (cx - 38, 1680)], fill=(255, 255, 255, 195), width=20)
            _draw_crescent_eye(d, cx, cy=EYE_Y + 25, w=250, h=190)
        _draw_brows(d, "sad")
        _draw_open_oval_mouth(d, MOUTH_X, MOUTH_Y + 45, w=360, h=270)

    elif emotion == "SCREAM":
        _draw_circle_eye(d, EYE_L, r=162, pupil_r=30)
        _draw_circle_eye(d, EYE_R, r=162, pupil_r=30)
        _draw_brows(d, "shock")
        _draw_sweat_drop(d, 1650, 680, scale=1.1)
        _draw_open_oval_mouth(d, MOUTH_X, MOUTH_Y + 45, w=430, h=380)

    elif emotion == "SUSPICIOUS":
        _draw_oval_eye(d, EYE_L, w=185, h=210, look_x=-26, half_lid=True, lid_y_offset=-8)
        _draw_oval_eye(d, EYE_R, w=185, h=245, look_x=-26)
        _draw_brows(d, "suspicious")
        d.line([(MOUTH_X - 145, MOUTH_Y + 10), (MOUTH_X + 150, MOUTH_Y - 22)], fill=INK, width=36)

    elif emotion == "DETERMINED":
        _draw_oval_eye(d, EYE_L, w=175, h=235)
        _draw_oval_eye(d, EYE_R, w=175, h=235)
        _draw_brows(d, "angry")
        d.line([(MOUTH_X - 165, MOUTH_Y + 5), (MOUTH_X + 165, MOUTH_Y - 12)], fill=INK, width=38)

    elif emotion == "SLEEPY":
        for cx in (EYE_L, EYE_R):
            d.arc([cx - 130, EYE_Y - 40, cx + 130, EYE_Y + 125], start=10, end=170, fill=INK, width=38)
        _draw_brows(d, "calm")
        _draw_open_oval_mouth(d, MOUTH_X, MOUTH_Y + 15, w=170, h=150)

    elif emotion == "CONFUSED":
        _draw_oval_eye(d, EYE_L, w=180, h=240, look_x=-18)
        _draw_oval_eye(d, EYE_R, w=195, h=265, look_x=18, look_y=-14)
        _draw_brows(d, "confused")
        pts = [(840, MOUTH_Y + 10), (945, MOUTH_Y - 30), (1055, MOUTH_Y + 25), (1185, MOUTH_Y - 20)]
        d.line(pts, fill=INK, width=34, joint="curve")
        # Small cartoon confusion swirl near upper right inside safe margin
        sx, sy = 1605, 535
        for rad, sa, ea in ((92, 20, 290), (54, 60, 330)):
            d.arc([sx - rad, sy - rad, sx + rad, sy + rad], start=sa, end=ea, fill=INK, width=22)

    return im.resize((1024, 1024), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols, rows, cell = 4, 4, 1024
    atlas = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
    atlas_map: dict[str, list[int]] = {}

    for slot, em in enumerate(EMOTIONS):
        tile = render_face(em)
        tile.save(OUT_DIR / f"{em}.png", "PNG")
        c = slot % cols
        r_top = slot // cols
        atlas.paste(tile, (c * cell, r_top * cell))
        # Blender UV space has V=0 at bottom and V=1 at top -> row_uv = (rows - 1) - r_top
        atlas_map[em] = [c, (rows - 1) - r_top]

    atlas.save(OUT_DIR / "cartoon_face_atlas.png", "PNG")
    (OUT_DIR / "cartoon_face_atlas_map.json").write_text(
        json.dumps({"cols": cols, "rows": rows, "faces": atlas_map}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved 4x4 4096x4096 cartoon_face_atlas.png + cartoon_face_atlas_map.json ({len(EMOTIONS)} emotions)")


if __name__ == "__main__":
    main()
