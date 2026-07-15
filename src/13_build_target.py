# -*- coding: utf-8 -*-
"""
[Phase 4 - 요청사항 1] 편의점 상권 매출(2,730행, 분기별)을 상권별 연평균으로 합친다.

목적: 분기 EDA(Phase 1)에서 확인했던 계절성(여름철 성수기 등)을 지워서,
      "입지 효과"만 남은 값을 모델의 타깃(정답)으로 쓰기 위함.

절차:
  1) 상권_코드별로 그룹을 묶어서, 있는 분기들의 당월_매출_금액을 평균낸다.
     (분기가 4개 다 있는 상권도 있고 1~3개만 있는 상권도 있음 -> 있는 만큼만 평균)
  2) 매출은 우상향 꼬리분포(왜도 큼, Phase 1 EDA에서 확인)이므로 log1p 변환을
     적용해보고, 적용 전/후 히스토그램을 비교해서 정말 정규분포에 가까워지는지 눈으로 확인한다.
     (log1p = log(1+x), 매출이 0인 경우가 있어도 에러 없이 계산되도록 1을 더함)
"""
import io
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import skew

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    df = pd.read_csv("data/processed/sales_trdar_convenience.csv", encoding="utf-8-sig")
    log(f"원본 행 수(상권x분기): {len(df)}, 고유 상권 수: {df['상권_코드'].nunique()}\n")

    # 상권별 연평균 매출 = 있는 분기들의 당월_매출_금액 평균
    target = df.groupby(["상권_코드", "상권_코드_명"]).agg(
        연평균_매출_금액=("당월_매출_금액", "mean"),
        연평균_매출_건수=("당월_매출_건수", "mean"),
        분기_수=("기준_년분기_코드", "nunique"),
    ).reset_index()

    log(f"상권별 연평균 타깃 행 수: {len(target)}")
    log(f"분기 수 분포:\n{target['분기_수'].value_counts().sort_index().to_string()}\n")

    sales = target["연평균_매출_금액"]
    log("===== 로그변환 전 (연평균_매출_금액) =====")
    log(f"평균 {sales.mean():,.0f}, 중앙값 {sales.median():,.0f}, 왜도 {skew(sales):.2f}")

    sales_log = np.log1p(sales)
    target["연평균_매출_금액_log"] = sales_log
    log("\n===== 로그변환 후 (log1p) =====")
    log(f"평균 {sales_log.mean():.2f}, 중앙값 {sales_log.median():.2f}, 왜도 {skew(sales_log):.2f}")

    # 히스토그램 비교 (전/후 나란히)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].hist(sales, bins=50, color="#4C72B0")
    axes[0].set_title(f"로그변환 전 (왜도 {skew(sales):.2f})")
    axes[0].set_xlabel("연평균 매출 금액(원)")
    axes[0].set_ylabel("상권 수")

    axes[1].hist(sales_log, bins=50, color="#55A868")
    axes[1].set_title(f"로그변환 후 log1p (왜도 {skew(sales_log):.2f})")
    axes[1].set_xlabel("log1p(연평균 매출 금액)")
    axes[1].set_ylabel("상권 수")
    fig.tight_layout()

    os.makedirs("outputs", exist_ok=True)
    fig.savefig("outputs/13_target_log_transform_compare.png", dpi=120)
    log("\n히스토그램 저장: outputs/13_target_log_transform_compare.png")
    log("-> 왜도가 크게 줄어들어(오른쪽으로 훨씬 덜 치우침) log1p 변환이 효과적임을 확인.")
    log("   모델 학습 시 타깃은 로그변환된 값(연평균_매출_금액_log)을 사용하고,")
    log("   예측 결과를 다시 원래 단위(원)로 보고 싶으면 expm1()로 역변환하면 됨.")

    os.makedirs("data/processed", exist_ok=True)
    target.to_csv("data/processed/target_trdar_annual.csv", index=False, encoding="utf-8-sig")
    log("\n저장 완료: data/processed/target_trdar_annual.csv")

    with open("outputs/13_build_target_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/13_build_target_log.txt 저장됨")
