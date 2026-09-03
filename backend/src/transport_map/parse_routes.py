import csv
import logging
from functools import lru_cache
from itertools import groupby
from sys import intern

from .config import STOP_TIMES_PATH
from .shared_func import parse_time

log = logging.getLogger("uvicorn.error")


def parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips):
    """Groups the stops into a list of (trip_id, stops) tuples.
    (trip_id, ((arrival_time, departure_time, stop_id), ... for all stops))
    Only trips whose id is in allowed_trips are kept; None keeps every trip."""
    to_time = lru_cache(maxsize=None)(parse_time)

    trips = [
        (tid, tuple((to_time(r[ARR]), to_time(r[DEP]), intern(r[STOP]))
                    for r in group))
        for tid, group in groupby(reader, key=lambda r: r[TRIP])
        if allowed_trips is None or tid in allowed_trips
    ]
    log.info("%s amount of trips, %s distinct times",
             len(trips), to_time.cache_info().currsize)
    return trips
def parse_routes_to_trips(allowed_trips: set = None, path=None):
    """Reads the given file and returns the patterns of trips"""
    with open(path or STOP_TIMES_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}

        ARR, DEP, STOP, TRIP = (cols[c] for c in (
            "arrival_time", 
            "departure_time", 
            "stop_id", 
            "trip_id"))

        trips = parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips)
        return trips


