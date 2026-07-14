# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 6] 생활인구 CSV의 집계구 코드와
BND_TOTAL_OA_PG(집계구 경계 SHP)의 집계구 코드 매칭률을 확인한다.

결과 요약 (자세한 내용은 아래 로그 참고):
  - 집계구코드 직접 비교: 0% 매칭 (자릿수부터 13 vs 14로 다름)
  - 행정동코드로도 비교해봤지만 7.5%만 매칭 -> 단순 자릿수 오류가 아니라
    "서로 다른 행정동코드 체계"를 쓰고 있는 것으로 확인됨.
  - 원인: 생활인구는 '서울시 자체 행정동/집계구코드 체계'를 쓰고,
    BND_ADM_DONG_PG/BND_TOTAL_OA_PG는 '행정안전부(국가공간정보포털) 표준코드
    체계'를 씀. 같은 동이라도 코드 값 자체가 다름
    (예: 청운효자동 -> 생활인구/상권분석서비스="11110515", 국가공간정보포털="11010720").
  - 반면 생활인구 행정동코드는 '서울시 상권분석서비스(영역-상권)' SHP의
    ADSTRD_CD와는 92.7% 매칭됨 -> 같은 서울시 코드 체계를 공유하는 것으로 보임.
"""
import io
import os

import geopandas as gpd
import pandas as pd

from utils_geo import load_shp_as_5179

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


if __name__ == "__main__":
    # 1. 생활인구 집계구코드 (3번 단계에서 만든 요약 파일 사용)
    lp = pd.read_csv("data/processed/local_people_summary.csv", encoding="utf-8-sig")
    lp_oa_codes = set(lp["집계구코드"].astype(str))
    log(f"[생활인구] 고유 집계구코드 수: {len(lp_oa_codes)}")
    log(f"[생활인구] 집계구코드 자릿수: {sorted(set(len(c) for c in lp_oa_codes))}")
    log(f"[생활인구] 샘플: {list(lp_oa_codes)[:3]}\n")

    # 2. BND_TOTAL_OA_PG 서울 집계구코드
    gdf = gpd.read_file("data/raw/BND_TOTAL_OA_PG/BND_TOTAL_OA_PG.shp")
    seoul_oa = gdf[gdf["ADM_CD"].astype(str).str.startswith("11")]
    oa_codes = set(seoul_oa["TOT_REG_CD"].astype(str))
    log(f"[BND_TOTAL_OA_PG] 서울 집계구코드 수: {len(oa_codes)}")
    log(f"[BND_TOTAL_OA_PG] 집계구코드 자릿수: {sorted(set(len(c) for c in oa_codes))}")
    log(f"[BND_TOTAL_OA_PG] 샘플: {list(oa_codes)[:3]}\n")

    # 3. 직접 매칭률
    direct_overlap = lp_oa_codes & oa_codes
    log("===== 집계구코드 직접 매칭 결과 =====")
    log(f"교집합: {len(direct_overlap)}건")
    log(f"매칭률(생활인구 기준): {len(direct_overlap) / len(lp_oa_codes) * 100:.2f}%")
    log(f"매칭률(BND_TOTAL_OA_PG 기준): {len(direct_overlap) / len(oa_codes) * 100:.2f}%")
    log("-> 자릿수부터 13(생활인구) vs 14(BND_TOTAL_OA_PG)로 달라 원천적으로 매칭 불가\n")

    # 4. 원인 조사: 행정동코드 레벨에서도 비교
    lp_raw = pd.read_csv(
        "data/raw/LOCAL_PEOPLE_202606/LOCAL_PEOPLE_20260601.csv", encoding="cp949", usecols=[2], header=0
    )
    lp_raw.columns = ["행정동코드"]
    lp_dong_codes = set(lp_raw["행정동코드"].astype(str).unique())

    dong_gdf = load_shp_as_5179("data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
    seoul_dong = dong_gdf[dong_gdf["ADM_CD"].astype(str).str.startswith("11")]
    adm_codes = set(seoul_dong["ADM_CD"].astype(str))

    dong_overlap = lp_dong_codes & adm_codes
    log("===== 원인 조사: 행정동코드 레벨 매칭 (BND_ADM_DONG_PG) =====")
    log(f"생활인구 행정동코드 수: {len(lp_dong_codes)}, BND_ADM_DONG_PG 서울 행정동코드 수: {len(adm_codes)}")
    log(f"교집합: {len(dong_overlap)}건 ({len(dong_overlap) / len(lp_dong_codes) * 100:.1f}%)")

    # 청운효자동 사례로 코드 체계가 다름을 예시로 보여줌
    example = seoul_dong[seoul_dong["ADM_NM"].astype(str).str.contains("청운효자", na=False)]
    log("예시) '청운효자동'의 코드값 비교:")
    log(f"  생활인구/서울시 코드체계 = 11110515")
    log(f"  BND_ADM_DONG_PG(행안부 코드체계) = {example['ADM_CD'].tolist()}")
    log("-> 같은 동인데 코드 값 자체가 다름 = 서로 다른 코드 체계를 사용 중\n")

    # 5. 대안 확인: 서울시 상권분석서비스(영역-상권) SHP의 ADSTRD_CD와는 얼마나 맞는지
    trdar_gdf = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    )
    adstrd_codes = set(trdar_gdf["ADSTRD_CD"].astype(str).unique())
    alt_overlap = lp_dong_codes & adstrd_codes
    log("===== 대안 확인: 상권분석서비스(영역-상권) SHP의 ADSTRD_CD와 매칭 =====")
    log(f"교집합: {len(alt_overlap)}건 ({len(alt_overlap) / len(lp_dong_codes) * 100:.1f}%)")
    log("-> 생활인구와 상권분석서비스는 '서울시 코드체계'를 공유하는 것으로 보임\n")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/06_code_matching_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/06_code_matching_log.txt 저장됨")
