# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 3] 생활인구 일별 CSV 30개를 취합해서
집계구별 주간/야간 x 평일/주말 평균 테이블로 요약한다.

시간대 구분 기준 (사용자와 합의, 2026-07-14):
  - 주간(활동인구 프록시): 09시 ~ 18시
  - 야간(거주인구 프록시): 22시 ~ 06시 (다음날로 안 넘어가고, 같은 파일 안에서
    시간대구분 값이 22,23,0,1,2,3,4,5,6 인 행들을 그대로 사용.
    생활인구 데이터는 시간대구분 0~23이 전부 '그 날짜(기준일)' 하나에 묶여
    있으므로 날짜를 넘나들며 합칠 필요가 없음)
  - 07~08시, 19~21시(출퇴근 경계 시간대)는 어느 쪽에도 포함하지 않음

평일/주말 구분은 파일명의 날짜(YYYYMMDD)에서 요일을 계산해서 판단한다.

생활인구 CSV는 헤더 첫 컬럼명이 손상되어 있어(데이터명세서 7번 항목 참고),
컬럼 이름 대신 '위치(순서)'로 필요한 컬럼만 골라서 읽는다.
  0번째: 기준일ID (사용하지 않음, 대신 파일명에서 날짜를 가져옴)
  1번째: 시간대구분
  3번째: 집계구코드
  4번째: 총생활인구수
"""
import glob
import io
import os
import re
from datetime import datetime

import pandas as pd

DAY_HOURS = set(range(9, 19))          # 09~18시
NIGHT_HOURS = {22, 23, 0, 1, 2, 3, 4, 5, 6}  # 22~06시

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def get_date_from_filename(path):
    """'LOCAL_PEOPLE_20260601.csv' 같은 파일명에서 날짜를 뽑아낸다."""
    m = re.search(r"(\d{8})", os.path.basename(path))
    return datetime.strptime(m.group(1), "%Y%m%d").date()


def process_one_file(path):
    """
    파일 하나(하루치)를 읽어서 집계구별로
    (주간 합계/건수, 야간 합계/건수)를 계산해 반환한다.
    """
    date = get_date_from_filename(path)
    is_weekend = date.weekday() >= 5  # 5=토요일, 6=일요일

    df = pd.read_csv(path, encoding="cp949", usecols=[1, 3, 4], header=0)
    df.columns = ["시간대구분", "집계구코드", "총생활인구수"]

    day_df = df[df["시간대구분"].isin(DAY_HOURS)]
    night_df = df[df["시간대구분"].isin(NIGHT_HOURS)]

    day_agg = day_df.groupby("집계구코드")["총생활인구수"].agg(["sum", "count"])
    night_agg = night_df.groupby("집계구코드")["총생활인구수"].agg(["sum", "count"])

    return date, is_weekend, day_agg, night_agg


if __name__ == "__main__":
    files = sorted(glob.glob("data/raw/LOCAL_PEOPLE_202606/*.csv"))
    log(f"대상 파일 수: {len(files)}")

    # 4개 그룹(주간평일/주간주말/야간평일/야간주말)별로 합계·건수를 누적할 그릇 준비
    group_names = ["주간_평일", "주간_주말", "야간_평일", "야간_주말"]
    sums = {g: pd.Series(dtype="float64") for g in group_names}
    counts = {g: pd.Series(dtype="float64") for g in group_names}

    n_weekday_files = 0
    n_weekend_files = 0

    for path in files:
        date, is_weekend, day_agg, night_agg = process_one_file(path)
        day_group = "주간_주말" if is_weekend else "주간_평일"
        night_group = "야간_주말" if is_weekend else "야간_평일"

        sums[day_group] = sums[day_group].add(day_agg["sum"], fill_value=0)
        counts[day_group] = counts[day_group].add(day_agg["count"], fill_value=0)
        sums[night_group] = sums[night_group].add(night_agg["sum"], fill_value=0)
        counts[night_group] = counts[night_group].add(night_agg["count"], fill_value=0)

        if is_weekend:
            n_weekend_files += 1
        else:
            n_weekday_files += 1
        log(f"처리 완료: {os.path.basename(path)} ({date} / {'주말' if is_weekend else '평일'})")

    log(f"\n평일 파일 수: {n_weekday_files}, 주말 파일 수: {n_weekend_files}")

    # 합계 / 건수 = 평균
    result = pd.DataFrame(index=sums["주간_평일"].index.union(
        sums["주간_주말"].index).union(sums["야간_평일"].index).union(sums["야간_주말"].index))
    result.index.name = "집계구코드"

    for g in group_names:
        col = f"{g}_평균인구"
        result[col] = sums[g] / counts[g]

    result = result.reset_index()

    log(f"\n최종 집계구 수: {len(result)}")
    for g in group_names:
        col = f"{g}_평균인구"
        na_count = result[col].isna().sum()
        log(f"  {col}: 결측 {na_count}건 (해당 집계구가 이 그룹 시간대에 값이 아예 없었던 경우)")

    os.makedirs("data/processed", exist_ok=True)
    out_path = "data/processed/local_people_summary.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    log(f"\n저장 완료: {out_path}")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/03_aggregate_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/03_aggregate_log.txt 저장됨")
