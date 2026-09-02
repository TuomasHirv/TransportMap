import csv

from .config import NAMES_PATH, TRIPS_PATH


def routename_to_shortname(path=None):
    """Returns a dict of key: route_id value: short_name"""
    returnable = {}
    with open(path or NAMES_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            returnable[r["route_id"].strip()] = r["route_short_name"].strip()
    return returnable


def tripname_to_shortname(routename_shortname: dict[str, str], path=None):
    with open(path or TRIPS_PATH, newline="", encoding="utf-8-sig") as fh:
        return {
            r["trip_id"].strip(): routename_shortname[r["route_id"].strip()]
            for r in csv.DictReader(fh)
            if r["route_id"].strip() in routename_shortname
        }