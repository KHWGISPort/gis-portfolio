# -*- coding: utf-8 -*-
"""
[Phase 4 - 요청사항 3, 4, 5] LightGBM으로 편의점 매출 예측 모델을 학습한다.

학습/검증 분리 방법 (초보자를 위한 설명):
  1) 전체 712개 상권 중 20%(약 143개)를 '테스트셋'으로 떼어놓고 학습에는
     절대 사용하지 않는다. 이건 마치 "모의고사 문제를 실전 시험 직전까지
     안 풀어보고 아껴두는 것"과 같다 -- 학습 때 본 적 없는 데이터로 채점해야
     실제 실력(=처음 보는 상권에도 잘 맞는지)을 알 수 있다.
  2) 나머지 80%(약 569개, '학습셋')로 5-겹 교차검증(5-Fold Cross Validation)을
     한다. 569개를 5조각으로 나눠서, 4조각으로 학습하고 나머지 1조각으로
     채점하기를 5번 반복(매번 채점하는 조각을 바꿔가며)한다. 데이터가 712개로
     많지 않아서, 테스트셋 하나만으로 채점하면 "우연히 쉬운/어려운 문제만
     걸렸을 수도" 있으니 5번 채점해서 평균+편차를 같이 보는 것.
  3) 마지막으로 학습셋 전체로 최종 모델을 학습하고, 맨 처음 떼어놓았던
     테스트셋으로 딱 한 번 최종 채점을 한다.

과적합(overfitting) 판단 방법 (초보자를 위한 설명):
  '과적합'이란 모델이 "문제(학습 데이터)를 이해"한 게 아니라 "문제와 답을
  통째로 암기"해버린 상태를 말한다. 암기한 모델은 학습 데이터에서는 점수가
  매우 높지만(거의 만점), 한 번도 못 본 테스트 데이터에서는 점수가 뚝 떨어진다.
  그래서 판단 기준은 간단하다: **학습셋 성능과 테스트셋 성능의 차이가 크면
  과적합을 의심한다.** (예: 학습 R²=0.95인데 테스트 R²=0.40이면 과적합)
  반대로 두 점수가 비슷하면(둘 다 적당히 높으면) 모델이 진짜 패턴을 배운 것.
"""
import io
import os

import lightgbm as lgb
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

FEATURE_COLS = [
    "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
    "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
    "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
]
TARGET_COL = "연평균_매출_금액_log"

# 데이터가 712건으로 많지 않으므로, 나무를 너무 복잡하게 키우지 않도록
# (과적합 방지) 일부러 보수적인 값을 사용한다.
LGB_PARAMS = dict(
    n_estimators=1000,
    learning_rate=0.03,
    num_leaves=7,
    min_child_samples=15,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    verbose=-1,
)

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def fit_with_early_stopping(X_tr, y_tr, X_val, y_val):
    """학습용 안에서 또 일부를 떼어 '검증용'으로 쓰고, 검증 점수가 더 이상
    안 좋아지면 학습을 멈춘다(early stopping) -- 과적합을 막는 대표적인 방법."""
    model = lgb.LGBMRegressor(**LGB_PARAMS)
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )
    return model


if __name__ == "__main__":
    df = pd.read_csv("data/processed/trdar_features_for_model.csv", encoding="utf-8-sig")
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]
    log(f"전체 상권 수: {len(df)}, 피처 수: {len(FEATURE_COLS)}\n")

    # 1) 테스트셋(20%) 분리 -- 학습에 절대 사용하지 않음
    X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    log(f"학습셋: {len(X_train_full)}개, 테스트셋: {len(X_test)}개\n")

    # 2) 학습셋(80%) 안에서 5-겹 교차검증
    log("===== 5-Fold 교차검증 (학습셋 안에서) =====")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2, cv_mae = [], []
    for fold, (tr_idx, va_idx) in enumerate(kf.split(X_train_full), start=1):
        X_tr, X_va = X_train_full.iloc[tr_idx], X_train_full.iloc[va_idx]
        y_tr, y_va = y_train_full.iloc[tr_idx], y_train_full.iloc[va_idx]
        model = fit_with_early_stopping(X_tr, y_tr, X_va, y_va)
        pred = model.predict(X_va)
        r2, mae = r2_score(y_va, pred), mean_absolute_error(y_va, pred)
        cv_r2.append(r2)
        cv_mae.append(mae)
        log(f"  Fold {fold}: R2={r2:.3f}, MAE={mae:.3f} (log 스케일)")
    log(f"5-Fold 평균: R2={np.mean(cv_r2):.3f} (표준편차 {np.std(cv_r2):.3f}), MAE={np.mean(cv_mae):.3f} (표준편차 {np.std(cv_mae):.3f})\n")

    # 3) 최종 모델: 학습셋 80% 중 다시 15%를 검증용으로 떼어 early stopping에 사용
    X_tr2, X_val2, y_tr2, y_val2 = train_test_split(X_train_full, y_train_full, test_size=0.15, random_state=42)
    final_model = fit_with_early_stopping(X_tr2, y_tr2, X_val2, y_val2)
    log(f"최종 모델 실제 사용된 트리 개수(early stopping): {final_model.best_iteration_}\n")

    # 4) 성능 평가: 학습셋(in-sample) vs 테스트셋(out-of-sample) -- 과적합 체크
    pred_train = final_model.predict(X_train_full)
    pred_test = final_model.predict(X_test)

    log("===== 최종 성능 (log 스케일) =====")
    log(f"[학습셋]   R2={r2_score(y_train_full, pred_train):.3f}, MAE={mean_absolute_error(y_train_full, pred_train):.3f}")
    log(f"[테스트셋] R2={r2_score(y_test, pred_test):.3f}, MAE={mean_absolute_error(y_test, pred_test):.3f}")

    r2_gap = r2_score(y_train_full, pred_train) - r2_score(y_test, pred_test)
    log(f"\n학습-테스트 R2 차이: {r2_gap:.3f}")
    if r2_gap > 0.3:
        log("-> 차이가 커서(0.3 초과) 과적합 가능성이 있음")
    else:
        log("-> 차이가 크지 않아 과적합 징후는 뚜렷하지 않음")

    # 원래 단위(원)로 되돌린 성능도 참고로 계산 (expm1로 로그 역변환)
    pred_test_won = np.expm1(pred_test)
    y_test_won = np.expm1(y_test)
    mae_won = mean_absolute_error(y_test_won, pred_test_won)
    r2_won = r2_score(y_test_won, pred_test_won)
    log(f"\n===== 참고: 원래 단위(원)로 되돌린 테스트셋 성능 =====")
    log(f"R2={r2_won:.3f}, MAE={mae_won:,.0f}원")

    # 5) Feature Importance
    log("\n===== Feature Importance (gain 기준) =====")
    importance = pd.Series(final_model.booster_.feature_importance(importance_type="gain"), index=FEATURE_COLS)
    importance = importance.sort_values(ascending=False)
    log(importance.to_string())

    fig, ax = plt.subplots(figsize=(8, 5))
    importance.sort_values().plot(kind="barh", ax=ax, color="#4C72B0")
    ax.set_xlabel("중요도 (gain)")
    ax.set_title("편의점 매출 예측 - 피처 중요도")
    fig.tight_layout()
    os.makedirs("outputs", exist_ok=True)
    fig.savefig("outputs/15_feature_importance.png", dpi=120)
    log("\n저장 완료: outputs/15_feature_importance.png")

    with open("outputs/15_train_model_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/15_train_model_log.txt 저장됨")
