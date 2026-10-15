import bpy
import bmesh
import os

# OBJ 파일을 저장할 폴더
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polyhedrons")
os.makedirs(OUT_DIR, exist_ok=True)

# 기존 장면의 물체 삭제
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def create_mesh_object(name, vertices, faces):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)

    # 면의 방향에 맞게 법선을 정리
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def export_obj(obj, filename):
    # 선택된 물체만 OBJ로 내보내기
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.wm.obj_export(
        filepath=os.path.join(OUT_DIR, filename),
        export_selected_objects=True,
        export_materials=False,
    )

# 치수는 미터 단위로 작성: 10 cm = 0.1 m
h = 0.05  # 중심에서 각 면까지 5 cm

# 정육면체: 한 변 10 cm
cube_vertices = [
    (-h, -h, -h), ( h, -h, -h), ( h,  h, -h), (-h,  h, -h),
    (-h, -h,  h), ( h, -h,  h), ( h,  h,  h), (-h,  h,  h),
]
cube_faces = [
    (0, 1, 2, 3), (4, 7, 6, 5),
    (0, 4, 5, 1), (1, 5, 6, 2),
    (2, 6, 7, 3), (3, 7, 4, 0),
]
cube = create_mesh_object("Cube_10cm", cube_vertices, cube_faces)
export_obj(cube, "cube_10cm.obj")

# 정팔면체: 가로·세로·깊이 각각 10 cm
octa_vertices = [
    ( h, 0, 0), (-h, 0, 0),
    (0,  h, 0), (0, -h, 0),
    (0, 0,  h), (0, 0, -h),
]
octa_faces = [
    (4, 0, 2), (4, 2, 1), (4, 1, 3), (4, 3, 0),
    (5, 2, 0), (5, 1, 2), (5, 3, 1), (5, 0, 3),
]
octa = create_mesh_object("Octahedron_10cm", octa_vertices, octa_faces)
export_obj(octa, "octahedron_10cm.obj")

print("완료:", OUT_DIR)
