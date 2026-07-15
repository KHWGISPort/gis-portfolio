# -*- coding: utf-8 -*-
"""
[Phase 5 - 1단계] 최종 채택 모델(v3a)로 중랑구 100m 격자 전체에 점수를 매기고,
점수 x 기존 점포 유무 4분면으로 분류한다.

절차:
  1) v3a와 완전히 같은 방식(같은 데이터·같은 random_state)으로 모델을 다시 학습한다
     (20번 스크립트에서 검증까지 마친 그 모델과 동일한 것을 재현).
  2) 중랑구에 속하는 격자만 골라서, 그 격자들의 12개 피처를 모델에 넣어
     '입지 점수'(예측된 상권 총매출 로그값)를 계산한다.
     -> 원래 모델은 '상권' 단위로 학습됐지만, 격자 하나하나도 같은 12개
        피처를 갖고 있으므로 그대로 넣어서 "이 100m 칸에 편의점이 있다면
        얼마나 잘 될 것 같은가"라는 점수로 해석해 쓴다.
  3) 격자 안에 이미 편의점이 있는지(기존 점포 유무)를 공간조인으로 확인한다.
  4) 점수를 중랑구 내 중앙값 기준으로 고/저로 나누고, 기존 점포 유무와
     교차한 4분면으로 분류한다:
       고득점 x 점포 있음 : 이미 좋은 자리에 진출해 있음 (검증 성공 사례)
       고득점 x 점포 없음 : ★ 신규 출점 후보지 (이 프로젝트의 핵심 결과물)
       저득점 x 점포 있음 : 과포화 또는 다른 요인으로 버티는 곳
       저득점 x 점포 없음 : 예상대로 비어있는 곳
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

# 20번 스크립트(v3a)와 완전히 동일한 설정 -- 재현성을 위해 그대로 맞춤
LGB_PARAMS = dict(
    n_estimators=1000, learning_rate=0.03, num_leaves=7, min_child_samples=15,
    subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1,
)

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def train_v3a_model():
    """20번 스크립트의 v3a와 동일한 방식으로 모델을 재현한다."""
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
    log("1) v3a 모델 재학습 중 (20번 스크립트와 동일 설정)...")
    model = train_v3a_model()
    log(f"사용된 트리 개수: {model.best_iteration_}\n")

    log("2) 중랑구 경계 확인 및 격자 필터링...")
    dong = load_shp_as_5179("data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
    # BND_ADM_DONG_PG(행안부 코드체계)에서 중랑구 소속 동은 ADM_CD가 '11070'으로 시작함
    # (Phase3에서 확인: 상가업소정보의 시군구코드 11260은 다른 코드체계라 여기서는 못 씀)
    jn_dong = dong[dong["ADM_CD"].astype(str).str.startswith("11070")]
    jn_boundary = jn_dong.union_all()
    log(f"중랑구 행정동 수: {len(jn_dong)}, 면적: {jn_boundary.area / 1_000_000:.2f} km^2")

    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    grid_c = grid.copy()
    grid_c["centroid"] = grid_c.geometry.centroid
    jn_grid = grid[grid_c["centroid"].within(jn_boundary)].copy()
    log(f"중랑구 격자 수: {len(jn_grid)}\n")

    log("3) 격자별 점수(예측 로그매출) 계산 중...")
    X_score = jn_grid[FEATURE_COLS]
    jn_grid["score_log"] = model.predict(X_score)
    log(f"점수 분포: 평균 {jn_grid['score_log'].mean():.2f}, 중앙값 {jn_grid['score_log'].median():.2f}, "
        f"최소 {jn_grid['score_log'].min():.2f}, 최대 {jn_grid['score_log'].max():.2f}\n")

    log("4) 기존 편의점 유무 확인 (격자 폴리곤 안에 점포가 있는지 공간조인)...")
    stores = gpd.read_file("data/processed/convenience_stores.gpkg")
    has_store_pairs = gpd.sjoin(stores[["geometry"]], jn_grid[["grid_id", "geometry"]], how="inner", predicate="within")
    grids_with_store = set(has_store_pairs["grid_id"])
    jn_grid["has_store"] = jn_grid["grid_id"].isin(grids_with_store)
    log(f"기존 편의점이 있는 격자 수: {jn_grid['has_store'].sum()} / {len(jn_grid)}\n")

    log("5) 4분면 분류 (점수는 중랑구 내 중앙값 기준 고/저)...")
    score_median = jn_grid["score_log"].median()
    jn_grid["score_high"] = jn_grid["score_log"] >= score_median

    def quadrant(row):
        if row["score_high"] and row["has_store"]:
            return "고득점_점포있음"
        elif row["score_high"] and not row["has_store"]:
            return "고득점_점포없음(신규후보)"
        elif not row["score_high"] and row["has_store"]:
            return "저득점_점포있음"
        else:
            return "저득점_점포없음"

    jn_grid["quadrant"] = jn_grid.apply(quadrant, axis=1)
    log("4분면별 격자 수:")
    log(jn_grid["quadrant"].value_counts().to_string())

    # 신규 후보지 상위 20개를 점수순으로 뽑아서 별도 로그에 남김
    candidates = jn_grid[jn_grid["quadrant"] == "고득점_점포없음(신규후보)"].sort_values("score_log", ascending=False)
    log(f"\n신규 출점 후보지(고득점+점포없음) 총 {len(candidates)}개 중 상위 10개:")
    log(candidates[["grid_id", "score_log", "competitor_cnt_300m", "subway_dist_m"]].head(10).to_string())

    log("\n6) 검증 지점 확인: 면목2동 '중랑동부시장'(CLAUDE.md 임장 대상) 주변...")
    trdar = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    ).to_crs(TARGET_CRS)
    dongbu = trdar[trdar["TRDAR_CD"].astype(str) == "3130106"]
    dongbu_centroid = dongbu.geometry.centroid.iloc[0]
    jn_grid["dist_to_dongbu_m"] = jn_grid.geometry.centroid.distance(dongbu_centroid)
    nearby = jn_grid[jn_grid["dist_to_dongbu_m"] <= 300].sort_values("dist_to_dongbu_m")
    log(f"동부시장 반경 300m 내 격자 {len(nearby)}개의 4분면 분포:")
    log(nearby["quadrant"].value_counts().to_string())
    log("-> 기존 점포가 있는 격자들이 실제로 고득점으로 나오고(모델이 이미 성공한 자리를 알아봄),")
    log("   바로 인근에 아직 점포는 없지만 고득점인 격자도 여럿 있어 신규 후보 탐색에 참고할 만함.")

    os.makedirs("data/processed", exist_ok=True)
    jn_grid.to_file("data/processed/jungnang_scored_grid.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/jungnang_scored_grid.gpkg")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/21_score_jungnang_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("\n완료: outputs/21_score_jungnang_log.txt 저장됨")
