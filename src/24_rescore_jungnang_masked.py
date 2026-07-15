# -*- coding: utf-8 -*-
"""
[Phase 5 - 보완] 산지/미개발지 오탐 문제를 마스킹 규칙으로 보완한다.

문제 진단 (사용자 지적으로 발견, 2026-07-15):
  중랑구 동/북쪽(망우산·용마산 인근 추정)에 '고득점_점포없음(신규후보)'
  격자가 큰 덩어리로 몰려 있었음. 원인을 파본 결과:
    1) 이 격자들은 competitor_cnt_300m=0, food_cnt_300m≈0.3으로
       사실상 상업활동이 전혀 없는 곳인데도 점수가 정상 후보지와 비슷하게 나옴.
    2) 학습 데이터(708개 상권)는 전부 '이미 상권으로 지정된 곳'이라서
       competitor_cnt_300m 최솟값이 1.57, food_cnt_300m 최솟값이 16.1로,
       상업활동이 0에 가까운 경우를 한 번도 학습해본 적이 없음.
       -> 모델이 학습 범위 밖(외삽) 입력을 받으면 트리 분기 규칙에 따라
          엉뚱한 리프(leaf)로 떨어져 근거 없이 높은 점수가 나올 수 있음.
    3) 부수적으로, 이 격자들이 속한 집계구는 면적이 매우 커서
       (중앙값 520,313m^2로 서울 전체 집계구 중앙값의 45배) 산+주거지가
       한 집계구로 묶여 있는 것으로 보임. 면적 가중 배분의 '균등분포 가정'
       때문에 이 집계구의 적은 인구가 산 부분에도 조금씩(약 23~26명) 배분돼,
       완전히 0이어야 할 인구가 소폭 과대추정됨 (다만 이 효과는 작아서
       점수 이상 현상의 주된 원인은 1)~2)의 외삽 문제로 판단됨).

대응: 반경 300m 내 '업종 무관 전체 상가업소 수'(total_biz_cnt_300m)를
시가지 여부 프록시로 써서, 이 값이 0인 격자는 "출점불가(시가지 아님)"로
마스킹하고 신규후보에서 제외한다.
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
BIZ_MASK_THRESHOLD = 0  # 반경 300m 내 전체 상가업소 수가 이 값 이하이면 마스킹

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

    log("2) 중랑구 격자(total_biz_cnt_300m 포함) 불러오는 중...")
    dong = load_shp_as_5179("data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
    jn_dong = dong[dong["ADM_CD"].astype(str).str.startswith("11070")]
    jn_boundary = jn_dong.union_all()

    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    grid_c = grid.copy()
    grid_c["centroid"] = grid_c.geometry.centroid
    jn_grid = grid[grid_c["centroid"].within(jn_boundary)].copy()
    log(f"중랑구 격자 수: {len(jn_grid)}\n")

    log("3) 점수 계산...")
    jn_grid["score_log"] = model.predict(jn_grid[FEATURE_COLS])

    log("4) 기존 편의점 유무 확인...")
    stores = gpd.read_file("data/processed/convenience_stores.gpkg")
    has_store_pairs = gpd.sjoin(stores[["geometry"]], jn_grid[["grid_id", "geometry"]], how="inner", predicate="within")
    grids_with_store = set(has_store_pairs["grid_id"])
    jn_grid["has_store"] = jn_grid["grid_id"].isin(grids_with_store)

    log(f"5) 마스킹 규칙 적용: 반경 300m 내 전체 상가업소 수 <= {BIZ_MASK_THRESHOLD} -> 출점불가...")
    jn_grid["masked_infeasible"] = jn_grid["total_biz_cnt_300m"] <= BIZ_MASK_THRESHOLD
    log(f"마스킹된(출점불가) 격자 수: {jn_grid['masked_infeasible'].sum()} / {len(jn_grid)} "
        f"({jn_grid['masked_infeasible'].mean()*100:.1f}%)")

    log("\n6) 4분면 분류 (마스킹된 격자는 별도 카테고리로 분리)...")
    score_median = jn_grid.loc[~jn_grid["masked_infeasible"], "score_log"].median()
    log(f"점수 중앙값(마스킹 제외 기준으로 재계산): {score_median:.3f}")
    jn_grid["score_high"] = jn_grid["score_log"] >= score_median

    def quadrant(row):
        if row["masked_infeasible"]:
            return "출점불가(시가지아님)"
        if row["score_high"] and row["has_store"]:
            return "고득점_점포있음"
        elif row["score_high"] and not row["has_store"]:
            return "고득점_점포없음(신규후보)"
        elif not row["score_high"] and row["has_store"]:
            return "저득점_점포있음"
        else:
            return "저득점_점포없음"

    jn_grid["quadrant"] = jn_grid.apply(quadrant, axis=1)
    log("\n마스킹 적용 후 분류별 격자 수:")
    log(jn_grid["quadrant"].value_counts().to_string())

    # 마스킹 전(21번 스크립트 결과)과 비교: 원래 신규후보였던 격자 중 몇 개가 마스킹으로 빠졌는지
    old_grid = gpd.read_file("data/processed/jungnang_scored_grid.gpkg", layer="grid")
    old_candidate_ids = set(old_grid[old_grid["quadrant"] == "고득점_점포없음(신규후보)"]["grid_id"])
    new_candidate_ids = set(jn_grid[jn_grid["quadrant"] == "고득점_점포없음(신규후보)"]["grid_id"])
    log(f"\n마스킹 전 신규후보(21번 스크립트): {len(old_candidate_ids)}개")
    log(f"마스킹 후 신규후보: {len(new_candidate_ids)}개")
    log(f"마스킹으로 제외된(=출점불가로 재분류된) 이전 신규후보 격자 수: {len(old_candidate_ids - new_candidate_ids)}개")

    os.makedirs("data/processed", exist_ok=True)
    jn_grid.to_file("data/processed/jungnang_scored_grid_v2.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/jungnang_scored_grid_v2.gpkg")

    candidates = jn_grid[jn_grid["quadrant"] == "고득점_점포없음(신규후보)"].sort_values("score_log", ascending=False)
    log(f"\n마스킹 후 신규 출점 후보지 상위 10개:")
    log(candidates[["grid_id", "score_log", "competitor_cnt_300m", "total_biz_cnt_300m", "subway_dist_m"]].head(10).to_string())

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/24_rescore_jungnang_masked_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/24_rescore_jungnang_masked_log.txt 저장됨")
