# -*- coding: utf-8 -*-
"""
[Phase 3 - 요청사항 1] 서울 전체를 정사각 격자로 나눈다.

절차 (공간 연산 그림으로 설명):
  1) 서울 경계(행정동 union)의 사각형 범위(bounding box)를 구한다.
  2) 그 범위를 GRID_SIZE(기본 100m) 간격으로 가로세로 촘촘히 나눠
     정사각형 셀들을 만든다. (마치 모눈종이를 서울 위에 겹쳐놓는 것과 같음)
  3) 이 중에서 서울 경계와 조금이라도 겹치는 셀만 남긴다.
     -> 셀 모양은 자르지 않고 정사각형 그대로 유지한다. 경계에 걸친 셀은
        면적의 일부만 서울 안에 있어도 통째로 포함시킨다 (셀을 실제로
        자르면 정사각형이 깨져서 "격자"의 의미가 없어지기 때문).

GRID_SIZE를 바꾸면(예: 150, 250) 같은 코드로 다른 크기의 격자를 바로
다시 만들 수 있다.
"""
import io
import os

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from utils_geo import build_seoul_boundary, TARGET_CRS

# ===== 여기 숫자만 바꾸면 격자 크기를 바꿔서 재실행할 수 있다 (단위: m) =====
GRID_SIZE = 100

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def build_grid(seoul_boundary, grid_size):
    """서울 경계의 bounding box를 grid_size 간격 정사각형으로 채우고, 경계와 겹치는 셀만 남긴다."""
    minx, miny, maxx, maxy = seoul_boundary.bounds

    # bounding box를 grid_size로 나눈 칸 수 (올림 처리해서 끝자락도 다 덮도록)
    n_cols = int(np.ceil((maxx - minx) / grid_size))
    n_rows = int(np.ceil((maxy - miny) / grid_size))

    cells = []
    for i in range(n_cols):
        x0 = minx + i * grid_size
        x1 = x0 + grid_size
        for j in range(n_rows):
            y0 = miny + j * grid_size
            y1 = y0 + grid_size
            cells.append(box(x0, y0, x1, y1))

    grid = gpd.GeoDataFrame({"geometry": cells}, crs=TARGET_CRS)
    log(f"전체 bounding box 격자 수(필터 전): {len(grid)} ({n_cols} x {n_rows})")

    # 서울 경계와 조금이라도 겹치는 셀만 남김 (셀 모양은 자르지 않음)
    intersects_mask = grid.geometry.intersects(seoul_boundary)
    grid = grid[intersects_mask].reset_index(drop=True)
    log(f"서울 경계와 겹치는 격자 수(필터 후): {len(grid)}")

    grid["grid_id"] = [f"G{grid_size}_{i:06d}" for i in range(len(grid))]
    grid = grid[["grid_id", "geometry"]]
    return grid


if __name__ == "__main__":
    log(f"GRID_SIZE = {GRID_SIZE}m\n")

    log("1) 서울 경계(행정동 union) 생성 중...")
    seoul_boundary = build_seoul_boundary()
    log(f"서울 전체 면적: {seoul_boundary.area / 1_000_000:.1f} km^2\n")

    log("2) 격자 생성 중...")
    grid = build_grid(seoul_boundary, GRID_SIZE)

    total_cell_area = GRID_SIZE * GRID_SIZE * len(grid) / 1_000_000
    log(f"격자 전체 면적(셀 정사각형 기준 합): {total_cell_area:.1f} km^2 (서울 실제 면적과 비슷하되, 경계 밖으로 살짝 튀어나온 셀들 때문에 더 큼)\n")

    os.makedirs("data/processed", exist_ok=True)
    out_path = "data/processed/grid_features.gpkg"
    grid.to_file(out_path, layer="grid", driver="GPKG")
    log(f"저장 완료: {out_path} (layer=grid)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/08_build_grid_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/08_build_grid_log.txt 저장됨")
