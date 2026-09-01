from math import cos, radians

from shapely import Point
from shapely.ops import unary_union

from .config import DETOUR_PRICE, WALK_SPEED
from .shared_func import to_latlon, to_xy

REF_LAT = 60.2
LAT_M = 111320.0
LON_M = LAT_M * cos(radians(REF_LAT))
 
 
def _polygons_only(geom):
    """intersection() can return a GeometryCollection with stray lines/points."""
    if geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [g for g in getattr(geom, "geoms", [])
             if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts) if parts else None


def build_bands(stops, land, bands=(600, 1200, 1800), simplify_m=20,):
    out = []
    for t in sorted(bands, reverse=True):
        circles = [
            Point(*to_xy(lat, lon)).buffer((t - travel) * WALK_SPEED / DETOUR_PRICE, quad_segs=6)
            for lat, lon, travel in stops
            if travel < t
        ]
        if not circles:
            continue

        poly = unary_union(circles)
        if land is not None:
            poly = _polygons_only(poly.intersection(land))
            if poly is None:
                continue

        out.append((t, poly.simplify(simplify_m)))
    return out 
 
def _rings(poly):
    """shapely Polygon -> GeoJSON coordinate rings ([lon, lat] order)."""
    def ring(seq):
        return [[lon, lat] for lat, lon in (to_latlon(x, y) for x, y in seq)]
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
