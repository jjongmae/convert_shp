#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
convert_shp.py
────────────────────────────────────────────────────────────
Task 1) 모든 SHP를 EPSG:32652(UTM Zone 52 N)로 지정/재투영
Task 2) Z 값: 정표고  →  타원체고 (지오이드 높이 N 더하기)
Task 3) 필드명 변경(id→ID, l_linkid→L_LinkID 등)
Task 4) 결과 SHP 세트를 OUT_DIR에 저장 (원본 보존) ★
※ 선·점·멀티선·멀티점만 Z 보정. Polygon 3D가 있으면 분기 추가
※ 스크립트 폴더(또는 data/)에 egm96_15.gtx 파일을 두면 자동 인식
"""

# ── [Imports & Paths] ─────────────────────────────────────
import sys, glob
from pathlib import Path

import geopandas as gpd
from shapely.geometry import (
    Point, LineString, MultiPoint, MultiLineString
)
from pyproj import CRS, Transformer

# ── [사용자 설정 상수] ─────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
SRC_DIR     = SCRIPT_DIR / "shp_input"          # 원본 SHP 폴더
OUT_DIR     = SCRIPT_DIR / "shp_output"         # ★ 결과 저장 폴더
GTX_PATH    = SCRIPT_DIR / "egm96_15.gtx"       # GTX 파일 위치

RENAME_FIELDS = {
    "id": "ID",
    "linkid": "LinkID",
    "l_linkid": "L_LinkID",
    "r_linkid": "R_LinkID",
    "tonodeid": "ToNodeID",
    "fromnodeid": "FromNodeID",
    "roadrank": "RoadRank",
    "roadno": "RoadNo",
    "laneno": "LaneNo",
    "distance": "Distance",
    "maxspeed": "MaxSpeed",
}
TARGET_EPSG = 32652
APPLY_Z_FIX = True
# ──────────────────────────────────────────────────────────

# ── [검사 & 폴더 준비] ───────────────────────────────────
if not GTX_PATH.exists():
    sys.exit(f"❌ 지오이드 파일이 없습니다 → {GTX_PATH}")
OUT_DIR.mkdir(parents=True, exist_ok=True)       # ★ 출력 폴더 생성

# ── [Transformers] ────────────────────────────────────────
CRS_TARGET = CRS.from_epsg(TARGET_EPSG)
to_wgs84   = Transformer.from_crs(CRS_TARGET, 4326, always_xy=True)

vshift = Transformer.from_pipeline(
    f"+proj=pipeline +step +proj=vgridshift +grids={GTX_PATH.as_posix()} "
    f"+multiplier=1"
)

# ── [Z 보정 함수] ─────────────────────────────────────────
def z_fix(geom):
    if not (APPLY_Z_FIX and geom.has_z):
        return geom

    def _ellip(c):
        x, y, z = c
        lon, lat = to_wgs84.transform(x, y)
        _, _, N = vshift.transform(lon, lat, 0)
        return (x, y, z + N)  # 정표고 + N = 타원체고

    if isinstance(geom, Point):
        return Point(_ellip(geom.coords[0]))
    if isinstance(geom, LineString):
        return LineString([_ellip(pt) for pt in geom.coords])
    if isinstance(geom, MultiPoint):
        return MultiPoint([Point(_ellip(pt.coords[0])) for pt in geom.geoms])
    if isinstance(geom, MultiLineString):
        return MultiLineString(
            [LineString([_ellip(pt) for pt in seg.coords]) for seg in geom.geoms]
        )
    return geom  # Polygon 등은 필요 시 추가

# ── [Main] SHP 일괄 변환 ─────────────────────────────────
def main():
    shp_files = glob.glob(str(SRC_DIR / "*.shp"))
    if not shp_files:
        sys.exit(f"❌ SHP가 없습니다 → {SRC_DIR}")

    for shp in shp_files:
        src_path = Path(shp)
        print(f"\n▶ {src_path.name}")
        gdf = gpd.read_file(src_path)

        # Task 1. 좌표계 지정/재투영
        if gdf.crs is None:
            gdf.set_crs(CRS_TARGET, inplace=True)
        elif gdf.crs != CRS_TARGET:
            gdf.to_crs(CRS_TARGET, inplace=True)

        # Task 2. Z 보정
        gdf["geometry"] = gdf.geometry.apply(z_fix)

        # Task 3. 필드명 변경
        gdf.rename(columns=RENAME_FIELDS, inplace=True, errors="ignore")

        # Task 4. OUT_DIR에 저장 ★
        out_path = OUT_DIR / f"{src_path.stem.upper()}{src_path.suffix}"
        gdf.to_file(out_path, driver="ESRI Shapefile")
        print(f"   ✔ 저장 완료 → {out_path}")

    print(f"\n✅ 모든 SHP 변환 완료 (출력 위치: {OUT_DIR})")

if __name__ == "__main__":
    main()
