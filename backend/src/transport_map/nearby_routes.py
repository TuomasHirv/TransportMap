import logging

log = logging.getLogger("uvicorn.error")

def lines_nearby(tt, walkable_stops, at, horizon):
    lines = {}
    for stop_id, walk_secs in walkable_stops:
        ready = at + walk_secs
        for route_id, pos in tt.routes_by_stop[stop_id]:
            r = tt.routes[route_id]
            if pos == len(r.stops) - 1:
                continue                       # terminus: you can only alight here
            t = r.earliest_trip(pos, ready)
            if t is None:
                continue
            dep = r.trips[t][pos][1]
            if dep > horizon:
                continue
            if not r.short_name:
                log.info("No short name for route: %s", route_id)
            name = r.short_name
            # a line can be catchable at several walkable stops, and one line may be
            # split across several Route objects -- keep the soonest departure.
            if name not in lines or dep < lines[name]:
                lines[name] = dep
    return lines