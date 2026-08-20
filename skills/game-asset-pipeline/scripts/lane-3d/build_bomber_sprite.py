# Render the bomber GLB for the game: seen from BELOW-FRONT (the player looks up
# at it bearing down / passing overhead). Nose should point toward screen-BOTTOM.
# Usage: blender -b -P build_bomber_sprite.py -- <glb> <out.png> [elev_deg] [az_deg] [roll_deg]
import bpy, sys, math
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--")+1:]
GLB  = argv[0]; OUT = argv[1]
ELEV = float(argv[2]) if len(argv) > 2 else -32.0   # negative = below, looking up
AZ   = float(argv[3]) if len(argv) > 3 else 0.0
ROLL = float(argv[4]) if len(argv) > 4 else 0.0     # camera roll to point nose down
RES  = 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for e in ("BLENDER_EEVEE_NEXT","BLENDER_EEVEE"):
    if e in [x.identifier for x in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]:
        sc.render.engine = e; break
sc.render.film_transparent = True
sc.render.resolution_x = RES; sc.render.resolution_y = RES
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'

bpy.ops.import_scene.gltf(filepath=GLB)
for o in list(sc.objects):
    if o.type=='MESH' and (o.name.startswith("Icosphere") or len(o.data.vertices)<100):
        bpy.data.objects.remove(o, do_unlink=True)
meshes=[o for o in sc.objects if o.type=='MESH']

def bbox(objs):
    lo=Vector((1e9,)*3); hi=Vector((-1e9,)*3)
    for o in objs:
        for c in o.bound_box:
            w=o.matrix_world@Vector(c); lo=Vector(map(min,lo,w)); hi=Vector(map(max,hi,w))
    return lo,hi
lo,hi=bbox(meshes); center=(lo+hi)/2; size=hi-lo
print("[bomber] dims", tuple(round(v,3) for v in size), flush=True)

def sun(rot,e):
    d=bpy.data.lights.new("s",'SUN'); d.energy=e
    o=bpy.data.objects.new("s",d); sc.collection.objects.link(o); o.rotation_euler=rot
sun((math.radians(50),0,math.radians(-30)),2.5)
sun((math.radians(-55),0,math.radians(140)),4.2)  # strong underlight (belly faces camera)
sun((math.radians(-70),0,math.radians(20)),2.5)
# ambient world fill so the belly isn't a black silhouette
world=bpy.data.worlds.new("w"); sc.world=world; world.use_nodes=True
bg=world.node_tree.nodes["Background"]
bg.inputs[0].default_value=(0.55,0.6,0.7,1); bg.inputs[1].default_value=0.5

# frame by the two largest axes so the whole plane fits from any angle
fill=0.82; fov=2*math.atan(18/50)
extent=max(size.x,size.y)
dist=(extent/fill/2)/math.tan(fov/2)
elev=math.radians(ELEV); az=math.radians(AZ)
cam_d=bpy.data.cameras.new("c"); cam_d.lens=50
cam=bpy.data.objects.new("c",cam_d); sc.collection.objects.link(cam); sc.camera=cam
cam.location=(center.x+dist*math.cos(elev)*math.sin(az),
              center.y-dist*math.cos(elev)*math.cos(az),
              center.z+dist*math.sin(elev))
rot=(center-cam.location).to_track_quat('-Z','Y').to_euler()
cam.rotation_euler=rot
# apply roll about the camera view axis
if ROLL:
    cam.rotation_mode='QUATERNION'
    q=cam.rotation_euler.to_quaternion()
    from mathutils import Quaternion
    view_axis=q@Vector((0,0,-1))
    cam.rotation_quaternion=Quaternion(view_axis, math.radians(ROLL))@q

sc.render.filepath=OUT
bpy.ops.render.render(write_still=True)
print("[bomber] wrote", OUT, flush=True); print("DONE", flush=True)
