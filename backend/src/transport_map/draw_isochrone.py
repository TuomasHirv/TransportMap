from math import cos, radians
from shapely import Point
from shapely.ops import unary_union


from .config import WALK_SPEED, DETOUR_PRICE

REF_LAT = 60.2
LAT_M = 111320.0
LON_M = LAT_M * cos(radians(REF_LAT))
 
 
def _to_xy(lat, lon):
    return lon * LON_M, lat * LAT_M
 
 
def _to_latlon(x, y):
    return round(y / LAT_M, 5), round(x / LON_M, 5)
 
 
def build_bands(stops, bands=(600, 1200, 1800), simplify_m=20):
    """
    stops: iterable of (lat, lon, travel_secs)
    returns [(threshold_secs, shapely geometry), ...] largest band first
    """
    out = []
    for t in sorted(bands, reverse=True):
        circles = [
            Point(*_to_xy(lat, lon)).buffer((t - travel) * WALK_SPEED / DETOUR_PRICE, quad_segs=6)
            for lat, lon, travel in stops
            if travel < t
        ]
        if not circles:
            continue
        out.append((t, unary_union(circles).simplify(simplify_m)))
    return out
 
 
def _rings(poly):
    """shapely Polygon -> GeoJSON coordinate rings ([lon, lat] order)."""
    def ring(seq):
        return [[lon, lat] for lat, lon in (_to_latlon(x, y) for x, y in seq)]
    return [ring(poly.exterior.coords)] + [ring(i.coords) for i in poly.interiors]
 
 
def to_geojson(bands):
    features = []
    for secs, geom in bands:
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        features.append({
            "type": "Feature",
            "properties": {"max_seconds": secs, "max_minutes": secs // 60},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [_rings(p) for p in polys],
            },
        })
    return {"type": "FeatureCollection", "features": features}
