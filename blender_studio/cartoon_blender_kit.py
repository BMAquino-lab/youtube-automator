"""Reusable Blender 4.2 LTS 2D-on-3D Stickman & Miniature Diorama Studio Kit (@aiwithcb / Fivestack style).

Provides:
  - EEVEE Next scene setup with GPU Bloom compositor, Standard vibrant color management, & H.264 MP4 output
  - Inverted-hull crisp black ink outline shader & modifier (`add_ink_outline`)
  - Stylized toon shaders + reusable Roblox PBR shader loader + high-DPI image prop shader
  - Parametric rigged 2D-on-3D `StickmanActor` (pure white sphere head, spherical 16-emotion UV face atlas,
    solid capsule torso, dark ink articulated stick arms/legs, modular 3D hats/vests/props, and pose helpers)
  - Quaternion-safe miniature diorama camera & DOF animation helpers
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import bpy
import bmesh
import mathutils

STUDIO_DIR = Path(__file__).resolve().parent
FACES_DIR = STUDIO_DIR / "assets" / "faces"
MATS_DIR = Path(os.environ.get("ROBLOX_MATS_DIR", str(STUDIO_DIR.parent.parent / "01-roblox-shorts" / "blender_studio" / "assets" / "materials" / "modern")))
ATLAS_META = json.loads((FACES_DIR / "cartoon_face_atlas_map.json").read_text(encoding="utf-8"))


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(hex_str: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    h = hex_str.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), alpha)


def get_or_create_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    target_parent = parent or bpy.context.scene.collection
    target_parent.children.link(col)
    return col


def link_to_collection(obj: bpy.types.Object, col: bpy.types.Collection | None) -> None:
    target = col or bpy.context.scene.collection
    if obj.name not in target.objects:
        target.objects.link(obj)
    for other in list(obj.users_collection):
        if other != target:
            other.objects.unlink(obj)


def clear_object_anim(owner) -> None:
    if owner and getattr(owner, "animation_data", None):
        owner.animation_data_clear()


def _load_image_cached(path: Path, non_color: bool = False) -> bpy.types.Image:
    key = f"{path.stem}_{'nc' if non_color else 'srgb'}_{abs(hash(str(path))) % 10000}"
    if key in bpy.data.images:
        return bpy.data.images[key]
    img = bpy.data.images.load(str(path))
    img.name = key
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def reset_scene(
    fps: int = 24,
    width: int = 720,
    height: int = 1280,
    samples: int = 8,
    bloom: bool = False,
    bloom_quality: str = "LOW",
) -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.render.fps = fps
    scn.render.resolution_x = width
    scn.render.resolution_y = height
    scn.render.resolution_percentage = 100
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.eevee.taa_render_samples = samples
    scn.eevee.use_raytracing = False
    scn.eevee.use_shadows = True
    if hasattr(scn.eevee, "use_shadow_jitter_viewport"):
        scn.eevee.use_shadow_jitter_viewport = False
    if hasattr(scn.eevee, "shadow_ray_count"):
        scn.eevee.shadow_ray_count = 1
    if hasattr(scn.eevee, "shadow_step_count"):
        scn.eevee.shadow_step_count = 6
    if hasattr(scn.eevee, "use_taa_reprojection"):
        scn.eevee.use_taa_reprojection = False

    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "Medium High Contrast"
    scn.view_settings.exposure = 0.05

    world = bpy.data.worlds.new("DioramaSky")
    scn.world = world
    setup_world_sky("#1E2B48", "#35496E", strength=0.65)

    if bloom:
        scn.use_nodes = True
        if hasattr(scn.render, "compositor_device"):
            scn.render.compositor_device = "GPU"
        nt = scn.node_tree
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        gl = nt.nodes.new("CompositorNodeGlare")
        gl.glare_type = "BLOOM"
        if hasattr(gl, "quality"):
            gl.quality = bloom_quality
        gl.threshold = 2.2
        gl.size = 6 if bloom_quality == "LOW" else 7
        gl.mix = -0.55
        comp = nt.nodes.new("CompositorNodeComposite")
        nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
        nt.links.new(gl.outputs["Image"], comp.inputs["Image"])

    return scn


def configure_mp4_output(scn: bpy.types.Scene, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "HIGH"
    scn.render.ffmpeg.ffmpeg_preset = "REALTIME"
    scn.render.filepath = str(filepath)


def setup_world_sky(top_hex: str, horizon_hex: str, strength: float = 0.65) -> None:
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("DioramaSky")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.44
    ramp.color_ramp.elements[0].color = hex_rgba(horizon_hex)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = hex_rgba(top_hex)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def get_ink_outline_mat() -> bpy.types.Material:
    if "Ink_Outline" in bpy.data.materials:
        return bpy.data.materials["Ink_Outline"]
    mat = bpy.data.materials.new("Ink_Outline")
    mat.use_nodes = True
    mat.use_backface_culling = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba("#141010")
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def add_ink_outline(obj: bpy.types.Object, thickness: float = 0.036) -> bpy.types.Modifier:
    if len(obj.data.materials) == 0:
        obj.data.materials.append(make_toon_mat(f"{obj.name}_Base", "#DDDDDD"))
    outline = get_ink_outline_mat()
    if len(obj.data.materials) == 1:
        obj.data.materials.append(outline)
    else:
        obj.data.materials[1] = outline
    mod = obj.modifiers.get("InkOutline") or obj.modifiers.new("InkOutline", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.material_offset = 1
    return mod


def make_toon_mat(name: str, hex_color: str, emission_lift: float = 0.14, roughness: float = 0.82) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    rgba = hex_rgba(hex_color)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Specular IOR Level"].default_value = 0.08
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission_lift
    return mat


def make_cel_cutout_mat(
    name: str,
    lit_hex: str = "#FCFBF8",
    shadow_hex: str = "#DFDDD6",
    cutoff: float = 0.28,
) -> bpy.types.Material:
    """Zero-grain 2-tone cel cutout shader immune to sky ambient blue wash (with animatable HeadTint node)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    s2r = nodes.new("ShaderNodeShaderToRGB")
    links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    ramp.color_ramp.elements[0].position = max(0.02, cutoff - 0.06)
    ramp.color_ramp.elements[0].color = hex_rgba(shadow_hex)
    ramp.color_ramp.elements[1].position = min(0.98, cutoff + 0.06)
    ramp.color_ramp.elements[1].color = hex_rgba(lit_hex)
    links.new(s2r.outputs["Color"], ramp.inputs["Fac"])

    tint = nodes.new("ShaderNodeRGB")
    tint.name = "HeadTint"
    tint.label = "HeadTint"
    tint.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)

    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    links.new(ramp.outputs["Color"], mix.inputs[6])
    links.new(tint.outputs[0], mix.inputs[7])

    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.96
    links.new(mix.outputs[2], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def make_emissive_mat(name: str, hex_color: str, strength: float = 4.0) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(hex_color)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def make_pbr_mat(
    name: str,
    mat_name: str,
    tint_hex: str = "#FFFFFF",
    uv_scale: float = 3.0,
    roughness_bias: float = 0.0,
    emission_lift: float = 0.12,
) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    folder = MATS_DIR / mat_name
    if not (folder / "color.png").exists():
        return make_toon_mat(name, tint_hex, emission_lift=0.05, roughness=0.55)

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    bsdf = nodes.get("Principled BSDF")

    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])

    col_tex = nodes.new("ShaderNodeTexImage")
    col_tex.image = _load_image_cached(folder / "color.png", non_color=False)
    col_tex.projection = "BOX"
    col_tex.projection_blend = 0.15
    links.new(mapping.outputs["Vector"], col_tex.inputs["Vector"])

    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs[6].default_value = hex_rgba(tint_hex)
    links.new(col_tex.outputs["Color"], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    if emission_lift > 0.0 and "Emission Color" in bsdf.inputs:
        links.new(mix.outputs[2], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission_lift

    if (folder / "roughness.png").exists():
        r_tex = nodes.new("ShaderNodeTexImage")
        r_tex.image = _load_image_cached(folder / "roughness.png", non_color=True)
        r_tex.projection = "BOX"
        links.new(mapping.outputs["Vector"], r_tex.inputs["Vector"])
        if abs(roughness_bias) > 1e-4:
            add_n = nodes.new("ShaderNodeMath")
            add_n.operation = "ADD"
            add_n.use_clamp = True
            add_n.inputs[1].default_value = roughness_bias
            links.new(r_tex.outputs["Color"], add_n.inputs[0])
            links.new(add_n.outputs["Value"], bsdf.inputs["Roughness"])
        else:
            links.new(r_tex.outputs["Color"], bsdf.inputs["Roughness"])

    if (folder / "normal.png").exists():
        n_tex = nodes.new("ShaderNodeTexImage")
        n_tex.image = _load_image_cached(folder / "normal.png", non_color=True)
        n_tex.projection = "BOX"
        links.new(mapping.outputs["Vector"], n_tex.inputs["Vector"])
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.65
        links.new(n_tex.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def make_image_mat(name: str, image_path: Path, emission: float = 0.12, roughness: float = 0.55) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Specular IOR Level"].default_value = 0.12

    tc = nodes.new("ShaderNodeTexCoord")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = _load_image_cached(Path(image_path), non_color=False)
    tex.extension = "CLIP"
    links.new(tc.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if emission > 0 and "Emission Color" in bsdf.inputs:
        links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def _smooth_mesh(obj: bpy.types.Object) -> None:
    for p in obj.data.polygons:
        p.use_smooth = True


def add_box(
    name: str,
    size: tuple[float, float, float],
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    bevel: float = 0.02,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    outline: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        bv = o.modifiers.new("Bevel", "BEVEL")
        bv.width = bevel
        bv.segments = 2
        bpy.ops.object.modifier_apply(modifier=bv.name)
    _smooth_mesh(o)
    o.data.materials.append(mat)
    if outline > 0:
        add_ink_outline(o, thickness=outline)
    link_to_collection(o, col)
    return o


def add_uv_plane(
    name: str,
    width: float,
    height: float,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Create a vertical XY/XZ quad facing +Y (rot=(0,0,0)) with clean 0..1 UVs."""
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    hw, hh = width * 0.5, height * 0.5
    # Facing +Y: viewer at +Y sees -X on right and +X on left!
    # So u=0 is at +hw (screen left) and u=1 is at -hw (screen right)
    v0 = bm.verts.new((hw, 0.0, -hh))
    v1 = bm.verts.new((-hw, 0.0, -hh))
    v2 = bm.verts.new((-hw, 0.0, hh))
    v3 = bm.verts.new((hw, 0.0, hh))
    face = bm.faces.new((v0, v1, v2, v3))
    for loop, coords in zip(face.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        loop[uv].uv = coords
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    obj.data.materials.append(mat)
    link_to_collection(obj, col)
    return obj


def add_warm_lantern(
    name: str,
    loc: tuple[float, float, float],
    col: bpy.types.Collection | None = None,
    color_hex: str = "#FFAC4B",
    energy: float = 42.0,
    radius: float = 0.22,
    light_radius: float = 0.25,
) -> tuple[bpy.types.Object, bpy.types.Object]:
    m_brass = make_toon_mat("Lantern_Brass", "#8E6A28", emission_lift=0.05, roughness=0.35)
    m_glow = make_emissive_mat("Lantern_Glow", color_hex, strength=5.5)

    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius * 0.55, depth=radius * 1.15, location=loc)
    glass = bpy.context.active_object
    glass.name = f"{name}_Glass"
    glass.data.materials.append(m_glow)
    _smooth_mesh(glass)
    if hasattr(glass, "visible_shadow"):
        glass.visible_shadow = False

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=radius * 0.78, depth=radius * 0.22, location=(loc[0], loc[1], loc[2] + radius * 0.68)
    )
    cap = bpy.context.active_object
    cap.name = f"{name}_Cap"
    cap.data.materials.append(m_brass)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=radius * 0.72, depth=radius * 0.20, location=(loc[0], loc[1], loc[2] - radius * 0.68)
    )
    base = bpy.context.active_object
    base.name = f"{name}_Base"
    base.data.materials.append(m_brass)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    for part in (cap, base):
        part.select_set(True)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.join()
    frame = bpy.context.active_object
    frame.name = f"{name}_Frame"
    add_ink_outline(frame, thickness=0.015)

    ldata = bpy.data.lights.new(f"{name}_Light", type="POINT")
    ldata.energy = energy
    ldata.color = hex_rgba(color_hex)[:3]
    ldata.shadow_soft_size = light_radius
    lobj = bpy.data.objects.new(f"{name}_Light", ldata)
    lobj.location = loc

    for o in (glass, frame, lobj):
        link_to_collection(o, col)
    return frame, lobj


def add_floating_motes(
    name: str,
    center: tuple[float, float, float],
    half_extents: tuple[float, float, float],
    col: bpy.types.Collection | None = None,
    count: int = 24,
    color_hex: str = "#FFE29A",
    frame_end: int = 100,
    seed: int = 17,
) -> list[bpy.types.Object]:
    import random

    rng = random.Random(seed)
    mat = make_emissive_mat(f"{name}_MoteMat", color_hex, strength=2.6)
    motes: list[bpy.types.Object] = []
    for i in range(count):
        x0 = center[0] + rng.uniform(-half_extents[0], half_extents[0])
        y0 = center[1] + rng.uniform(-half_extents[1], half_extents[1])
        z0 = center[2] + rng.uniform(-half_extents[2], half_extents[2])
        r = rng.uniform(0.014, 0.028)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r, location=(x0, y0, z0))
        m = bpy.context.active_object
        m.name = f"{name}_m{i:02d}"
        m.data.materials.append(mat)
        if hasattr(m, "visible_shadow"):
            m.visible_shadow = False
        link_to_collection(m, col)

        dx = rng.uniform(-0.18, 0.18)
        dz = rng.uniform(0.18, 0.42)
        m.location = (x0, y0, z0)
        m.keyframe_insert(data_path="location", frame=1)
        m.location = (x0 + dx, y0 + rng.uniform(-0.08, 0.08), z0 + dz)
        m.keyframe_insert(data_path="location", frame=max(2, frame_end))
        for fc in m.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        motes.append(m)
    return motes


def add_cylinder(
    name: str,
    radius: float,
    depth: float,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    vertices: int = 16,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    outline: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _smooth_mesh(o)
    o.data.materials.append(mat)
    if outline > 0:
        add_ink_outline(o, thickness=outline)
    link_to_collection(o, col)
    return o


def add_sphere(
    name: str,
    radius: float,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    segments: int = 16,
    rings: int = 12,
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    outline: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _smooth_mesh(o)
    o.data.materials.append(mat)
    if outline > 0:
        add_ink_outline(o, thickness=outline)
    link_to_collection(o, col)
    return o


def add_cone(
    name: str,
    radius1: float,
    radius2: float,
    depth: float,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    vertices: int = 16,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    outline: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2, depth=depth, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    _smooth_mesh(o)
    o.data.materials.append(mat)
    if outline > 0:
        add_ink_outline(o, thickness=outline)
    link_to_collection(o, col)
    return o


def add_torus(
    name: str,
    major_radius: float,
    minor_radius: float,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    col: bpy.types.Collection | None = None,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    outline: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_segments=28,
        minor_segments=10,
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=loc,
    )
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    _smooth_mesh(o)
    o.data.materials.append(mat)
    if outline > 0:
        add_ink_outline(o, thickness=outline)
    link_to_collection(o, col)
    return o


def add_cinematic_3point_rig(
    name: str,
    col: bpy.types.Collection | None = None,
    *,
    key_loc: tuple[float, float, float] = (3.4, 4.8, 4.4),
    fill_loc: tuple[float, float, float] = (-3.8, 4.2, 2.6),
    rim_loc: tuple[float, float, float] = (0.0, -3.6, 3.3),
    key_color: str = "#FFE6C2",
    fill_color: str = "#9AC2FF",
    rim_color: str = "#FFCF7A",
    key_energy: float = 190.0,
    fill_energy: float = 75.0,
    rim_energy: float = 210.0,
) -> list[bpy.types.Object]:
    """Create a 3-point key/fill/rim area+point light rig for strong stylized silhouette separation."""
    objs: list[bpy.types.Object] = []
    specs = [
        ("Key", "AREA", key_loc, key_color, key_energy, 3.2),
        ("Fill", "AREA", fill_loc, fill_color, fill_energy, 4.0),
        ("Rim", "AREA", rim_loc, rim_color, rim_energy, 2.8),
    ]
    center = mathutils.Vector((0.0, 0.0, 1.5))
    for tag, ltype, loc, hx, energy, size in specs:
        ld = bpy.data.lights.new(f"{name}_{tag}", type=ltype)
        ld.energy = energy
        ld.color = hex_rgba(hx)[:3]
        if ltype == "AREA":
            ld.size = size
        lo = bpy.data.objects.new(f"{name}_{tag}", ld)
        lo.location = loc
        lo.rotation_mode = "QUATERNION"
        lo.rotation_quaternion = (center - mathutils.Vector(loc)).to_track_quat("-Z", "Y")
        link_to_collection(lo, col)
        objs.append(lo)
    return objs


def add_atmospheric_haze_planes(
    name: str,
    col: bpy.types.Collection | None = None,
    *,
    count: int = 3,
    center: tuple[float, float, float] = (0.0, -3.0, 1.6),
    y_step: float = -1.6,
    width: float = 11.0,
    height: float = 4.2,
    hex_color: str = "#A8C0E0",
    alpha: float = 0.16,
    frame_end: int = 60,
) -> list[bpy.types.Object]:
    """Soft translucent atmospheric depth bands with subtle horizontal drift."""
    mat = bpy.data.materials.new(f"{name}_HazeMat")
    mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_rgba(hex_color)
    bsdf.inputs["Roughness"].default_value = 1.0
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = hex_rgba(hex_color)
        bsdf.inputs["Emission Strength"].default_value = 0.55

    # Soft UV-based oval fade so edges never show hard card rectangles
    uv = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "QUADRATIC_SPHERE"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (-1.0, -1.0, 0.0)
    mp.inputs["Scale"].default_value = (2.0, 2.0, 1.0)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = alpha
    nt.links.new(grad.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    planes: list[bpy.types.Object] = []
    for i in range(count):
        px = center[0] + (0.6 if i % 2 else -0.6)
        py = center[1] + i * y_step
        pz = center[2] + i * 0.25
        p = add_uv_plane(f"{name}_Haze{i:02d}", width, height, (px, py, pz), mat, col)
        if hasattr(p, "visible_shadow"):
            p.visible_shadow = False
        drift = 0.45 if i % 2 == 0 else -0.45
        p.location = (px, py, pz)
        p.keyframe_insert(data_path="location", frame=1)
        p.location = (px + drift, py, pz + 0.08)
        p.keyframe_insert(data_path="location", frame=max(2, frame_end))
        planes.append(p)
    return planes


def add_sunlit_sky_rig(
    name: str,
    col: bpy.types.Collection | None = None,
    *,
    sun_rot_deg: tuple[float, float, float] = (48.0, 12.0, -32.0),
    sun_energy: float = 2.3,
    sun_color: str = "#FFF1D0",
    sky_top: str = "#2164C8",
    sky_horizon: str = "#78BAF5",
    sky_strength: float = 0.82,
    sun_disc_loc: tuple[float, float, float] | None = (-5.5, -14.0, 9.5),
) -> list[bpy.types.Object]:
    """Bright @RicksClips3000-style daylight / golden-hour sky dome, crisp shadow SUN, and zero-cost sun halo."""
    setup_world_sky(sky_top, sky_horizon, strength=sky_strength)
    objs: list[bpy.types.Object] = []
    sd = bpy.data.lights.new(f"{name}_Sun", type="SUN")
    sd.energy = sun_energy
    sd.color = hex_rgba(sun_color)[:3]
    sd.angle = math.radians(1.0)
    so = bpy.data.objects.new(f"{name}_Sun", sd)
    so.location = (0.0, 0.0, 8.0)
    so.rotation_euler = tuple(math.radians(a) for a in sun_rot_deg)
    link_to_collection(so, col)
    objs.append(so)

    # Warm balanced fill so cutout stickmen & props stay clean without blue ambient tint
    fd = bpy.data.lights.new(f"{name}_SkyFill", type="AREA")
    fd.energy = 42.0
    fd.color = hex_rgba("#FFF4E0")[:3]
    fd.size = 8.0
    fo = bpy.data.objects.new(f"{name}_SkyFill", fd)
    fo.location = (2.5, 6.5, 3.8)
    fo.rotation_mode = "QUATERNION"
    fo.rotation_quaternion = (mathutils.Vector((0.0, 0.0, 1.4)) - fo.location).to_track_quat("-Z", "Y")
    link_to_collection(fo, col)
    objs.append(fo)

    if sun_disc_loc is not None:
        m_sun = make_emissive_mat(f"{name}_SunDiscMat", "#FFF9E2", strength=1.35)
        disc = add_sphere(f"{name}_SunDisc", 1.30, sun_disc_loc, m_sun, col, segments=20, rings=14)
        if hasattr(disc, "visible_shadow"):
            disc.visible_shadow = False
        objs.append(disc)
        # Soft smooth radial sun halo using Layer Weight Facing -> EASE falloff to 0 at rim (zero compositor glare)
        m_halo = bpy.data.materials.new(f"{name}_SunHaloMat")
        m_halo.use_nodes = True
        if hasattr(m_halo, "surface_render_method"):
            m_halo.surface_render_method = "BLENDED"
        nt = m_halo.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        hramp = nt.nodes.new("ShaderNodeValToRGB")
        hramp.color_ramp.interpolation = "EASE"
        hramp.color_ramp.elements[0].position = 0.0
        hramp.color_ramp.elements[0].color = (0.42, 0.42, 0.42, 1.0)
        hramp.color_ramp.elements[1].position = 0.72
        hramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
        nt.links.new(lw.outputs["Facing"], hramp.inputs["Fac"])

        mix_h = nt.nodes.new("ShaderNodeMixShader")
        tr_h = nt.nodes.new("ShaderNodeBsdfTransparent")
        em_h = nt.nodes.new("ShaderNodeEmission")
        em_h.inputs["Color"].default_value = hex_rgba("#FFF2B8")
        em_h.inputs["Strength"].default_value = 1.15
        nt.links.new(hramp.outputs["Color"], mix_h.inputs["Fac"])
        nt.links.new(tr_h.outputs["BSDF"], mix_h.inputs[1])
        nt.links.new(em_h.outputs["Emission"], mix_h.inputs[2])
        nt.links.new(mix_h.outputs["Shader"], out.inputs["Surface"])
        halo = add_sphere(f"{name}_SunHalo", 2.05, sun_disc_loc, m_halo, col, segments=24, rings=16)
        if hasattr(halo, "visible_shadow"):
            halo.visible_shadow = False
        objs.append(halo)
    return objs


def _build_capsule_mesh(name: str, radius: float, cyl_h: float, segs: int = 24, rings: int = 16) -> bpy.types.Mesh:
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    half = cyl_h * 0.5
    for v in bm.verts:
        if v.co.z > 0.001:
            v.co.z += half
        elif v.co.z < -0.001:
            v.co.z -= half
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    return mesh


def _build_stick_segment(
    name: str,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    radius: float,
    end_ball_r: float = 0.0,
) -> bpy.types.Object:
    v0 = mathutils.Vector(p0)
    v1 = mathutils.Vector(p1)
    diff = v1 - v0
    length = diff.length
    mid = (v0 + v1) * 0.5

    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=max(0.02, length), location=mid)
    cyl = bpy.context.active_object
    cyl.rotation_mode = "QUATERNION"
    cyl.rotation_quaternion = diff.normalized().to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    parts = [cyl]

    if end_ball_r > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=end_ball_r, location=p1)
        parts.append(bpy.context.active_object)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=radius * 1.04, location=p0)
    parts.append(bpy.context.active_object)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = cyl
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    _smooth_mesh(obj)
    obj.select_set(False)
    return obj


def _build_spherical_face_patch(actor_name: str, head_z: float = 2.04, radius: float = 0.562) -> tuple[bpy.types.Object, bpy.types.Node, bpy.types.Node]:
    """Spherical front face decal hugging the white sphere head on +Y with CONSTANT atlas switching."""
    mesh = bpy.data.meshes.new(f"{actor_name}_FaceMesh")
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    segs, rows = 20, 12
    ang_l = math.radians(90.0 - 48.0)  # +X (screen left when looking from +Y) -> u=0
    ang_r = math.radians(90.0 + 48.0)  # -X (screen right when looking from +Y) -> u=1
    phi_bot = math.radians(-36.0)
    phi_top = math.radians(40.0)

    grid = []
    for r in range(rows + 1):
        vf = r / rows
        phi = phi_bot + vf * (phi_top - phi_bot)
        z = head_z + radius * math.sin(phi)
        rho = radius * math.cos(phi)
        row_v = []
        for s in range(segs + 1):
            uf = s / segs
            th = ang_l + uf * (ang_r - ang_l)
            row_v.append((bm.verts.new((rho * math.cos(th), rho * math.sin(th), z)), uf, vf))
        grid.append(row_v)

    for r in range(rows):
        for s in range(segs):
            v00, u00, fv00 = grid[r][s]
            v10, u10, fv10 = grid[r][s + 1]
            v11, u11, fv11 = grid[r + 1][s + 1]
            v01, u01, fv01 = grid[r + 1][s]
            # (-X) x (+Z) = +Y outward normal
            face = bm.faces.new((v00, v10, v11, v01))
            face.smooth = True
            for loop, uv in zip(face.loops, ((u00, fv00), (u10, fv10), (u11, fv11), (u01, fv01))):
                loop[uv_layer].uv = uv

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(f"{actor_name}_Face", mesh)
    bpy.context.collection.objects.link(obj)
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False

    mat = bpy.data.materials.new(f"{actor_name}_FaceMat")
    mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False

    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    mix_sh = nodes.new("ShaderNodeMixShader")
    transp = nodes.new("ShaderNodeBsdfTransparent")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    links.new(transp.outputs["BSDF"], mix_sh.inputs[1])
    links.new(em.outputs["Emission"], mix_sh.inputs[2])
    links.new(mix_sh.outputs["Shader"], out.inputs["Surface"])

    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.uv_map = "UVMap"
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv_node.outputs["UV"], sep.inputs["Vector"])

    col_node = nodes.new("ShaderNodeValue")
    col_node.name = "FaceCol"
    col_node.label = "FaceCol"
    col_node.outputs[0].default_value = 0.0

    row_node = nodes.new("ShaderNodeValue")
    row_node.name = "FaceRow"
    row_node.label = "FaceRow"
    row_node.outputs[0].default_value = 4.0

    add_u = nodes.new("ShaderNodeMath")
    add_u.operation = "ADD"
    links.new(sep.outputs["X"], add_u.inputs[0])
    links.new(col_node.outputs[0], add_u.inputs[1])

    div_u = nodes.new("ShaderNodeMath")
    div_u.operation = "DIVIDE"
    div_u.inputs[1].default_value = float(ATLAS_META["cols"])
    links.new(add_u.outputs[0], div_u.inputs[0])

    add_v = nodes.new("ShaderNodeMath")
    add_v.operation = "ADD"
    links.new(sep.outputs["Y"], add_v.inputs[0])
    links.new(row_node.outputs[0], add_v.inputs[1])

    div_v = nodes.new("ShaderNodeMath")
    div_v.operation = "DIVIDE"
    div_v.inputs[1].default_value = float(ATLAS_META["rows"])
    links.new(add_v.outputs[0], div_v.inputs[0])

    comb = nodes.new("ShaderNodeCombineXYZ")
    links.new(div_u.outputs[0], comb.inputs["X"])
    links.new(div_v.outputs[0], comb.inputs["Y"])

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = _load_image_cached(FACES_DIR / "cartoon_face_atlas.png", non_color=False)
    tex.extension = "CLIP"
    tex.interpolation = "Linear"
    links.new(comb.outputs["Vector"], tex.inputs["Vector"])

    links.new(tex.outputs["Alpha"], mix_sh.inputs["Fac"])
    links.new(tex.outputs["Color"], em.inputs["Color"])

    obj.data.materials.append(mat)
    return obj, col_node, row_node


class StickmanActor:
    """Parametric 2D-on-3D cartoon stickman character (~2.45 BU tall, standing on Z=0, facing +Y)."""

    def __init__(
        self,
        name: str,
        *,
        preset: str = "george",
        torso_hex: str | None = None,
        col: bpy.types.Collection | None = None,
    ):
        self.name = name
        self.preset = preset
        self.collection = col
        self.all_objs: list[bpy.types.Object] = []
        self.props: dict[str, bpy.types.Object] = {}

        default_colors = {
            "george": "#227C7E",        # teal wool waistcoat
            "owner": "#D49B26",         # mustard-gold brocade vest
            "foreman": "#EAE4D6",       # cream work shirt under rust-orange suspenders
            "soldier": "#5A6641",       # olive-drab WWII field tunic
            "general": "#4B5836",       # brass-buttoned olive command jacket
            "officer": "#46515E",       # slate-grey German field coat
            "painter": "#354F6B",       # navy artist/marine uniform jacket
            "artist": "#426A8C",        # French artist camouflage smock
            "admiral": "#1D2C44",       # Royal Navy dark coat
            "uboat_captain": "#2A3038", # weathered dark leather U-boat coat
            "crew": "#D9D2C4",          # rolled wool dock/sailor sweater
            "cartographer": "#2C5978",  # Prussian-blue 1930s drafting smock / vest
            "storekeeper": "#9E462C",   # warm rust-brown Catskills country vest
            "naval_engineer": "#2B5B84", # slate-blue WWII naval shipyard engineer jacket
        }
        t_hex = torso_hex or default_colors.get(preset, "#2B7A78")

        m_head = make_cel_cutout_mat(f"{name}_WhiteHead", "#FCFBF8", "#DFDDD6", cutoff=0.28)
        self.head_mat = m_head
        m_torso = make_toon_mat(f"{name}_Torso", t_hex, emission_lift=0.16, roughness=0.78)
        m_ink = make_toon_mat(f"{name}_LimbInk", "#161316", emission_lift=0.04, roughness=0.70)

        # 1) White sphere head (Z=2.04, r=0.55) + bold ink outline (@RicksClips3000 cutout pop)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=18, radius=0.55, location=(0.0, 0.0, 2.04))
        self.head_obj = bpy.context.active_object
        self.head_obj.name = f"{name}_Head"
        _smooth_mesh(self.head_obj)
        self.head_obj.data.materials.append(m_head)
        add_ink_outline(self.head_obj, thickness=0.044)

        # 2) Spherical front face patch (r=0.562)
        self.face_obj, self.face_col_node, self.face_row_node = _build_spherical_face_patch(name, head_z=2.04, radius=0.562)

        # 3) Capsule torso (r=0.33, Z=0.80..1.60) + outline
        t_mesh = _build_capsule_mesh(f"{name}_TorsoMesh", radius=0.33, cyl_h=0.22)
        self.torso_obj = bpy.data.objects.new(f"{name}_Torso", t_mesh)
        self.torso_obj.location = (0.0, 0.0, 1.20)
        bpy.context.collection.objects.link(self.torso_obj)
        bpy.context.view_layer.objects.active = self.torso_obj
        self.torso_obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        self.torso_obj.select_set(False)
        self.torso_obj.data.materials.append(m_torso)
        add_ink_outline(self.torso_obj, thickness=0.038)

        # 4) Thin stick limbs + hands + oval shoes
        self.arm_l_obj = _build_stick_segment(f"{name}_UpperArmL", (-0.33, 0.0, 1.44), (-0.48, 0.02, 1.14), 0.034)
        self.forearm_l_obj = _build_stick_segment(f"{name}_ForearmL", (-0.48, 0.02, 1.14), (-0.54, 0.06, 0.84), 0.032, end_ball_r=0.070)
        self.arm_r_obj = _build_stick_segment(f"{name}_UpperArmR", (0.33, 0.0, 1.44), (0.48, 0.02, 1.14), 0.034)
        self.forearm_r_obj = _build_stick_segment(f"{name}_ForearmR", (0.48, 0.02, 1.14), (0.54, 0.06, 0.84), 0.032, end_ball_r=0.070)

        self.thigh_l_obj = _build_stick_segment(f"{name}_ThighL", (-0.16, 0.0, 0.84), (-0.16, 0.0, 0.44), 0.036)
        self.shin_l_obj = _build_stick_segment(f"{name}_ShinL", (-0.16, 0.0, 0.44), (-0.16, 0.0, 0.06), 0.035)
        self.thigh_r_obj = _build_stick_segment(f"{name}_ThighR", (0.16, 0.0, 0.84), (0.16, 0.0, 0.44), 0.036)
        self.shin_r_obj = _build_stick_segment(f"{name}_ShinR", (0.16, 0.0, 0.44), (0.16, 0.0, 0.06), 0.035)

        for limb in (
            self.arm_l_obj,
            self.forearm_l_obj,
            self.arm_r_obj,
            self.forearm_r_obj,
            self.thigh_l_obj,
            self.shin_l_obj,
            self.thigh_r_obj,
            self.shin_r_obj,
        ):
            limb.data.materials.append(m_ink)

        # Add clean oval shoes joined to shins
        for side_lbl, sx, shin_obj in (("L", -0.16, self.shin_l_obj), ("R", 0.16, self.shin_r_obj)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=10, radius=0.095, location=(sx, 0.08, 0.05))
            shoe = bpy.context.active_object
            shoe.scale = (0.85, 1.45, 0.55)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _smooth_mesh(shoe)
            shoe.data.materials.append(m_ink)
            for o in bpy.context.selected_objects:
                o.select_set(False)
            shin_obj.select_set(True)
            shoe.select_set(True)
            bpy.context.view_layer.objects.active = shin_obj
            bpy.ops.object.join()
            shin_obj.select_set(False)

        # 5) Modular 3D Costume Accessories & Held Props
        head_accs: list[bpy.types.Object] = []
        torso_accs: list[bpy.types.Object] = []
        self._build_costume(preset, head_accs, torso_accs)
        self._build_motion_fx(col)

        # 6) Clean zero-cycle Armature
        arm_data = bpy.data.armatures.new(f"{name}_ArmData")
        self.rig = bpy.data.objects.new(f"{name}_Rig", arm_data)
        bpy.context.collection.objects.link(self.rig)
        bpy.context.view_layer.objects.active = self.rig
        bpy.ops.object.mode_set(mode="EDIT")
        eb = arm_data.edit_bones

        def _bone(bname: str, hx: float, hy: float, hz: float, parent=None):
            b = eb.new(bname)
            b.head = (hx, hy, hz)
            b.tail = (hx, hy + 0.32, hz)
            b.roll = 0.0
            if parent is not None:
                b.parent = parent
            return b

        b_root = _bone("Root", 0.0, 0.0, 0.0)
        b_pelvis = _bone("Pelvis", 0.0, 0.0, 0.84, b_root)
        b_torso = _bone("Torso", 0.0, 0.0, 0.84, b_pelvis)
        b_head = _bone("Head", 0.0, 0.0, 1.54, b_torso)

        b_arm_l = _bone("Arm.L", -0.33, 0.0, 1.44, b_torso)
        _bone("Forearm.L", -0.48, 0.02, 1.14, b_arm_l)
        b_arm_r = _bone("Arm.R", 0.33, 0.0, 1.44, b_torso)
        _bone("Forearm.R", 0.48, 0.02, 1.14, b_arm_r)

        b_thigh_l = _bone("Thigh.L", -0.16, 0.0, 0.84, b_pelvis)
        _bone("Shin.L", -0.16, 0.0, 0.44, b_thigh_l)
        b_thigh_r = _bone("Thigh.R", 0.16, 0.0, 0.84, b_pelvis)
        _bone("Shin.R", 0.16, 0.0, 0.44, b_thigh_r)

        bpy.ops.object.mode_set(mode="OBJECT")
        for pb in self.rig.pose.bones:
            pb.rotation_mode = "XYZ"

        bindings = [
            (self.head_obj, "Head"),
            (self.face_obj, "Head"),
            (self.torso_obj, "Torso"),
            (self.arm_l_obj, "Arm.L"),
            (self.forearm_l_obj, "Forearm.L"),
            (self.arm_r_obj, "Arm.R"),
            (self.forearm_r_obj, "Forearm.R"),
            (self.thigh_l_obj, "Thigh.L"),
            (self.shin_l_obj, "Shin.L"),
            (self.thigh_r_obj, "Thigh.R"),
            (self.shin_r_obj, "Shin.R"),
        ]
        for o in head_accs:
            bindings.append((o, "Head"))
        for o in torso_accs:
            bindings.append((o, "Torso"))
        bindings.append((self.fx_head_root, "Head"))
        bindings.append((self.fx_torso_root, "Torso"))
        for p_name, p_obj in self.props.items():
            b = "Forearm.R" if p_name in ("whistle_hand", "turning_bar", "trowel", "binoculars", "pointer_stick", "paintbrush", "telescope", "magnifying_glass") else "Forearm.L"
            bindings.append((p_obj, b))

        self.all_objs = [self.rig] + [o for o, _ in bindings] + self._all_fx_objs()
        for child, bname in bindings:
            mw = child.matrix_world.copy()
            child.parent = self.rig
            child.parent_type = "BONE"
            child.parent_bone = bname
            child.matrix_world = mw
            link_to_collection(child, col)

        link_to_collection(self.rig, col)
        # Hide optional held hand props & v5 comic FX by default; scenes turn them on when needed
        for pname in self.props:
            self.set_prop_visible(pname, False)
        for fx_obj in self._all_fx_objs():
            fx_obj.hide_render = True
            fx_obj.hide_viewport = True

    def _build_costume(
        self,
        preset: str,
        head_accs: list[bpy.types.Object],
        torso_accs: list[bpy.types.Object],
    ) -> None:
        m_dark_hat = make_toon_mat(f"{self.name}_HatDark", "#201E24", emission_lift=0.08, roughness=0.72)
        m_gold = make_toon_mat(f"{self.name}_Gold", "#E4B238", emission_lift=0.16, roughness=0.32)
        m_brass = make_toon_mat(f"{self.name}_Brass", "#D6A134", emission_lift=0.14, roughness=0.35)
        m_hair = make_toon_mat(f"{self.name}_Beard", "#332218", emission_lift=0.05, roughness=0.82)
        m_white_col = make_toon_mat(f"{self.name}_Collar", "#F5F2EA", emission_lift=0.15, roughness=0.75)

        def _finish(obj: bpy.types.Object, mat: bpy.types.Material, outline: float = 0.022, dest=head_accs):
            _smooth_mesh(obj)
            obj.data.materials.append(mat)
            if outline > 0:
                add_ink_outline(obj, thickness=outline)
            dest.append(obj)
            return obj

        if preset == "george":
            # Tall black stovepipe top hat + dark teal ribbon
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.58, depth=0.055, location=(0.0, -0.02, 2.46))
            brim = bpy.context.active_object
            brim.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(brim, m_dark_hat, 0.022, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.41, depth=0.66, location=(0.0, -0.05, 2.78))
            crown = bpy.context.active_object
            crown.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(crown, m_dark_hat, 0.024, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.422, depth=0.11, location=(0.0, -0.03, 2.54))
            band = bpy.context.active_object
            band.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(band, make_toon_mat(f"{self.name}_HatBand", "#195256", 0.12), 0.0, head_accs)

            # Neat closed-manifold chinstrap beard hugging lower jaw curvature cleanly (r_jaw ~ 0.425 at z=1.75)
            bpy.ops.mesh.primitive_torus_add(
                major_segments=28, minor_segments=10, major_radius=0.42, minor_radius=0.056, location=(0.0, 0.02, 1.75)
            )
            beard = bpy.context.active_object
            beard.rotation_euler = (math.radians(-14.0), 0.0, 0.0)
            _finish(beard, m_hair, 0.014, head_accs)

            # White shirt collar V + vest buttons + brass whistle hanging on chest
            for bx in (-0.08, 0.08):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, 0.25, 1.54))
                col_wing = bpy.context.active_object
                col_wing.scale = (0.14, 0.12, 0.11)
                col_wing.rotation_euler = (math.radians(15), 0.0, math.radians(-22 if bx > 0 else 22))
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                _finish(col_wing, m_white_col, 0.015, torso_accs)

            for bz in (1.36, 1.18, 1.00):
                bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.038, location=(0.0, 0.33, bz))
                _finish(bpy.context.active_object, m_dark_hat, 0.0, torso_accs)

            # Neck cord + brass whistle on chest
            bpy.ops.mesh.primitive_torus_add(major_segments=20, minor_segments=8, major_radius=0.22, minor_radius=0.015, location=(0.0, 0.16, 1.47))
            cord = bpy.context.active_object
            cord.rotation_euler = (math.radians(58.0), 0.0, 0.0)
            _finish(cord, m_dark_hat, 0.0, torso_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=0.14, location=(0.03, 0.35, 1.32))
            whistle = bpy.context.active_object
            whistle.rotation_euler = (math.radians(75.0), math.radians(20.0), 0.0)
            _finish(whistle, m_brass, 0.016, torso_accs)

            # Held props for George (Forearm.R = whistle, Forearm.L = rolled blueprint)
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=0.18, location=(0.54, 0.12, 0.84))
            wh_hand = bpy.context.active_object
            wh_hand.name = f"{self.name}_PropWhistleHand"
            wh_hand.rotation_euler = (math.radians(85.0), 0.0, math.radians(15.0))
            _smooth_mesh(wh_hand)
            wh_hand.data.materials.append(m_brass)
            add_ink_outline(wh_hand, 0.016)
            self.props["whistle_hand"] = wh_hand

            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.068, depth=0.62, location=(-0.54, 0.16, 0.84))
            bp = bpy.context.active_object
            bp.name = f"{self.name}_PropBlueprint"
            bp.rotation_euler = (math.radians(78.0), math.radians(18.0), 0.0)
            _smooth_mesh(bp)
            bp.data.materials.append(make_toon_mat(f"{self.name}_BlueprintBlue", "#2868B8", 0.14))
            add_ink_outline(bp, 0.018)
            self.props["blueprint"] = bp

        elif preset == "owner":
            # Burgundy velvet smoking cap + gold band + tassel
            m_cap = make_toon_mat(f"{self.name}_SmokingCap", "#781B2C", 0.12, roughness=0.78)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.43, depth=0.30, location=(0.0, -0.02, 2.52))
            cap = bpy.context.active_object
            cap.rotation_euler = (math.radians(-8.0), 0.0, 0.0)
            _finish(cap, m_cap, 0.022, head_accs)

            bpy.ops.mesh.primitive_torus_add(major_segments=24, minor_segments=8, major_radius=0.43, minor_radius=0.036, location=(0.0, -0.01, 2.40))
            trim = bpy.context.active_object
            trim.rotation_euler = (math.radians(-8.0), 0.0, 0.0)
            _finish(trim, m_gold, 0.015, head_accs)

            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.06, radius2=0.015, depth=0.18, location=(0.36, -0.04, 2.48))
            tassel = bpy.context.active_object
            tassel.rotation_euler = (0.0, math.radians(-22.0), 0.0)
            _finish(tassel, m_gold, 0.014, head_accs)

            # Gold monocle around viewer-right eye (-X is viewer right when facing +Y)
            bpy.ops.mesh.primitive_torus_add(major_segments=20, minor_segments=8, major_radius=0.095, minor_radius=0.016, location=(-0.135, 0.525, 2.095))
            mono = bpy.context.active_object
            mono.rotation_euler = (math.radians(84.0), 0.0, math.radians(-14.0))
            _finish(mono, m_gold, 0.012, head_accs)

            # Curled handlebar mustache below mouth/eye area
            for sx in (-1.0, 1.0):
                bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.09, location=(sx * 0.11, 0.525, 1.93))
                m_part = bpy.context.active_object
                m_part.scale = (1.55, 0.55, 0.62)
                m_part.rotation_euler = (0.0, math.radians(sx * -14.0), math.radians(sx * -12.0))
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                _finish(m_part, m_hair, 0.014, head_accs)

            # Black 3D bow tie on collar
            for sx in (-1.0, 1.0):
                bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.07, radius2=0.02, depth=0.14, location=(sx * 0.08, 0.30, 1.54))
                wing = bpy.context.active_object
                wing.rotation_euler = (0.0, math.radians(sx * 90.0), 0.0)
                _finish(wing, m_dark_hat, 0.014, torso_accs)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.042, location=(0.0, 0.31, 1.54))
            _finish(bpy.context.active_object, m_dark_hat, 0.0, torso_accs)

        elif preset == "foreman":
            # Brown leather flat cap
            m_flat = make_toon_mat(f"{self.name}_FlatCap", "#6B4423", 0.10, roughness=0.75)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.50, location=(0.0, -0.02, 2.44))
            dome = bpy.context.active_object
            dome.scale = (1.04, 1.15, 0.42)
            dome.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(dome, m_flat, 0.020, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.45, depth=0.05, location=(0.0, 0.24, 2.38))
            visor = bpy.context.active_object
            visor.scale = (0.98, 0.85, 1.0)
            visor.rotation_euler = (math.radians(8.0), 0.0, 0.0)
            _finish(visor, make_toon_mat(f"{self.name}_Visor", "#4A2E16", 0.08), 0.018, head_accs)

            # Rust-orange suspenders on shirt torso
            m_susp = make_toon_mat(f"{self.name}_Suspenders", "#C85A28", 0.14, roughness=0.72)
            for sx in (-0.15, 0.15):
                bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.045, depth=0.72, location=(sx, 0.27, 1.22))
                strap = bpy.context.active_object
                strap.scale = (1.0, 0.55, 1.0)
                _finish(strap, m_susp, 0.014, torso_accs)
                bpy.ops.mesh.primitive_cube_add(size=0.075, location=(sx, 0.30, 1.02))
                _finish(bpy.context.active_object, m_brass, 0.0, torso_accs)

            # Optional held heavy iron turning bar or mason trowel
            m_iron = make_toon_mat(f"{self.name}_IronTool", "#3C4046", 0.06, roughness=0.42)
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.036, depth=1.15, location=(0.54, 0.45, 0.84))
            bar = bpy.context.active_object
            bar.name = f"{self.name}_PropTurningBar"
            bar.rotation_euler = (math.radians(90.0), 0.0, math.radians(18.0))
            _smooth_mesh(bar)
            bar.data.materials.append(m_iron)
            add_ink_outline(bar, 0.016)
            self.props["turning_bar"] = bar

            # Mason trowel
            bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.14, radius2=0.01, depth=0.34, location=(0.54, 0.32, 0.84))
            blade = bpy.context.active_object
            blade.scale = (1.0, 0.15, 1.0)
            blade.rotation_euler = (math.radians(90.0), 0.0, 0.0)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.028, depth=0.18, location=(0.54, 0.10, 0.84))
            handle = bpy.context.active_object
            handle.rotation_euler = (math.radians(90.0), 0.0, 0.0)
            for o in bpy.context.selected_objects:
                o.select_set(False)
            blade.select_set(True)
            handle.select_set(True)
            bpy.context.view_layer.objects.active = blade
            bpy.ops.object.join()
            trowel = bpy.context.active_object
            trowel.name = f"{self.name}_PropTrowel"
            trowel.data.materials.append(m_iron)
            add_ink_outline(trowel, 0.015)
            self.props["trowel"] = trowel

        elif preset in ("soldier", "artist"):
            # WWII M1 olive helmet + field belt + binoculars (or artist beret if artist)
            m_helmet = make_toon_mat(f"{self.name}_HelmetOlive", "#4E5A36", 0.10, roughness=0.65)
            if preset == "artist":
                # Jaunty black/charcoal wool beret + paint-stained smock collar + paintbrush
                m_beret = make_toon_mat(f"{self.name}_Beret", "#242834", 0.10, roughness=0.80)
                bpy.ops.mesh.primitive_uv_sphere_add(segments=22, ring_count=12, radius=0.52, location=(0.06, -0.02, 2.48))
                beret = bpy.context.active_object
                beret.scale = (1.12, 1.08, 0.34)
                beret.rotation_euler = (math.radians(-6.0), math.radians(-14.0), 0.0)
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                _finish(beret, m_beret, 0.020, head_accs)
                bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=0.12, location=(0.12, -0.02, 2.66))
                _finish(bpy.context.active_object, m_beret, 0.012, head_accs)
            else:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=22, ring_count=12, radius=0.55, location=(0.0, -0.02, 2.38))
                helm = bpy.context.active_object
                helm.scale = (1.03, 1.06, 0.62)
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                _finish(helm, m_helmet, 0.022, head_accs)
                bpy.ops.mesh.primitive_torus_add(major_segments=22, minor_segments=8, major_radius=0.55, minor_radius=0.028, location=(0.0, -0.01, 2.36))
                rim = bpy.context.active_object
                rim.scale = (1.02, 1.05, 0.85)
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                _finish(rim, m_helmet, 0.012, head_accs)

            # Webbing belt + brass buckle
            m_belt = make_toon_mat(f"{self.name}_Belt", "#7B6B46", 0.08, roughness=0.75)
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.345, depth=0.09, location=(0.0, 0.0, 0.98))
            _finish(bpy.context.active_object, m_belt, 0.012, torso_accs)
            bpy.ops.mesh.primitive_cube_add(size=0.10, location=(0.0, 0.34, 0.98))
            _finish(bpy.context.active_object, m_brass, 0.0, torso_accs)

            # Shared paintbrush prop + binoculars prop
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.026, depth=0.48, location=(0.54, 0.24, 0.84))
            handle = bpy.context.active_object
            handle.rotation_euler = (math.radians(82.0), 0.0, 0.0)
            handle.name = f"{self.name}_PropBrush"
            _smooth_mesh(handle)
            handle.data.materials.append(make_toon_mat(f"{self.name}_BrushWood", "#B85C2A", 0.14))
            add_ink_outline(handle, 0.014)
            self.props["paintbrush"] = handle

        elif preset in ("general", "officer", "admiral", "uboat_captain"):
            cap_hex = {
                "general": "#435030",
                "officer": "#3C4450",
                "admiral": "#1A2942",
                "uboat_captain": "#EAE6DA",
            }[preset]
            m_cap = make_toon_mat(f"{self.name}_PeakedCap", cap_hex, 0.12, roughness=0.65)
            bpy.ops.mesh.primitive_cylinder_add(vertices=22, radius=0.52, depth=0.22, location=(0.0, -0.02, 2.50))
            crown = bpy.context.active_object
            crown.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(crown, m_cap, 0.022, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.45, depth=0.045, location=(0.0, 0.24, 2.40))
            visor = bpy.context.active_object
            visor.scale = (0.96, 0.82, 1.0)
            visor.rotation_euler = (math.radians(8.0), 0.0, 0.0)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            _finish(visor, m_dark_hat, 0.016, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=0.03, location=(0.0, 0.49, 2.52))
            badge = bpy.context.active_object
            badge.rotation_euler = (math.radians(90.0), 0.0, 0.0)
            _finish(badge, m_gold, 0.0, head_accs)

            if preset in ("general", "admiral"):
                # Gold epaulets + chest medals
                for sx in (-0.30, 0.30):
                    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sx, 0.0, 1.54))
                    ep = bpy.context.active_object
                    ep.scale = (0.20, 0.12, 0.05)
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                    _finish(ep, m_gold, 0.012, torso_accs)
                for mx in (-0.14, -0.06, 0.02):
                    bpy.ops.mesh.primitive_cube_add(size=0.06, location=(mx, 0.32, 1.32))
                    _finish(bpy.context.active_object, m_gold, 0.0, torso_accs)

            if preset == "uboat_captain":
                bpy.ops.mesh.primitive_torus_add(
                    major_segments=26, minor_segments=10, major_radius=0.42, minor_radius=0.056, location=(0.0, 0.02, 1.75)
                )
                beard = bpy.context.active_object
                beard.rotation_euler = (math.radians(-14.0), 0.0, 0.0)
                _finish(beard, m_hair, 0.014, head_accs)

            # Shared officer/naval props: binoculars & telescope
            m_iron = make_toon_mat(f"{self.name}_OpticMetal", "#2C3038", 0.08, roughness=0.38)
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=0.22, location=(0.48, 0.20, 0.86))
            bino = bpy.context.active_object
            bino.name = f"{self.name}_PropBinos"
            bino.rotation_euler = (math.radians(82.0), 0.0, 0.0)
            _smooth_mesh(bino)
            bino.data.materials.append(m_iron)
            add_ink_outline(bino, 0.014)
            self.props["binoculars"] = bino

            bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.045, depth=0.52, location=(0.54, 0.28, 0.86))
            scope = bpy.context.active_object
            scope.name = f"{self.name}_PropTelescope"
            scope.rotation_euler = (math.radians(80.0), 0.0, 0.0)
            _smooth_mesh(scope)
            scope.data.materials.append(m_brass)
            add_ink_outline(scope, 0.014)
            self.props["telescope"] = scope

        elif preset in ("painter", "crew"):
            # Knitted navy cap or painter cap
            m_beanie = make_toon_mat(f"{self.name}_SailorCap", "#1F3654" if preset == "crew" else "#384E68", 0.12)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.52, location=(0.0, -0.01, 2.42))
            dome = bpy.context.active_object
            dome.scale = (1.02, 1.04, 0.45)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(dome, m_beanie, 0.020, head_accs)
            if preset == "painter":
                bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.44, depth=0.04, location=(0.0, 0.24, 2.38))
                vis = bpy.context.active_object
                vis.scale = (0.95, 0.80, 1.0)
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                _finish(vis, m_dark_hat, 0.016, head_accs)
                bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.028, depth=0.52, location=(0.54, 0.26, 0.84))
                br = bpy.context.active_object
                br.rotation_euler = (math.radians(82.0), 0.0, 0.0)
                br.name = f"{self.name}_PropPaintbrush"
                _smooth_mesh(br)
                br.data.materials.append(make_toon_mat(f"{self.name}_PaintCyan", "#2AA6C8", 0.18))
                add_ink_outline(br, 0.014)
                self.props["paintbrush"] = br

        elif preset == "cartographer":
            # Green-tinted draftsman visor / spectacles + bow tie + magnifying glass + rolled map
            m_visor = make_toon_mat(f"{self.name}_DraftVisor", "#2D7A4E", 0.22, roughness=0.35)
            m_band = make_toon_mat(f"{self.name}_VisorBand", "#1E2228", 0.08, roughness=0.72)
            bpy.ops.mesh.primitive_torus_add(major_segments=24, minor_segments=8, major_radius=0.51, minor_radius=0.032, location=(0.0, 0.0, 2.34))
            band = bpy.context.active_object
            band.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
            _finish(band, m_band, 0.014, head_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.46, depth=0.035, location=(0.0, 0.30, 2.31))
            vis = bpy.context.active_object
            vis.scale = (0.98, 0.72, 1.0)
            vis.rotation_euler = (math.radians(14.0), 0.0, 0.0)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            _finish(vis, m_visor, 0.016, head_accs)

            # Brass spectacles rim around both eyes
            for sx in (-0.135, 0.135):
                bpy.ops.mesh.primitive_torus_add(major_segments=18, minor_segments=6, major_radius=0.095, minor_radius=0.014, location=(sx, 0.525, 2.09))
                spec = bpy.context.active_object
                spec.rotation_euler = (math.radians(84.0), 0.0, 0.0)
                _finish(spec, m_brass, 0.010, head_accs)

            # Red bow tie + white collar
            m_bow = make_toon_mat(f"{self.name}_RedBow", "#B8362B", 0.18, roughness=0.65)
            for sx in (-1.0, 1.0):
                bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.065, radius2=0.02, depth=0.13, location=(sx * 0.075, 0.30, 1.54))
                w = bpy.context.active_object
                w.rotation_euler = (0.0, math.radians(sx * 90.0), 0.0)
                _finish(w, m_bow, 0.014, torso_accs)

            # Held magnifying glass (Forearm.R) + rolled paper map (Forearm.L)
            bpy.ops.mesh.primitive_torus_add(major_segments=20, minor_segments=8, major_radius=0.15, minor_radius=0.022, location=(0.54, 0.38, 0.84))
            ring = bpy.context.active_object
            ring.rotation_euler = (math.radians(78.0), 0.0, 0.0)
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.024, depth=0.22, location=(0.54, 0.16, 0.84))
            hdl = bpy.context.active_object
            hdl.rotation_euler = (math.radians(78.0), 0.0, 0.0)
            for o in bpy.context.selected_objects:
                o.select_set(False)
            ring.select_set(True)
            hdl.select_set(True)
            bpy.context.view_layer.objects.active = ring
            bpy.ops.object.join()
            mag = bpy.context.active_object
            mag.name = f"{self.name}_PropMagGlass"
            _smooth_mesh(mag)
            mag.data.materials.append(m_brass)
            add_ink_outline(mag, 0.015)
            self.props["magnifying_glass"] = mag

            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.065, depth=0.58, location=(-0.54, 0.16, 0.84))
            rmap = bpy.context.active_object
            rmap.name = f"{self.name}_PropRolledMap"
            rmap.rotation_euler = (math.radians(78.0), math.radians(16.0), 0.0)
            _smooth_mesh(rmap)
            rmap.data.materials.append(make_toon_mat(f"{self.name}_MapPaper", "#EFE2BF", 0.18))
            add_ink_outline(rmap, 0.016)
            self.props["rolled_map"] = rmap

        elif preset == "storekeeper":
            # Straw boater / country flat hat + apron + rolled map
            m_straw = make_toon_mat(f"{self.name}_StrawHat", "#DEC078", 0.18, roughness=0.72)
            m_ribbon = make_toon_mat(f"{self.name}_StrawRibbon", "#9C2F28", 0.14, roughness=0.70)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.62, depth=0.045, location=(0.0, -0.02, 2.43))
            _finish(bpy.context.active_object, m_straw, 0.020, head_accs)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.42, depth=0.22, location=(0.0, -0.02, 2.54))
            _finish(bpy.context.active_object, m_straw, 0.020, head_accs)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.43, depth=0.075, location=(0.0, -0.02, 2.49))
            _finish(bpy.context.active_object, m_ribbon, 0.0, head_accs)

            m_apron = make_toon_mat(f"{self.name}_ApronCream", "#EFE8D8", 0.16, roughness=0.80)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.28, 1.05))
            apron = bpy.context.active_object
            apron.scale = (0.44, 0.14, 0.56)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(apron, m_apron, 0.014, torso_accs)

            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.065, depth=0.58, location=(-0.54, 0.16, 0.84))
            rmap = bpy.context.active_object
            rmap.name = f"{self.name}_PropRolledMap"
            rmap.rotation_euler = (math.radians(78.0), math.radians(16.0), 0.0)
            _smooth_mesh(rmap)
            rmap.data.materials.append(make_toon_mat(f"{self.name}_MapPaper", "#EFE2BF", 0.18))
            add_ink_outline(rmap, 0.016)
            self.props["rolled_map"] = rmap

        elif preset == "naval_engineer":
            # Hard hat + safety goggles rim + white shirt collar + rolled blueprint + mason trowel
            m_helm = make_toon_mat(f"{self.name}_HardHat", "#E8B838", 0.22, roughness=0.45)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=22, ring_count=12, radius=0.55, location=(0.0, -0.02, 2.38))
            dome = bpy.context.active_object
            dome.scale = (1.03, 1.08, 0.56)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(dome, m_helm, 0.022, head_accs)
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.58, depth=0.04, location=(0.0, 0.06, 2.34))
            brim = bpy.context.active_object
            brim.scale = (1.0, 1.08, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(brim, m_helm, 0.016, head_accs)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -0.02, 2.66))
            ridge = bpy.context.active_object
            ridge.scale = (0.14, 0.72, 0.10)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(ridge, m_gold, 0.012, head_accs)

            # Tie + white collar
            for bx in (-0.08, 0.08):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, 0.25, 1.54))
                col_wing = bpy.context.active_object
                col_wing.scale = (0.14, 0.12, 0.11)
                col_wing.rotation_euler = (math.radians(15), 0.0, math.radians(-22 if bx > 0 else 22))
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                _finish(col_wing, m_white_col, 0.015, torso_accs)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.32, 1.24))
            tie = bpy.context.active_object
            tie.scale = (0.11, 0.05, 0.44)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            _finish(tie, make_toon_mat(f"{self.name}_EngTie", "#B8362B", 0.18), 0.012, torso_accs)

            # Rolled blueprint (Forearm.L) & mason trowel (Forearm.R)
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.068, depth=0.62, location=(-0.54, 0.16, 0.84))
            bp = bpy.context.active_object
            bp.name = f"{self.name}_PropBlueprint"
            bp.rotation_euler = (math.radians(78.0), math.radians(18.0), 0.0)
            _smooth_mesh(bp)
            bp.data.materials.append(make_toon_mat(f"{self.name}_BlueprintBlue", "#2868B8", 0.16))
            add_ink_outline(bp, 0.018)
            self.props["blueprint"] = bp

            m_iron = make_toon_mat(f"{self.name}_EngIron", "#4A525D", 0.10, roughness=0.38)
            bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.14, radius2=0.01, depth=0.34, location=(0.54, 0.32, 0.84))
            blade = bpy.context.active_object
            blade.scale = (1.0, 0.15, 1.0)
            blade.rotation_euler = (math.radians(90.0), 0.0, 0.0)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.028, depth=0.18, location=(0.54, 0.10, 0.84))
            handle = bpy.context.active_object
            handle.rotation_euler = (math.radians(90.0), 0.0, 0.0)
            for o in bpy.context.selected_objects:
                o.select_set(False)
            blade.select_set(True)
            handle.select_set(True)
            bpy.context.view_layer.objects.active = blade
            bpy.ops.object.join()
            trowel = bpy.context.active_object
            trowel.name = f"{self.name}_PropTrowel"
            trowel.data.materials.append(m_iron)
            add_ink_outline(trowel, 0.015)
            self.props["trowel"] = trowel

        if "pointer_stick" not in self.props:
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.022, depth=0.95, location=(0.54, 0.38, 0.86))
            ptr = bpy.context.active_object
            ptr.name = f"{self.name}_PropPointer"
            ptr.rotation_euler = (math.radians(78.0), 0.0, math.radians(-8.0))
            _smooth_mesh(ptr)
            ptr.data.materials.append(make_toon_mat(f"{self.name}_PointerWood", "#A66A38", 0.12))
            add_ink_outline(ptr, 0.012)
            self.props["pointer_stick"] = ptr

    def _build_motion_fx(self, col: bpy.types.Collection | None) -> None:
        """Build v5 comic motion FX meshes: sweat drops, steam puffs, shock burst streaks & speed lines."""
        self.fx_head_root = bpy.data.objects.new(f"{self.name}_FXHeadRoot", None)
        self.fx_head_root.empty_display_type = "PLAIN_AXES"
        self.fx_head_root.empty_display_size = 0.12
        self.fx_head_root.location = (0.0, 0.0, 2.04)
        link_to_collection(self.fx_head_root, col)

        self.fx_torso_root = bpy.data.objects.new(f"{self.name}_FXTorsoRoot", None)
        self.fx_torso_root.empty_display_type = "PLAIN_AXES"
        self.fx_torso_root.empty_display_size = 0.12
        self.fx_torso_root.location = (0.0, 0.0, 1.20)
        link_to_collection(self.fx_torso_root, col)

        self.fx_groups: dict[str, list[bpy.types.Object]] = {
            "sweat": [],
            "steam": [],
            "shock": [],
            "speed": [],
        }
        self.fx_base: dict[str, tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = {}

        def _reg_fx(group: str, obj: bpy.types.Object, parent: bpy.types.Object, local_loc: tuple[float, float, float]) -> None:
            if hasattr(obj, "visible_shadow"):
                obj.visible_shadow = False
            obj.parent = parent
            obj.location = local_loc
            link_to_collection(obj, col)
            self.fx_groups[group].append(obj)
            self.fx_base[obj.name] = (
                tuple(obj.location),
                tuple(obj.rotation_euler),
                tuple(obj.scale),
            )

        # 1) Comic sweat-drop beads (NERVOUS_SWEAT)
        m_sweat = make_toon_mat(f"{self.name}_FXSweat", "#68D8FF", emission_lift=0.45, roughness=0.28)
        sweat_specs = (
            ((-0.62, 0.14, 0.24), (0.070, 0.050, 0.115), (0.0, -14.0, 0.0)),
            ((0.64, 0.12, 0.18), (0.065, 0.048, 0.105), (0.0, 14.0, 0.0)),
            ((-0.68, 0.06, -0.04), (0.056, 0.042, 0.090), (0.0, -10.0, 0.0)),
        )
        for idx, (loc, sc, rot_d) in enumerate(sweat_specs):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1.0, location=(0.0, 0.0, 0.0))
            drop = bpy.context.active_object
            drop.name = f"{self.name}_FXSweat{idx}"
            drop.scale = sc
            drop.rotation_euler = tuple(math.radians(a) for a in rot_d)
            _smooth_mesh(drop)
            drop.data.materials.append(m_sweat)
            add_ink_outline(drop, thickness=0.013)
            _reg_fx("sweat", drop, self.fx_head_root, loc)

        # 2) Drifting comic steam puffs (FURIOUS)
        m_steam = make_toon_mat(f"{self.name}_FXSteam", "#F7E4FF", emission_lift=0.48, roughness=0.72)
        steam_specs = (
            ((-0.64, 0.02, 0.34), (0.13, 0.10, 0.10)),
            ((0.64, 0.02, 0.36), (0.13, 0.10, 0.10)),
            ((-0.78, -0.04, 0.56), (0.17, 0.12, 0.12)),
            ((0.78, -0.04, 0.58), (0.17, 0.12, 0.12)),
        )
        for idx, (loc, sc) in enumerate(steam_specs):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1.0, location=(0.0, 0.0, 0.0))
            puff = bpy.context.active_object
            puff.name = f"{self.name}_FXSteam{idx}"
            puff.scale = sc
            _smooth_mesh(puff)
            puff.data.materials.append(m_steam)
            add_ink_outline(puff, thickness=0.014)
            _reg_fx("steam", puff, self.fx_head_root, loc)

        # 3) Radial comic burst streaks (SHOCK / SCREAM) - flare outward cleanly past hats
        m_shock = make_toon_mat(f"{self.name}_FXShock", "#FFE44A", emission_lift=0.68, roughness=0.40)
        shock_angles = (-108.0, -72.0, -38.0, 38.0, 72.0, 108.0)
        for idx, ang_deg in enumerate(shock_angles):
            ang = math.radians(ang_deg)
            rad = 1.02 if idx % 2 == 0 else 1.10
            lx = math.sin(ang) * rad
            lz = math.cos(ang) * rad
            bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.010, radius2=0.052, depth=0.34, location=(0.0, 0.0, 0.0))
            spk = bpy.context.active_object
            spk.name = f"{self.name}_FXShock{idx}"
            spk.rotation_euler = (0.0, ang, 0.0)
            _smooth_mesh(spk)
            spk.data.materials.append(m_shock)
            add_ink_outline(spk, thickness=0.012)
            _reg_fx("shock", spk, self.fx_head_root, (lx, 0.02, lz))

        # 4) Stylized action speed lines (high-energy reactions / rushes)
        m_speed = make_toon_mat(f"{self.name}_FXSpeed", "#F2FAFF", emission_lift=0.60, roughness=0.40)
        speed_specs = (
            ((-0.76, -0.32, 0.42), (0.016, 0.56, 0.016)),
            ((0.76, -0.32, 0.38), (0.016, 0.56, 0.016)),
            ((-0.86, -0.36, 0.04), (0.014, 0.48, 0.014)),
            ((0.86, -0.36, 0.08), (0.014, 0.48, 0.014)),
        )
        for idx, (loc, sc) in enumerate(speed_specs):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
            ln = bpy.context.active_object
            ln.name = f"{self.name}_FXSpeed{idx}"
            ln.scale = sc
            _smooth_mesh(ln)
            ln.data.materials.append(m_speed)
            add_ink_outline(ln, thickness=0.010)
            _reg_fx("speed", ln, self.fx_torso_root, loc)

    def _all_fx_objs(self) -> list[bpy.types.Object]:
        return [o for grp in self.fx_groups.values() for o in grp]

    def set_visible(self, visible: bool) -> None:
        for o in self.all_objs:
            o.hide_render = not visible
            o.hide_viewport = not visible
        if visible:
            for pname in self.props:
                self.set_prop_visible(pname, False)
            for fx_obj in self._all_fx_objs():
                fx_obj.hide_render = True
                fx_obj.hide_viewport = True

    def set_prop_visible(self, prop_name: str, visible: bool) -> None:
        obj = self.props.get(prop_name)
        if obj is not None:
            obj.hide_render = not visible
            obj.hide_viewport = not visible

    def reset_animation(self) -> None:
        clear_object_anim(self.rig)
        for fx_obj in self._all_fx_objs():
            clear_object_anim(fx_obj)
            b_loc, b_rot, b_sc = self.fx_base[fx_obj.name]
            fx_obj.location = b_loc
            fx_obj.rotation_euler = b_rot
            fx_obj.scale = b_sc
            fx_obj.hide_render = True
            fx_obj.hide_viewport = True
        if self.face_obj.data.materials:
            clear_object_anim(self.face_obj.data.materials[0].node_tree)
        if hasattr(self, "head_mat") and self.head_mat and self.head_mat.node_tree:
            clear_object_anim(self.head_mat.node_tree)
            bsdf = self.head_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                rgba = hex_rgba("#F5F5F3")
                bsdf.inputs["Base Color"].default_value = rgba
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = rgba
        # Reset pose bones to neutral rest
        for pb in self.rig.pose.bones:
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)

    def key_face(self, frame: int, emotion: str) -> None:
        em = emotion if emotion in ATLAS_META["faces"] else "NEUTRAL"
        col, row = ATLAS_META["faces"][em]
        self.face_col_node.outputs[0].default_value = float(col)
        self.face_row_node.outputs[0].default_value = float(row)
        self.face_col_node.outputs[0].keyframe_insert(data_path="default_value", frame=frame)
        self.face_row_node.outputs[0].keyframe_insert(data_path="default_value", frame=frame)

        nt = self.face_obj.data.materials[0].node_tree
        if nt.animation_data and nt.animation_data.action:
            for fc in nt.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"

        # @RicksClips3000 rage color gag: flush head purple on FURIOUS, crisp paper-white otherwise
        if hasattr(self, "head_mat") and self.head_mat and self.head_mat.node_tree:
            h_rgba = hex_rgba("#D478FF") if em == "FURIOUS" else (1.0, 1.0, 1.0, 1.0)
            tint = self.head_mat.node_tree.nodes.get("HeadTint")
            if tint is not None:
                tint.outputs[0].default_value = h_rgba
                tint.outputs[0].keyframe_insert(data_path="default_value", frame=frame)
            else:
                bsdf = self.head_mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    w_rgba = hex_rgba("#D478FF" if em == "FURIOUS" else "#FCFBF8")
                    bsdf.inputs["Base Color"].default_value = w_rgba
                    bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame)
                    if "Emission Color" in bsdf.inputs:
                        bsdf.inputs["Emission Color"].default_value = w_rgba
                        bsdf.inputs["Emission Color"].keyframe_insert(data_path="default_value", frame=frame)
            hnt = self.head_mat.node_tree
            if hnt.animation_data and hnt.animation_data.action:
                for fc in hnt.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"

    def set_emotion_at(self, frame: int, emotion: str) -> None:
        """Key a mid-shot CONSTANT face expression (and optional FURIOUS purple flush) swap."""
        self.key_face(frame, emotion)

    def animate_lip_flap(
        self,
        f0: int,
        f1: int,
        base_emotion: str,
        *,
        mid_emotion: str | None = None,
        mid_frame: int | None = None,
    ) -> None:
        """Alternate mouth open/closed every ~4 frames at 24fps + one natural blink (preserving frame f0)."""
        talk_map = {
            "HAPPY": "TALK_OPEN",
            "NEUTRAL": "TALK_OPEN",
            "SMUG": "TALK_OPEN",
            "NERVOUS_SWEAT": "TALK_OPEN",
            "DETERMINED": "TALK_SERIOUS",
            "DEADPAN": "TALK_SERIOUS",
            "SUSPICIOUS": "TALK_SERIOUS",
            "CONFUSED": "TALK_SERIOUS",
            "SAD": "TALK_SERIOUS",
            "ANGRY": "TALK_ANGRY",
        }
        self.key_face(f0, base_emotion)
        if mid_emotion and mid_frame is not None and f0 < mid_frame <= f1:
            self.key_face(mid_frame, mid_emotion)

        blink_f = f0 + max(8, int(round((f1 - f0) * 0.58)))
        f = f0 + 4
        open_mouth = True
        while f <= f1 - 2:
            cur_base = mid_emotion if (mid_emotion and mid_frame is not None and f >= mid_frame) else base_emotion
            if cur_base in ("FURIOUS", "SHOCK", "SCREAM", "CRYING", "LAUGH", "SLEEPY", "BLINK"):
                f += 4
                continue
            if abs(f - blink_f) <= 1 and cur_base != "FURIOUS":
                self.key_face(f, "BLINK")
                self.key_face(min(f1, f + 2), cur_base)
                f += 4
                open_mouth = True
                continue
            talk_em = talk_map.get(cur_base)
            if talk_em and talk_em in ATLAS_META["faces"]:
                self.key_face(f, talk_em if open_mouth else cur_base)
                open_mouth = not open_mouth
            f += 4

    def animate_emotion_fx(
        self,
        f0: int,
        f1: int,
        base_emotion: str,
        *,
        mid_emotion: str | None = None,
        mid_frame: int | None = None,
        speed_lines: bool = False,
    ) -> None:
        """Animate v5 3D comic FX: sweat drops (NERVOUS_SWEAT), steam puffs (FURIOUS), shock bursts (SHOCK/SCREAM), and speed lines."""
        def _emo_group(em: str | None) -> str | None:
            if em == "NERVOUS_SWEAT":
                return "sweat"
            if em == "FURIOUS":
                return "steam"
            if em in ("SHOCK", "SCREAM"):
                return "shock"
            return None

        g0 = _emo_group(base_emotion)
        g1 = _emo_group(mid_emotion) if (mid_emotion and mid_frame is not None and f0 < mid_frame <= f1) else g0
        active_groups = {g for g in (g0, g1) if g is not None}
        if speed_lines:
            active_groups.add("speed")

        for grp_name, objs in self.fx_groups.items():
            if grp_name not in active_groups:
                for o in objs:
                    o.hide_render = True
                    o.hide_viewport = True
                continue

            if grp_name == "speed":
                start_f, end_f = f0, f1
            elif g0 == grp_name and g1 == grp_name:
                start_f, end_f = f0, f1
            elif g0 == grp_name:
                start_f, end_f = f0, max(f0 + 1, (mid_frame or f1) - 1)
            else:
                start_f, end_f = max(f0 + 1, mid_frame or f0), f1

            for idx, o in enumerate(objs):
                b_loc, _, b_sc = self.fx_base[o.name]
                bx, by, bz = b_loc
                sx, sy, sz = b_sc

                # Visibility window via CONSTANT keyframes
                if start_f > f0:
                    o.hide_render = True
                    o.hide_viewport = True
                    o.keyframe_insert(data_path="hide_render", frame=f0)
                    o.keyframe_insert(data_path="hide_viewport", frame=f0)
                o.hide_render = False
                o.hide_viewport = False
                o.keyframe_insert(data_path="hide_render", frame=start_f)
                o.keyframe_insert(data_path="hide_viewport", frame=start_f)
                if end_f < f1:
                    o.hide_render = True
                    o.hide_viewport = True
                    o.keyframe_insert(data_path="hide_render", frame=end_f + 1)
                    o.keyframe_insert(data_path="hide_viewport", frame=end_f + 1)

                span = max(4, end_f - start_f)
                if grp_name == "sweat":
                    # Dripping teardrop cascade
                    step = max(6, span // 2)
                    for k, kf in enumerate((start_f, min(end_f, start_f + step), end_f)):
                        phase = (k + idx * 0.35) % 1.4
                        dz = 0.05 - phase * 0.22
                        pulse = 0.88 + 0.26 * math.sin(phase * math.pi)
                        o.location = (bx, by, bz + dz)
                        o.scale = (sx * pulse, sy * pulse, sz * pulse)
                        o.keyframe_insert(data_path="location", frame=kf)
                        o.keyframe_insert(data_path="scale", frame=kf)
                elif grp_name == "steam":
                    # Billowing steam puffs rising & expanding
                    mid_k = start_f + span // 2
                    dx_out = 0.14 if bx > 0 else -0.14
                    for kf, prog, p_sc in ((start_f, 0.0, 0.72), (mid_k, 0.55, 1.24), (end_f, 1.0, 0.82)):
                        o.location = (bx + dx_out * prog, by, bz + 0.36 * prog + 0.06 * (idx // 2))
                        o.scale = (sx * p_sc, sy * p_sc, sz * p_sc)
                        o.keyframe_insert(data_path="location", frame=kf)
                        o.keyframe_insert(data_path="scale", frame=kf)
                elif grp_name == "shock":
                    # Snappy radial comic burst outward + slight vibrate
                    pop_f = min(end_f, start_f + 5)
                    mid_k = min(end_f, start_f + max(7, span // 2))
                    for kf, rad_mul, sc_mul in ((start_f, 0.78, 0.45), (pop_f, 1.15, 1.22), (mid_k, 1.04, 1.05), (end_f, 1.10, 1.12)):
                        o.location = (bx * rad_mul, by, bz * rad_mul)
                        o.scale = (sx * sc_mul, sy * sc_mul, sz * sc_mul)
                        o.keyframe_insert(data_path="location", frame=kf)
                        o.keyframe_insert(data_path="scale", frame=kf)
                elif grp_name == "speed":
                    # Streaking comic action lines pulsing along -Y
                    mid_k = start_f + span // 2
                    for kf, dy, sc_y in ((start_f, 0.12, 0.80), (mid_k, -0.22, 1.28), (end_f, 0.05, 0.92)):
                        o.location = (bx, by + dy, bz)
                        o.scale = (sx, sy * sc_y, sz)
                        o.keyframe_insert(data_path="location", frame=kf)
                        o.keyframe_insert(data_path="scale", frame=kf)

                if o.animation_data and o.animation_data.action:
                    for fc in o.animation_data.action.fcurves:
                        is_hide = fc.data_path in ("hide_render", "hide_viewport")
                        for kp in fc.keyframe_points:
                            kp.interpolation = "CONSTANT" if is_hide else "BEZIER"

    def key_pose(
        self,
        frame: int,
        *,
        root_loc: tuple[float, float, float] | None = None,
        root_yaw_deg: float | None = None,
        torso_scale: tuple[float, float, float] | None = None,
        pelvis_loc: tuple[float, float, float] | None = None,
        torso_rot_deg: tuple[float, float, float] | None = None,
        head_rot_deg: tuple[float, float, float] | None = None,
        arm_l_deg: tuple[float, float, float] | None = None,
        forearm_l_deg: tuple[float, float, float] | None = None,
        arm_r_deg: tuple[float, float, float] | None = None,
        forearm_r_deg: tuple[float, float, float] | None = None,
        thigh_l_deg: tuple[float, float, float] | None = None,
        shin_l_deg: tuple[float, float, float] | None = None,
        thigh_r_deg: tuple[float, float, float] | None = None,
        shin_r_deg: tuple[float, float, float] | None = None,
        interp: str = "BEZIER",
    ) -> None:
        pb = self.rig.pose.bones
        if root_loc is not None:
            pb["Root"].location = root_loc
            pb["Root"].keyframe_insert(data_path="location", frame=frame)
        if root_yaw_deg is not None:
            pb["Root"].rotation_euler = (0.0, 0.0, math.radians(root_yaw_deg))
            pb["Root"].keyframe_insert(data_path="rotation_euler", frame=frame)
        if torso_scale is not None:
            pb["Torso"].scale = torso_scale
            pb["Torso"].keyframe_insert(data_path="scale", frame=frame)
        if pelvis_loc is not None:
            pb["Pelvis"].location = pelvis_loc
            pb["Pelvis"].keyframe_insert(data_path="location", frame=frame)

        rot_map = {
            "Torso": torso_rot_deg,
            "Head": head_rot_deg,
            "Arm.L": arm_l_deg,
            "Forearm.L": forearm_l_deg,
            "Arm.R": arm_r_deg,
            "Forearm.R": forearm_r_deg,
            "Thigh.L": thigh_l_deg,
            "Shin.L": shin_l_deg,
            "Thigh.R": thigh_r_deg,
            "Shin.R": shin_r_deg,
        }
        for bname, degs in rot_map.items():
            if degs is not None:
                pb[bname].rotation_euler = tuple(math.radians(a) for a in degs)
                pb[bname].keyframe_insert(data_path="rotation_euler", frame=frame)

        if self.rig.animation_data and self.rig.animation_data.action:
            for fc in self.rig.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    if int(round(kp.co.x)) == frame:
                        kp.interpolation = interp
                        if interp in ("BACK", "QUAD", "CUBIC") and hasattr(kp, "easing"):
                            kp.easing = "EASE_OUT"

    def animate_idle_talk(
        self,
        f0: int,
        f1: int,
        emotion: str,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        intensity: float = 1.0,
    ) -> None:
        self.key_face(f0, emotion)
        atk = min(f1, f0 + max(5, (f1 - f0) // 6))
        mid = (f0 + f1) // 2
        q3 = min(f1, f0 + (3 * (f1 - f0)) // 4)
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.95),
            pelvis_loc=(0.0, 0.0, -0.02),
            torso_rot_deg=(-4.0 * intensity, 0.0, 5.0 * intensity),
            head_rot_deg=(-6.0 * intensity, 0.0, 8.0 * intensity),
            arm_l_deg=(20.0, 0.0, -14.0),
            forearm_l_deg=(38.0, 0.0, 8.0),
            arm_r_deg=(36.0 * intensity, 0.0, 18.0),
            forearm_r_deg=(52.0 * intensity, 0.0, -12.0),
            thigh_l_deg=(0.0, 0.0, -3.0),
            shin_l_deg=(0.0, 0.0, 0.0),
            thigh_r_deg=(0.0, 0.0, 3.0),
            shin_r_deg=(0.0, 0.0, 0.0),
            interp="BACK",
        )
        self.key_pose(
            atk,
            torso_scale=(0.96, 0.96, 1.05),
            pelvis_loc=(0.0, 0.0, 0.045 * intensity),
            torso_rot_deg=(3.0 * intensity, 0.0, -4.0 * intensity),
            head_rot_deg=(8.0 * intensity, 3.0 * intensity, -6.0 * intensity),
            arm_l_deg=(34.0 * intensity, 0.0, -20.0),
            forearm_l_deg=(62.0 * intensity, 0.0, 14.0),
            arm_r_deg=(66.0 * intensity, 0.0, 24.0),
            forearm_r_deg=(72.0 * intensity, 0.0, -18.0),
            interp="BACK",
        )
        self.key_pose(
            mid,
            torso_scale=(1.03, 1.03, 0.97),
            pelvis_loc=(0.0, 0.0, -0.015 * intensity),
            torso_rot_deg=(-2.0 * intensity, 0.0, 4.0 * intensity),
            head_rot_deg=(-5.0 * intensity, 4.0 * intensity, 6.0 * intensity),
            arm_l_deg=(24.0 * intensity, 0.0, -16.0),
            forearm_l_deg=(46.0 * intensity, 0.0, 10.0),
            arm_r_deg=(48.0 * intensity, 0.0, 18.0),
            forearm_r_deg=(58.0 * intensity, 0.0, -14.0),
            interp="BEZIER",
        )
        self.key_pose(
            q3,
            torso_scale=(0.97, 0.97, 1.04),
            pelvis_loc=(0.0, 0.0, 0.035 * intensity),
            head_rot_deg=(7.0 * intensity, -3.0 * intensity, -5.0 * intensity),
            arm_r_deg=(62.0 * intensity, 0.0, 22.0),
            forearm_r_deg=(70.0 * intensity, 0.0, -16.0),
            interp="BACK",
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            pelvis_loc=(0.0, 0.0, 0.0),
            torso_rot_deg=(-2.0 * intensity, 0.0, 2.0 * intensity),
            head_rot_deg=(-2.0 * intensity, -2.0 * intensity, 3.0 * intensity),
            arm_l_deg=(22.0, 0.0, -14.0),
            forearm_l_deg=(42.0, 0.0, 8.0),
            arm_r_deg=(40.0 * intensity, 0.0, 14.0),
            forearm_r_deg=(54.0 * intensity, 0.0, -12.0),
        )

    def animate_whistle_blow(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
    ) -> None:
        self.set_prop_visible("whistle_hand", True)
        self.key_face(f0, "DETERMINED")
        f_blow = f0 + int((f1 - f0) * 0.35)
        self.key_face(f_blow, "SMUG")
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            pelvis_loc=(0.0, 0.0, 0.0),
            torso_rot_deg=(0.0, 0.0, 0.0),
            head_rot_deg=(-4.0, 0.0, 4.0),
            arm_l_deg=(12.0, 0.0, -14.0),
            forearm_l_deg=(25.0, 0.0, 0.0),
            arm_r_deg=(55.0, 0.0, 12.0),
            forearm_r_deg=(75.0, 0.0, -25.0),
        )
        self.key_pose(
            f_blow,
            pelvis_loc=(0.0, 0.0, 0.04),
            torso_rot_deg=(6.0, 0.0, 0.0),
            head_rot_deg=(8.0, 0.0, -4.0),
            arm_r_deg=(95.0, 0.0, -18.0),
            forearm_r_deg=(118.0, 0.0, -35.0),
        )
        self.key_pose(
            f1,
            pelvis_loc=(0.0, 0.0, 0.02),
            torso_rot_deg=(3.0, 0.0, 0.0),
            head_rot_deg=(10.0, 3.0, -2.0),
            arm_r_deg=(88.0, 0.0, -15.0),
            forearm_r_deg=(112.0, 0.0, -30.0),
        )

    def animate_turn_bar(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
    ) -> None:
        self.set_prop_visible("turning_bar", True)
        self.key_face(f0, "HAPPY")
        mid = (f0 + f1) // 2
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg - 12.0,
            pelvis_loc=(0.0, 0.0, -0.04),
            torso_rot_deg=(-10.0, 0.0, -18.0),
            head_rot_deg=(6.0, 0.0, 14.0),
            arm_l_deg=(58.0, 0.0, -10.0),
            forearm_l_deg=(45.0, 0.0, 18.0),
            arm_r_deg=(72.0, 0.0, 8.0),
            forearm_r_deg=(55.0, 0.0, -12.0),
            thigh_l_deg=(14.0, 0.0, -4.0),
            shin_l_deg=(-18.0, 0.0, 0.0),
            thigh_r_deg=(-8.0, 0.0, 4.0),
            shin_r_deg=(-10.0, 0.0, 0.0),
        )
        self.key_pose(
            mid,
            root_yaw_deg=yaw_deg + 14.0,
            pelvis_loc=(0.0, 0.0, 0.02),
            torso_rot_deg=(-4.0, 0.0, 22.0),
            head_rot_deg=(4.0, 0.0, -10.0),
            arm_l_deg=(66.0, 0.0, -8.0),
            forearm_l_deg=(50.0, 0.0, 22.0),
            arm_r_deg=(76.0, 0.0, 10.0),
            forearm_r_deg=(62.0, 0.0, -14.0),
        )
        self.key_pose(
            f1,
            root_yaw_deg=yaw_deg + 28.0,
            pelvis_loc=(0.0, 0.0, 0.0),
            torso_rot_deg=(0.0, 0.0, 26.0),
            head_rot_deg=(2.0, 0.0, -16.0),
        )

    def animate_laugh(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
    ) -> None:
        self.key_face(f0, "LAUGH")
        step = max(4, (f1 - f0) // 5)
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.95),
            pelvis_loc=(0.0, 0.0, 0.0),
            torso_rot_deg=(8.0, 0.0, 0.0),
            head_rot_deg=(16.0, 0.0, 0.0),
            arm_l_deg=(35.0, 0.0, -24.0),
            forearm_l_deg=(68.0, 0.0, 22.0),
            arm_r_deg=(35.0, 0.0, 24.0),
            forearm_r_deg=(68.0, 0.0, -22.0),
            interp="BACK",
        )
        for i, f in enumerate(range(f0 + step, f1 + 1, step)):
            up = 0.07 if (i % 2 == 0) else -0.02
            ts = (0.96, 0.96, 1.05) if (i % 2 == 0) else (1.03, 1.03, 0.96)
            self.key_pose(
                min(f, f1),
                torso_scale=ts,
                pelvis_loc=(0.0, 0.0, up),
                torso_rot_deg=(14.0 if i % 2 == 0 else 5.0, 0.0, 5.0 if i % 2 == 0 else -5.0),
                head_rot_deg=(24.0 if i % 2 == 0 else 10.0, 0.0, 7.0 if i % 2 == 0 else -7.0),
                arm_l_deg=(54.0 if i % 2 == 0 else 28.0, 0.0, -28.0),
                arm_r_deg=(54.0 if i % 2 == 0 else 28.0, 0.0, 28.0),
                interp="BACK",
            )

    def animate_shock_recoil(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "SHOCK",
    ) -> None:
        self.key_face(f0, emotion)
        f_pop = min(f1, f0 + 6)
        f_settle = min(f1, f0 + max(12, (f1 - f0) // 2))
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.06, 1.06, 0.93),
            pelvis_loc=(0.0, 0.0, -0.05),
            torso_rot_deg=(4.0, 0.0, 0.0),
            head_rot_deg=(6.0, 0.0, 0.0),
            arm_l_deg=(35.0, 0.0, -22.0),
            forearm_l_deg=(55.0, 0.0, 12.0),
            arm_r_deg=(35.0, 0.0, 22.0),
            forearm_r_deg=(55.0, 0.0, -12.0),
            interp="BACK",
        )
        self.key_pose(
            f_pop,
            torso_scale=(0.95, 0.95, 1.07),
            pelvis_loc=(0.0, -0.09, 0.08),
            torso_rot_deg=(14.0, 0.0, -5.0),
            head_rot_deg=(18.0, 0.0, 7.0),
            arm_l_deg=(104.0, 0.0, -36.0),
            forearm_l_deg=(92.0, 0.0, 20.0),
            arm_r_deg=(104.0, 0.0, 36.0),
            forearm_r_deg=(92.0, 0.0, -20.0),
            interp="BACK",
        )
        self.key_pose(
            f_settle,
            torso_scale=(1.02, 1.02, 0.98),
            pelvis_loc=(0.0, -0.06, 0.01),
            torso_rot_deg=(8.0, 0.0, 4.0),
            head_rot_deg=(12.0, 0.0, -5.0),
            arm_l_deg=(86.0, 0.0, -30.0),
            arm_r_deg=(86.0, 0.0, 30.0),
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            pelvis_loc=(0.0, -0.04, 0.02),
            torso_rot_deg=(10.0, 0.0, -2.0),
            head_rot_deg=(14.0, 0.0, 3.0),
            arm_l_deg=(90.0, 0.0, -32.0),
            arm_r_deg=(90.0, 0.0, 32.0),
        )

    def animate_point(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "SMUG",
        side: str = "R",
    ) -> None:
        self.key_face(f0, emotion)
        f_snap = min(f1, f0 + 6)
        mid = (f0 + f1) // 2
        if side == "R":
            a_l, fa_l = (18.0, 0.0, -16.0), (38.0, 0.0, 8.0)
            a_r0, fa_r0 = (55.0, 0.0, 18.0), (42.0, 0.0, -10.0)
            a_r1, fa_r1 = (98.0, 0.0, 12.0), (14.0, 0.0, -6.0)
        else:
            a_r, fa_r = (18.0, 0.0, 16.0), (38.0, 0.0, -8.0)
            a_l0, fa_l0 = (55.0, 0.0, -18.0), (42.0, 0.0, 10.0)
            a_l1, fa_l1 = (98.0, 0.0, -12.0), (14.0, 0.0, 6.0)

        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.96),
            pelvis_loc=(0.0, 0.0, -0.02),
            torso_rot_deg=(-4.0, 0.0, 6.0),
            head_rot_deg=(2.0, 0.0, -8.0),
            arm_l_deg=a_l if side == "R" else a_l0,
            forearm_l_deg=fa_l if side == "R" else fa_l0,
            arm_r_deg=a_r0 if side == "R" else a_r,
            forearm_r_deg=fa_r0 if side == "R" else fa_r,
            interp="BACK",
        )
        self.key_pose(
            f_snap,
            torso_scale=(0.97, 0.97, 1.04),
            pelvis_loc=(0.0, 0.0, 0.04),
            torso_rot_deg=(-9.0, 0.0, -6.0),
            head_rot_deg=(5.0, 4.0, 7.0),
            arm_l_deg=a_l if side == "R" else a_l1,
            forearm_l_deg=fa_l if side == "R" else fa_l1,
            arm_r_deg=a_r1 if side == "R" else a_r,
            forearm_r_deg=fa_r1 if side == "R" else fa_r,
            interp="BACK",
        )
        self.key_pose(
            mid,
            torso_scale=(1.02, 1.02, 0.98),
            pelvis_loc=(0.0, 0.0, 0.01),
            torso_rot_deg=(-6.0, 0.0, -2.0),
            head_rot_deg=(-2.0, -3.0, 4.0),
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            pelvis_loc=(0.0, 0.0, 0.03),
            torso_rot_deg=(-8.0, 0.0, -5.0),
            head_rot_deg=(4.0, 2.0, 6.0),
        )

    def animate_masonry(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
    ) -> None:
        self.set_prop_visible("trowel", True)
        self.key_face(f0, "DETERMINED")
        mid = (f0 + f1) // 2
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            pelvis_loc=(0.0, 0.0, -0.05),
            torso_rot_deg=(-14.0, 0.0, 8.0),
            head_rot_deg=(-10.0, 0.0, -4.0),
            arm_l_deg=(42.0, 0.0, -14.0),
            forearm_l_deg=(48.0, 0.0, 12.0),
            arm_r_deg=(58.0, 0.0, 12.0),
            forearm_r_deg=(46.0, 0.0, -16.0),
            thigh_l_deg=(12.0, 0.0, -3.0),
            shin_l_deg=(-16.0, 0.0, 0.0),
        )
        self.key_pose(
            mid,
            pelvis_loc=(0.0, 0.0, -0.02),
            torso_rot_deg=(-18.0, 0.0, -10.0),
            head_rot_deg=(-14.0, 0.0, 6.0),
            arm_r_deg=(82.0, 0.0, 24.0),
            forearm_r_deg=(26.0, 0.0, -24.0),
        )
        self.key_pose(
            f1,
            pelvis_loc=(0.0, 0.0, -0.05),
            torso_rot_deg=(-12.0, 0.0, 4.0),
            head_rot_deg=(-8.0, 0.0, -2.0),
            arm_r_deg=(62.0, 0.0, 10.0),
            forearm_r_deg=(48.0, 0.0, -12.0),
        )

    def animate_lift_prop(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "SMUG",
    ) -> None:
        """Both arms raised effortlessly hoisting a decoy tank or heavy crate overhead/waist."""
        self.key_face(f0, emotion)
        mid = (f0 + f1) // 2
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.95),
            pelvis_loc=(0.0, 0.0, -0.06),
            torso_rot_deg=(4.0, 0.0, 0.0),
            head_rot_deg=(8.0, 0.0, 0.0),
            arm_l_deg=(110.0, 0.0, -18.0),
            forearm_l_deg=(45.0, 0.0, 12.0),
            arm_r_deg=(110.0, 0.0, 18.0),
            forearm_r_deg=(45.0, 0.0, -12.0),
            thigh_l_deg=(14.0, 0.0, -4.0),
            shin_l_deg=(-20.0, 0.0, 0.0),
            thigh_r_deg=(14.0, 0.0, 4.0),
            shin_r_deg=(-20.0, 0.0, 0.0),
        )
        self.key_pose(
            mid,
            torso_scale=(0.97, 0.97, 1.04),
            pelvis_loc=(0.0, 0.0, 0.05),
            torso_rot_deg=(-4.0, 0.0, 3.0),
            head_rot_deg=(12.0, 0.0, -5.0),
            arm_l_deg=(148.0, 0.0, -14.0),
            forearm_l_deg=(28.0, 0.0, 8.0),
            arm_r_deg=(148.0, 0.0, 14.0),
            forearm_r_deg=(28.0, 0.0, -8.0),
            thigh_l_deg=(2.0, 0.0, -3.0),
            shin_l_deg=(-4.0, 0.0, 0.0),
            thigh_r_deg=(2.0, 0.0, 3.0),
            shin_r_deg=(-4.0, 0.0, 0.0),
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            pelvis_loc=(0.0, 0.0, 0.02),
            head_rot_deg=(10.0, 0.0, 4.0),
            arm_l_deg=(140.0, 0.0, -16.0),
            arm_r_deg=(140.0, 0.0, 16.0),
        )

    def animate_salute(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "DETERMINED",
    ) -> None:
        self.key_face(f0, emotion)
        f_snap = min(f1, f0 + 5)
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.96),
            pelvis_loc=(0.0, 0.0, -0.02),
            torso_rot_deg=(0.0, 0.0, 0.0),
            head_rot_deg=(0.0, 0.0, 0.0),
            arm_l_deg=(8.0, 0.0, -12.0),
            forearm_l_deg=(16.0, 0.0, 0.0),
            arm_r_deg=(35.0, 0.0, 12.0),
            forearm_r_deg=(45.0, 0.0, 0.0),
            interp="BACK",
        )
        self.key_pose(
            f_snap,
            torso_scale=(0.96, 0.96, 1.05),
            pelvis_loc=(0.0, 0.0, 0.045),
            torso_rot_deg=(5.0, 0.0, 0.0),
            head_rot_deg=(7.0, 0.0, 0.0),
            arm_r_deg=(122.0, 0.0, -14.0),
            forearm_r_deg=(108.0, 0.0, -32.0),
            interp="BACK",
        )
        self.key_pose(f1, torso_scale=(1.0, 1.0, 1.0), pelvis_loc=(0.0, 0.0, 0.02), head_rot_deg=(4.0, 0.0, 2.0))

    def animate_peer_periscope(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "SUSPICIOUS",
    ) -> None:
        self.key_face(f0, emotion)
        atk = min(f1, f0 + 6)
        mid = (f0 + f1) // 2
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.03, 1.03, 0.97),
            pelvis_loc=(0.0, 0.0, -0.02),
            torso_rot_deg=(-10.0, 0.0, -8.0),
            head_rot_deg=(-6.0, 0.0, -10.0),
            arm_l_deg=(78.0, 0.0, -28.0),
            forearm_l_deg=(62.0, 0.0, 26.0),
            arm_r_deg=(78.0, 0.0, 28.0),
            forearm_r_deg=(62.0, 0.0, -26.0),
            interp="BACK",
        )
        self.key_pose(
            atk,
            torso_scale=(0.97, 0.97, 1.04),
            root_yaw_deg=yaw_deg + 10.0,
            pelvis_loc=(0.0, 0.0, 0.02),
            torso_rot_deg=(-14.0, 0.0, 8.0),
            head_rot_deg=(-9.0, 0.0, 10.0),
            interp="BACK",
        )
        self.key_pose(
            mid,
            torso_scale=(1.02, 1.02, 0.98),
            root_yaw_deg=yaw_deg - 10.0,
            torso_rot_deg=(-8.0, 0.0, -10.0),
            head_rot_deg=(-4.0, 0.0, -12.0),
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            root_yaw_deg=yaw_deg + 4.0,
            pelvis_loc=(0.0, 0.0, 0.0),
            torso_rot_deg=(-11.0, 0.0, 4.0),
            head_rot_deg=(-6.0, 0.0, 6.0),
        )

    def animate_paint_stroke(
        self,
        f0: int,
        f1: int,
        root_loc: tuple[float, float, float] = (0.0, 0.0, 0.0),
        yaw_deg: float = 0.0,
        emotion: str = "DETERMINED",
    ) -> None:
        self.set_prop_visible("paintbrush", True)
        self.key_face(f0, emotion)
        atk = min(f1, f0 + 6)
        mid = (f0 + f1) // 2
        self.key_pose(
            f0,
            root_loc=root_loc,
            root_yaw_deg=yaw_deg,
            torso_scale=(1.04, 1.04, 0.96),
            torso_rot_deg=(-4.0, 0.0, -10.0),
            head_rot_deg=(4.0, 0.0, 8.0),
            arm_l_deg=(24.0, 0.0, -18.0),
            forearm_l_deg=(42.0, 0.0, 12.0),
            arm_r_deg=(88.0, 0.0, 24.0),
            forearm_r_deg=(38.0, 0.0, -18.0),
            interp="BACK",
        )
        self.key_pose(
            atk,
            torso_scale=(0.96, 0.96, 1.05),
            torso_rot_deg=(-9.0, 0.0, 14.0),
            head_rot_deg=(7.0, 0.0, -12.0),
            arm_r_deg=(118.0, 0.0, -20.0),
            forearm_r_deg=(16.0, 0.0, 14.0),
            interp="BACK",
        )
        self.key_pose(
            mid,
            torso_scale=(1.02, 1.02, 0.98),
            torso_rot_deg=(-5.0, 0.0, -8.0),
            head_rot_deg=(2.0, 0.0, 8.0),
            arm_r_deg=(82.0, 0.0, 20.0),
            forearm_r_deg=(42.0, 0.0, -14.0),
        )
        self.key_pose(
            f1,
            torso_scale=(1.0, 1.0, 1.0),
            torso_rot_deg=(-7.0, 0.0, 8.0),
            head_rot_deg=(5.0, 0.0, -6.0),
            arm_r_deg=(110.0, 0.0, -12.0),
            forearm_r_deg=(22.0, 0.0, 10.0),
        )


def ensure_camera(name: str = "MainCam") -> bpy.types.Object:
    if name in bpy.data.objects:
        cam = bpy.data.objects[name]
    else:
        cdata = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cdata)
        bpy.context.scene.collection.objects.link(cam)
    cam.rotation_mode = "QUATERNION"
    bpy.context.scene.camera = cam
    return cam


def aim_camera(
    cam: bpy.types.Object,
    loc: tuple[float, float, float],
    target: tuple[float, float, float],
    lens: float = 45.0,
    dof_dist: float | None = None,
    fstop: float = 3.2,
    use_dof: bool = True,
) -> mathutils.Quaternion:
    v_loc = mathutils.Vector(loc)
    v_tgt = mathutils.Vector(target)
    direction = v_tgt - v_loc
    quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_mode = "QUATERNION"
    cam.location = v_loc
    cam.rotation_quaternion = quat
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    cam.data.clip_end = 250.0
    cam.data.dof.use_dof = use_dof
    if use_dof:
        cam.data.dof.focus_distance = dof_dist if dof_dist is not None else max(0.3, direction.length)
        cam.data.dof.aperture_fstop = fstop
    return quat


def animate_camera(
    cam: bpy.types.Object,
    f0: int,
    f1: int,
    loc0: tuple[float, float, float],
    tgt0: tuple[float, float, float],
    loc1: tuple[float, float, float],
    tgt1: tuple[float, float, float],
    lens0: float = 45.0,
    lens1: float | None = None,
    fstop: float = 3.2,
    use_dof: bool = False,
    dof_dist0: float | None = None,
    dof_dist1: float | None = None,
    dof_dist_mid: float | None = None,
    dof_mid_frac: float = 0.50,
    fstop1: float | None = None,
) -> None:
    clear_object_anim(cam)
    clear_object_anim(cam.data)
    q0 = aim_camera(cam, loc0, tgt0, lens=lens0, dof_dist=dof_dist0, fstop=fstop, use_dof=use_dof)
    cam.keyframe_insert(data_path="location", frame=f0)
    cam.keyframe_insert(data_path="rotation_quaternion", frame=f0)
    cam.data.keyframe_insert(data_path="lens", frame=f0)
    if use_dof:
        cam.data.dof.keyframe_insert(data_path="focus_distance", frame=f0)
        cam.data.dof.keyframe_insert(data_path="aperture_fstop", frame=f0)

    if use_dof and dof_dist_mid is not None and f1 - f0 >= 4:
        f_mid = max(f0 + 1, min(f1 - 1, f0 + int(round((f1 - f0) * dof_mid_frac))))
        cam.data.dof.focus_distance = float(dof_dist_mid)
        cam.data.dof.keyframe_insert(data_path="focus_distance", frame=f_mid)
        if fstop1 is not None:
            cam.data.dof.aperture_fstop = float(fstop + (fstop1 - fstop) * dof_mid_frac)
            cam.data.dof.keyframe_insert(data_path="aperture_fstop", frame=f_mid)

    end_fstop = float(fstop1) if fstop1 is not None else fstop
    q1 = aim_camera(cam, loc1, tgt1, lens=(lens1 if lens1 is not None else lens0), dof_dist=dof_dist1, fstop=end_fstop, use_dof=use_dof)
    if q1.dot(q0) < 0.0:
        q1.negate()
        cam.rotation_quaternion = q1
    cam.keyframe_insert(data_path="location", frame=f1)
    cam.keyframe_insert(data_path="rotation_quaternion", frame=f1)
    cam.data.keyframe_insert(data_path="lens", frame=f1)
    if use_dof:
        cam.data.dof.keyframe_insert(data_path="focus_distance", frame=f1)
        cam.data.dof.keyframe_insert(data_path="aperture_fstop", frame=f1)

    for owner in (cam, cam.data):
        if owner.animation_data and owner.animation_data.action:
            for fc in owner.animation_data.action.fcurves:
                is_dof_curve = "dof." in fc.data_path
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER" if is_dof_curve else "LINEAR"


def add_foreground_framing_prop(
    name: str,
    kind: str,
    loc: tuple[float, float, float],
    col: bpy.types.Collection | None = None,
    *,
    scale: float = 1.0,
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Create a subtle dark foreground silhouette framing prop (branches, railing, rivets, drafting_edge)."""
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.15
    root.location = loc
    root.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    root.scale = (scale, scale, scale)
    link_to_collection(root, col)

    m_sil = make_toon_mat(f"{name}_SilMat", "#191C22", emission_lift=0.02, roughness=0.90)
    parts: list[bpy.types.Object] = []

    if kind == "branches":
        parts.append(add_cylinder(f"{name}_Limb", 0.045, 1.45, (0.0, 0.0, 0.0), m_sil, col, vertices=8, rot_deg=(12.0, 68.0, 8.0)))
        for idx, (lx, ly, lz, sc) in enumerate(((-0.35, 0.05, 0.12, 0.26), (0.05, -0.04, 0.22, 0.22), (0.38, 0.04, 0.14, 0.20))):
            parts.append(add_sphere(f"{name}_Leaf{idx}", sc, (lx, ly, lz), m_sil, col, segments=8, rings=6, scale=(1.3, 0.7, 0.8)))
    elif kind == "railing":
        parts.append(add_box(f"{name}_TopRail", (2.6, 0.08, 0.09), (0.0, 0.0, 0.42), m_sil, col, bevel=0.015))
        for px in (-0.95, 0.0, 0.95):
            parts.append(add_box(f"{name}_Post{px}", (0.08, 0.08, 0.85), (px, 0.0, 0.0), m_sil, col, bevel=0.012))
    elif kind == "rivets":
        parts.append(add_box(f"{name}_Beam", (0.28, 0.12, 2.4), (0.0, 0.0, 0.0), m_sil, col, bevel=0.02))
        for rz in (-0.85, -0.45, -0.05, 0.35, 0.75):
            parts.append(add_sphere(f"{name}_Rivet{rz}", 0.045, (0.0, 0.06, rz), m_sil, col, segments=8, rings=6))
    elif kind == "drafting_edge":
        parts.append(add_box(f"{name}_Ruler", (1.6, 0.08, 0.14), (0.0, 0.0, 0.0), m_sil, col, bevel=0.01, rot_deg=(0.0, 18.0, 0.0)))
        parts.append(add_cylinder(f"{name}_LampArm", 0.04, 1.35, (-0.55, 0.0, 0.48), m_sil, col, vertices=10, rot_deg=(0.0, -28.0, 0.0)))
    else:  # fence_corner
        parts.append(add_box(f"{name}_Post", (0.14, 0.14, 1.25), (0.0, 0.0, 0.0), m_sil, col, bevel=0.02))
        parts.append(add_box(f"{name}_Bar1", (1.5, 0.07, 0.09), (0.65, 0.0, 0.30), m_sil, col, bevel=0.01))
        parts.append(add_box(f"{name}_Bar2", (1.5, 0.07, 0.09), (0.65, 0.0, -0.05), m_sil, col, bevel=0.01))

    for p in parts:
        if hasattr(p, "visible_shadow"):
            p.visible_shadow = False
        p.parent = root
    return root


# --------------------------------------------------------------------------- Iteration 3-4 Studio Helpers
def spawn_background_crew(
    name: str,
    placements: list[tuple[float, float, float, float, str, str, float]],
    col: bpy.types.Collection | None = None,
    *,
    frame_end: int = 60,
) -> list[bpy.types.Object]:
    """Spawn lightweight animated miniature background stickmen (x, y, z, yaw_deg, torso_hex, cap_hex, scale)."""
    m_head = make_cel_cutout_mat(f"{name}_CrewWhiteHead", "#FCFBF8", "#DFDDD6", cutoff=0.28)
    m_ink = make_toon_mat(f"{name}_CrewInk", "#161316", emission_lift=0.04, roughness=0.70)
    roots: list[bpy.types.Object] = []
    mid = max(2, frame_end // 2)

    for idx, (x, y, z, yaw_deg, t_hex, c_hex, sc) in enumerate(placements):
        root = bpy.data.objects.new(f"{name}_CrewRoot{idx}", None)
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 0.2
        root.location = (x, y, z)
        root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
        root.scale = (sc, sc, sc)
        link_to_collection(root, col)

        m_t = make_toon_mat(f"{name}_CrewTorso_{idx}", t_hex, emission_lift=0.16, roughness=0.78)
        m_c = make_toon_mat(f"{name}_CrewCap_{idx}", c_hex, emission_lift=0.12, roughness=0.75)

        hd = add_sphere(f"{name}_C{idx}_Head", 0.50, (0.0, 0.0, 2.02), m_head, col, segments=16, rings=10, outline=0.036)
        cap = add_sphere(f"{name}_C{idx}_Cap", 0.48, (0.0, 0.0, 2.38), m_c, col, segments=14, rings=8, scale=(1.02, 1.04, 0.42), outline=0.018)
        e_l = add_sphere(f"{name}_C{idx}_EyeL", 0.06, (-0.16, 0.47, 2.05), m_ink, col, segments=8, rings=6)
        e_r = add_sphere(f"{name}_C{idx}_EyeR", 0.06, (0.16, 0.47, 2.05), m_ink, col, segments=8, rings=6)

        t_mesh = _build_capsule_mesh(f"{name}_C{idx}_TMesh", radius=0.31, cyl_h=0.20, segs=14, rings=10)
        tor = bpy.data.objects.new(f"{name}_C{idx}_Torso", t_mesh)
        tor.location = (0.0, 0.0, 1.20)
        tor.data.materials.append(m_t)
        add_ink_outline(tor, thickness=0.030)
        link_to_collection(tor, col)

        leg_l = add_cylinder(f"{name}_C{idx}_LegL", 0.038, 0.86, (-0.15, 0.0, 0.43), m_ink, col, vertices=8)
        leg_r = add_cylinder(f"{name}_C{idx}_LegR", 0.038, 0.86, (0.15, 0.0, 0.43), m_ink, col, vertices=8)
        arm_l = add_cylinder(f"{name}_C{idx}_ArmL", 0.034, 0.58, (-0.39, 0.05, 1.22), m_ink, col, vertices=8, rot_deg=(-20.0, 0.0, 18.0))
        arm_r = add_cylinder(f"{name}_C{idx}_ArmR", 0.034, 0.58, (0.39, 0.05, 1.22), m_ink, col, vertices=8, rot_deg=(35.0 if idx % 2 == 0 else -15.0, 0.0, -18.0))

        for part in (hd, cap, e_l, e_r, tor, leg_l, leg_r, arm_l, arm_r):
            part.parent = root

        # Subtle lively work/cheer bobbing
        phase_up = 0.06 if idx % 2 == 0 else -0.04
        root.location = (x, y, z)
        root.keyframe_insert(data_path="location", frame=1)
        root.location = (x, y, z + abs(phase_up))
        root.keyframe_insert(data_path="location", frame=mid)
        root.location = (x, y, z)
        root.keyframe_insert(data_path="location", frame=max(3, frame_end))
        roots.append(root)
    return roots


def add_3d_callout_arrow(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    color_hex: str,
    col: bpy.types.Collection | None = None,
    *,
    frame_end: int = 60,
    shaft_r: float = 0.06,
) -> bpy.types.Object:
    """Create a pulsing 3D geometric directional callout arrow pointing from `start` to `end`."""
    v0 = mathutils.Vector(start)
    v1 = mathutils.Vector(end)
    vec = v1 - v0
    length = max(0.25, vec.length)
    direction = vec.normalized()
    mid_pt = (v0 + v1) * 0.5

    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.2
    root.location = mid_pt
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = direction.to_track_quat("Z", "Y")
    link_to_collection(root, col)

    mat = make_toon_mat(f"{name}_Mat", color_hex, emission_lift=0.85, roughness=0.4)
    head_len = min(0.45, length * 0.36)
    shaft_len = max(0.08, length - head_len)

    shaft = add_cylinder(f"{name}_Shaft", shaft_r, shaft_len, (0.0, 0.0, -head_len * 0.5), mat, col, vertices=12, outline=0.018)
    head = add_cone(f"{name}_Head", shaft_r * 2.5, 0.01, head_len, (0.0, 0.0, shaft_len * 0.5), mat, col, vertices=12, outline=0.018)
    for part in (shaft, head):
        if hasattr(part, "visible_shadow"):
            part.visible_shadow = False
        part.parent = root

    mid_f = max(2, frame_end // 2)
    root.scale = (1.0, 1.0, 1.0)
    root.keyframe_insert(data_path="scale", frame=1)
    root.scale = (1.16, 1.16, 1.12)
    root.keyframe_insert(data_path="scale", frame=mid_f)
    root.scale = (1.0, 1.0, 1.0)
    root.keyframe_insert(data_path="scale", frame=max(3, frame_end))
    return root
