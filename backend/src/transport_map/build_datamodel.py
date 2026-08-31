import logging
import time

from collections import defaultdict
from math import cos, hypot, radians

from transport_map.models import Timetable
from .config import MAX_WALK_METERS, MAX_WALK_SECONDS, WALK_SPEED


from .parse_date import service_id_for_day, trips_from_services
from .parse_footpaths import load_stops
from .parse_routes import parse_routes_to_trips
log = logging.getLogger("uvicorn.error")


def build_data_model(day_type = "weekday"):
    t0 = time.perf_counter()
    service_ids = service_id_for_day(day_type)
    accepted_trips = trips_from_services(service_ids)
    log.info("Service ids: %s. Accepted trips: %s", len(service_ids), len(accepted_trips))
    trips = parse_routes_to_trips(accepted_trips)
    parents, stop_names, coords = load_stops()
    tt = create_timetable(trips)
    tt.coords = coords
    tt.stop_names = stop_names

    build_footpaths(tt, parents)

    n_trips = sum(len(r.trips) for r in tt.routes.values())
    n_fp = sum(len(v) for v in tt.footpaths.values())
    log.info("%d stops, %d routes, %d trips (%.1f trips/route)",
             len(tt.stops), len(tt.routes), n_trips, n_trips / max(1, len(tt.routes)))
    log.info("%d coords, %d footpath edges", len(tt.coords), n_fp)
    log.info("built in %.2fs", time.perf_counter() - t0)
    return close_footpaths(tt)


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


def finalize_timetable(patterns):
    tt = Timetable()
    trip_index = {}
    n = 0
    for seq, pattern_trips in patterns.items():
        for group in split_overtaking(len(seq), pattern_trips):
            rid = f"r{n}"
            n += 1
            tt.add_route(rid, seq, [st for _, st in group])
            for i, (trip_id, _) in enumerate(group):
                trip_index[(rid, i)] = trip_id
    tt.finalize()
    return tt

def create_timetable(trips):
    patterns = build_patterns(trips)
    tt = finalize_timetable(patterns)
    return tt

def build_patterns(trips):
    patterns = defaultdict(list)
    for trip_id, events in trips:
        seq = tuple(e[2] for e in events)
        stoptimes = [(a, d) for a, d, _ in events]
        patterns[seq].append((trip_id, stoptimes))
    return patterns

def split_overtaking(n_stops, trips):
    """Partition a pattern's trips into maximal non-overtaking groups."""
    trips = sorted(trips, key=lambda t: t[1][0][1])
    groups = []
    for trip_id, st in trips:
        for g in groups:
            last = g[-1][1]
            if all(last[i][0] <= st[i][0] and last[i][1] <= st[i][1]
                   for i in range(n_stops)):
                g.append((trip_id, st))
                break
        else:
            groups.append([(trip_id, st)])
    return groups
