# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 4] 정제 결과를 data/processed에 저장하고,
정제 전/후 건수 비교표를 만든다.

02번 스크립트(편의점 필터링·정제)의 함수를 그대로 재사용해서
결과를 다시 만들고, 이번에는 파일로 저장까지 한다.
(02번 파일명이 숫자로 시작해서 일반 import 문으로는 불러올 수 없으므로
importlib을 사용한다.)
"""
import glob
import importlib
import io
import os

import pandas as pd

clean_module = importlib.import_module("02_filter_clean_convenience_store")

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def count_raw_rows(path, encoding):
    """원본 CSV의 행 수(헤더 제외)를 빠르게 센다."""
    with open(path, "r", encoding=encoding, errors="replace") as f:
        return sum(1 for _ in f) - 1


if __name__ == "__main__":
    os.makedirs("data/processed", exist_ok=True)

    # 1. 02번 스크립트의 정제 로직을 그대로 실행해서 정제된 결과를 받아온다
    log("정제 로직 재실행 중 (02_filter_clean_convenience_store)...")
    seoul_boundary, seoul_boundary_buffered = clean_module.build_seoul_boundary()
    stores_gdf = clean_module.clean_stores(seoul_boundary_buffered)
    sales_trdar_df = clean_module.clean_sales(
        "data/raw/서울시 상권분석서비스(추정매출-상권)_2025년.csv",
        encoding="cp949",
        area_col="상권_코드",
        area_name_col="상권_코드_명",
        name="추정매출-상권(메인 타깃)",
    )
    sales_dong_df = clean_module.clean_sales(
        "data/raw/서울시 상권분석서비스(추정매출-행정동)_2025년.csv",
        encoding="cp949",
        area_col="행정동_코드",
        area_name_col="행정동_코드_명",
        name="추정매출-행정동(보조·검증용)",
    )
    log("완료\n")

    # 2. data/processed 에 저장
    #    점포 데이터는 EPSG:5179 좌표(geometry)를 x,y 컬럼으로 풀어서 일반 CSV로도 저장한다.
    #    (좌표를 지도 도구 없이도 바로 확인할 수 있도록 하기 위함. GeoPackage 저장은 5번 단계에서 별도 진행)
    stores_out = stores_gdf.drop(columns="geometry").copy()
    stores_out["x_5179"] = stores_gdf.geometry.x
    stores_out["y_5179"] = stores_gdf.geometry.y
    stores_out.to_csv("data/processed/convenience_stores.csv", index=False, encoding="utf-8-sig")

    sales_trdar_df.to_csv("data/processed/sales_trdar_convenience.csv", index=False, encoding="utf-8-sig")
    sales_dong_df.to_csv("data/processed/sales_dong_convenience.csv", index=False, encoding="utf-8-sig")

    log("저장 완료:")
    log("  data/processed/convenience_stores.csv")
    log("  data/processed/sales_trdar_convenience.csv")
    log("  data/processed/sales_dong_convenience.csv")
    log("  data/processed/local_people_summary.csv (3번 단계에서 이미 저장됨)\n")

    # 3. 정제 전/후 건수 비교표 만들기
    log("원본 행 수 세는 중 (상가업소정보, 추정매출 2종)...")
    raw_stores_n = count_raw_rows(
        "data/raw/소상공인시장진흥공단_상가(상권)정보_서울_202603.csv", encoding="utf-8-sig"
    )
    raw_trdar_n = count_raw_rows(
        "data/raw/서울시 상권분석서비스(추정매출-상권)_2025년.csv", encoding="cp949"
    )
    raw_dong_n = count_raw_rows(
        "data/raw/서울시 상권분석서비스(추정매출-행정동)_2025년.csv", encoding="cp949"
    )

    local_people_files = sorted(glob.glob("data/raw/LOCAL_PEOPLE_202606/*.csv"))
    raw_local_people_total = sum(count_raw_rows(fp, encoding="cp949") for fp in local_people_files)
    local_people_summary_n = len(pd.read_csv("data/processed/local_people_summary.csv"))

    compare = pd.DataFrame(
        [
            ["상가업소정보(전체) -> 편의점 매장(최종)", raw_stores_n, len(stores_gdf),
             "업종 필터 + 결측/중복/좌표오류 제거"],
            ["추정매출-상권(전체) -> 편의점(메인 타깃)", raw_trdar_n, len(sales_trdar_df),
             "서비스업종코드(CS300002) 필터 + 결측/중복/음수 제거"],
            ["추정매출-행정동(전체) -> 편의점(보조·검증용)", raw_dong_n, len(sales_dong_df),
             "서비스업종코드(CS300002) 필터 + 결측/중복/음수 제거"],
            ["생활인구 30일(원본 레코드 총합) -> 집계구 요약", raw_local_people_total, local_people_summary_n,
             "일별x시간대별 레코드를 집계구 단위 4개 평균값으로 요약 (건수 개념이 다름)"],
        ],
        columns=["데이터셋", "정제 전 건수", "정제 후 건수", "비고"],
    )

    log("\n===== 정제 전/후 건수 비교표 =====")
    log(compare.to_string(index=False))

    compare.to_csv("outputs/04_before_after_comparison.csv", index=False, encoding="utf-8-sig")

    with open("outputs/04_save_processed_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("\n완료: outputs/04_before_after_comparison.csv, outputs/04_save_processed_log.txt 저장됨")
