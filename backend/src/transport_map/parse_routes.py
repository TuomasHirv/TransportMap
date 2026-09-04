import csv
import logging
from functools import lru_cache
from itertools import groupby
from sys import intern

from .config import STOP_TIMES_PATH
from .shared_func import parse_time

log = logging.getLogger("uvicorn.error")

DAY_IN_SECONDS = 86400

def parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips, prev_allowed_trips):
    """Groups the stops into a list of (trip_id, stops) tuples.
    (trip_id, ((arrival_time, departure_time, stop_id), ... for all stops))
    Trips in allowed_trips are kept whole; trips only in prev_allowed_trips
    are kept only if they run past midnight."""
    to_time = lru_cache(maxsize=None)(parse_time)
    trips = []
    night = 0

    for tid, group in groupby(reader, key=lambda r: r[TRIP]):
        full = tid in allowed_trips
        if not full and tid not in prev_allowed_trips:
            continue

        events = tuple((to_time(r[ARR]), to_time(r[DEP]), intern(r[STOP]))
                       for r in group)

        if full:
            trips.append((tid, events))
        elif events[-1][0] >= DAY_IN_SECONDS:
            trips.append((tid, events))
            night += 1

    log.info("%s trips (%s prev-day night), %s distinct times",
             len(trips), night, to_time.cache_info().currsize)
    return trips

def parse_routes_to_trips(allowed_trips: set, prev_allowed_trips: set, path=None):
    """Reads the given file and returns the patterns of trips"""
    with open(path or STOP_TIMES_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}

        ARR, DEP, STOP, TRIP = (cols[c] for c in (
            "arrival_time", 
            "departure_time", 
            "stop_id", 
            "trip_id"))

        trips = parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips, prev_allowed_trips)
        return trips


