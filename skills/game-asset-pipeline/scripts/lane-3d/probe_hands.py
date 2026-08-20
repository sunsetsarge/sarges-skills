import bpy, sys
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=argv[0])
sc = bpy.context.scene
act = max(bpy.data.actions, key=lambda a: a.frame_range[1]-a.frame_range[0])
sc.frame_set(int((act.frame_range[0]+act.frame_range[1])/2))
arm = next(o for o in sc.objects if o.type == 'ARMATURE')
dg = bpy.context.evaluated_depsgraph_get()
armE = arm.evaluated_get(dg)
for bn in ('RightHand','LeftHand','Head','Hips'):
    w = (arm.matrix_world @ armE.pose.bones[bn].matrix).translation
    print(f"[probe] {bn}: ({w.x:.3f}, {w.y:.3f}, {w.z:.3f})", flush=True)
