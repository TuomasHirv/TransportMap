from math import cos, radians, hypot

REF_LAT = 60.2
LAT_M = 111320.0
LON_M = LAT_M * cos(radians(REF_LAT))


def _to_xy(lat, lon):
    return lon * LON_M, lat * LAT_M
 
 
def _to_latlon(x, y):
    return round(y / LAT_M, 5), round(x / LON_M, 5)


def metres(a, b):
    """Equirectangular approximation -- accurate well under 1% at walking range."""
    (la1, lo1), (la2, lo2) = a, b
    k = cos(radians((la1 + la2) / 2))
    return hypot((la2 - la1) * 111320, (lo2 - lo1) * 111320 * k)
