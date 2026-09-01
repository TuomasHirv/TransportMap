import json
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import transform, unary_union

from .draw_isochrone import LAT_M, LON_M

LAND_PATH = Path(__file__).parent.parent.parent / "data" / "land.geojson"

def _proj(lon, lat):
    return lon * LON_M, lat * LAT_M


def load_land():
    gj = json.loads(LAND_PATH.read_text(encoding="utf-8"))
    geom = unary_union([shape(f["geometry"]) for f in gj["features"]])
    return transform(_proj, geom).buffer(0).simplify(15)