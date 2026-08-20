import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--")+1:]
GLB = argv[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print("=== OBJECTS ===", flush=True)
print("mesh object count:", len(meshes), flush=True)
for o in meshes:
    n = len(o.data.vertices)
    # world bbox
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    dim = hi - lo
    print(f"  '{o.name}' verts={n} bbox_lo=({lo.x:.2f},{lo.y:.2f},{lo.z:.2f}) dim=({dim.x:.2f},{dim.y:.2f},{dim.z:.2f})", flush=True)

# Overall bbox across all meshes
lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
dim = hi - lo
print("=== OVERALL ===", flush=True)
print(f"bbox lo=({lo.x:.2f},{lo.y:.2f},{lo.z:.2f}) hi=({hi.x:.2f},{hi.y:.2f},{hi.z:.2f})", flush=True)
print(f"dims=({dim.x:.2f},{dim.y:.2f},{dim.z:.2f})  [longest axis = hull length]", flush=True)
# Which axis is longest (hull length), which is up
axes = sorted([('x',dim.x),('y',dim.y),('z',dim.z)], key=lambda t:-t[1])
print("axis order (long->short):", axes, flush=True)
print("DONE", flush=True)
