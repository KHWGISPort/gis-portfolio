# -*- coding: utf-8 -*-
"""
[Phase 4 v2 - 요청사항 2] 집객시설 피처 추가: 격자별 반경 300m 내 음식점 수, 학원/교육시설 수.

v1에서는 상가업소정보 전체(537,489건) 중 편의점만 썼는데, 이번에는 같은 파일에서
음식점(상권업종대분류명='음식')과 교육시설(상권업종대분류명='교육')을 추가로 뽑는다.
계산 방식은 경쟁 밀도 피처(09번 스크립트)와 동일한 KD-Tree 반경 탐색.
"""
import io
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from utils_geo import points_from_lonlat

RADIUS = 300

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 격자 불러오는 중...")
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    grid = grid.drop(columns=[c for c in ["food_cnt_300m", "edu_cnt_300m"] if c in grid.columns])
    centroids = grid.geometry.centroid
    centroid_xy = np.column_stack([centroids.x.values, centroids.y.values])
    log(f"격자 수: {len(grid)}\n")

    log("2) 상가업소정보 전체 불러오는 중 (음식점 + 교육시설 추출)...")
    df = pd.read_csv(
        "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv",
        encoding="utf-8-sig", low_memory=False,
        usecols=["상권업종대분류명", "위도", "경도"],
    )
    food_df = df[df["상권업종대분류명"] == "음식"]
    edu_df = df[df["상권업종대분류명"] == "교육"]
    log(f"음식점 수: {len(food_df)}, 교육시설 수: {len(edu_df)}\n")

    food_pts = points_from_lonlat(food_df, lon_col="경도", lat_col="위도", source_crs="EPSG:4326")
    edu_pts = points_from_lonlat(edu_df, lon_col="경도", lat_col="위도", source_crs="EPSG:4326")

    for name, pts, col in [("음식점", food_pts, "food_cnt_300m"), ("교육시설", edu_pts, "edu_cnt_300m")]:
        xy = np.column_stack([pts.geometry.x.values, pts.geometry.y.values])
        tree = cKDTree(xy)
        counts = tree.query_ball_point(centroid_xy, r=RADIUS, return_length=True)
        grid[col] = counts
        log(f"[{col}] 평균 {counts.mean():.2f}개, 최댓값 {counts.max()}개, 0개인 격자 {int((counts == 0).sum())}개")

    grid.to_file("data/processed/grid_features.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/grid_features.gpkg (layer=grid, 집객시설 컬럼 추가)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/16_feature_amenities_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/16_feature_amenities_log.txt 저장됨")
