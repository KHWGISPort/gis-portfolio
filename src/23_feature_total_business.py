# -*- coding: utf-8 -*-
"""
[Phase 5 - 사후 보완] 반경 300m 내 '전체' 상가업소 수를 격자 피처로 추가한다.

목적: 편의점 매출 모델은 상권(=이미 상업활동이 있는 곳)으로만 학습됐기 때문에,
      상업활동이 전혀 없는 산지·미개발지에 적용하면 학습 범위 밖 외삽(extrapolation)이
      일어나 엉뚱하게 높은 점수가 나올 수 있음이 확인됐다(중랑구 진단 결과).
      이를 막기 위해 업종을 가리지 않고 '상가업소가 있기는 한지'(=시가지 여부)를
      나타내는 프록시 피처를 만들어, 이후 마스킹 규칙에 사용한다.
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
    grid = grid.drop(columns=[c for c in ["total_biz_cnt_300m"] if c in grid.columns])
    centroids = grid.geometry.centroid
    centroid_xy = np.column_stack([centroids.x.values, centroids.y.values])
    log(f"격자 수: {len(grid)}\n")

    log("2) 상가업소정보 전체(업종 구분 없이) 불러오는 중...")
    df = pd.read_csv(
        "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv",
        encoding="utf-8-sig", low_memory=False, usecols=["위도", "경도"],
    )
    log(f"전체 상가업소 수: {len(df)}\n")

    pts = points_from_lonlat(df, lon_col="경도", lat_col="위도", source_crs="EPSG:4326")
    xy = np.column_stack([pts.geometry.x.values, pts.geometry.y.values])
    tree = cKDTree(xy)
    counts = tree.query_ball_point(centroid_xy, r=RADIUS, return_length=True)
    grid["total_biz_cnt_300m"] = counts

    log(f"[total_biz_cnt_300m] 평균 {counts.mean():.1f}개, 중앙값 {np.median(counts):.0f}개, 0개인 격자 {int((counts == 0).sum())}개")
    log(f"분위수: 5%={np.percentile(counts,5):.0f}, 10%={np.percentile(counts,10):.0f}, 25%={np.percentile(counts,25):.0f}")

    grid.to_file("data/processed/grid_features.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/grid_features.gpkg (layer=grid, total_biz_cnt_300m 컬럼 추가)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/23_feature_total_business_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/23_feature_total_business_log.txt 저장됨")
