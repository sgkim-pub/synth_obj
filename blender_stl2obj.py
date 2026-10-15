#!/usr/bin/env python3
"""
Blender 내부 실행용 스크립트 (blender -b -P 로 호출됨).
Blender 프로세스 내장 Python(bpy) 환경에서 실제 STL -> OBJ 변환 작업을 수행합니다.
"""

import math
import sys
import argparse
from pathlib import Path

# Blender 내부 환경에서만 임포트되는 bpy
import bpy


def parse_arguments():
    # '--' 뒤의 인자 파싱
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender 내부 STL to OBJ 변환기")
    parser.add_argument("input", help="입력 STL 파일 경로")
    parser.add_argument("output", help="출력 OBJ 파일 경로")
    parser.add_argument("--target-size", type=float, default=0.10, help="가장 긴 변 목표 크기(m)")
    parser.add_argument("--decimate", type=int, default=8000, help="목표 면 수")
    parser.add_argument("--rotate-x", type=float, default=0.0, help="X축 회전 각도")
    parser.add_argument("--rotate-y", type=float, default=0.0, help="Y축 회전 각도")
    parser.add_argument("--rotate-z", type=float, default=0.0, help="Z축 회전 각도")
    return parser.parse_args(argv)


def convert():
    args = parse_arguments()
    input_stl = Path(args.input).resolve()
    output_obj = Path(args.output).resolve()

    if not input_stl.is_file():
        sys.exit(f"[오류] 입력 STL 파일을 찾을 수 없습니다: {input_stl}")

    output_obj.parent.mkdir(parents=True, exist_ok=True)

    print(f"[Blender Worker] Blender {bpy.app.version_string} 가동")
    print(f"[Blender Worker] 입력 STL: {input_stl}")
    print(f"[Blender Worker] 출력 OBJ: {output_obj}")

    # 1. 기존 장면의 모든 객체 제거
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. STL 임포트
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=str(input_stl))
    elif hasattr(bpy.ops.import_mesh, "stl"):
        bpy.ops.import_mesh.stl(filepath=str(input_stl))
    else:
        sys.exit("[오류] 현재 Blender 버전에 STL 임포트 기능이 없습니다.")

    # 3. 메시 객체 필터링 및 병합 (Join)
    mesh_objs = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objs:
        sys.exit(f"[오류] STL 파일에서 유효한 3D 메시를 찾을 수 없습니다: {input_stl}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]

    if len(mesh_objs) > 1:
        print(f"[Blender Worker] {len(mesh_objs)}개 메시 객체 병합")
        bpy.ops.object.join()

    active_obj = bpy.context.view_layer.objects.active

    # 4. 재질(Material) 제거
    active_obj.data.materials.clear()

    # 5. 사용자 지정 회전 적용
    if args.rotate_x != 0 or args.rotate_y != 0 or args.rotate_z != 0:
        print(f"[Blender Worker] 회전 적용: X={args.rotate_x}°, Y={args.rotate_y}°, Z={args.rotate_z}°")
        active_obj.rotation_euler = (
            math.radians(args.rotate_x),
            math.radians(args.rotate_y),
            math.radians(args.rotate_z),
        )
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # 6. 면 수 감소 (Decimate)
    orig_faces = len(active_obj.data.polygons)
    if args.decimate > 0 and orig_faces > args.decimate:
        ratio = float(args.decimate) / float(orig_faces)
        print(f"[Blender Worker] 면 수 최적화(Decimate): {orig_faces}개 -> 목표 {args.decimate}개 (비율: {ratio:.4f})")
        mod = active_obj.modifiers.new(name="Decimate_hw2", type="DECIMATE")
        mod.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=mod.name)
        print(f"[Blender Worker] 면 수 최적화 완료: 현재 {len(active_obj.data.polygons)}개")
    else:
        print(f"[Blender Worker] 현재 면 수: {orig_faces}개 (Decimate 생략)")

    # 7. 원점 중심 정렬 및 목표 크기(미터 단위) 스케일링
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    vertices = [v.co for v in active_obj.data.vertices]
    if not vertices:
        sys.exit("[오류] 메시에 정점이 없습니다.")

    lo = [min(v[i] for v in vertices) for i in range(3)]
    hi = [max(v[i] for v in vertices) for i in range(3)]
    current_dims = [hi[i] - lo[i] for i in range(3)]
    current_center = [(hi[i] + lo[i]) / 2.0 for i in range(3)]
    longest_dim = max(current_dims)

    if longest_dim <= 0:
        sys.exit("[오류] 메시의 크기가 유효하지 않습니다(0 이하).")

    print(f"[Blender Worker] 원본 크기(m): {[round(d, 4) for d in current_dims]}")
    print(f"[Blender Worker] 원본 중심: {[round(c, 4) for c in current_center]}")

    scale_factor = args.target_size / longest_dim
    print(f"[Blender Worker] 목표 크기: {args.target_size:.4f} m (스케일 배율: {scale_factor:.6f})")

    # (v - center) * scale_factor 변환
    for v in active_obj.data.vertices:
        v.co.x = (v.co.x - current_center[0]) * scale_factor
        v.co.y = (v.co.y - current_center[1]) * scale_factor
        v.co.z = (v.co.z - current_center[2]) * scale_factor

    active_obj.data.update()

    # 8. OBJ 내보내기 (Wavefront OBJ 규약: Forward -Z, Up +Y)
    print(f"[Blender Worker] OBJ 파일 내보내는 중: {output_obj}")
    if hasattr(bpy.ops.wm, "obj_export"):
        bpy.ops.wm.obj_export(
            filepath=str(output_obj),
            export_selected_objects=True,
            export_materials=False,
            export_uv=False,
            export_normals=True,
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
        )
    elif hasattr(bpy.ops.export_scene, "obj"):
        bpy.ops.export_scene.obj(
            filepath=str(output_obj),
            use_selection=True,
            use_materials=False,
            use_uvs=False,
            use_normals=True,
            axis_forward="-Z",
            axis_up="Y",
        )
    else:
        sys.exit("[오류] OBJ 내보내기 연산자를 찾을 수 없습니다.")

    print(f"[Blender Worker] OBJ 생성 성공: {output_obj}")


if __name__ == "__main__":
    convert()
