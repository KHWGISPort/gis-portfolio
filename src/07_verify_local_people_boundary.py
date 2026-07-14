# -*- coding: utf-8 -*-
"""
[Phase 2 - 요청사항 6 최종 해결] 생활인구 집계구코드와 매칭되는 경계 SHP를 찾는다.

지금까지의 경위:
  1차 시도: BND_TOTAL_OA_PG(2024년 개편 이후 최신 경계) -> 매칭률 0%
  2차 시도: bnd_oa_11_2015_4Q(SGIS 승인자료, 2015년 4분기 경계) -> 매칭률 81.98%
  3차 시도: bnd_oa_11_2016_4Q(SGIS 승인자료, 2016년 4분기 경계) -> 매칭률 100%  <- 채택

원인은 애초에 추정했던 '코드 체계 충돌'이 아니라 '기준 연도 불일치'였음.
서울시 생활인구는 집계구 코드를 2016년 4분기 경계 기준으로 고정해서 쓰고 있고,
BND_TOTAL_OA_PG는 그 이후(2024년) 개편된 최신 경계라서 코드값 자체가 달라진 것.
2015년 4분기 경계는 아직 그 이전 버전이라 완전히 일치하지 않았음(82%).

출처: 이 SHP들(bnd_oa_11_2015_4Q, bnd_oa_11_2016_4Q)은 SGIS(통계지리정보서비스)
승인을 받아 취득한 자료로, 사용 시 출처 표기가 의무 조건임 (데이터명세서·README에 명시).
"""
import io
import os

import geopandas as gpd
import pandas as pd

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def check_match(name, path, code_col):
    gdf = gpd.read_file(path)
    codes = set(gdf[code_col].astype(str))
    matched = lp_codes & codes
    log(f"[{name}] 행 수: {len(gdf)}, 코드 개수: {len(codes)}")
    log(f"[{name}] 매칭: {len(matched)} / {len(lp_codes)} ({len(matched) / len(lp_codes) * 100:.2f}%)")
    return codes, matched


if __name__ == "__main__":
    lp = pd.read_csv("data/processed/local_people_summary.csv", encoding="utf-8-sig")
    lp_codes = set(lp["집계구코드"].astype(str))
    log(f"생활인구 고유 집계구코드 수: {len(lp_codes)}\n")

    log("===== 1차: BND_TOTAL_OA_PG (2024년 개편 이후 최신 경계) =====")
    codes_2024, matched_2024 = check_match(
        "BND_TOTAL_OA_PG(2024)", "data/raw/BND_TOTAL_OA_PG/BND_TOTAL_OA_PG.shp", "TOT_REG_CD"
    )
    log("")

    log("===== 2차: bnd_oa_11_2015_4Q (SGIS, 2015년 4분기 경계) =====")
    codes_2015, matched_2015 = check_match(
        "2015 4Q", "data/raw/bnd_oa_11_2015_4Q/bnd_oa_11_2015_4Q.shp", "TOT_OA_CD"
    )
    log("")

    log("===== 3차: bnd_oa_11_2016_4Q (SGIS, 2016년 4분기 경계) =====")
    codes_2016, matched_2016 = check_match(
        "2016 4Q", "data/raw/bnd_oa_11_2016_4Q/bnd_oa_11_2016_4Q.shp", "TOT_REG_CD"
    )
    log("")

    unmatched_2016 = lp_codes - codes_2016
    log(f"2016 4Q 기준 미매칭 잔여: {len(unmatched_2016)}건")

    # 코드 집합이 겹치는 수준을 넘어, 실제 행 단위 1:1 배정이 되는지 엄격하게 검증
    log("\n===== 1:1 관계 엄격 검증 (merge validate) =====")
    lp_dup = lp["집계구코드"].duplicated().sum()
    gdf_2016 = gpd.read_file("data/raw/bnd_oa_11_2016_4Q/bnd_oa_11_2016_4Q.shp")
    oa_dup = gdf_2016["TOT_REG_CD"].astype(str).duplicated().sum()
    log(f"생활인구 집계구코드 중복 행: {lp_dup}건, 2016 경계 TOT_REG_CD 중복 행: {oa_dup}건")

    lp_str = lp.assign(집계구코드=lp["집계구코드"].astype(str))
    gdf_str = gdf_2016.assign(TOT_REG_CD=gdf_2016["TOT_REG_CD"].astype(str))
    merged = lp_str.merge(
        gdf_str[["TOT_REG_CD", "geometry"]],
        left_on="집계구코드", right_on="TOT_REG_CD",
        how="outer", validate="one_to_one", indicator=True,
    )
    log(f"merge(validate='one_to_one') 성공 -> 순수 1:1 관계 확인됨")
    log(merged["_merge"].value_counts().to_string())

    log("\n결론: bnd_oa_11_2016_4Q를 생활인구 공간 조인의 공식 기준 경계로 채택 (100% 매칭, 행 단위 1:1 확인).")
    log("BND_TOTAL_OA_PG(2024)는 생활인구 조인에는 더 이상 사용하지 않음.")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/07_local_people_boundary_check.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/07_local_people_boundary_check.txt 저장됨")
