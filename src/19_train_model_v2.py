# -*- coding: utf-8 -*-
"""
[Phase 4 v2 - 요청사항 3] v1과 v2를 같은 방식으로 학습·평가해서 나란히 비교한다.

v1 -> v2 변경사항
  - 타깃: 상권 총매출(log) -> 점포당 평균매출(log) (상권 규모 효과 제거)
  - 피처: 10종 -> 12종 (음식점/교육시설 반경 300m 개수 추가)

추가된 평가지표 (우리 목적은 "정확한 금액 예측"이 아니라 "상대적으로 어디가
더 좋은 입지인지 줄 세우기(스코어링)"이므로, 그 목적에 맞는 지표를 더 본다):
  - 스피어만 순위상관: 실제 매출 순위와 예측 순위가 얼마나 비슷한지
    (값 자체가 아니라 '순서'만 맞으면 1에 가까움 -- 스코어링에 더 맞는 지표)
  - 적중률(Top 20% Hit Rate): 실제로 매출 상위 20%인 상권들 중에서,
    모델이 매긴 예측 점수도 상위 20% 안에 들어간 비율. 예를 들어 적중률이
    60%면, "실제 우량 상권 10곳 중 6곳을 모델이 상위권으로 짚어냈다"는 뜻.
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
    """실제 상위 20% 중 예측도 상위 20%에 든 비율."""
    n_top = max(1, int(len(y_true) * 0.2))
    true_top_idx = set(np.argsort(-y_true)[:n_top])
    pred_top_idx = set(np.argsort(-y_pred)[:n_top])
    return len(true_top_idx & pred_top_idx) / n_top


def train_and_evaluate(df, feature_cols, target_col, label):
    log(f"\n{'=' * 20} {label} {'=' * 20}")
    X, y = df[feature_cols], df[target_col]
    log(f"상권 수: {len(df)}, 피처 수: {len(feature_cols)}")

    X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 5-Fold 교차검증
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2 = []
    for tr_idx, va_idx in kf.split(X_train_full):
        X_tr, X_va = X_train_full.iloc[tr_idx], X_train_full.iloc[va_idx]
        y_tr, y_va = y_train_full.iloc[tr_idx], y_train_full.iloc[va_idx]
        model = fit_with_early_stopping(X_tr, y_tr, X_va, y_va)
        cv_r2.append(r2_score(y_va, model.predict(X_va)))
    log(f"5-Fold CV R2: 평균 {np.mean(cv_r2):.3f} (표준편차 {np.std(cv_r2):.3f})")

    # 최종 모델
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
    log(f"학습-테스트 R2 차이: {r2_train - r2_test:.3f}")

    importance = pd.Series(
        final_model.booster_.feature_importance(importance_type="gain"), index=feature_cols
    ).sort_values(ascending=False)
    log(f"\nFeature Importance (상위 5개):\n{importance.head().to_string()}")

    return {
        "label": label,
        "cv_r2_mean": np.mean(cv_r2),
        "cv_r2_std": np.std(cv_r2),
        "train_r2": r2_train,
        "test_r2": r2_test,
        "test_mae": mae_test,
        "test_spearman": spearman_test,
        "test_hit_rate_top20": hit_rate,
        "train_test_gap": r2_train - r2_test,
    }, importance


if __name__ == "__main__":
    # ----- v1 -----
    v1_features = [
        "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
        "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
        "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
    ]
    df_v1 = pd.read_csv("data/processed/trdar_features_for_model.csv", encoding="utf-8-sig")
    result_v1, importance_v1 = train_and_evaluate(df_v1, v1_features, "연평균_매출_금액_log", "v1 (총매출 x 10피처)")

    # ----- v2 -----
    v2_features = v1_features + ["food_cnt_300m", "edu_cnt_300m"]
    df_v2 = pd.read_csv("data/processed/trdar_features_for_model_v2.csv", encoding="utf-8-sig")
    result_v2, importance_v2 = train_and_evaluate(df_v2, v2_features, "점포당_평균매출_log", "v2 (점포당매출 x 12피처)")

    # ----- 비교표 -----
    compare = pd.DataFrame([result_v1, result_v2]).set_index("label")
    log(f"\n{'=' * 20} v1 vs v2 비교표 {'=' * 20}")
    log(compare.to_string())

    os.makedirs("outputs", exist_ok=True)
    compare.to_csv("outputs/19_v1_vs_v2_comparison.csv", encoding="utf-8-sig")
    importance_v2.to_frame("importance").to_csv("outputs/19_v2_feature_importance.csv", encoding="utf-8-sig")

    with open("outputs/19_train_model_v2_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("\n완료: outputs/19_v1_vs_v2_comparison.csv, outputs/19_train_model_v2_log.txt 저장됨")
