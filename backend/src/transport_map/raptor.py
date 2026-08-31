from transport_map.parse_footpaths import build_footpaths, close_footpaths, load_stops, metres
from transport_map.parse_routes import create_timetable

from .config import MAX_WALK_METERS, WALK_SPEED, STOPS_PATH, STOP_TIMES_PATH

import logging, time

log = logging.getLogger("uvicorn.error")


def hm(h, m):
    return h * 3600 + m * 60

INF = float("inf")

def getNearby(tt, source):
    src_lat, src_lon = source
    walkable_stops = []
    for stop_id, (lat, lon) in tt.coords.items():
        d = metres((lat, lon), (src_lat, src_lon))
        if (d < MAX_WALK_METERS):
            walkable_stops.append((stop_id, round(d / WALK_SPEED)))
    return walkable_stops



def reachable(tt, source, start_time, budget, max_rounds=8):
    """Calculates all reachable stops and how much time is left for each"""
    t0 = time.perf_counter()
    horizon = start_time + budget
    best  = {}     # earliest arrival at each stop
    board = {}     # earliest time we may board there
    marked = set()
    walkable_stops = getNearby(tt, source)
    if not walkable_stops: 
        return {}
    for q, w in walkable_stops:                # NEW: round 0, walk from source
        if start_time + w <= horizon:
            best[q] = board[q] = start_time + w
            marked.add(q)

    for _ in range(max_rounds):
        queue = {}                                   # route -> first position
        for p in marked:
            for rid, pos in tt.routes_by_stop[p]:
                queue[rid] = min(queue.get(rid, pos), pos)

        marked = set()
        prev_board = dict(board)                     # boarding uses round k-1

        for rid, start_pos in queue.items():
            r, t = tt.routes[rid], None
            for i in range(start_pos, len(r.stops)):
                p = r.stops[i]
                if t is not None:                            # get off?
                    arr = r.trips[t][i][0]
                    if arr <= horizon and arr < best.get(p, INF):
                        best[p] = arr
                        board[p] = arr + tt.transfer_time[p]
                        marked.add(p)
                ready = prev_board.get(p)                    # get on?
                if ready is not None and (t is None or ready <= r.trips[t][i][1]):
                    et = r.earliest_trip(i, ready)
                    if et is not None and et != t:
                        t = et
        for p in list(marked):
            for q, w in tt.footpaths[p]:
                arr = best[p] + w
                if arr <= horizon and arr < best.get(q, INF):
                    best[q] = board[q] = arr
                    marked.add(q)

        if not marked:
            break
    log.info("reachable finished in %.2fs", time.perf_counter() - t0)
    return {p: horizon - a for p, a in best.items()}
