# -*- coding: utf-8 -*-
"""
[Phase 5 - 2단계] 중랑구 4분면 스코어링 결과를 folium 웹지도로 만든다.

프로젝트 규칙(CLAUDE.md): 웹지도 출력은 EPSG:4326으로 재변환해서 사용.
"""
import os

import folium
import geopandas as gpd

from utils_geo import TARGET_CRS

QUADRANT_COLOR = {
    "고득점_점포없음(신규후보)": "#e41a1c",  # 빨강 - 핵심 관심 지점
    "고득점_점포있음": "#4daf4a",             # 초록 - 이미 검증된 좋은 자리
    "저득점_점포있음": "#377eb8",             # 파랑 - 과포화/다른 요인으로 버티는 곳
    "저득점_점포없음": "#cccccc",             # 회색 - 예상대로 비어있는 곳
}

if __name__ == "__main__":
    grid = gpd.read_file("data/processed/jungnang_scored_grid.gpkg", layer="grid")
    grid_4326 = grid.to_crs("EPSG:4326")

    stores = gpd.read_file("data/processed/convenience_stores.gpkg").to_crs("EPSG:4326")
    # 중랑구 격자 범위 안에 있는 점포만 추림 (지도가 너무 무거워지지 않도록)
    jn_boundary_4326 = grid_4326.geometry.union_all()
    stores_jn = stores[stores.geometry.within(jn_boundary_4326)]

    trdar = gpd.read_file(
        "data/raw/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권).shp"
    ).to_crs(TARGET_CRS)
    dongbu = trdar[trdar["TRDAR_CD"].astype(str) == "3130106"]
    # 중심점은 미터 단위 좌표계(5179)에서 구한 뒤에 지도용 4326으로 변환 (정확도 위해)
    dongbu_centroid = dongbu.geometry.centroid.to_crs("EPSG:4326").iloc[0]

    center = [dongbu_centroid.y, dongbu_centroid.x]
    m = folium.Map(location=center, zoom_start=15, tiles="cartodbpositron")

    quadrant_layer = {}
    for q in QUADRANT_COLOR:
        quadrant_layer[q] = folium.FeatureGroup(name=q, show=True)

    for _, row in grid_4326.iterrows():
        color = QUADRANT_COLOR[row["quadrant"]]
        tooltip = (
            f"격자: {row['grid_id']}<br>점수(log): {row['score_log']:.2f}<br>"
            f"기존점포: {'있음' if row['has_store'] else '없음'}<br>"
            f"경쟁점(300m): {row['competitor_cnt_300m']:.0f}<br>"
            f"지하철거리: {row['subway_dist_m']:.0f}m"
        )
        folium.GeoJson(
            row["geometry"].__geo_interface__,
            style_function=lambda feat, color=color: {
                "fillColor": color, "color": color, "weight": 0.5, "fillOpacity": 0.55,
            },
            tooltip=tooltip,
        ).add_to(quadrant_layer[row["quadrant"]])

    for layer in quadrant_layer.values():
        layer.add_to(m)

    store_layer = folium.FeatureGroup(name="기존 편의점 위치", show=True)
    for _, row in stores_jn.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=2, color="#000000", weight=1, fill=True, fill_opacity=0.8,
            tooltip=row.get("상호명", "편의점"),
        ).add_to(store_layer)
    store_layer.add_to(m)

    folium.Marker(
        location=[dongbu_centroid.y, dongbu_centroid.x],
        popup="중랑동부시장 (면목2동, 현장 검증 대상지)",
        icon=folium.Icon(color="purple", icon="star"),
    ).add_to(m)

    # 범례를 간단한 HTML로 추가
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background-color: white; padding: 10px; border: 1px solid #999;
                font-size: 13px; line-height: 1.6;">
      <b>4분면 범례</b><br>
      <span style="color:#e41a1c;">■</span> 고득점 · 점포없음 (신규 후보지)<br>
      <span style="color:#4daf4a;">■</span> 고득점 · 점포있음 (검증된 자리)<br>
      <span style="color:#377eb8;">■</span> 저득점 · 점포있음<br>
      <span style="color:#cccccc;">■</span> 저득점 · 점포없음<br>
      <span style="color:#800080;">★</span> 중랑동부시장(임장 대상지)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/22_jungnang_map.html"
    m.save(out_path)
    print(f"저장 완료: {out_path}")
    print(f"격자 수: {len(grid_4326)}, 지도 내 편의점 수: {len(stores_jn)}")
