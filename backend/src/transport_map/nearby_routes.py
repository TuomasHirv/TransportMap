import logging

log = logging.getLogger("uvicorn.error")

def lines_nearby(tt, walkable_stops, at, horizon):
    lines = {}
    for stop_id, walk_secs in walkable_stops:
        log.info("Current stop_id: %s", stop_id)
        ready = at + walk_secs
        for route_id, pos in tt.routes_by_stop[stop_id]:
            r = tt.routes[route_id]
            t = r.earliest_trip(pos, ready)
            if t is None:
                log.info("No earliest trip %s", route_id)
                continue
            dep = r.trips[t][pos][1]
            if dep > horizon:
                log.info("Departure was after horizon: %s %s", dep, route_id)
                continue
            if not r.short_name:
                log.info("No short name: %s", route_id)
            name = r.short_name
            if name not in lines:
                lines[name] = dep
    return lines