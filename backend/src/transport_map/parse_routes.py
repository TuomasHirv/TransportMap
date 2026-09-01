import csv
import logging
from itertools import groupby

from .config import STOP_TIMES_PATH
from .shared_func import parse_time

log = logging.getLogger("uvicorn.error")


def parse_routes(reader, ARR, DEP, STOP, TRIP):
    """Groups the stops in to a dict of a list of tuples.
    KEY: trip_id = [(arrival_time, departure_time, stop_id), ... for all stops]
    Also filters by the accepted trips which we got from calendar."""
    trips = [
    (tid, [(parse_time(r[ARR]), parse_time(r[DEP]), r[STOP])
           for r in group])
    for tid, group in groupby(reader, key=lambda r: r[TRIP])
    ]
    log.info("%s amount of trips", len(trips))
    return trips

def parse_routes_to_trips():
    """Reads the given file and returns the patterns of trips"""
    with open(STOP_TIMES_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}

        ARR, DEP, STOP, TRIP = (cols[c] for c in (
            "arrival_time", 
            "departure_time", 
            "stop_id", 
            "trip_id"))

        trips = parse_routes(reader, ARR, DEP, STOP, TRIP)
        return trips


