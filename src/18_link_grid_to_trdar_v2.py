# -*- coding: utf-8 -*-
"""
[Phase 4 v2] target_trdar_v2(708개 상권, 점포당 평균매출)에 격자 피처
(v1의 10종 + 집객시설 2종 = 12종)를 면적 가중평균으로 연결한다.

방식은 14번 스크립트와 완전히 동일 (면적 가중평균). 타깃과 피처 목록만 v2로 교체.
"""
import io
import os

import geopandas as gpd
import pandas as pd

from utils_geo import TARGET_CRS

FEATURE_COLS = [
    "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
    "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
    "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
    "food_cnt_300m", "edu_cnt_300m",
]

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 타깃 v2(점포당 평균매출) 불러오는 중...")
    target = pd.read_csv("data/processed/target_trdar_v2.csv", encoding="utf-8-sig")
    target["상권_코드"] = target["상권_코드"].astype(str)
    log(f"타깃 상권 수: {len(target)}\n")

    log("2) 상권 폴리곤 불러오는 중...")
    trdar = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    ).to_crs(TARGET_CRS)
    trdar["TRDAR_CD"] = trdar["TRDAR_CD"].astype(str)
    trdar = trdar[trdar["TRDAR_CD"].isin(target["상권_코드"])][["TRDAR_CD", "geometry"]].copy()
    log(f"매칭되는 상권 폴리곤 수: {len(trdar)}\n")

    log("3) 격자 피처(v2, 12종) 불러오는 중...")
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    log(f"격자 수: {len(grid)}\n")

    log("4) 상권 x 격자 겹치는 쌍 찾고 교집합 면적 계산 중...")
    pairs = gpd.sjoin(
        trdar, grid[["grid_id", "geometry"] + FEATURE_COLS], how="inner", predicate="intersects"
    )
    log(f"겹치는 (상권, 격자) 쌍의 수: {len(pairs)}")

    grid_geom_by_id = grid.set_index("grid_id")["geometry"]
    trdar_geom_by_cd = trdar.set_index("TRDAR_CD")["geometry"]
    pairs["grid_geom"] = pairs["grid_id"].map(grid_geom_by_id)
    pairs["trdar_geom"] = pairs["TRDAR_CD"].map(trdar_geom_by_cd)
    pairs["overlap_area"] = gpd.GeoSeries(pairs["trdar_geom"], crs=TARGET_CRS).intersection(
        gpd.GeoSeries(pairs["grid_geom"], crs=TARGET_CRS)
    ).area

    log("\n5) 겹친 면적으로 가중평균 계산 중...")
    agg_rows = []
    for trdar_cd, g in pairs.groupby("TRDAR_CD"):
        row = {"TRDAR_CD": trdar_cd}
        for col in FEATURE_COLS:
            valid = g.dropna(subset=[col])
            if len(valid) == 0 or valid["overlap_area"].sum() == 0:
                row[col] = float("nan")
            else:
                row[col] = (valid[col] * valid["overlap_area"]).sum() / valid["overlap_area"].sum()
        agg_rows.append(row)
    agg = pd.DataFrame(agg_rows)

    result = target.merge(agg, left_on="상권_코드", right_on="TRDAR_CD", how="left").drop(columns="TRDAR_CD")

    log(f"\n최종 상권x피처(v2) 테이블 행 수: {len(result)}")
    log("피처별 결측 상권 수:")
    for col in FEATURE_COLS:
        log(f"  {col}: {result[col].isna().sum()}개")

    os.makedirs("data/processed", exist_ok=True)
    result.to_csv("data/processed/trdar_features_for_model_v2.csv", index=False, encoding="utf-8-sig")
    log("\n저장 완료: data/processed/trdar_features_for_model_v2.csv")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/18_link_grid_to_trdar_v2_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/18_link_grid_to_trdar_v2_log.txt 저장됨")
