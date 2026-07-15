# -*- coding: utf-8 -*-
"""
[Phase 3 - 요청사항 2] 경쟁 밀도 피처: 격자 중심점 기준 반경 100/300/500m 내 편의점 수.

공간 연산 그림으로 설명:
  1) 각 격자 셀의 중심점(centroid)을 하나씩 뽑는다. (격자 61,644개 -> 점 61,644개)
  2) 편의점 9,407개 점의 위치를 바탕으로 최근접 탐색 트리(KD-Tree)를 만든다.
     -> 트리를 쓰면 "이 중심점에서 반경 R 안에 점이 몇 개 있는지"를 매번 전수
        비교하지 않고 훨씬 빠르게 찾을 수 있다 (마치 지도를 미리 색인해둔 것과 같음).
  3) 각 중심점마다 반경 100m, 300m, 500m 세 가지로 각각 질의해서
     "그 반경 안에 들어오는 편의점 개수"를 센다. (동심원 3개를 그려서
     각 동심원 안에 점이 몇 개 있는지 세는 것과 같은 방식)
"""
import io
import os

import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree

RADII = [100, 300, 500]

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("격자 불러오는 중...")
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    log(f"격자 수: {len(grid)}")

    log("편의점 포인트 불러오는 중...")
    stores = gpd.read_file("data/processed/convenience_stores.gpkg")
    log(f"편의점 수: {len(stores)}\n")

    # 격자 중심점 좌표, 편의점 좌표를 (x, y) 배열로 뽑는다
    centroids = grid.geometry.centroid
    centroid_xy = np.column_stack([centroids.x.values, centroids.y.values])
    store_xy = np.column_stack([stores.geometry.x.values, stores.geometry.y.values])

    # 편의점 좌표로 KD-Tree 생성 (반경 검색을 빠르게 하기 위함)
    tree = cKDTree(store_xy)

    for r in RADII:
        counts = tree.query_ball_point(centroid_xy, r=r, return_length=True)
        col = f"competitor_cnt_{r}m"
        grid[col] = counts
        log(f"[{col}] 평균 {counts.mean():.2f}개, 최댓값 {counts.max()}개, 0개인 격자 {int((counts == 0).sum())}개")

    grid.to_file("data/processed/grid_features.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/grid_features.gpkg (layer=grid, 경쟁밀도 컬럼 추가)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/09_feature_competition_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/09_feature_competition_log.txt 저장됨")
