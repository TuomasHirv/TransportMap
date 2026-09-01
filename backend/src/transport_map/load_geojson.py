import json
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import transform, unary_union

from .config import LAND_GEOJSON
from .draw_isochrone import LAT_M, LON_M


def _proj(lon, lat):
    return lon * LON_M, lat * LAT_M


def load_land(path=None):
    gj = json.loads(Path(path or LAND_GEOJSON).read_text(encoding="utf-8"))
    geom = unary_union([shape(f["geometry"]) for f in gj["features"]])
    return transform(_proj, geom).buffer(0).simplify(15)
