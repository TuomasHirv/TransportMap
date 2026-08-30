import csv
from math import cos, hypot, radians

from .config import MAX_WALK_METERS, MAX_WALK_SECONDS, WALK_SPEED


def load_stops(tt, path):
    """-> {stop_id: (lat, lon)}, {stop_id: parent_station}, skipping stations."""
    parents = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            sid = r["stop_id"].strip()
            if r["location_type"].strip() == "1":
                continue                       # a station, not a boarding point
            tt.coords[sid] = (float(r["stop_lat"]), float(r["stop_lon"]))
            parent = r.get("parent_station", "").strip()
            if parent:
                parents[sid] = parent
    return parents
 
 
def metres(a, b):
    """Equirectangular approximation -- accurate well under 1% at walking range."""
    (la1, lo1), (la2, lo2) = a, b
    k = cos(radians((la1 + la2) / 2))
    return hypot((la2 - la1) * 111320, (lo2 - lo1) * 111320 * k)
 
 
def build_footpaths(tt, parents,
                    min_transfer=60):
    """Add walking transfers to a Timetable. speed in m/s (1.33 ~ 4.8 km/h)."""
    ids = [s for s in tt.coords if s in tt.stops]
 
    added = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = metres(tt.coords[a], tt.coords[b])
            same_station = (a in parents and parents[a] == parents.get(b))
            if d <= MAX_WALK_METERS or same_station:
                secs = max(min_transfer, round(d / WALK_SPEED))
                tt.add_footpath(a, b, secs)
                added += 1
    return added

def close_footpaths(tt):
    """Transitive closure -- RAPTOR relaxes footpaths only once per round."""
    INF = float("inf")
    for src in list(tt.stops):
        dist, stack = {src: 0}, [src]
        while stack:
            u = stack.pop()
            for v, w in tt.footpaths[u]:
                nd = dist[u] + w
                if nd <= MAX_WALK_SECONDS and nd < dist.get(v, INF):
                    dist[v] = nd
                    stack.append(v)
        tt.footpaths[src] = [(v, d) for v, d in dist.items() if v != src]
    return tt
