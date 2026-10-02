"""Capture two same-frame references from the CURRENT Blender camera.

Run through the Blender MCP tool `blender_execute_blender_code`, or paste into
Blender's Python console. Writes next to the .blend file:

  ref_now.png      EEVEE render, 1536x864  -> camera, framing, materials
  massing_now.png  Workbench white + outline -> pure structure (geometry lock)

Then feed both to grsai:
  python grsai.py gen -p prompt.txt -r ref_now.png massing_now.png \
      --model gpt-image-2.5 --quality high --aspect 1536x1024 --out result.png
"""
import bpy
from mathutils import Vector

sc = bpy.context.scene
cam = sc.camera
if cam is None:
    raise RuntimeError("scene has no camera")

print("CAM", cam.name, list(cam.location), [round(v, 4) for v in cam.rotation_euler], "lens", cam.data.lens)
print("VIEW_DIST_M", round((cam.matrix_world.translation - Vector((4, 4, 0))).length, 2))

# building bounds without the large ground plane (report storeys / footprint in the prompt)
mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
for o in sc.objects:
    if o.type != "MESH" or o.name.lower() in {"ground", "floor", "site"}:
        continue
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
print("BUILD_BOUNDS", [round(v, 2) for v in mn], [round(v, 2) for v in mx])

was_engine = sc.render.engine
was_res = (sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage)

sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1536, 864, 100

# 1) styled view render
sc.render.engine = "BLENDER_EEVEE"
sc.render.filepath = "//ref_now.png"
bpy.ops.render.render(write_still=True)
print("WROTE", bpy.path.abspath("//ref_now.png"))

# 2) white massing render (structure lock reference)
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (1, 1, 1)
sh.show_object_outline = True
sh.show_shadows = True
sh.show_cavity = True
sc.render.filepath = "//massing_now.png"
bpy.ops.render.render(write_still=True)
print("WROTE", bpy.path.abspath("//massing_now.png"))

sc.render.engine = was_engine
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = was_res
print("DONE")
