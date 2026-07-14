# -*- coding: utf-8 -*-
"""
data/raw 폴더의 모든 원본 데이터를 훑어서 구조를 파악하는 점검용 스크립트.
docs/데이터명세서.md 작성을 위한 사전 조사 목적이며, 파이프라인 본 코드는 아님.
결과는 outputs/raw_inspection.txt 에 저장한다 (콘솔 한글 깨짐 방지).
"""
import glob
import os

import geopandas as gpd
import pandas as pd

# 결과를 담을 리스트 (나중에 파일로 한 번에 저장)
report_lines = []


def log(text=""):
    """콘솔 대신 리스트에 모아뒀다가 파일로 저장하기 위한 헬퍼 함수"""
    report_lines.append(str(text))


def inspect_shapefile(name, path):
    """Shapefile 하나를 읽어서 좌표계·행열수·컬럼·샘플을 기록"""
    log(f"===== [SHP] {name} =====")
    gdf = gpd.read_file(path)
    log(f"경로: {path}")
    log(f"좌표계(CRS): {gdf.crs}")
    log(f"행/열 수: {gdf.shape}")
    log(f"컬럼: {list(gdf.columns)}")
    log("샘플 2행:")
    log(gdf.head(2).drop(columns="geometry").to_string())
    log(f"geometry 타입: {gdf.geom_type.unique()}")
    log("")


def inspect_csv(name, path, encoding_candidates=("utf-8-sig", "cp949", "euc-kr")):
    """CSV 하나를 읽어서 인코딩·행열수·컬럼·샘플을 기록. 인코딩을 순서대로 시도."""
    log(f"===== [CSV] {name} =====")
    log(f"경로: {path}")
    used_encoding = None
    df = None
    for enc in encoding_candidates:
        try:
            df = pd.read_csv(path, encoding=enc, nrows=5000, low_memory=False)
            used_encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if df is None:
        log("!!! 인코딩 자동 감지 실패")
        log("")
        return
    log(f"감지된 인코딩: {used_encoding}")
    # 전체 행 수는 파일을 다시 스트리밍하며 셈 (메모리 절약)
    with open(path, "r", encoding=used_encoding, errors="replace") as f:
        total_rows = sum(1 for _ in f) - 1  # 헤더 제외
    log(f"전체 행 수(헤더 제외): {total_rows}")
    log(f"컬럼 수: {len(df.columns)}")
    log(f"컬럼: {list(df.columns)}")
    log("샘플 2행:")
    log(df.head(2).to_string())
    log("")


def inspect_xlsx(name, path):
    log(f"===== [XLSX] {name} =====")
    df = pd.read_excel(path)
    log(f"경로: {path}")
    log(f"행/열 수: {df.shape}")
    log(f"컬럼: {list(df.columns)}")
    log("샘플 2행:")
    log(df.head(2).to_string())
    log("")


# ---------- 1. Shapefile 3종 ----------
inspect_shapefile("BND_ADM_DONG_PG (행정동 경계)", "data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
inspect_shapefile("BND_TOTAL_OA_PG (집계구 경계)", "data/raw/BND_TOTAL_OA_PG/BND_TOTAL_OA_PG.shp")
inspect_shapefile(
    "서울시 상권분석서비스(영역-상권)",
    "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp",
)

# ---------- 2. 단일 CSV들 ----------
inspect_csv("CARD_SUBWAY_MONTH_202606 (지하철 카드)", "data/raw/CARD_SUBWAY_MONTH_202606.csv")
inspect_csv("서울시 상권분석서비스(추정매출-상권)_2025년", "data/raw/서울시 상권분석서비스(추정매출-상권)_2025년.csv")
inspect_csv("서울시 상권분석서비스(추정매출-행정동)_2025년", "data/raw/서울시 상권분석서비스(추정매출-행정동)_2025년.csv")
inspect_csv("서울시 역사마스터 정보", "data/raw/서울시 역사마스터 정보.csv")
inspect_csv("소상공인시장진흥공단_상가(상권)정보_서울_202603", "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv")

# ---------- 3. 엑셀 ----------
inspect_xlsx("서울시버스정류소위치정보(20260701)", "data/raw/서울시버스정류소위치정보(20260701).xlsx")

# ---------- 4. 생활인구 일별 CSV 30개 (첫 파일만 상세, 나머지는 파일명·행수만) ----------
local_people_files = sorted(glob.glob("data/raw/LOCAL_PEOPLE_202606/*.csv"))
log(f"===== [CSV 그룹] LOCAL_PEOPLE_202606 (생활인구 일별, 총 {len(local_people_files)}개 파일) =====")
inspect_csv("LOCAL_PEOPLE 첫 번째 파일 상세", local_people_files[0])

log("각 파일별 행 수 (헤더 제외):")
for fp in local_people_files:
    # cp949로 우선 시도, 실패하면 utf-8-sig
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            with open(fp, "r", encoding=enc, errors="strict") as f:
                n = sum(1 for _ in f) - 1
            log(f"  {os.path.basename(fp)}: {n}행 (encoding={enc})")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

# ---------- 결과 저장 ----------
os.makedirs("outputs", exist_ok=True)
with open("outputs/raw_inspection.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print("완료: outputs/raw_inspection.txt 저장됨")
