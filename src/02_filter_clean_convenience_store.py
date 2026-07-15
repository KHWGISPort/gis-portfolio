# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 2] 편의점 관련 데이터만 필터링하고,
결측·중복·좌표 오류(서울 밖에 찍힌 점 등)를 처리한다.

대상 3개 테이블
  1) 소상공인 상가업소정보  -> 편의점 매장 포인트 (메인 포인트 데이터)
  2) 추정매출-상권          -> 편의점 매출 (메인 타깃)
  3) 추정매출-행정동        -> 편의점 매출 (보조·검증용)

처리 결과와 "무엇을 왜 버렸는지"는 outputs/02_clean_log.txt 에 기록한다.
"""
import io
import os

import geopandas as gpd
import pandas as pd

from utils_geo import load_shp_as_5179, points_from_lonlat, TARGET_CRS
from utils_geo import build_seoul_boundary as _build_seoul_boundary

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def build_seoul_boundary():
    """
    서울 경계(원본 그대로)와 200m 버퍼를 준 버전을 함께 반환한다.
    (좌표 오류 판정 시, 딱 경계선에 걸친 점까지 억울하게 걸러지는 것을 막기 위해
    버퍼 버전이 필요함. 실제 경계 생성 로직은 utils_geo.build_seoul_boundary 재사용.)
    """
    boundary = _build_seoul_boundary()
    boundary_buffered = _build_seoul_boundary(buffer_m=200)
    return boundary, boundary_buffered


def clean_stores(seoul_boundary_buffered):
    """상가업소정보 -> 편의점만 필터링 + 정제"""
    log("===== 1) 소상공인 상가업소정보 -> 편의점 정제 =====")

    df = pd.read_csv(
        "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv",
        encoding="utf-8-sig",
        low_memory=False,
    )
    log(f"원본 전체 상가업소 수: {len(df)}")

    # 1. 편의점 업종만 필터링
    is_conv = (
        (df["상권업종대분류명"] == "소매")
        & (df["상권업종중분류명"] == "종합 소매")
        & (df["상권업종소분류명"] == "편의점")
    )
    df = df[is_conv].copy()
    log(f"편의점 필터 후: {len(df)}")

    # 2. 결측치 처리: 좌표(위도/경도)가 없으면 지도에 쓸 수 없으므로 제외
    before = len(df)
    df = df.dropna(subset=["위도", "경도"])
    dropped = before - len(df)
    log(f"[버림] 위경도 결측: {dropped}건 (좌표 없이는 격자 매칭 불가능하므로 제외)")

    # 3. 완전 중복(상가업소번호가 그대로 중복) 제거
    before = len(df)
    df = df.drop_duplicates(subset=["상가업소번호"])
    dropped = before - len(df)
    log(f"[버림] 상가업소번호 완전 중복: {dropped}건 (동일 레코드가 두 번 이상 실림)")

    # 4. 이름+주소+좌표가 완전히 같은 행(별개 번호로 잘못 중복 등록된 경우) 제거
    before = len(df)
    df = df.drop_duplicates(subset=["상호명", "도로명주소", "위도", "경도"])
    dropped = before - len(df)
    log(f"[버림] 상호명+도로명주소+좌표 완전 중복: {dropped}건 (사실상 같은 매장이 중복 등록됨)")

    # 5. 좌표계 통일 (위경도 -> EPSG:5179 포인트)
    gdf = points_from_lonlat(df, lon_col="경도", lat_col="위도", source_crs="EPSG:4326")

    # 6. 좌표 오류 처리: 서울 경계(200m 버퍼) 밖에 찍힌 점 제거
    before = len(gdf)
    within_seoul = gdf.geometry.within(seoul_boundary_buffered)
    dropped_gdf = gdf[~within_seoul]
    gdf = gdf[within_seoul].copy()
    dropped = before - len(gdf)
    log(f"[버림] 서울 경계 밖 좌표: {dropped}건 (원본이 '서울특별시'로 표기되어 있지만 실제 좌표가 서울 밖으로 확인됨)")
    if dropped > 0:
        log("  -> 버려진 상호명 샘플: " + ", ".join(dropped_gdf["상호명"].astype(str).head(5).tolist()))

    log(f"최종 편의점 수: {len(gdf)}")
    log("")
    return gdf


def clean_sales(path, encoding, area_col, area_name_col, name):
    """추정매출(상권 또는 행정동) -> 편의점만 필터링 + 정제"""
    log(f"===== 2) {name} -> 편의점(CS300002) 정제 =====")

    df = pd.read_csv(path, encoding=encoding)
    log(f"원본 전체 행 수: {len(df)}")

    # 1. 편의점 서비스업종코드만 필터링
    df = df[df["서비스_업종_코드"] == "CS300002"].copy()
    log(f"편의점(CS300002) 필터 후: {len(df)}")

    # 2. 중복 처리: (지역코드, 분기)는 유일해야 정상 -> 중복이면 뒤 레코드만 남김
    before = len(df)
    df = df.drop_duplicates(subset=["기준_년분기_코드", area_col])
    dropped = before - len(df)
    log(f"[버림] (기준_년분기_코드, {area_col}) 중복: {dropped}건")

    # 3. 결측치 처리: 매출 관련 핵심 컬럼(당월_매출_금액, 당월_매출_건수)이 비어있으면 학습에 못 쓰므로 제외
    before = len(df)
    df = df.dropna(subset=["당월_매출_금액", "당월_매출_건수"])
    dropped = before - len(df)
    log(f"[버림] 당월_매출_금액/건수 결측: {dropped}건")

    # 4. 값 오류 처리: 매출 금액/건수가 음수인 행은 논리적으로 불가능하므로 제외
    before = len(df)
    df = df[(df["당월_매출_금액"] >= 0) & (df["당월_매출_건수"] >= 0)]
    dropped = before - len(df)
    log(f"[버림] 매출 금액/건수 음수: {dropped}건")

    log(f"최종 {name} 편의점 매출 행 수: {len(df)}")
    log("")
    return df


if __name__ == "__main__":
    log("서울 경계(행정동 union, 200m 버퍼) 생성 중...")
    seoul_boundary, seoul_boundary_buffered = build_seoul_boundary()
    log("완료\n")

    stores_gdf = clean_stores(seoul_boundary_buffered)
    sales_trdar_df = clean_sales(
        "data/raw/서울시 상권분석서비스(추정매출-상권)_2025년.csv",
        encoding="cp949",
        area_col="상권_코드",
        area_name_col="상권_코드_명",
        name="추정매출-상권(메인 타깃)",
    )
    sales_dong_df = clean_sales(
        "data/raw/서울시 상권분석서비스(추정매출-행정동)_2025년.csv",
        encoding="cp949",
        area_col="행정동_코드",
        area_name_col="행정동_코드_명",
        name="추정매출-행정동(보조·검증용)",
    )

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/02_clean_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/02_clean_log.txt 저장됨")
