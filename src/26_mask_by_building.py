# -*- coding: utf-8 -*-
"""
[Phase 5 - 마스킹 최종 확정] GIS건물통합정보(중랑구)로 마스킹 규칙을 교체한다.

기존 규칙(24번 스크립트): 반경 300m 내 전체 상가업소 수가 0이면 마스킹
  -> '업소'는 상업시설만 잡히므로, 순수 주거지·나대지처럼 건물은 있지만
     반경 300m 안에 상가가 하나도 없는 곳까지 같이 걸러버릴 수 있어서
     "완전한 배제"가 안 된다는 한계가 있었음.

새 규칙: 격자와 교차하는 '건물'이 0개면 마스킹 (업종/용도는 따지지 않음)
  -> 건물 자체가 있는지만 보므로, 도로·하천·산지처럼 애초에 건물을 지을 수
     없는 땅을 더 직접적으로 걸러낼 수 있음. 대신 상가가 없어도 건물(주택 등)만
     있으면 마스킹되지 않으므로, "지을 수는 있는 땅"은 후보로 남는다는 차이가 있음.

지오메트리 이상치 처리:
  - 건물 30,902개 중 결측/무효(is_valid=False)/빈 지오메트리는 없었음.
  - 면적이 1㎡ 미만인 폴리곤 49개(0.16%) 발견 -- 실제 건물이 1㎡보다 작을 수는
    없으므로(예: 최소 0.02㎡) 디지타이징 과정의 스냅 오류로 판단해 마스킹
    판정에서 제외(있어도 "건물 없음"과 동일하게 취급). 다만 격자 전체 기준으로
    49개는 매우 적어 결과에 미치는 영향은 미미할 것으로 예상.
"""
import io
import os

import geopandas as gpd
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split

from utils_geo import load_shp_as_5179, TARGET_CRS

FEATURE_COLS = [
    "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
    "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
    "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
    "food_cnt_300m", "edu_cnt_300m",
]
TARGET_COL = "연평균_매출_금액_log"
MIN_BUILDING_AREA = 1.0  # m^2 미만은 디지타이징 오류로 보고 제외

# 사용자 지시: 이번에 확정한 고/저 임계값을 이후 고정해서 쓴다.
# (다음에 이 스크립트를 다시 돌려도 매번 임계값이 흔들리지 않도록 상수로 못박아 둠)
# 2026-07-15, 건물기반 마스킹 적용 후 모집단(마스킹 제외 1,390개 격자)의
# score_log 중앙값으로 1회 확정. 데이터명세서 "Phase5 마스킹 규칙 변경 이력"에도 기록.
FIXED_SCORE_THRESHOLD = 19.840999

LGB_PARAMS = dict(
    n_estimators=1000, learning_rate=0.03, num_leaves=7, min_child_samples=15,
    subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1,
)

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def train_v3a_model():
    df = pd.read_csv("data/processed/trdar_features_for_model_v2.csv", encoding="utf-8-sig")
    X, y = df[FEATURE_COLS], df[TARGET_COL]
    X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_tr2, X_val2, y_tr2, y_val2 = train_test_split(X_train_full, y_train_full, test_size=0.15, random_state=42)
    model = lgb.LGBMRegressor(**LGB_PARAMS)
    model.fit(
        X_tr2, y_tr2, eval_set=[(X_val2, y_val2)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )
    return model


if __name__ == "__main__":
    log("1) v3a 모델 재학습 중...")
    model = train_v3a_model()

    log("2) 중랑구 격자 불러오는 중 (업소기반 마스킹 결과 포함된 v2 파일 사용)...")
    jn_grid = gpd.read_file("data/processed/jungnang_scored_grid_v2.gpkg", layer="grid")
    jn_grid = jn_grid.rename(columns={
        "masked_infeasible": "masked_biz_based",
        "quadrant": "quadrant_biz_based",
    })
    log(f"중랑구 격자 수: {len(jn_grid)}\n")

    log("3) GIS건물통합정보(중랑구) 불러와 좌표계 통일 및 지오메트리 점검 중...")
    buildings = load_shp_as_5179("data/raw/F_FAC_BUILDING_서울_중랑구/F_FAC_BUILDING_11260_202605.shp")
    log(f"전체 건물 수: {len(buildings)}")
    log(f"결측 geometry: {buildings.geometry.isna().sum()}, 무효(is_valid=False): "
        f"{(~buildings.geometry.is_valid).sum()}, 빈 geometry: {buildings.geometry.is_empty.sum()}")

    tiny = buildings.geometry.area < MIN_BUILDING_AREA
    log(f"면적 {MIN_BUILDING_AREA}㎡ 미만(디지타이징 오류로 판단, 제외): {tiny.sum()}개")
    buildings = buildings[~tiny].copy()
    log(f"마스킹 판정에 사용할 최종 건물 수: {len(buildings)}\n")

    log("4) 격자와 교차하는 건물이 있는지 공간조인으로 확인 중 (predicate='intersects')...")
    pairs = gpd.sjoin(jn_grid[["grid_id", "geometry"]], buildings[["geometry"]], how="inner", predicate="intersects")
    grids_with_building = set(pairs["grid_id"].unique())
    jn_grid["building_cnt"] = jn_grid["grid_id"].apply(lambda g: 1 if g in grids_with_building else 0)
    # 참고용으로 실제 교차 건물 개수도 남겨둔다 (마스킹 판정 자체는 0개/1개 이상으로만 씀)
    building_count_per_grid = pairs.groupby("grid_id").size()
    jn_grid["building_cnt"] = jn_grid["grid_id"].map(building_count_per_grid).fillna(0).astype(int)

    jn_grid["masked_building_based"] = jn_grid["building_cnt"] == 0
    log(f"건물 기반 마스킹된 격자 수: {jn_grid['masked_building_based'].sum()} / {len(jn_grid)} "
        f"({jn_grid['masked_building_based'].mean()*100:.1f}%)\n")

    log("5) 업소 기반 마스크 vs 건물 기반 마스크 비교...")
    compare = pd.crosstab(jn_grid["masked_biz_based"], jn_grid["masked_building_based"],
                           rownames=["업소기반(이전)"], colnames=["건물기반(신규)"])
    log(compare.to_string())
    only_biz = ((jn_grid["masked_biz_based"]) & (~jn_grid["masked_building_based"])).sum()
    only_building = ((~jn_grid["masked_biz_based"]) & (jn_grid["masked_building_based"])).sum()
    both = ((jn_grid["masked_biz_based"]) & (jn_grid["masked_building_based"])).sum()
    log(f"\n업소기반에서만 마스킹(건물기반에선 해제): {only_biz}개 -- 상가는 없지만 건물(주택 등)은 있는 곳")
    log(f"건물기반에서만 마스킹(업소기반에선 통과): {only_building}개 -- 상가 300m 반경엔 뭔가 있었지만 격자 자체엔 건물이 없는 곳(도로/공터 등)")
    log(f"둘 다 마스킹: {both}개")

    log("\n6) 점수 계산...")
    jn_grid["score_log"] = model.predict(jn_grid[FEATURE_COLS])

    log("7) 고/저 임계값 적용 (건물기반 마스킹 이후 모집단 중앙값으로 확정된 고정값 사용)...")
    computed_median = jn_grid.loc[~jn_grid["masked_building_based"], "score_log"].median()
    log(f"참고: 지금 다시 계산한 모집단 중앙값 = {computed_median:.6f} (고정값과 비교용)")
    log(f"*** 사용하는 고정 임계값: {FIXED_SCORE_THRESHOLD} (log 스케일, 2026-07-15 확정) ***")
    jn_grid["score_high"] = jn_grid["score_log"] >= FIXED_SCORE_THRESHOLD

    def quadrant(row):
        if row["masked_building_based"]:
            return "출점불가(건물없음)"
        if row["score_high"] and row["has_store"]:
            return "고득점_점포있음"
        elif row["score_high"] and not row["has_store"]:
            return "고득점_점포없음(신규후보)"
        elif not row["score_high"] and row["has_store"]:
            return "저득점_점포있음"
        else:
            return "저득점_점포없음"

    jn_grid["quadrant"] = jn_grid.apply(quadrant, axis=1)
    log("\n최종(건물기반 마스킹) 분류별 격자 수:")
    log(jn_grid["quadrant"].value_counts().to_string())

    log("\n8) 도로·하천·산지가 걸러졌는지 표본 확인...")
    # 중랑천은 중랑구 서쪽 경계를 흐르는 하천. 건물이 있을 수 없는 대표 지점으로 확인.
    river_check = jn_grid[jn_grid["building_cnt"] == 0]
    log(f"건물 0개인 격자의 total_biz_cnt_300m 분포(참고, 상가 자체는 있었을 수도 있는지 확인):")
    log(river_check["total_biz_cnt_300m"].describe().to_string())

    os.makedirs("data/processed", exist_ok=True)
    jn_grid.to_file("data/processed/jungnang_scored_grid_v3.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/jungnang_scored_grid_v3.gpkg")

    candidates = jn_grid[jn_grid["quadrant"] == "고득점_점포없음(신규후보)"].sort_values("score_log", ascending=False)
    log(f"\n최종 신규 출점 후보지: {len(candidates)}개, 상위 10개:")
    log(candidates[["grid_id", "score_log", "competitor_cnt_300m", "building_cnt", "subway_dist_m"]].head(10).to_string())

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/26_mask_by_building_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/26_mask_by_building_log.txt 저장됨")
