# -*- coding: utf-8 -*-
"""
[Phase 4 - 요청사항 2] 상권 매출 타깃(712개 상권)에 격자 피처를 면적 가중평균으로 연결한다.

방식: 면적 가중평균 (사용자와 상의해서 결정, 2026-07-14)
  상권 폴리곤과 겹치는 격자들을 찾아서, 겹친 면적 비율로 가중평균한 값을
  그 상권의 "대표 피처값"으로 사용한다.

  [Phase 3 생활인구 배분과의 차이 주의]
  Phase 3에서는 '인구수'가 그 구역 전체의 합산 가능한 값이라서
  겹친 면적만큼 '비례 배분해서 합산'하는 방식을 썼다 (평균을 내면 틀림).
  여기서는 반대로 '이 상권은 평균적으로 얼마나 밀집한 동네인가'를 나타내는
  대표값(전형적인 밀도/거리 수준)을 구하는 것이 목적이라서 '가중평균'이 맞다.
  (이미 각 격자 피처 자체가 "그 지점 주변의 밀도/거리"라서, 상권 전체를
  대표하는 값 = 그 상권을 이루는 격자들의 평균이 되어야 자연스럽다.)

공간 연산: 상권 폴리곤과 격자를 겹쳐서 교집합 조각의 면적을 구하고,
그 면적을 가중치로 각 상권의 피처 평균을 낸다 (Phase 3와 같은 방식의
공간 연산이지만, 마지막에 '합산' 대신 '평균'을 낸다는 점만 다름).
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
]

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 타깃(상권별 연평균 매출) 불러오는 중...")
    target = pd.read_csv("data/processed/target_trdar_annual.csv", encoding="utf-8-sig")
    target["상권_코드"] = target["상권_코드"].astype(str)
    log(f"타깃 상권 수: {len(target)}\n")

    log("2) 상권 폴리곤 불러오는 중...")
    trdar = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    ).to_crs(TARGET_CRS)
    trdar["TRDAR_CD"] = trdar["TRDAR_CD"].astype(str)
    trdar = trdar[trdar["TRDAR_CD"].isin(target["상권_코드"])][["TRDAR_CD", "geometry"]].copy()
    trdar["trdar_area"] = trdar.geometry.area
    log(f"매칭되는 상권 폴리곤 수: {len(trdar)}\n")

    log("3) 격자 피처 불러오는 중...")
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
    for col in FEATURE_COLS:
        pairs[f"_w_{col}"] = pairs[col] * pairs["overlap_area"]

    # 결측(subway_monthly_traffic 등)이 있는 격자는 그 피처의 가중평균 계산에서만 자연스럽게 제외되도록
    # weight도 결측이 아닌 행만 따로 합산한다 (건수형 na 처리)
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

    log(f"\n최종 상권x피처 테이블 행 수: {len(result)}")
    log("피처별 결측 상권 수:")
    for col in FEATURE_COLS:
        log(f"  {col}: {result[col].isna().sum()}개")

    os.makedirs("data/processed", exist_ok=True)
    result.to_csv("data/processed/trdar_features_for_model.csv", index=False, encoding="utf-8-sig")
    log("\n저장 완료: data/processed/trdar_features_for_model.csv")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/14_link_grid_to_trdar_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/14_link_grid_to_trdar_log.txt 저장됨")
