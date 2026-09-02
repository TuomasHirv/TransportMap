import logging
import time
from collections import defaultdict
from itertools import combinations
from math import cos, radians

import numpy as np

from transport_map.models import Timetable

from .config import MAX_WALK_METERS, MAX_WALK_SECONDS, WALK_SPEED
from .parse_date import service_id_for_day, trips_from_services
from .shared_func import metres

log = logging.getLogger("uvicorn.error")
DAY_IN_SECONDS = 86400


def build_datamodel(all_trips, parents, stop_names, coords, trip_id_shortname, day_type = "weekday",
                    on = None, calendar_path = None, trips_path = None):
    """`on` pins the date the calendar window is evaluated against (default: today)."""
    t0 = time.perf_counter()
    service_ids, prev_day_service_ids = service_id_for_day(day_type, on, calendar_path)
    accepted_trips, prev_accepted_trips = trips_from_services(
        service_ids, prev_day_service_ids, trips_path)
    # Morning trips are marked as >24:00:00 of the last day
    curr_day_trips = [t for t in all_trips if t[0] in accepted_trips]
    log.info("Trips in the current day: %s", len(curr_day_trips))
    prev_day_night_trips = [
    (tid, 
     [(arr - DAY_IN_SECONDS, dep - DAY_IN_SECONDS, stop) for arr, dep, stop in events])
        for tid, events in all_trips
        if tid in prev_accepted_trips and events[-1][0] >= DAY_IN_SECONDS
    ]
    log.info("Morning trips from prev day: %s", len(prev_day_night_trips))
    trips_by_daytype = curr_day_trips + prev_day_night_trips

    log.info("Service ids: %s. Accepted trips: %s", len(service_ids), len(accepted_trips))
    tt = create_timetable(trips_by_daytype, trip_id_shortname)
    
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



def build_footpaths(tt, parents, min_transfer=60):
    ids = [s for s in tt.coords if s in tt.stops]
    lats = np.fromiter((tt.coords[s][0] for s in ids), float, len(ids))
    lons = np.fromiter((tt.coords[s][1] for s in ids), float, len(ids))

    k = cos(radians(float(lats.mean())))
    y = lats * 111320.0
    x = lons * 111320.0 * k
    r2 = MAX_WALK_METERS ** 2

    pairs = {}                                   # (a, b) -> seconds
    for i in range(len(ids)):
        dy = y[i + 1:] - y[i]
        dx = x[i + 1:] - x[i]
        d2 = dy * dy + dx * dx
        for j in np.flatnonzero(d2 <= r2):
            d = float(np.sqrt(d2[j]))
            pairs[(ids[i], ids[i + 1 + j])] = max(min_transfer, round(d / WALK_SPEED))

    # same-station override, regardless of distance
    groups = defaultdict(list)
    for s in ids:
        if s in parents:
            groups[parents[s]].append(s)
    for members in groups.values():
        for a, b in combinations(members, 2):
            if (a, b) not in pairs and (b, a) not in pairs:
                d = metres(tt.coords[a], tt.coords[b])
                pairs[(a, b)] = max(min_transfer, round(d / WALK_SPEED))

    for (a, b), secs in pairs.items():
        tt.add_footpath(a, b, secs)
    return len(pairs)

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


def finalize_timetable(patterns, trip_id_shortname):
    tt = Timetable()
    trip_index = {}
    n = 0
    for seq, pattern_trips in patterns.items():
        for group in split_overtaking(len(seq), pattern_trips):
            rid = f"r{n}"
            n += 1
            name = trip_id_shortname.get(group[0][0], "")
            tt.add_route(rid, seq, [st for _, st in group], name)
            for i, (trip_id, _) in enumerate(group):
                trip_index[(rid, i)] = trip_id
    tt.finalize()
    return tt

def create_timetable(trips, trip_id_shortname):
    patterns = build_patterns(trips)
    tt = finalize_timetable(patterns, trip_id_shortname)
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
