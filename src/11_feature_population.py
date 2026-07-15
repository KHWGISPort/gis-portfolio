# -*- coding: utf-8 -*-
"""
[Phase 3 - 요청사항 2] 생활인구 4종 피처를 면적 가중 배분으로 격자에 붙인다.

방식: 면적 가중 배분 (areal weighting) - 사용자와 상의해서 결정 (2026-07-14)
  가정: 집계구 안에서는 인구가 고르게(균등하게) 분포한다고 가정한다.
  (실제로는 건물/도로/공원 등에 따라 인구가 고르지 않지만, 이보다 더 정교하게
   하려면 건물 데이터 등 추가 자료가 필요해 이번 범위에서는 균등분포로 가정함
   -- 데이터명세서에 한계로 기록.)

공간 연산 그림으로 설명:
  1) 격자(정사각형 61,644개)와 집계구 폴리곤(19,153개)을 겹쳐 놓는다.
     -> 마치 두 장의 서로 다른 모양 스티커를 겹쳐 붙이는 것과 같다.
  2) 겹치는 부분(교집합)마다 "그 겹친 조각의 면적"을 구한다.
     격자 하나가 집계구 여러 개에 걸쳐 있으면, 조각도 여러 개 생긴다.
  3) [핵심] 생활인구 값은 "그 집계구 전체의 인구수"라서, 밀도가 아니라
     합산 가능한(extensive) 값이다. 그래서 겹친 면적으로 '평균'을 내면 안 되고,
     '그 집계구 면적 대비 겹친 면적의 비율'만큼만 인구를 떼어와서 더해야 한다.
     예) 집계구 X(면적 20,000㎡, 인구 100명)와 겹친 조각이 6,000㎡면
         -> 그 조각에서 떼어올 인구 = 100 * (6,000 / 20,000) = 30명
     격자 A가 집계구 X 조각(30명)과 집계구 Y 조각(20명)에 걸쳐 있으면
         -> A의 인구 = 30 + 20 = 50명 (단순 평균이 아니라 합산)
  4) 이렇게 하면 좋은 검증 방법이 하나 생긴다: 모든 격자의 인구를 전부 더하면
     원래 집계구별 인구 총합과 거의 같아야 한다(경계 미세 불일치로 아주 살짝만
     달라짐). 이 스크립트 마지막에 이 총합 비교로 배분이 맞았는지 검증한다.
"""
import io
import os

import geopandas as gpd
import pandas as pd

from utils_geo import TARGET_CRS

POP_COLS = ["주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구"]

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 격자 불러오는 중...")
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    # 이전에 잘못된 방식(가중평균)으로 계산해 저장했던 컬럼이 있으면 제거하고 다시 계산
    grid = grid.drop(columns=[c for c in POP_COLS + ["pop_overlap_ratio"] if c in grid.columns])
    grid["grid_area"] = grid.geometry.area
    log(f"격자 수: {len(grid)}\n")

    log("2) 2016년 집계구 경계(bnd_oa_11_2016_4Q) + 생활인구 요약 불러오는 중...")
    oa = gpd.read_file("data/raw/bnd_oa_11_2016_4Q/bnd_oa_11_2016_4Q.shp")
    oa = oa.set_crs(TARGET_CRS, allow_override=True)  # .prj가 EPSG로 자동 인식 안 돼서 명시 지정
    oa["TOT_REG_CD"] = oa["TOT_REG_CD"].astype(str)
    oa["oa_area"] = oa.geometry.area

    lp = pd.read_csv("data/processed/local_people_summary.csv", encoding="utf-8-sig")
    lp["집계구코드"] = lp["집계구코드"].astype(str)

    oa = oa.merge(lp, left_on="TOT_REG_CD", right_on="집계구코드", how="left")
    log(f"집계구 폴리곤 수: {len(oa)} (생활인구 값 결측: {oa[POP_COLS[0]].isna().sum()}개 -- 6번 단계에서 확인한 대로 100% 매칭이므로 0이어야 함)")

    total_by_col = {col: lp[col].sum() for col in POP_COLS}
    log(f"검증용 원본 총합(모든 집계구 합산): { {c: round(v) for c, v in total_by_col.items()} }\n")

    log("3) 격자 x 집계구 겹치는 쌍 찾는 중 (공간 인덱스 사용, sjoin)...")
    pairs = gpd.sjoin(
        grid[["grid_id", "geometry"]], oa[["TOT_REG_CD", "oa_area", "geometry"] + POP_COLS],
        how="inner", predicate="intersects",
    )
    log(f"겹치는 (격자, 집계구) 쌍의 수: {len(pairs)}")

    log("\n4) 각 쌍의 실제 겹친 면적(교집합 면적) 계산 중...")
    # sjoin 결과에는 격자 geometry만 남아있으므로, 집계구 geometry를 다시 붙여서 교집합을 구한다
    pairs = pairs.merge(oa[["TOT_REG_CD", "geometry"]].rename(columns={"geometry": "oa_geom"}), on="TOT_REG_CD")
    grid_geom_by_id = grid.set_index("grid_id")["geometry"]
    pairs["grid_geom"] = pairs["grid_id"].map(grid_geom_by_id)
    pairs["overlap_area"] = gpd.GeoSeries(pairs["grid_geom"], crs=TARGET_CRS).intersection(
        gpd.GeoSeries(pairs["oa_geom"], crs=TARGET_CRS)
    ).area

    log("5) 비례 배분(면적 비율만큼 인구를 떼어와서 합산) 계산 중...")
    # 겹친 조각이 그 집계구 면적의 몇 %를 차지하는지 비율을 구하고, 그 비율만큼만 인구를 떼어온다
    pairs["area_share"] = pairs["overlap_area"] / pairs["oa_area"]
    for col in POP_COLS:
        pairs[f"_alloc_{col}"] = pairs[col] * pairs["area_share"]

    agg = pairs.groupby("grid_id").agg(
        total_overlap_area=("overlap_area", "sum"),
        **{col: (f"_alloc_{col}", "sum") for col in POP_COLS},
    )

    grid = grid.merge(agg[POP_COLS + ["total_overlap_area"]], left_on="grid_id", right_index=True, how="left")

    # 겹치는 면적이 아예 없는 격자는 결측으로 남기고, 겹침 비율은 참고용으로 기록
    grid["pop_overlap_ratio"] = (grid["total_overlap_area"] / grid["grid_area"]).clip(upper=1.0)
    grid = grid.drop(columns=["total_overlap_area", "grid_area"])

    log(f"\n집계구와 전혀 안 겹쳐서 생활인구 값이 결측된 격자 수: {grid[POP_COLS[0]].isna().sum()} / {len(grid)}")
    log(f"겹침 비율(pop_overlap_ratio) 평균: {grid['pop_overlap_ratio'].mean():.3f}, 90% 미만인 격자 수: {(grid['pop_overlap_ratio'] < 0.9).sum()}")
    for col in POP_COLS:
        log(f"[{col}] 평균 {grid[col].mean():.1f}, 최댓값 {grid[col].max():.1f}")

    log("\n6) 검증: 격자 전체 합산 인구 vs 원본 집계구 총합 비교...")
    for col in POP_COLS:
        grid_total = grid[col].sum()
        orig_total = total_by_col[col]
        diff_pct = (grid_total - orig_total) / orig_total * 100
        log(f"[{col}] 격자 합산 {grid_total:,.0f} vs 원본 합산 {orig_total:,.0f} (차이 {diff_pct:+.2f}%)")

    grid.to_file("data/processed/grid_features.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/grid_features.gpkg (layer=grid, 생활인구 컬럼 추가)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/11_feature_population_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/11_feature_population_log.txt 저장됨")
