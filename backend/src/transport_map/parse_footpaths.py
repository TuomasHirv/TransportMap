import csv

from .config import STOPS_PATH


def load_stops():
    """-> {stop_id: (lat, lon)}, {stop_id: parent_station}, skipping stations."""
    parents = {}
    stop_names = {}
    coords = {}
    with open(STOPS_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            sid = r["stop_id"].strip()
            if r["location_type"].strip() == "1":
                continue                       # a station, not a boarding point
            stop_names[sid] = r["stop_name"]
            coords[sid] = (float(r["stop_lat"]), float(r["stop_lon"]))
            parent = r.get("parent_station", "").strip()
            if parent:
                parents[sid] = parent
    return parents, stop_names, coords