# Build a WW2 Higgins boat (LCVP) from primitives and render it bow-on:
# open rectangular hull, flat bow ramp (up + down variants), engine box,
# helmeted troop heads in the well. Renders 4 roll-wobble frames (ramp up)
# + 1 beached frame (ramp down). blender -b -P build_lcvp.py -- <out_dir>
import bpy, math, sys, os
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index("--")+1]
os.makedirs(OUT, exist_ok=True)
RES = 768

sc = bpy.context.scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
sc.render.film_transparent = True
sc.render.resolution_x = RES; sc.render.resolution_y = RES
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'

def mat(name, rgb, rough=0.7, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m

M_HULL = mat("hull", (0.28, 0.30, 0.22))       # gray-green plywood
M_DARK = mat("dark", (0.16, 0.17, 0.13))
M_RAMP = mat("ramp", (0.32, 0.33, 0.28), 0.6, 0.3)  # steel ramp
M_HELM = mat("helm", (0.22, 0.26, 0.16))
M_SKIN = mat("skin", (0.75, 0.55, 0.42))

objs = []
def box(name, sx, sy, sz, loc, material, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name
    o.scale = (sx, sy, sz)
    if rot: o.rotation_euler = rot
    o.data.materials.append(material)
    objs.append(o); return o

# Boat axis: bow toward -Y (camera at az 0 sees the bow head-on).
L, W, H = 4.2, 1.5, 0.75    # hull length, beam, side height
# hull floor
box("floor", W*0.92, L*0.94, 0.06, (0, 0, 0.05), M_HULL)
# hull sides (slight inward taper at stern)
box("side_l", 0.07, L*0.96, H, (-W/2+0.05, 0, H/2), M_HULL)
box("side_r", 0.07, L*0.96, H, ( W/2-0.05, 0, H/2), M_HULL)
# stern transom
box("stern", W*0.98, 0.07, H, (0, L/2-0.05, H/2), M_HULL)
# gunwale caps
box("cap_l", 0.10, L*0.98, 0.05, (-W/2+0.05, 0, H+0.02), M_DARK)
box("cap_r", 0.10, L*0.98, 0.05, ( W/2-0.05, 0, H+0.02), M_DARK)
# engine box at stern
box("engine", W*0.5, 0.5, 0.32, (0, L/2-0.4, H+0.12), M_DARK)
# bow sheer strakes angling down to the ramp
box("sheer_l", 0.07, 0.9, H*0.75, (-W/2+0.05, -L/2+0.45, H*0.62), M_HULL, rot=(math.radians(-14),0,0))
box("sheer_r", 0.07, 0.9, H*0.75, ( W/2-0.05, -L/2+0.45, H*0.62), M_HULL, rot=(math.radians(-14),0,0))

def add_ramp(down):
    if down:
        # ramp rotated forward flat onto the "water"
        r = box("ramp", W*0.86, 0.06, H*1.05, (0, -L/2-0.45, 0.10), M_RAMP, rot=(math.radians(80),0,0))
    else:
        # ramp upright at the bow, slight outward lean
        r = box("ramp", W*0.86, 0.06, H*1.15, (0, -L/2+0.02, H*0.62), M_RAMP, rot=(math.radians(-8),0,0))
    return r

def add_troops():
    heads = []
    import random
    random.seed(7)
    for i in range(6):
        x = random.uniform(-W*0.30, W*0.30)
        y = random.uniform(-L*0.28, L*0.30)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(x, y, H+0.04), segments=12, ring_count=8)
        o = bpy.context.active_object; o.name = f"head{i}"
        o.data.materials.append(M_SKIN); objs.append(o); heads.append(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.13, location=(x, y, H+0.09), segments=12, ring_count=8)
        h = bpy.context.active_object; h.name = f"helm{i}"
        h.scale = (1, 1, 0.62)
        h.data.materials.append(M_HELM); objs.append(h); heads.append(h)
    return heads

add_troops()

# lights + camera (bow-on, matches the fleet: az 0 → camera on -Y, elev 10°)
def sun(name, rot, e):
    d = bpy.data.lights.new(name, 'SUN'); d.energy = e
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o)
    o.rotation_euler = rot
sun("key", (math.radians(50), 0, math.radians(-30)), 3.5)
sun("fill", (math.radians(60), 0, math.radians(140)), 1.2)

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 50
cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam)
sc.camera = cam
# frame generously for the whole boat
center = Vector((0, 0, H*0.7)); dist = 7.2
elev = math.radians(12)
cam.location = (0, -dist*math.cos(elev), center.z + dist*math.sin(elev))
cam.rotation_euler = (center - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()

# render ramp-up wobble frames
ramp = add_ramp(False)
base_mw = [(o, o.matrix_world.copy()) for o in objs + [ramp]]
pivot = Vector((0, 0, 0))
for i in range(4):
    ph = 2*math.pi*i/4
    roll = math.radians(1.5)*math.cos(ph)
    R = Matrix.Rotation(roll, 4, 'Y')
    for o, mw in base_mw: o.matrix_world = R @ mw
    sc.render.filepath = os.path.join(OUT, f"lcvp_{i}.png")
    bpy.ops.render.render(write_still=True)
    print("[lcvp] wrote", sc.render.filepath, flush=True)
for o, mw in base_mw: o.matrix_world = mw

# beached frame: ramp down
bpy.data.objects.remove(ramp, do_unlink=True)
add_ramp(True)
sc.render.filepath = os.path.join(OUT, "lcvp_beached.png")
bpy.ops.render.render(write_still=True)
print("[lcvp] wrote beached", flush=True)
print("[lcvp] DONE", flush=True)
