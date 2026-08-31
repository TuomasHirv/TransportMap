from .parse_footpaths import build_footpaths, close_footpaths, load_stops
from .parse_date import service_id_for_day, trips_from_services
from .parse_routes import create_timetable



import logging, time

log = logging.getLogger("uvicorn.error")


def build_data_model(day_type = "saturday"):
    t0 = time.perf_counter()
    service_ids = service_id_for_day(day_type)
    accepted_trips = trips_from_services(service_ids)
    log.info("Service ids: %s. Accepted trips: %s", len(service_ids), len(accepted_trips))
    tt = create_timetable(accepted_trips)
    parents = load_stops(tt)
    build_footpaths(tt, parents)

    n_trips = sum(len(r.trips) for r in tt.routes.values())
    n_fp = sum(len(v) for v in tt.footpaths.values())
    log.info("%d stops, %d routes, %d trips (%.1f trips/route)",
             len(tt.stops), len(tt.routes), n_trips, n_trips / max(1, len(tt.routes)))
    log.info("%d coords, %d footpath edges", len(tt.coords), n_fp)
    log.info("built in %.2fs", time.perf_counter() - t0)
    return close_footpaths(tt)
