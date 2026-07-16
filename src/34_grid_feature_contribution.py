# -*- coding: utf-8 -*-
"""
[임장 대조 - 3단계] 답사한 5개 격자(종합 1/2/3/8/9위)의 피처 기여도를 분석한다.

LightGBM의 pred_contrib=True 예측을 쓰면, 최종 점수가 어떤 피처가
얼마나 밀어올리고(+) 끌어내렸는지(-)를 피처별로 쪼개서 볼 수 있다
(SHAP 값과 동일한 방식 -- 나무들이 이 격자를 평가하면서 각 피처를
얼마나 근거로 삼았는지의 수치). 전부 더하면 최종 점수(로그 스케일)가 된다.

각 격자의 상위 기여 피처를 뽑고, 그 피처 값이 중랑구 전체(1,858개
격자) 안에서 몇 번째 퍼센타일인지 같이 보여줘서 "이 격자가 왜 이런
점수를 받았는지"를 숫자로 설명한다.
"""
import io
import os

import geopandas as gpd
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

FEATURE_COLS = [
    "competitor_cnt_100m", "competitor_cnt_300m", "competitor_cnt_500m",
    "subway_dist_m", "subway_monthly_traffic", "bus_stop_cnt_300m",
    "주간_평일_평균인구", "주간_주말_평균인구", "야간_평일_평균인구", "야간_주말_평균인구",
    "food_cnt_300m", "edu_cnt_300m",
]
TARGET_COL = "연평균_매출_금액_log"

LGB_PARAMS = dict(
    n_estimators=1000, learning_rate=0.03, num_leaves=7, min_child_samples=15,
    subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1,
)

# 종합 순위 1/2/3/8/9위 격자 (임장 대상)
FIELD_GRIDS = {
    1: ("G100_051921", "상봉역"),
    2: ("G100_051899", "금강사거리"),
    3: ("G100_051623", "타임호프"),
    8: ("G100_052726", "먹자골목"),
    9: ("G100_053794", "진로아파트"),
}

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


FEATURE_KOR = {
    "competitor_cnt_100m": "반경 100m 경쟁 편의점 수",
    "competitor_cnt_300m": "반경 300m 경쟁 편의점 수",
    "competitor_cnt_500m": "반경 500m 경쟁 편의점 수",
    "subway_dist_m": "최근접 지하철역 거리",
    "subway_monthly_traffic": "최근접 역 월간 승하차량",
    "bus_stop_cnt_300m": "반경 300m 버스정류장 수",
    "주간_평일_평균인구": "주간·평일 생활인구",
    "주간_주말_평균인구": "주간·주말 생활인구",
    "야간_평일_평균인구": "야간·평일 생활인구",
    "야간_주말_평균인구": "야간·주말 생활인구",
    "food_cnt_300m": "반경 300m 음식점 수",
    "edu_cnt_300m": "반경 300m 교육시설 수",
}

# 거리처럼 '값이 작을수록 notable'한 피처. 나머지는 전부 '값이 클수록 notable'.
LOWER_IS_NOTABLE = {"subway_dist_m"}


def describe_percentile(feat, pct):
    """표준 퍼센타일(0=중랑구 내 최솟값, 100=최댓값)을 사람이 읽기 좋은 문구로 바꾼다."""
    if feat in LOWER_IS_NOTABLE:
        # 거리는 작을수록 '가까움'이 notable하므로, 하위 퍼센타일을 그대로 강조
        return f"중랑구 내 하위 {pct:.0f}퍼센타일 (거리가 짧은 축)" if pct <= 50 \
            else f"중랑구 내 상위 {100-pct:.0f}퍼센타일 (거리가 먼 축)"
    else:
        return f"중랑구 내 상위 {100-pct:.0f}퍼센타일" if pct >= 50 \
            else f"중랑구 내 하위 {pct:.0f}퍼센타일"


if __name__ == "__main__":
    log("1) v3a 모델 재학습 중...")
    model = train_v3a_model()

    log("2) 중랑구 전체 격자(퍼센타일 계산 기준) + 답사 5곳 불러오는 중...")
    grid = gpd.read_file("data/processed/jungnang_scored_grid_v4.gpkg", layer="grid")
    log(f"중랑구 격자 수: {len(grid)}\n")

    log("3) pred_contrib(SHAP 방식 기여도) 계산 중...")
    booster = model.booster_
    contrib = booster.predict(grid[FEATURE_COLS], pred_contrib=True)
    # contrib의 마지막 열은 base value(기준값), 그 앞 열들이 각 피처의 기여도
    contrib_df = pd.DataFrame(contrib[:, :-1], columns=FEATURE_COLS, index=grid.index)
    base_value = contrib[:, -1][0]
    log(f"기준값(base value, 모든 상권의 평균 예측): {base_value:.3f}\n")

    md_lines = ["# 임장 5곳 격자 피처 기여도 분석 (LightGBM pred_contrib)\n"]
    md_lines.append(f"모델: v3a(총매출 타깃, 12피처). 기준값(전체 평균 예측) = {base_value:.3f} (log 스케일)\n")
    md_lines.append("각 격자의 최종 점수 = 기준값 + 모든 피처의 기여도 합. "
                     "기여도가 +이면 그 피처가 점수를 끌어올렸고, -면 끌어내린 것.\n")

    for rank in sorted(FIELD_GRIDS):
        grid_id, name = FIELD_GRIDS[rank]
        idx = grid[grid["grid_id"] == grid_id].index
        if len(idx) == 0:
            log(f"[경고] {grid_id} 격자를 찾을 수 없음")
            continue
        i = idx[0]
        row = grid.loc[i]
        contribs = contrib_df.loc[i].sort_values(key=abs, ascending=False)

        log(f"\n===== {rank}위 {name} ({grid_id}) =====")
        log(f"최종 점수: {row['score_log']:.3f} (기준값 {base_value:.3f} + 기여도 합 {contribs.sum():.3f})")

        md_lines.append(f"\n## {rank}위 {name} (`{grid_id}`)\n")
        md_lines.append(f"최종 점수: **{row['score_log']:.3f}** (log 스케일)\n")
        md_lines.append("| 피처 | 기여도 | 이 격자 값 | 중랑구 내 위치 |")
        md_lines.append("|---|---|---|---|")

        for feat, c in contribs.head(5).items():
            val = row[feat]
            pct = (grid[feat] <= val).mean() * 100  # 표준 퍼센타일: 100=중랑구 내 최댓값
            direction = "▲ 상승" if c > 0 else "▼ 하강"
            desc = describe_percentile(feat, pct)
            log(f"  {feat}: 기여도 {c:+.3f} ({direction}), 값={val:.1f}, {desc} (표준퍼센타일 {pct:.0f})")
            md_lines.append(f"| {FEATURE_KOR[feat]} | {c:+.3f} ({direction}) | {val:.1f} | {desc} |")

        # 한국어 해석 문장 생성 (거리류는 방향 단어를 다르게: 짧다/길다)
        top_feat, top_c = contribs.index[0], contribs.iloc[0]
        top_val = row[top_feat]
        top_pct = (grid[top_feat] <= top_val).mean() * 100
        top_desc = describe_percentile(top_feat, top_pct)
        if top_feat in LOWER_IS_NOTABLE:
            direction_word = "짧아서" if top_c > 0 else "길어서"
        else:
            direction_word = "높아서" if top_c > 0 else "낮아서"
        interp = (
            f"이 격자는 **{FEATURE_KOR[top_feat]}**이(가) {top_desc}로 {direction_word} "
            f"점수에 가장 큰 영향을 줬습니다."
        )
        log(f"  해석: {interp}")
        md_lines.append(f"\n**해석**: {interp}\n")

    with open("outputs/34_grid_feature_contribution.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    log("\n저장 완료: outputs/34_grid_feature_contribution.md")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/34_grid_feature_contribution_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/34_grid_feature_contribution_log.txt 저장됨")
