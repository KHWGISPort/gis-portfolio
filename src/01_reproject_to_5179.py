# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 1] 모든 공간 데이터의 좌표계를 EPSG:5179로 통일한다.

- 폴리곤 3종(행정동, 집계구, 상권 영역)과 위경도 기반 포인트 3종
  (상가업소, 지하철역, 버스정류소)을 각각 EPSG:5179로 변환하고,
  변환 전/후 좌표계와 좌표 범위(bounds)를 검증 로그로 남긴다.
- 실제 필터링/정제(02번 스크립트)에서 이 파일의 함수들을 재사용할 것이므로
  여기서는 데이터를 파일로 저장하지 않고 '검증'만 수행한다.
"""
import io
import os

import pandas as pd

from utils_geo import load_shp_as_5179, points_from_lonlat, TARGET_CRS

report = io.StringIO()


def log(text=""):
    print(text)  # 콘솔에도 출력 (진행상황 확인용, 한글이 깨져도 파일에는 정상 기록됨)
    report.write(str(text) + "\n")


def check_polygon(name, path):
    """폴리곤 Shapefile을 5179로 변환하고 결과를 검증 로그에 남긴다."""
    log(f"===== [폴리곤] {name} =====")
    import geopandas as gpd

    original = gpd.read_file(path)
    original_crs = original.crs
    original_bounds = original.total_bounds

    converted = load_shp_as_5179(path)

    log(f"변환 전 좌표계: {original_crs}")
    log(f"변환 전 범위(bounds): {original_bounds}")
    log(f"변환 후 좌표계: {converted.crs}")
    log(f"변환 후 범위(bounds): {converted.total_bounds}")
    log(f"행 수: {len(converted)} (변환 전후 동일해야 함: {len(original) == len(converted)})")
    log("")
    return converted


def check_points(name, csv_path, lon_col, lat_col, encoding, usecols=None):
    """위경도 컬럼을 가진 CSV를 5179 포인트로 변환하고 결과를 검증 로그에 남긴다."""
    log(f"===== [포인트] {name} =====")
    df = pd.read_csv(csv_path, encoding=encoding, usecols=usecols)
    converted = points_from_lonlat(df, lon_col, lat_col, source_crs="EPSG:4326")

    log(f"원본 행 수: {len(df)}")
    log(f"변환 후 행 수(위경도 결측 제외): {len(converted)}")
    log(f"변환 전 좌표계(가정): EPSG:4326")
    log(f"변환 후 좌표계: {converted.crs}")
    log(f"변환 후 범위(bounds): {converted.total_bounds}")
    log("")
    return converted


def check_points_xlsx(name, xlsx_path, lon_col, lat_col):
    """엑셀 파일(위경도 포함)을 5179 포인트로 변환하고 검증 로그에 남긴다."""
    log(f"===== [포인트] {name} =====")
    df = pd.read_excel(xlsx_path)
    converted = points_from_lonlat(df, lon_col, lat_col, source_crs="EPSG:4326")

    log(f"원본 행 수: {len(df)}")
    log(f"변환 후 행 수(위경도 결측 제외): {len(converted)}")
    log(f"변환 후 좌표계: {converted.crs}")
    log(f"변환 후 범위(bounds): {converted.total_bounds}")
    log("")
    return converted


if __name__ == "__main__":
    log(f"목표 좌표계: {TARGET_CRS}\n")

    # 1) 폴리곤 3종
    check_polygon("BND_ADM_DONG_PG (행정동 경계)", "data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
    check_polygon("BND_TOTAL_OA_PG (집계구 경계)", "data/raw/BND_TOTAL_OA_PG/BND_TOTAL_OA_PG.shp")
    check_polygon(
        "서울시 상권분석서비스(영역-상권)",
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp",
    )

    # 2) 포인트 3종 (위경도 -> 5179)
    check_points(
        "소상공인 상가업소정보",
        "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv",
        lon_col="경도",
        lat_col="위도",
        encoding="utf-8-sig",
        usecols=["상권업종소분류명", "위도", "경도"],
    )
    check_points(
        "서울시 역사마스터 정보",
        "data/raw/서울시 역사마스터 정보.csv",
        lon_col="경도",
        lat_col="위도",
        encoding="cp949",
    )
    check_points_xlsx(
        "서울시버스정류소위치정보",
        "data/raw/서울시버스정류소위치정보(20260701).xlsx",
        lon_col="X좌표",
        lat_col="Y좌표",
    )

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/01_reproject_check.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/01_reproject_check.txt 저장됨")
