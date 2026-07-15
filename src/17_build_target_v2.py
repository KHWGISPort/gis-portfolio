# -*- coding: utf-8 -*-
"""
[Phase 4 v2 - 요청사항 1] 타깃 재정의: 상권 '총매출' -> '점포당 평균 매출'

목적: v1에서는 상권의 총매출을 그대로 썼는데, 상권이 크면(편의점이 많으면)
      당연히 총매출도 커지므로 "상권 규모 효과"가 섞여 있었다. 총매출을
      그 상권 안의 편의점 점포 수로 나누면 "점포 하나당 평균 매출"이 되어,
      상권 규모와 상관없이 "이 입지가 얼마나 장사가 잘 되는 자리인가"를
      더 직접적으로 잴 수 있다.

절차:
  1) 정제된 편의점 포인트(9,407개)를 상권 폴리곤(712개) 안에 점이 있는지로
     세어서 상권별 편의점 점포 수를 구한다 (공간조인, point-in-polygon).
  2) 13번 스크립트에서 만든 상권별 연평균 총매출을 점포 수로 나눈다.
  3) 점포 수가 0인 상권은 나눗셈이 불가능하므로(분모 0) 별도로 확인해서 보고한다.
"""
import io
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import skew

from utils_geo import TARGET_CRS

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    log("1) 정제된 편의점 포인트 불러오는 중...")
    stores = gpd.read_file("data/processed/convenience_stores.gpkg")
    log(f"편의점 수: {len(stores)}\n")

    log("2) 상권 폴리곤 불러오는 중...")
    target_v1 = pd.read_csv("data/processed/target_trdar_annual.csv", encoding="utf-8-sig")
    target_v1["상권_코드"] = target_v1["상권_코드"].astype(str)

    trdar = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    ).to_crs(TARGET_CRS)
    trdar["TRDAR_CD"] = trdar["TRDAR_CD"].astype(str)
    trdar = trdar[trdar["TRDAR_CD"].isin(target_v1["상권_코드"])][["TRDAR_CD", "geometry"]].copy()
    log(f"타깃 상권 폴리곤 수: {len(trdar)}\n")

    log("3) 상권 안에 편의점이 몇 개 있는지 공간조인으로 세는 중...")
    joined = gpd.sjoin(stores[["geometry"]], trdar, how="inner", predicate="within")
    store_cnt = joined.groupby("TRDAR_CD").size().rename("편의점_점포수")
    log(f"편의점이 1개 이상 있는 상권 수: {len(store_cnt)} / {len(trdar)}")

    result = target_v1.merge(store_cnt, left_on="상권_코드", right_index=True, how="left")
    zero_cnt = result["편의점_점포수"].isna().sum()
    log(f"편의점이 0개로 집계된 상권 수: {zero_cnt}개")
    if zero_cnt > 0:
        log("  (매출 데이터는 있지만 정제된 점포 포인트가 폴리곤 안에 없는 경우 -- 경계 근처 위치오차 등으로 추정)")
        log("  이 상권들은 점포당 평균을 계산할 수 없으므로 이후 모델링에서 제외한다.")

    result = result.dropna(subset=["편의점_점포수"]).copy()
    result["편의점_점포수"] = result["편의점_점포수"].astype(int)
    result["점포당_평균매출"] = result["연평균_매출_금액"] / result["편의점_점포수"]
    result["점포당_평균매출_log"] = np.log1p(result["점포당_평균매출"])

    log(f"\n최종 타깃 상권 수(점포수 0 제외): {len(result)}")
    log(f"상권당 편의점 수 분포: 평균 {result['편의점_점포수'].mean():.1f}, 중앙값 {result['편의점_점포수'].median():.0f}, 최댓값 {result['편의점_점포수'].max()}")

    log("\n===== 점포당 평균매출 (로그변환 전) =====")
    log(f"평균 {result['점포당_평균매출'].mean():,.0f}, 중앙값 {result['점포당_평균매출'].median():,.0f}, 왜도 {skew(result['점포당_평균매출']):.2f}")
    log("===== 점포당 평균매출 (로그변환 후) =====")
    log(f"평균 {result['점포당_평균매출_log'].mean():.2f}, 중앙값 {result['점포당_평균매출_log'].median():.2f}, 왜도 {skew(result['점포당_평균매출_log']):.2f}")

    os.makedirs("data/processed", exist_ok=True)
    result.to_csv("data/processed/target_trdar_v2.csv", index=False, encoding="utf-8-sig")
    log("\n저장 완료: data/processed/target_trdar_v2.csv")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/17_build_target_v2_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/17_build_target_v2_log.txt 저장됨")
