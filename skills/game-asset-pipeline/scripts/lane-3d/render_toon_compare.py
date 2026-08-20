"""Track A (realism) vs Track B (toon / pixel-art-flat) render of the SAME Meshy
model with IDENTICAL camera + lighting, so the only variable is the shading.

Track A is what SHORE PATROL already ships (raw PBR render, reads as "a 3D render
pasted into a pixel-art scene"). Track B is the missing recipe that makes a render
read as PIXEL ART instead of as a render:

  1. Roughness -> 1.0  (mathematically Specular = 0): kills the glossy tell.
  2. Toon ramp: Diffuse -> Shader-to-RGB -> ColorRamp on CONSTANT interpolation,
     2-3 hard bands. Smooth lighting gradients are the strongest "render" tell;
     hard bands are the strongest "hand-shaded" read. (Shader-to-RGB is EEVEE-only.)
  3. Inverted-hull outline: duplicate the mesh, flip normals, push out with a
     NEGATIVE Solidify, flat dark UNLIT material. Line thickness VARIES per-vertex
     (a noise-weighted vertex group) for a hand-drawn, non-mechanical read.

Kept from the rules that were already right (do not regress these):
  4. Orthographic camera; view_transform = 'Standard' (never Filmic/AgX).
  5. Render at 2-3x target, then LANCZOS down (in postprocess, not here).
  6. ONE shared palette across ALL frames (per-frame quantisation picks different
     cluster centres and produces colour flicker) -- see quantize_shared() below,
     run over the whole frame set after rendering.

Usage:
  blender -b -P render_toon_compare.py -- --glb model.glb --mode b --out out_b.png [--res 1024] [--elev 12] [--az 205]
  blender -b -P render_toon_compare.py -- --glb model.glb --mode a --out out_a.png ...same framing...

Then downscale + shared-palette both PNGs with the companion postprocess
(quantize_shared / lanczos_down in this file, importable without Blender).
"""
import sys
import os
import math


# ------------------------------------------------------------------ Blender side
def _run_blender():
    import bpy
    from mathutils import Vector

    argv = sys.argv[sys.argv.index("--") + 1:]
    opts = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    GLB = opts["glb"]
    MODE = opts.get("mode", "b").lower()
    OUT = os.path.abspath(opts["out"])
    RES = int(opts.get("res", 1024))
    ELEV = math.radians(float(opts.get("elev", 12)))
    AZ = math.radians(float(opts.get("az", 205)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    def log(*a): print("[toon]", *a, flush=True)

    # --- scene: EEVEE Next (Shader-to-RGB needs EEVEE), Standard, transparent ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else \
        ("BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "CYCLES")
    sc.render.film_transparent = True
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'   # RULE 4: never Filmic/AgX

    bpy.ops.import_scene.gltf(filepath=GLB)
    # drop Meshy's stray Icosphere placeholder / tiny meshes
    for o in list(sc.objects):
        if o.type == 'MESH' and (o.name.startswith("Icosphere") or len(o.data.vertices) < 100):
            bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for o in sc.objects if o.type == 'MESH']

    # --- lights (identical for A and B) ---
    def add_sun(name, rot, energy):
        d = bpy.data.lights.new(name, 'SUN'); d.energy = energy
        o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o)
        o.rotation_euler = rot
        return o
    add_sun("key", (math.radians(50), 0, math.radians(-30)), 3.5)
    add_sun("fill", (math.radians(60), 0, math.radians(140)), 1.2)
    world = bpy.data.worlds.new("w"); sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    # --- bbox / framing ---
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in meshes:
        oe = o.evaluated_get(dg)
        for c in oe.bound_box:
            w = oe.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    center = (lo + hi) / 2
    size = hi - lo
    reach = max(size.x, size.y, size.z)

    # --- ORTHOGRAPHIC camera (RULE 4) ---
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = 'ORTHO'
    cam_d.ortho_scale = reach * 1.15            # ~8% margin each side
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    dist = reach * 3.0
    cam.location = (center.x + dist * math.cos(ELEV) * math.sin(AZ),
                    center.y - dist * math.cos(ELEV) * math.cos(AZ),
                    center.z + dist * math.sin(ELEV))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()

    if MODE == "b":
        _apply_toon(bpy, meshes, reach)

    sc.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    log("MODE", MODE, "wrote", OUT)


def _base_color_source(nt, nodes):
    """Return ('tex', node) if base colour is an image, else ('rgb', (r,g,b,a))."""
    princ = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if princ is None:
        return ("rgb", (0.8, 0.8, 0.8, 1.0))
    bc = princ.inputs["Base Color"]
    if bc.is_linked:
        return ("tex", bc.links[0].from_node)
    return ("rgb", tuple(bc.default_value))


def _apply_toon(bpy, meshes, reach):
    """RULES 1-3: roughness->1 (via unlit emission), toon ramp, inverted-hull outline."""
    # --- 1 + 2: rebuild every material as base_colour x banded-lighting -> Emission ---
    done = set()
    for o in meshes:
        for slot in o.material_slots:
            mat = slot.material
            if mat is None or mat.name in done:
                continue
            done.add(mat.name)
            mat.use_nodes = True
            nt = mat.node_tree
            nodes, links = nt.nodes, nt.links
            kind, src = _base_color_source(nt, nodes)

            out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None) \
                or nodes.new('ShaderNodeOutputMaterial')

            diff = nodes.new('ShaderNodeBsdfDiffuse')            # white lighting probe
            s2rgb = nodes.new('ShaderNodeShaderToRGB')
            ramp = nodes.new('ShaderNodeValToRGB')
            cr = ramp.color_ramp
            cr.interpolation = 'CONSTANT'                        # RULE 2: hard bands
            cr.elements[0].position = 0.0; cr.elements[0].color = (0.34, 0.34, 0.34, 1)
            cr.elements[1].position = 0.5; cr.elements[1].color = (0.68, 0.68, 0.68, 1)
            e3 = cr.elements.new(0.82); e3.color = (1.0, 1.0, 1.0, 1)   # 3 bands
            mult = nodes.new('ShaderNodeMixRGB')
            mult.blend_type = 'MULTIPLY'; mult.inputs['Fac'].default_value = 1.0
            emis = nodes.new('ShaderNodeEmission')

            links.new(diff.outputs['BSDF'], s2rgb.inputs['Shader'])
            links.new(s2rgb.outputs['Color'], ramp.inputs['Fac'])
            links.new(ramp.outputs['Color'], mult.inputs['Color2'])
            if kind == "tex":
                links.new(src.outputs['Color'], mult.inputs['Color1'])
            else:
                mult.inputs['Color1'].default_value = src
            links.new(mult.outputs['Color'], emis.inputs['Color'])
            links.new(emis.outputs['Emission'], out.inputs['Surface'])
            mat.use_backface_culling = False                    # model shows fully

    # --- 3: inverted-hull outline, per mesh, with VARYING thickness ---
    outline_mat = bpy.data.materials.new("outline_dark")
    outline_mat.use_nodes = True
    ont = outline_mat.node_tree; ont.nodes.clear()
    oout = ont.nodes.new('ShaderNodeOutputMaterial')
    oemis = ont.nodes.new('ShaderNodeEmission')
    oemis.inputs['Color'].default_value = (0.02, 0.02, 0.03, 1)   # flat dark, unlit
    ont.links.new(oemis.outputs['Emission'], oout.inputs['Surface'])
    # Inverted-hull: cull the near (front) faces of the outward, normal-flipped
    # shell so ONLY the far rim pokes past the model's silhouette as the outline.
    outline_mat.use_backface_culling = True

    base_thick = reach * 0.016
    for o in list(meshes):
        hull = o.copy()
        hull.data = o.data.copy()
        bpy.context.collection.objects.link(hull)
        hull.data.materials.clear()
        hull.data.materials.append(outline_mat)

        # VARYING line thickness: a vertex group weighted by a cheap positional
        # noise, mapped to [0.45, 1.0], drives the Solidify thickness so the line
        # swells and thins like a hand-drawn stroke instead of a uniform CAD offset.
        vg = hull.vertex_groups.new(name="outline_w")
        me = hull.data
        for v in me.vertices:
            p = v.co
            n = (math.sin(p.x * 12.1 + p.y * 7.3)
                 + math.sin(p.y * 9.7 + p.z * 5.1)
                 + math.sin(p.z * 11.3 + p.x * 3.9))          # -3..3
            w = 0.45 + 0.55 * ((n / 3.0) * 0.5 + 0.5)          # -> ~0.45..1.0
            vg.add([v.index], max(0.0, min(1.0, w)), 'REPLACE')

        solid = hull.modifiers.new("outline", 'SOLIDIFY')
        solid.thickness = -base_thick                          # negative -> outward shell
        solid.offset = 1.0
        solid.use_flip_normals = True
        solid.vertex_group = "outline_w"                       # group NAME (str)
        solid.thickness_vertex_group = 1.0                     # group INFLUENCE (float 0..1)
        solid.use_rim = True


# ------------------------------------------------------------ postprocess (no bpy)
def lanczos_down(in_path, out_path, target_h):
    """RULE 5: render big, then LANCZOS down to the on-screen height."""
    from PIL import Image
    im = Image.open(in_path).convert("RGBA")
    w = round(im.width * target_h / im.height)
    im.resize((w, target_h), Image.LANCZOS).save(out_path)


def quantize_shared(paths, n_colors=24):
    """RULE 6: ONE shared palette across ALL frames. Build the palette from every
    frame pooled together, then map each frame to it — no per-frame flicker."""
    from PIL import Image
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    # pool opaque pixels, quantise once to get a shared palette
    pooled = Image.new("RGB", (sum(i.width for i in imgs), max(i.height for i in imgs)))
    x = 0
    for im in imgs:
        pooled.paste(im.convert("RGB"), (x, 0)); x += im.width
    pal_img = pooled.quantize(colors=n_colors, method=Image.MEDIANCUT)
    for p, im in zip(paths, imgs):
        rgb = im.convert("RGB").quantize(palette=pal_img, dither=Image.NONE)
        out = rgb.convert("RGBA")
        # restore original alpha (quantise drops it)
        out.putalpha(im.getchannel("A"))
        out.save(p)


if __name__ == "__main__":
    if "bpy" in sys.modules or any("blender" in a.lower() for a in sys.argv[:1]):
        _run_blender()
    else:
        try:
            import bpy  # noqa
            _run_blender()
        except ImportError:
            print("Run inside Blender: blender -b -P render_toon_compare.py -- --glb ... --mode a|b --out ...")
