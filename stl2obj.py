#!/usr/bin/env python3
"""
stl2obj: STL 3D 모델을 OBJ 파일로 가공하는 파이썬 스크립트.

[방식 1: Blender 실행 파일 호출 전용]
시스템에 설치된 Blender 실행 파일(blender / blender.exe)을 subprocess로 호출하여
백그라운드(--background)에서 STL을 OBJ로 가공합니다.

주요 처리 단계:
1. CLI 인자 식별 및 시스템 Blender 실행 파일 경로 탐색
2. subprocess로 Blender 프로세스 실행 (blender_stl2obj.py에 작업 위임)
3. Blender 내에서:
   - STL 불러오기 및 단일 메시로 병합 (Join)
   - 재질(Material) 제거
   - 사용자 지정 각도 회전 (필요 시)
   - 면 수 단순화 (Decimate: 기본 8000개)
   - 바운딩 박스 중심을 원점 (0, 0, 0)에 맞춤
   - 가장 긴 변의 길이를 지정된 크기(기본 0.10 m = 10 cm)로 스케일링
   - Wavefront OBJ (+Y Up, -Z Forward)로 내보내기
4. 변환 완료 후 결과 파일 검증

사용법:
  python stl2obj.py <입력 stl 파일 경로> <출력 obj 파일 경로. *기본 경로: statues/출력 파일 경로>

사용법 예:
  python stl2obj.py input.stl horse.obj
  python stl2obj.py input.stl hydra.obj --target-size 0.10 --decimate 8000
  python stl2obj.py input.stl horse.obj --rotate-x 90
"""

import os
import sys
import argparse
import shutil
import subprocess
from pathlib import Path


def find_blender_binary():
    """시스템에 설치된 Blender 실행 파일 경로를 탐색"""
    # 1. 환경변수 확인 (BLENDER_BIN, BLENDER_PATH, BLENDER)
    for env_var in ("BLENDER_BIN", "BLENDER_PATH", "BLENDER"):
        val = os.environ.get(env_var)
        if val:
            candidate = Path(val)
            if candidate.is_file():
                return str(candidate)

    # 2. PATH 환경변수 확인
    blender_in_path = shutil.which("blender")
    if blender_in_path:
        return blender_in_path

    # 3. 홈 디렉토리의 blender (BlenderProc 다운로드 기본 위치: ~/blender/)
    home = Path.home()
    candidates = list(home.glob("blender/**/blender")) + list(home.glob("blender/**/blender.exe"))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    # 4. Windows 일반 설치 경로
    if sys.platform == "win32":
        prog_files = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        ]
        for pf in prog_files:
            found = list(Path(pf).glob("Blender Foundation/Blender */blender.exe"))
            if found:
                return str(found[-1])

    # 5. macOS 일반 설치 경로
    if sys.platform == "darwin":
        mac_app = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if mac_app.is_file():
            return str(mac_app)

    # 6. Linux 일반 설치 경로
    for p in ("/usr/bin/blender", "/snap/bin/blender", "/usr/local/bin/blender"):
        if Path(p).is_file():
            return p

    return None


def verify_obj(path: Path, expected_longest: float):
    """생성된 OBJ 파일이 규격을 만족하는지 검증합니다."""
    if not path.is_file():
        sys.exit(f"[오류] OBJ 파일이 생성되지 않았습니다: {path}")

    lo, hi, nv, nf = [1e9] * 3, [-1e9] * 3, 0, 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                xyz = [float(t) for t in line.split()[1:4]]
                lo = [min(a, b) for a, b in zip(lo, xyz)]
                hi = [max(a, b) for a, b in zip(hi, xyz)]
                nv += 1
            elif line.startswith("f "):
                nf += 1

    dims = [hi[i] - lo[i] for i in range(3)]
    centre = [(hi[i] + lo[i]) / 2.0 for i in range(3)]
    longest = max(dims)

    print("\n" + "=" * 60)
    print(f"[검증 결과] {path.name}")
    print(f"  - 정점(Vertex): {nv:,}개, 면(Face): {nf:,}개")
    print(f"  - 최종 크기 (X, Y, Z m): {[round(d, 4) for d in dims]}")
    print(f"  - 가장 긴 변: {longest:.4f} m (기대값: {expected_longest:.4f} m)")
    print(f"  - 바운딩박스 중심: {[round(c, 6) for c in centre]}")

    warn = 0
    if abs(longest - expected_longest) > 0.1 * expected_longest:
        print(f"  [경고] 가장 긴 변이 기대값({expected_longest} m)과 10% 이상 차이납니다.")
        warn += 1
    if max(abs(c) for c in centre) > 0.05 * longest:
        print("  [경고] 바운딩박스 중심이 원점에서 다소 벗어나 있습니다.")
        warn += 1

    if warn == 0:
        print("  => [OK] OBJ 에셋 규격을 완벽히 만족합니다!")
    else:
        print(f"  => [주의] 경고 {warn}건 발생. 옵션 설정을 확인하세요.")
    print("=" * 60 + "\n")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Blender 실행 파일을 subprocess로 호출하여 STL을 hw2_repro 규격의 OBJ로 변환합니다."
    )
    parser.add_argument("input", help="입력 STL 파일 경로 (예: my_horse.stl)")
    parser.add_argument("output", help="출력 OBJ 파일 경로 (예: assets/statue/horse.obj)")
    parser.add_argument(
        "--target-size",
        type=float,
        default=0.10,
        help="가장 긴 변의 목표 크기 (단위: 미터, 기본값: 0.10 m = 10 cm)",
    )
    parser.add_argument(
        "--decimate",
        type=int,
        default=8000,
        help="단순화할 목표 면(Face) 수 (기본값: 8000, 0 지정 시 생략)",
    )
    parser.add_argument(
        "--rotate-x",
        type=float,
        default=0.0,
        help="X축 기준 회전 각도(도 단위, 기본값: 0.0)",
    )
    parser.add_argument(
        "--rotate-y",
        type=float,
        default=0.0,
        help="Y축 기준 회전 각도(도 단위, 기본값: 0.0)",
    )
    parser.add_argument(
        "--rotate-z",
        type=float,
        default=0.0,
        help="Z축 기준 회전 각도(도 단위, 기본값: 0.0)",
    )
    parser.add_argument(
        "--blender-bin",
        default=None,
        help="사용할 Blender 실행 파일 경로 직접 지정",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statues")
    os.makedirs(OUT_DIR, exist_ok=True)

    input_file = Path(args.input).resolve()
    output_file = Path(OUT_DIR, args.output).resolve()

    if not input_file.is_file():
        sys.exit(f"[오류] 입력 STL 파일을 찾을 수 없습니다: {input_file}")

    # Blender 실행 파일 탐색
    blender_bin = args.blender_bin or find_blender_binary()
    if not blender_bin:
        sys.exit(
            "[오류] 시스템에서 Blender 실행 파일을 찾을 수 없습니다.\n"
            "  해결 방법:\n"
            "  1) Blender가 설치되어 있다면 --blender-bin <경로> 또는 환경변수 BLENDER_BIN에 지정하세요.\n"
            "  2) ./00_setup.sh 를 실행하여 ~/blender 에 설치된 Blender 4.2.1을 사용할 수도 있습니다."
        )

    # Blender 내부에서 실행될 작업자 스크립트 경로
    here = Path(__file__).resolve().parent
    worker_script = here / "blender_stl2obj.py"
    if not worker_script.is_file():
        sys.exit(f"[오류] Blender 작업자 스크립트를 찾을 수 없습니다: {worker_script}")

    # subprocess로 Blender 호출 명령어 구성
    # 형식: blender --background --python <worker.py> -- <arguments>
    cmd = [
        blender_bin,
        "--background",
        "--python",
        str(worker_script),
        "--",
        str(input_file),
        str(output_file),
        "--target-size",
        str(args.target_size),
        "--decimate",
        str(args.decimate),
        "--rotate-x",
        str(args.rotate_x),
        "--rotate-y",
        str(args.rotate_y),
        "--rotate-z",
        str(args.rotate_z),
    ]

    print(f"[stl2obj] Blender 실행 파일 호출 중: {blender_bin}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        sys.exit(f"[오류] Blender 변환 작업 중 오류가 발생했습니다 (종료 코드: {result.returncode})")

    # 변환 결과 OBJ 자가 검증
    verify_obj(output_file, args.target_size)


if __name__ == "__main__":
    main()
