# -*- coding: utf-8 -*-
"""
[Phase 1 - 요청사항 5] 정제된 편의점 점포 데이터를 GeoPackage로 저장한다.
QGIS에서 직접 열어 눈으로 검수할 수 있도록 하기 위함.

좌표계는 프로젝트 규칙에 따라 EPSG:5179로 저장한다.
"""
import importlib
import os

clean_module = importlib.import_module("02_filter_clean_convenience_store")

if __name__ == "__main__":
    print("정제 로직 재실행 중 (02_filter_clean_convenience_store)...")
    seoul_boundary, seoul_boundary_buffered = clean_module.build_seoul_boundary()
    stores_gdf = clean_module.clean_stores(seoul_boundary_buffered)

    os.makedirs("data/processed", exist_ok=True)
    out_path = "data/processed/convenience_stores.gpkg"
    stores_gdf.to_file(out_path, layer="convenience_stores", driver="GPKG")

    print(f"저장 완료: {out_path}")
    print(f"좌표계: {stores_gdf.crs}")
    print(f"행 수: {len(stores_gdf)}")
