from math import cos, hypot, radians

REF_LAT = 60.2
LAT_M = 111320.0
LON_M = LAT_M * cos(radians(REF_LAT))


def to_xy(lat, lon):
    return lon * LON_M, lat * LAT_M
 
 
def to_latlon(x, y):
    return round(y / LAT_M, 5), round(x / LON_M, 5)


def metres(a, b):
    """Equirectangular approximation -- accurate well under 1% at walking range."""
    (la1, lo1), (la2, lo2) = a, b
    k = cos(radians((la1 + la2) / 2))
    return hypot((la2 - la1) * 111320, (lo2 - lo1) * 111320 * k)

def parse_time(unprocessed_time):
    """Parses a time string that is given to it to seconds INT."""
    time_list = unprocessed_time.split(":")
    # time_list is 0: hours 1: minutes 2: seconds STRING
    time_seconds = (int(time_list[0])*3600) + (int(time_list[1])*60) + int(time_list[2])
    return(time_seconds)

def hm(h, m):
    return h * 3600 + m * 60
