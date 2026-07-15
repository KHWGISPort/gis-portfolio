# -*- coding: utf-8 -*-
"""
[Phase 3 - 요청사항 2] 접근성 피처
  - 최근접 지하철역까지 거리 + 그 역의 월간 승하차 규모
  - 반경 300m 내 버스정류장 수

공간 연산 그림으로 설명:
  1) 지하철: 역사마스터(수도권 전역, 784개 지점)로 KD-Tree를 만들고,
     격자 중심점마다 '가장 가까운 점 1개'를 찾는다(k=1 최근접 탐색).
     그 점까지의 거리가 "최근접 역까지 거리"가 된다. 서울 경계를 자르지
     않고 수도권 전역을 그대로 쓰기 때문에(데이터명세서 8번 항목), 서울
     경계 바로 안쪽 격자가 경기도의 역을 최근접 역으로 찾는 것도 자연스럽게
     허용된다 (경계 효과 방지).
  2) 그 최근접 역의 이름으로 CARD_SUBWAY(월간 승하차 인원)를 찾아 붙인다.
     -> "지하철역 위치 마스터"와 "지하철 카드 승하차 집계"는 서로 다른 표라서
        역 이름으로 연결(조인)해야 한다.
  3) 버스: 정류소 9,407개(가 아니라 11,248개) 위치로 KD-Tree를 만들고,
     경쟁 밀도 때와 같은 방식으로 반경 300m 안의 점 개수를 센다.

[중요 발견] CARD_SUBWAY_MONTH_202606.csv 원본은 각 데이터 행 끝에
빈 칸(트레일링 콤마)이 하나 더 있는데 헤더에는 그 칸의 이름이 없어서,
그냥 pandas.read_csv()로 읽으면 모든 컬럼이 한 칸씩 밀려 읽힌다
(예: '역명' 컬럼에 숫자인 승차인원이 들어가는 등). 여기서는 컬럼 이름을
7개(더미 1개 포함) 직접 지정해서 읽고 더미 컬럼을 버리는 방식으로 바로잡는다.
"""
import io
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from utils_geo import points_from_lonlat

BUS_RADIUS = 300

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def load_subway_ridership():
    """CARD_SUBWAY_MONTH_202606.csv를 올바른 컬럼으로 읽고 역명별 월간 승하차 합계를 구한다."""
    cols = ["사용일자", "노선명", "역명", "승차총승객수", "하차총승객수", "등록일자", "_extra"]
    df = pd.read_csv(
        "data/raw/CARD_SUBWAY_MONTH_202606.csv", encoding="utf-8-sig", names=cols, header=0
    ).drop(columns="_extra")

    df["월간승하차_총계"] = df["승차총승객수"] + df["하차총승객수"]
    # 노선이 여러 개인 역(환승역 등)은 같은 역명으로 다시 합산
    ridership = df.groupby("역명")["월간승하차_총계"].sum()
    return ridership


def normalize_name(name):
    """'낙성대(강감찬)' -> '낙성대' 처럼 괄호 부가정보를 뗀 이름으로 정규화."""
    return str(name).split("(")[0].strip()


if __name__ == "__main__":
    log("1) 격자 불러오는 중...")
    grid = gpd.read_file("data/processed/grid_features.gpkg", layer="grid")
    centroids = grid.geometry.centroid
    centroid_xy = np.column_stack([centroids.x.values, centroids.y.values])
    log(f"격자 수: {len(grid)}\n")

    log("2) 지하철역 마스터 불러오는 중 (수도권 전역 유지)...")
    station_df = pd.read_csv("data/raw/서울시 역사마스터 정보.csv", encoding="cp949")
    stations = points_from_lonlat(station_df, lon_col="경도", lat_col="위도", source_crs="EPSG:4326")
    log(f"지하철역 지점 수: {len(stations)}\n")

    log("3) CARD_SUBWAY 월간 승하차 집계 중 (컬럼 밀림 버그 수정 후 읽음)...")
    ridership = load_subway_ridership()
    log(f"역명별 월간 승하차 합계 계산 완료: {len(ridership)}개 역")

    # 역명 매칭: 우선 원래 이름으로, 안 되면 괄호를 뗀 이름으로 한 번 더 시도
    ridership_norm = ridership.copy()
    ridership_norm.index = ridership_norm.index.map(normalize_name)
    ridership_norm = ridership_norm.groupby(level=0).sum()

    def lookup_ridership(station_name):
        if station_name in ridership.index:
            return ridership[station_name]
        norm = normalize_name(station_name)
        if norm in ridership_norm.index:
            return ridership_norm[norm]
        return np.nan

    stations["월간승하차_총계"] = stations["역사명"].apply(lookup_ridership)
    matched_rate = stations["월간승하차_총계"].notna().mean() * 100
    log(f"역사마스터 지점 중 CARD_SUBWAY 매칭된 비율: {matched_rate:.1f}%\n")

    log("4) 격자별 최근접 지하철역 거리 + 그 역의 월간 승하차 계산 중...")
    station_xy = np.column_stack([stations.geometry.x.values, stations.geometry.y.values])
    station_tree = cKDTree(station_xy)
    dist, idx = station_tree.query(centroid_xy, k=1)

    grid["subway_dist_m"] = dist
    grid["subway_nearest_name"] = stations["역사명"].values[idx]
    grid["subway_monthly_traffic"] = stations["월간승하차_총계"].values[idx]

    log(f"최근접 역 거리 평균: {dist.mean():.0f}m, 최댓값: {dist.max():.0f}m")
    na_ratio = grid["subway_monthly_traffic"].isna().mean() * 100
    log(f"subway_monthly_traffic 결측 비율(최근접 역의 카드 데이터가 없는 경우): {na_ratio:.1f}%\n")

    log("5) 버스정류장 불러오는 중...")
    bus_df = pd.read_excel("data/raw/서울시버스정류소위치정보(20260701).xlsx")
    bus_stops = points_from_lonlat(bus_df, lon_col="X좌표", lat_col="Y좌표", source_crs="EPSG:4326")
    log(f"버스정류장 수: {len(bus_stops)}\n")

    log(f"6) 격자별 반경 {BUS_RADIUS}m 내 버스정류장 수 계산 중...")
    bus_xy = np.column_stack([bus_stops.geometry.x.values, bus_stops.geometry.y.values])
    bus_tree = cKDTree(bus_xy)
    bus_counts = bus_tree.query_ball_point(centroid_xy, r=BUS_RADIUS, return_length=True)
    grid[f"bus_stop_cnt_{BUS_RADIUS}m"] = bus_counts
    log(f"버스정류장 평균 {bus_counts.mean():.2f}개, 최댓값 {bus_counts.max()}개, 0개인 격자 {int((bus_counts == 0).sum())}개")

    grid.to_file("data/processed/grid_features.gpkg", layer="grid", driver="GPKG")
    log("\n저장 완료: data/processed/grid_features.gpkg (layer=grid, 접근성 컬럼 추가)")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/10_feature_accessibility_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/10_feature_accessibility_log.txt 저장됨")
