# -*- coding: utf-8 -*-
"""
공간 데이터 관련 공용 함수 모음.
이후 단계(02_filter_clean.py 등)에서 반복적으로 재사용하기 위해
좌표계 변환 로직을 여기 함수로 모아둔다.
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# 프로젝트 CLAUDE.md 규칙: 분석용 좌표계는 EPSG:5179로 통일
TARGET_CRS = "EPSG:5179"


def load_shp_as_5179(path, source_crs_if_missing=None):
    """
    Shapefile을 읽어서 EPSG:5179 좌표계로 변환해 반환한다.

    - Shapefile은 보통 .prj 파일에 좌표계 정보가 이미 들어있으므로
      geopandas가 자동으로 인식한다 (source_crs_if_missing은 그런 정보가 없을 때만 사용).
    """
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        if source_crs_if_missing is None:
            raise ValueError(f"{path}: 좌표계 정보가 없고 source_crs_if_missing도 지정되지 않았습니다.")
        gdf = gdf.set_crs(source_crs_if_missing)
    return gdf.to_crs(TARGET_CRS)


def points_from_lonlat(df: pd.DataFrame, lon_col: str, lat_col: str, source_crs="EPSG:4326"):
    """
    위도/경도 컬럼을 가진 일반 표(DataFrame)를 포인트 GeoDataFrame으로 변환하고
    EPSG:5179로 재투영해서 반환한다.

    - 위경도 값이 없는(NaN) 행은 포인트를 만들 수 없으므로 여기서 제외한다.
    """
    valid = df.dropna(subset=[lon_col, lat_col]).copy()
    geometry = [Point(xy) for xy in zip(valid[lon_col], valid[lat_col])]
    gdf = gpd.GeoDataFrame(valid, geometry=geometry, crs=source_crs)
    return gdf.to_crs(TARGET_CRS)


def build_seoul_boundary(buffer_m=0):
    """
    서울 경계(폴리곤 하나)를 만든다.
    BND_ADM_DONG_PG(전국 행정동 경계)에서 ADM_CD가 '11'(서울 시도코드)로
    시작하는 행만 모아 하나로 합친다(union). 좌표계는 5179로 통일.

    buffer_m > 0 이면 여유 공간을 준 버전을 반환한다
    (예: 좌표 오류 판정 시 경계선에 딱 걸친 점까지 억울하게 걸러지는 것을 방지).
    """
    gdf = load_shp_as_5179("data/raw/BND_ADM_DONG_PG/BND_ADM_DONG_PG.shp")
    seoul = gdf[gdf["ADM_CD"].astype(str).str.startswith("11")]
    boundary = seoul.union_all()
    if buffer_m:
        boundary = boundary.buffer(buffer_m)
    return boundary
