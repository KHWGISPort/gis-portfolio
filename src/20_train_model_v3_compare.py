# -*- coding: utf-8 -*-
"""
[Phase 4 v3] v2가 왜 v1보다 나빠졌는지 원인을 분리해서 확인한다.

v2는 "타깃"과 "피처"를 동시에 바꿔서, 성능이 나빠진 게 어느 쪽 때문인지
알 수 없었다. 그래서 한 가지씩만 바꾼 버전을 추가로 만들어 비교한다.

  v1  : 타깃=총매출        피처=10종(집객시설 없음)                [기준]
  v2  : 타깃=점포당매출     피처=12종(집객시설 포함)     -> 둘 다 바뀜
  v3a : 타깃=총매출        피처=12종(집객시설 포함)     -> 피처 효과만 분리
  v3b : 타깃=점포당매출     피처=10종(집객시설 없음), 점포 4개 이상 상권만 -> 타깃(안정화) 효과만 분리

v3a를 v1과 비교하면 "집객시설 피처를 추가한 게 도움이 됐는지" 알 수 있고,
v3b를 v1과 비교하면 "점포당 매출 + 노이즈 필터링이 도움이 됐는지" 알 수 있다.
"""
import io
import os

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from scipy.stats import spearmanr

LGB_PARAMS = dict(
    n_estimators=1000, learning_rate=0.03, num_leaves=7, min_child_samples=15,
    subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1,
)

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def fit_with_early_stopping(X_tr, y_tr, X_val, y_val):
    model = lgb.LGBMRegressor(**LGB_PARAMS)
    model.fit(
        X_tr, y_tr, eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )
    return model


def hit_rate_top20(y_true, y_pred):
    n_top = max(1, int(len(y_true) * 0.2))
    true_top_idx = set(np.argsort(-y_true)[:n_top])
    pred_top_idx = set(np.argsort(-y_pred)[:n_top])
    return len(true_top_idx & pred_top_idx) / n_top


def train_and_evaluate(df, feature_cols, target_col, label):
    log(f"\n{'=' * 20} {label} {'=' * 20}")
    X, y = df[feature_cols], df[target_col]
    log(f"상권 수: {len(df)}, 피처 수: {len(feature_cols)}")

    X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2 = []
    for tr_idx, va_idx in kf.split(X_train_full):
        X_tr, X_va = X_train_full.iloc[tr_idx], X_train_full.iloc[va_idx]
        y_tr, y_va = y_train_full.iloc[tr_idx], y_train_full.iloc[va_idx]
        model = fit_with_early_stopping(X_tr, y_tr, X_va, y_va)
        cv_r2.append(r2_score(y_va, model.predict(X_va)))
    log(f"5-Fold CV R2: 평균 {np.mean(cv_r2):.3f} (표준편차 {np.std(cv_r2):.3f})")

    X_tr2, X_val2, y_tr2, y_val2 = train_test_split(X_train_full, y_train_full, test_size=0.15, random_state=42)
    final_model = fit_with_early_stopping(X_tr2, y_tr2, X_val2, y_val2)

    pred_train = final_model.predict(X_train_full)
    pred_test = final_model.predict(X_test)

    r2_train, r2_test = r2_score(y_train_full, pred_train), r2_score(y_test, pred_test)
    mae_test = mean_absolute_error(y_test, pred_test)
    spearman_test, _ = spearmanr(y_test, pred_test)
    hit_rate = hit_rate_top20(y_test.values, pred_test)

    log(f"[학습셋] R2={r2_train:.3f}")
    log(f"[테스트셋] R2={r2_test:.3f}, MAE={mae_test:.3f}, 스피어만={spearman_test:.3f}, Top20% 적중률={hit_rate*100:.1f}%")

    return {
        "label": label, "n": len(df), "n_features": len(feature_cols),
        "cv_r2_mean": np.mean(cv_r2), "cv_r2_std": np.std(cv_r2),
        "train_r2": r2_train, "test_r2": r2_test, "test_mae": mae_test,
        "test_spearman": spearman_test, "test_hit_rate_top20": hit_rate,
        "train_test_gap": r2_train - r2_test,
    }


if __name__ == "__main__":
    v1_features = [
        "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
        "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
        "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
    ]
    v2_features = v1_features + ["food_cnt_300m", "edu_cnt_300m"]

    df_v1 = pd.read_csv("data/processed/trdar_features_for_model.csv", encoding="utf-8-sig")
    # v2/v3a/v3b는 모두 같은 파일(trdar_features_for_model_v2.csv)에서 파생된다.
    # (17,18번 스크립트에서 이미 총매출/점포당매출 타깃과 12종 피처를 한 표에 합쳐뒀음)
    df_v2 = pd.read_csv("data/processed/trdar_features_for_model_v2.csv", encoding="utf-8-sig")
    df_v3b = df_v2[df_v2["편의점_점포수"] >= 4].copy()

    results = []
    results.append(train_and_evaluate(df_v1, v1_features, "연평균_매출_금액_log", "v1  총매출 x 10피처(기준)"))
    results.append(train_and_evaluate(df_v2, v2_features, "점포당_평균매출_log", "v2  점포당매출 x 12피처(타깃+피처 동시변경)"))
    results.append(train_and_evaluate(df_v2, v2_features, "연평균_매출_금액_log", "v3a 총매출 x 12피처(피처 효과만)"))
    results.append(train_and_evaluate(df_v3b, v1_features, "점포당_평균매출_log", "v3b 점포당매출(점포4+) x 10피처(타깃 효과만)"))

    compare = pd.DataFrame(results).set_index("label")
    log(f"\n{'=' * 20} v1 / v2 / v3a / v3b 비교표 {'=' * 20}")
    log(compare.to_string())

    log("\n===== 순위상관·적중률 중심 요약 =====")
    log(compare[["n", "test_spearman", "test_hit_rate_top20", "cv_r2_mean"]].sort_values("test_spearman", ascending=False).to_string())

    best = compare["test_spearman"].idxmax()
    log(f"\n스피어만 기준 최고 성능: {best}")

    os.makedirs("outputs", exist_ok=True)
    compare.to_csv("outputs/20_v1_v2_v3a_v3b_comparison.csv", encoding="utf-8-sig")
    with open("outputs/20_train_model_v3_compare_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/20_v1_v2_v3a_v3b_comparison.csv 저장됨")
