import csv

from .config import STOP_TIMES_PATH, STOPS_PATH


def create_parents_stopnames_coords():
    parents = {}
    stop_names = {}
    coords = {}
    with open(STOPS_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            sid = r["stop_id"].strip()
            if r["location_type"].strip() == "1":
                continue                       # a station, not a boarding point
            stop_names[sid] = r["stop_name"].strip()
            coords[sid] = (float(r["stop_lat"]), float(r["stop_lon"]))
            parent = r.get("parent_station", "").strip()
            if parent:
                parents[sid] = parent
    return {parents: parents, stop_names: stop_names, coords:coords}

def create_stops():
    stops = set()
    with open(STOP_TIMES_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}
        stops.add(cols[c] for c in ("stop_id"))
    return stops
