# -*- coding: utf-8 -*-
"""
[Phase 5 - 마스킹 최종 완성] 건물기반 마스크와 업소기반 마스크를 '결합'(합집합)한다.

출점 가능 = (격자에 교차 건물 1개 이상) AND (반경 300m 내 상가업소 1개 이상)
즉 둘 중 하나라도 마스킹 조건에 걸리면 출점불가로 본다 (OR = 합집합).

근거: 건물은 '물리적으로 지을 수 있는가'를, 주변 상가는 '상업적 맥락이 있는가'를
각각 다르게 걸러낸다. 건물만 보면 산속 관리소·고립된 주거처럼 건물은 있어도
상업활동이 전혀 없는 곳까지 후보로 남는데, 편의점 후보지로는 부적합하므로
업소기반 조건을 추가로 요구한다.

임계값은 재계산하지 않고 26번 스크립트에서 고정한 19.840999(log)를 그대로 사용.
"""
import io
import os

import geopandas as gpd
import pandas as pd

FIXED_SCORE_THRESHOLD = 19.840999  # 26번 스크립트에서 확정, 재계산 금지

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 중랑구 격자(v3, 건물기반+업소기반 마스크 컬럼 모두 있음) 불러오는 중...")
    grid = gpd.read_file("data/processed/jungnang_scored_grid_v3.gpkg", layer="grid")
    log(f"격자 수: {len(grid)}\n")

    log("2) 마스크 결합 (OR = 합집합)...")
    grid["masked_combined"] = grid["masked_building_based"] | grid["masked_biz_based"]
    log(f"건물기반만: {grid['masked_building_based'].sum()}개")
    log(f"업소기반만: {grid['masked_biz_based'].sum()}개")
    log(f"결합(합집합): {grid['masked_combined'].sum()}개\n")

    newly_masked = grid[(grid["masked_combined"]) & (~grid["masked_building_based"])]
    log(f"3) 이번에 추가로 마스킹된 격자(건물기반에선 통과했지만 업소기반에 걸림): {len(newly_masked)}개")
    if len(newly_masked) > 0:
        log(newly_masked[["grid_id", "building_cnt", "total_biz_cnt_300m", "competitor_cnt_300m",
                           "food_cnt_300m", "subway_dist_m", "야간_평일_평균인구"]].to_string(index=False))

    log("\n4) 고정 임계값으로 4분면 재분류 (재계산 없이 19.840999 그대로 사용)...")
    grid["score_high"] = grid["score_log"] >= FIXED_SCORE_THRESHOLD

    def quadrant(row):
        if row["masked_combined"]:
            return "출점불가(건물+업소결합)"
        if row["score_high"] and row["has_store"]:
            return "고득점_점포있음"
        elif row["score_high"] and not row["has_store"]:
            return "고득점_점포없음(신규후보)"
        elif not row["score_high"] and row["has_store"]:
            return "저득점_점포있음"
        else:
            return "저득점_점포없음"

    grid["quadrant"] = grid.apply(quadrant, axis=1)
    log("\n최종(결합 마스킹) 분류별 격자 수:")
    log(grid["quadrant"].value_counts().to_string())

    old_candidates = set(grid[grid["quadrant_biz_based"] == "고득점_점포없음(신규후보)"]["grid_id"]) if "quadrant_biz_based" in grid.columns else None
    log("\n5) 마스킹 단계별 신규후보 수 변화:")
    log(f"  1단계(업소기반, 21/24번): 806개")
    log(f"  2단계(건물기반, 26번): 550개")
    log(f"  3단계(결합, 최종): {(grid['quadrant']=='고득점_점포없음(신규후보)').sum()}개")

    os.makedirs("data/processed", exist_ok=True)
    grid.to_file("data/processed/jungnang_scored_grid_v4.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/jungnang_scored_grid_v4.gpkg")

    candidates = grid[grid["quadrant"] == "고득점_점포없음(신규후보)"].sort_values("score_log", ascending=False)
    log(f"\n최종 신규 출점 후보지 상위 10개:")
    log(candidates[["grid_id", "score_log", "competitor_cnt_300m", "building_cnt",
                     "total_biz_cnt_300m", "subway_dist_m"]].head(10).to_string())

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/29_mask_combined_final_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/29_mask_combined_final_log.txt 저장됨")
