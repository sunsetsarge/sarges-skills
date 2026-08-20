# Split a GLB mesh into "part" (verts above z_frac of bbox height) and "base",
# then render: base frames (with optional wobble, same recipe as render_frames.py)
# and the part at N z-rotations about its own centroid (perspective-correct
# rotation steps for code-composited turret/rotor overlays).
# Usage: blender -b -P split_render.py -- <config.json>
# unit: {name, glb, azimuth_deg, z_frac, part_rotations: [deg,...],
#        base_frames, base_wobble{...}, elev_deg}
import bpy, bmesh, json, math, sys, os
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--")+1:]
cfg = json.load(open(argv[0]))
OUT = cfg["out_dir"]; RES = cfg.get("res", 768)
os.makedirs(OUT, exist_ok=True)

def log(*a): print("[split]", *a, flush=True)

def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if e in engines:
            sc.render.engine = e; break
    else:
        sc.render.engine = "CYCLES"; sc.cycles.samples = 32
    sc.render.film_transparent = True
    sc.render.resolution_x = RES; sc.render.resolution_y = RES
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    return sc

def add_sun(name, rot, energy):
    d = bpy.data.lights.new(name, 'SUN'); d.energy = energy
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o)
    o.rotation_euler = rot
    return o

def world_bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for o in objs:
        if o.type != 'MESH' or o.hide_render: continue
        oe = o.evaluated_get(dg)
        for c in oe.bound_box:
            w = oe.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi

def place_camera(sc, lo, hi, az_deg, elev_deg):
    center = (lo+hi)/2; size = hi-lo
    height = size.z; width_xy = max(size.x, size.y)
    cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 50
    cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam)
    sc.camera = cam
    fill = 0.84
    fov = 2*math.atan(18/50)
    dist = max((height/fill/2)/math.tan(fov/2), (width_xy/fill/2)/math.tan(fov/2))
    az = math.radians(az_deg); elev = math.radians(elev_deg)
    cam.location = (center.x + dist*math.cos(elev)*math.sin(az),
                    center.y - dist*math.cos(elev)*math.cos(az),
                    center.z + dist*math.sin(elev))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    return center, height

for unit in cfg["units"]:
    name = unit["name"]
    sc = setup_scene()
    bpy.ops.import_scene.gltf(filepath=unit["glb"])
    for o in list(sc.objects):
        if o.type == 'MESH' and (o.name.startswith("Icosphere") or len(o.data.vertices) < 100):
            bpy.data.objects.remove(o, do_unlink=True)
    add_sun("key", (math.radians(50), 0, math.radians(-30)), 3.5)
    add_sun("fill", (math.radians(60), 0, math.radians(140)), 1.2)

    meshes = [o for o in sc.objects if o.type == 'MESH']
    lo, hi = world_bbox(meshes)
    zsplit = lo.z + (hi.z - lo.z) * unit["z_frac"]
    log(name, "bbox z", round(lo.z,3), round(hi.z,3), "split at", round(zsplit,3))

    # Split every mesh at the z plane deterministically with bmesh:
    # faces are assigned by centroid z (no edit-mode selection semantics —
    # glTF imports carry stale edge/face select flags that break ops.separate).
    part_objs = []
    for o in list(meshes):
        mw = o.matrix_world.copy()
        src_me = o.data

        def build_half(keep_above):
            bm = bmesh.new(); bm.from_mesh(src_me)
            drop = []
            for f in bm.faces:
                cz = sum((mw @ v.co).z for v in f.verts) / len(f.verts)
                above = cz > zsplit
                if above != keep_above: drop.append(f)
            if len(drop) == len(bm.faces):
                bm.free(); return None
            bmesh.ops.delete(bm, geom=drop, context='FACES')
            me = bpy.data.meshes.new(src_me.name + ('_part' if keep_above else '_base'))
            bm.to_mesh(me); bm.free()
            # keep materials so textures render
            for mat in src_me.materials: me.materials.append(mat)
            ob = bpy.data.objects.new(me.name, me)
            ob.matrix_world = mw
            bpy.context.collection.objects.link(ob)
            return ob

        p = build_half(True); b = build_half(False)
        if p and b:
            part_objs.append(p)
            # remove the original outright so no visibility pass can resurrect it
            bpy.data.objects.remove(o, do_unlink=True)
            meshes = [m for m in meshes if m is not o] + [b]
    log(name, "part objects:", [o.name for o in part_objs])
    base_objs = [o for o in sc.objects if o.type == 'MESH' and o not in part_objs]
    log(name, "base objects:", [o.name for o in base_objs])

    # camera framed on the FULL model so base and part renders align 1:1
    center, height = place_camera(sc, lo, hi, unit.get("azimuth_deg", 0), unit.get("elev_deg", 10))

    def set_vis(objs, visible):
        for o in objs: o.hide_render = not visible

    # 1) base renders (part hidden), optional wobble around bbox bottom
    set_vis(part_objs, False); set_vis(base_objs, True)
    wob = unit.get("base_wobble"); nb = unit.get("base_frames", 1)
    pivot = Vector((center.x, center.y, lo.z))
    base_mw = [(o, o.matrix_world.copy()) for o in base_objs]
    for i in range(nb):
        if wob:
            ph = 2*math.pi*i/nb
            pitch = math.radians(wob.get("pitch",0))*math.sin(ph)
            roll = math.radians(wob.get("roll",0))*math.cos(ph)
            R = (Matrix.Translation(pivot) @ Matrix.Rotation(pitch,4,'X')
                 @ Matrix.Rotation(roll,4,'Y') @ Matrix.Translation(-pivot))
            for o, mw in base_mw: o.matrix_world = R @ mw
        sc.render.filepath = os.path.join(OUT, f"{name}_base_{i}.png")
        bpy.ops.render.render(write_still=True)
        log("wrote", sc.render.filepath)
    for o, mw in base_mw: o.matrix_world = mw

    # 2) part renders at z-rotations about the part centroid (same camera!)
    set_vis(part_objs, True); set_vis(base_objs, False)
    plo, phi = world_bbox(part_objs)
    pcent = (plo + phi) / 2
    part_mw = [(o, o.matrix_world.copy()) for o in part_objs]
    for j, deg in enumerate(unit.get("part_rotations", [0])):
        R = (Matrix.Translation(pcent) @ Matrix.Rotation(math.radians(deg), 4, 'Z')
             @ Matrix.Translation(-pcent))
        for o, mw in part_mw: o.matrix_world = R @ mw
        sc.render.filepath = os.path.join(OUT, f"{name}_part_{j}.png")
        bpy.ops.render.render(write_still=True)
        log("wrote", sc.render.filepath, "rot", deg)
    for o, mw in part_mw: o.matrix_world = mw
log("ALL DONE")
