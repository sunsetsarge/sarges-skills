import bpy, sys
argv = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=argv[0])
for o in bpy.context.scene.objects:
    if o.type == 'ARMATURE':
        print("[bones]", [b.name for b in o.data.bones], flush=True)
        for bn in o.data.bones:
            if 'hand' in bn.name.lower() or 'Hand' in bn.name:
                print("[hand]", bn.name, "head", list(bn.head_local), flush=True)
acts = [(a.name, list(a.frame_range)) for a in bpy.data.actions]
print("[actions]", acts, flush=True)
