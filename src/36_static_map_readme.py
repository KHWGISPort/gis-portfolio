# -*- coding: utf-8 -*-
"""
[Phase 6 - README용] 중랑구 최종 스코어링 결과를 정적 이미지로 저장한다.
(인터랙티브 웹지도는 격자 1,858개 때문에 브라우저 스크린샷이 무거워서,
README에 바로 박아 넣을 정적 PNG를 matplotlib로 별도 생성)
"""
import os

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

QUADRANT_COLOR = {
    "고득점_점포없음(신규후보)": "#e41a1c",
    "고득점_점포있음": "#4daf4a",
    "저득점_점포있음": "#377eb8",
    "저득점_점포없음": "#e8e8e8",
    "출점불가(건물+업소결합)": "#4d3b2a",
}
QUADRANT_LABEL = {
    "고득점_점포없음(신규후보)": "고득점 · 점포없음 (신규 후보지)",
    "고득점_점포있음": "고득점 · 점포있음 (검증된 자리)",
    "저득점_점포있음": "저득점 · 점포있음",
    "저득점_점포없음": "저득점 · 점포없음",
    "출점불가(건물+업소결합)": "출점불가 (건물·업소 없음)",
}

if __name__ == "__main__":
    grid = gpd.read_file("data/processed/jungnang_scored_grid_v4.gpkg", layer="grid")

    os.makedirs("outputs", exist_ok=True)

    # (1) README용: 제목 + 범례 포함
    fig, ax = plt.subplots(figsize=(10, 10))
    for q, color in QUADRANT_COLOR.items():
        grid[grid["quadrant"] == q].plot(ax=ax, color=color, edgecolor="none", linewidth=0)
    ax.set_axis_off()
    ax.set_title("중랑구 편의점 입지 스코어링 — 최종 결과", fontsize=18, fontweight="bold", pad=15)
    legend_elems = [Patch(facecolor=c, label=QUADRANT_LABEL[q]) for q, c in QUADRANT_COLOR.items()]
    ax.legend(handles=legend_elems, loc="lower left", fontsize=11, frameon=True, framealpha=0.9)
    fig.tight_layout()
    out_path = "outputs/36_readme_hero_map.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"저장 완료: {out_path}")

    # (2) 이력서 PDF용: 제목·범례 없이 지도만(범례는 PDF 캡션이 대신) — 왜곡 없이 크게 삽입하기 위함
    fig2, ax2 = plt.subplots(figsize=(8, 8))
    for q, color in QUADRANT_COLOR.items():
        grid[grid["quadrant"] == q].plot(ax=ax2, color=color, edgecolor="none", linewidth=0)
    ax2.set_axis_off()
    ax2.margins(0.01)
    out_path2 = "outputs/36_hero_for_pdf.png"
    fig2.savefig(out_path2, dpi=150, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig2)
    from PIL import Image as _PILImage
    _sz = _PILImage.open(out_path2).size
    print(f"저장 완료: {out_path2}  (크기 {_sz[0]}x{_sz[1]}, 세로/가로 비율 {_sz[1]/_sz[0]:.3f})")
