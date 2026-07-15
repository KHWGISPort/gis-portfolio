# -*- coding: utf-8 -*-
"""
[Phase 3 - 요청사항 4, 5] 최종 격자 피처의 분포 히스토그램을 저장하고,
격자 수·피처별 결측 비율·이상해 보이는 분포를 요약한다.
"""
import io
import os

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = "Malgun Gothic"  # 한글 깨짐 방지 (Windows 기본 한글 폰트)
matplotlib.rcParams["axes.unicode_minus"] = False

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
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    log(f"최종 격자 수: {len(grid)}")
    log(f"피처 컬럼 수: {len(FEATURE_COLS)}\n")

    os.makedirs("outputs", exist_ok=True)

    log("===== 피처별 결측 비율 =====")
    for col in FEATURE_COLS:
        na_ratio = grid[col].isna().mean() * 100
        log(f"{col}: 결측 {na_ratio:.2f}%")

    log("\n===== 피처별 기초 통계 =====")
    stats = grid[FEATURE_COLS].describe().T
    log(stats.to_string())

    log("\n===== 히스토그램 저장 =====")
    fig, axes = plt.subplots(4, 3, figsize=(15, 16))
    axes = axes.flatten()
    for i, col in enumerate(FEATURE_COLS):
        ax = axes[i]
        data = grid[col].dropna()
        ax.hist(data, bins=50, color="#4C72B0", edgecolor="none")
        ax.set_title(col, fontsize=10)
        ax.set_ylabel("격자 수")
    for j in range(len(FEATURE_COLS), len(axes)):
        axes[j].axis("off")
    fig.tight_layout()
    fig.savefig("outputs/12_grid_feature_histograms.png", dpi=120)
    log("저장 완료: outputs/12_grid_feature_histograms.png")

    # 이상 분포 후보: 왜도(skewness)가 큰 피처, 0이 유난히 많은 피처
    log("\n===== 이상해 보이는 분포 체크 =====")
    for col in FEATURE_COLS:
        data = grid[col].dropna()
        skew = data.skew()
        zero_ratio = (data == 0).mean() * 100
        flag = []
        if abs(skew) > 3:
            flag.append(f"왜도 {skew:.1f} (한쪽으로 크게 치우침)")
        if zero_ratio > 50:
            flag.append(f"0값 비율 {zero_ratio:.0f}%")
        if flag:
            log(f"[주의] {col}: " + ", ".join(flag))

    with open("outputs/12_grid_histograms_summary_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("\n완료: outputs/12_grid_histograms_summary_log.txt 저장됨")
