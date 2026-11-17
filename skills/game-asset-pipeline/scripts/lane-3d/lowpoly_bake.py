"""High-poly textured GLB -> game-size GLB with freshly baked colour and normal maps.

Made for local image-to-3D output (local_i23d.py), which looks clean at ~600k triangles but is a
thin double wall, so it tears when any simplifier (ComfyUI's or Blender's) takes it to a game
budget. This rebuilds one solid skin with a voxel remesh, collapses that to the target, makes a
new UV layout and re-bakes base colour, metallic, roughness and normals from the dense model.

usage: blender -b --factory-startup -P lowpoly_bake.py -- <in.glb> <out.glb> [target_tris=60000] [tex=2048] [voxel_frac=0.004]

Writes <out>.glb, <out>_basecolor.png, <out>_normal.png, <out>_metallic_roughness.png and
<out>_report.json. Bakes on CPU so it never competes for the GPU. A 700k -> 60k model at 2048
takes about 10 seconds.
"""
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = Path(argv[0]), Path(argv[1])
target = int(argv[2]) if len(argv) > 2 else 60000
tex = int(argv[3]) if len(argv) > 3 else 2048
voxel_frac = float(argv[4]) if len(argv) > 4 else 0.004  # voxel size as a fraction of the bbox diagonal
dst.parent.mkdir(parents=True, exist_ok=True)
t0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no mesh in " + str(src))
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
high = bpy.context.view_layer.objects.active
high.name = "high"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


high_tris = tri_count(high)
corners = [high.matrix_world @ Vector(c) for c in high.bound_box]
diag = (Vector(map(max, zip(*corners))) - Vector(map(min, zip(*corners)))).length

# --- low-poly: duplicate, collapse, fresh UVs ------------------------------------------
low = high.copy()
low.data = high.data.copy()
low.name = "low"
scene.collection.objects.link(low)
bpy.ops.object.select_all(action="DESELECT")
low.select_set(True)
bpy.context.view_layer.objects.active = low
# glTF import splits vertices along every UV seam; weld them or the collapse cannot cross a seam
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=diag * 1e-5)
bpy.ops.object.mode_set(mode="OBJECT")
welded_verts = len(low.data.vertices)

# TRELLIS.2 output is a thin double wall (outer and inner skin joined), and any simplifier tears it.
# Rebuild one solid skin: voxel remesh, then drop inside-out and stray pieces.
low.data.remesh_voxel_size = diag * voxel_frac
low.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
bm = bmesh.new()
bm.from_mesh(low.data)
bm.verts.ensure_lookup_table()
seen, shells = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, faces = [v], set()
    seen.add(v.index)
    while stack:
        x = stack.pop()
        faces.update(x.link_faces)
        for e in x.link_edges:
            o = e.other_vert(x)
            if o.index not in seen:
                seen.add(o.index)
                stack.append(o)
    vol = 0.0
    for f in faces:
        co = [l.vert.co for l in f.loops]
        for i in range(1, len(co) - 1):
            vol += co[0].dot(co[i].cross(co[i + 1])) / 6.0
    shells.append((vol, faces))
biggest = max(s[0] for s in shells)
drop = [f for vol, faces in shells if vol <= 0 or vol < biggest * 0.001 for f in faces]
shells_kept = sum(1 for vol, _ in shells if vol > 0 and vol >= biggest * 0.001)
bmesh.ops.delete(bm, geom=drop, context="FACES")
bm.to_mesh(low.data)
bm.free()
low.data.update()
remeshed_tris = tri_count(low)

if tri_count(low) > target:
    dec = low.modifiers.new("Dec", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = target / tri_count(low)
    bpy.ops.object.modifier_apply(modifier=dec.name)
while low.data.uv_layers:
    low.data.uv_layers.remove(low.data.uv_layers[0])
low.data.uv_layers.new(name="UVMap")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

# --- material that receives the bakes ---------------------------------------------------
def new_image(name, colour):
    img = bpy.data.images.new(name, tex, tex, alpha=False)
    if not colour:
        img.colorspace_settings.name = "Non-Color"
    return img


mat = bpy.data.materials.new("LowPoly")
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
targets = {}
for key, colour in (("basecolor", True), ("metallic", False), ("roughness", False), ("normal", False)):
    targets[key] = nt.nodes.new("ShaderNodeTexImage")
    targets[key].image = new_image(key, colour)
low.data.materials.clear()
low.data.materials.append(mat)

# --- bake dense -> low (links are added after baking so the targets are not read while written)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 4
bpy.ops.object.select_all(action="DESELECT")
high.select_set(True)
low.select_set(True)
bpy.context.view_layer.objects.active = low
common = dict(use_selected_to_active=True, cage_extrusion=diag * 0.015, max_ray_distance=diag * 0.04,
              margin=8, margin_type="EXTEND", use_clear=True)
times = {}


def run_bake(key, kind, **extra):
    for n in nt.nodes:
        n.select = False
    targets[key].select = True
    nt.nodes.active = targets[key]
    t = time.time()
    bpy.ops.object.bake(type=kind, **common, **extra)
    times[key + "_sec"] = round(time.time() - t, 1)


def bake_input(key, socket_name):
    """Bake what feeds one Principled input of the dense model, as plain emission.
    A DIFFUSE colour bake would do for base colour only on non-metals: metal has no diffuse
    part, so gold trim comes out black."""
    undo = []
    for m in high.data.materials:
        if not m or not m.use_nodes:
            continue
        t = m.node_tree
        b = next((n for n in t.nodes if n.type == "BSDF_PRINCIPLED"), None)
        o = next((n for n in t.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if not b or not o:
            continue
        em = t.nodes.new("ShaderNodeEmission")
        inp = b.inputs[socket_name]
        if inp.is_linked:
            t.links.new(inp.links[0].from_socket, em.inputs["Color"])
        else:
            v = inp.default_value
            em.inputs["Color"].default_value = tuple(v) if hasattr(v, "__len__") else (v, v, v, 1.0)
        t.links.new(em.outputs["Emission"], o.inputs["Surface"])
        undo.append((t, b, o, em))
    run_bake(key, "EMIT")
    for t, b, o, em in undo:
        t.links.new(b.outputs["BSDF"], o.inputs["Surface"])
        t.nodes.remove(em)


bake_input("basecolor", "Base Color")
bake_input("metallic", "Metallic")
bake_input("roughness", "Roughness")
run_bake("normal", "NORMAL", normal_space="TANGENT")


def pixels(img):
    a = np.empty(tex * tex * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(-1, 4)


# glTF wants roughness in green and metallic in blue of one image
packed = np.ones((tex * tex, 4), dtype=np.float32)
packed[:, 1] = pixels(targets["roughness"].image)[:, 0]
packed[:, 2] = pixels(targets["metallic"].image)[:, 0]
metal_mean = float(packed[:, 2].mean())
img_mr = new_image("metallic_roughness", False)
img_mr.pixels.foreach_set(packed.ravel())
for key in ("metallic", "roughness"):
    bpy.data.images.remove(targets[key].image)
    nt.nodes.remove(targets.pop(key))
n_mr = nt.nodes.new("ShaderNodeTexImage")
n_mr.image = img_mr
n_sep = nt.nodes.new("ShaderNodeSeparateColor")
n_map = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(targets["basecolor"].outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(n_mr.outputs["Color"], n_sep.inputs["Color"])
nt.links.new(n_sep.outputs["Green"], bsdf.inputs["Roughness"])
nt.links.new(n_sep.outputs["Blue"], bsdf.inputs["Metallic"])
nt.links.new(targets["normal"].outputs["Color"], n_map.inputs["Color"])
nt.links.new(n_map.outputs["Normal"], bsdf.inputs["Normal"])
for img, suffix in ((targets["basecolor"].image, "_basecolor.png"), (targets["normal"].image, "_normal.png"),
                    (img_mr, "_metallic_roughness.png")):
    img.filepath_raw = str(dst.with_name(dst.stem + suffix))
    img.file_format = "PNG"
    img.save()

bpy.ops.object.select_all(action="DESELECT")
low.select_set(True)
bpy.context.view_layer.objects.active = low
bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB", use_selection=True)

report = {"source": str(src), "output": str(dst), "high_tris": high_tris, "low_tris": tri_count(low),
          "high_verts": len(high.data.vertices), "welded_verts": welded_verts,
          "remeshed_tris": remeshed_tris, "shells_found": len(shells), "shells_kept": shells_kept,
          "low_verts": len(low.data.vertices), "texture_px": tex, "bytes": dst.stat().st_size,
          "metallic_mean": round(metal_mean, 3),
          "total_sec": round(time.time() - t0, 1), **times}
dst.with_name(dst.stem + "_report.json").write_text(json.dumps(report, indent=1))
print("LOWPOLY", json.dumps(report))
