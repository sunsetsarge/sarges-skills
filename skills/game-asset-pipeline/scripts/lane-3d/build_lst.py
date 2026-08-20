# Build a WW2 LST (Landing Ship, Tank) from primitives, rendered bow-3/4.
# An LST is a long low flat-decked transport with a tall BLUNT bow that opens
# into two doors + a ramp — unmistakably NOT a battleship. Renders 4 roll frames.
# blender -b -P build_lst.py -- <abs_out_dir>
import bpy, math, sys, os
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index("--")+1]
os.makedirs(OUT, exist_ok=True)
RES = 768

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
sc.render.film_transparent = True
sc.render.resolution_x = RES; sc.render.resolution_y = RES
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'

def mat(name, rgb, rough=0.7, metal=0.2):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    return m

M_HULL = mat("hull", (0.30, 0.32, 0.30))    # navy gray-green
M_DECK = mat("deck", (0.22, 0.23, 0.20))
M_DARK = mat("dark", (0.14, 0.15, 0.13))
M_RED  = mat("red",  (0.35, 0.14, 0.10), 0.8, 0.0)  # boot-topping / red hull below waterline
M_RAMP = mat("ramp", (0.26, 0.27, 0.24), 0.5, 0.4)

objs = []
def box(name, sx, sy, sz, loc, m, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = (sx, sy, sz)
    if rot: o.rotation_euler = rot
    o.data.materials.append(m); objs.append(o); return o

# Ship axis: bow toward -Y (camera looks up -Y). Long, low, flat.
L, W, H = 9.0, 2.2, 1.1
box("hull", W, L, H, (0, 0, H/2), M_HULL)            # main box hull
box("belowwl", W*1.02, L*0.96, 0.35, (0,0,0.18), M_RED)  # red below-waterline strip
box("deck", W*0.92, L*0.9, 0.10, (0, 0, H+0.05), M_DECK) # flat tank deck
# tall blunt bow (the LST signature) at the front (-Y)
box("bow", W, 1.6, H*1.5, (0, -L/2+0.55, H*0.75), M_HULL)
# bow doors (two vertical panels, slightly darker) + ramp seam
box("door_l", W*0.36, 0.10, H*1.2, (-W*0.24, -L/2-0.16, H*0.72), M_DARK)
box("door_r", W*0.36, 0.10, H*1.2, ( W*0.24, -L/2-0.16, H*0.72), M_DARK)
box("ramp",   W*0.7, 0.9, 0.10, (0, -L/2-0.55, H*0.18), M_RAMP, rot=(math.radians(78),0,0))
# small bridge/superstructure at the STERN (+Y) — LSTs have aft island
box("bridge", W*0.7, 1.1, H*1.3, (0, L/2-0.9, H+0.75), M_HULL)
box("bridge2", W*0.5, 0.7, H*0.8, (0, L/2-0.9, H+1.7), M_DECK)
box("mast", 0.06, 0.06, 1.3, (0, L/2-0.9, H+2.5), M_DARK)
# a couple AA gun tubs on deck
for gx, gy in [(-W*0.28, L*0.2), (W*0.28, -L*0.05)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.28, depth=0.35, location=(gx, gy, H+0.28))
    o = bpy.context.active_object; o.name = "tub"; o.data.materials.append(M_DARK); objs.append(o)
# hint of cargo: two tank-ish blocks on the open deck
for tx in (-0.4, 0.5):
    box("cargo", 0.7, 1.0, 0.5, (tx, 0.3, H+0.35), M_DECK)

def sun(name, rot, e):
    d = bpy.data.lights.new(name, 'SUN'); d.energy = e
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o); o.rotation_euler = rot
sun("key", (math.radians(52), 0, math.radians(-28)), 3.4)
sun("fill", (math.radians(60), 0, math.radians(140)), 1.1)

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 50
cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
center = Vector((0, 0, H*0.9)); dist = 15.5
az = math.radians(22); elev = math.radians(14)   # bow-3/4 so the LST shape reads
cam.location = (dist*math.cos(elev)*math.sin(az), -dist*math.cos(elev)*math.cos(az), center.z + dist*math.sin(elev))
cam.rotation_euler = (center - Vector(cam.location)).to_track_quat('-Z','Y').to_euler()

base_mw = [(o, o.matrix_world.copy()) for o in objs]
for i in range(4):
    ph = 2*math.pi*i/4
    roll = math.radians(1.2)*math.cos(ph)
    R = Matrix.Rotation(roll, 4, 'Y')
    for o, mw in base_mw: o.matrix_world = R @ mw
    sc.render.filepath = os.path.join(OUT, f"lst2_{i}.png")
    bpy.ops.render.render(write_still=True)
    print("[lst2] wrote", sc.render.filepath, flush=True)
print("[lst2] DONE", flush=True)
