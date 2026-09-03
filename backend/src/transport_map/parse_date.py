import csv
from datetime import date

from .config import CALENDAR_PATH, TRIPS_PATH

DAY_FLAG = {"weekday": "wednesday", "saturday": "saturday", "sunday": "sunday"}
PREV_DAY_FLAG = {"weekday": "tuesday", "saturday": "friday", "sunday": "saturday"}

def service_id_for_day(day_type, path=None):
    filter = DAY_FLAG[day_type]
    prev_filter = PREV_DAY_FLAG[day_type]

    service_ids = set()
    prev_day_service_ids = set()
    with open(path or CALENDAR_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r[filter].strip() == "1":
                service_ids.add(r["service_id"].strip())
                continue
            if r[prev_filter].strip() == "1":
                prev_day_service_ids.add(r["service_id"].strip())
    return service_ids, prev_day_service_ids

def trips_from_services(service_ids, prev_day_service_ids, path=None):
    with open(path or TRIPS_PATH, newline="", encoding="utf-8-sig") as fh:
        accepted_trips = set()
        prev_accepted_trips = set()
        for r in csv.DictReader(fh):
            if r["service_id"].strip() in service_ids:
                accepted_trips.add(r["trip_id"].strip())
                continue
            if r["service_id"].strip() in prev_day_service_ids:
                prev_accepted_trips.add(r["trip_id"].strip())
        return accepted_trips, prev_accepted_trips

def filter_monday_thursday(on=None, path=None, trips_path=None):
    """Trips worth reading from stop_times.csv: those on a service running inside the
    calendar window on one of the five days the three day types consult. Monday and
    Thursday are the two that are never needed, hence the name."""
    filter = ["tuesday","wednesday", "friday", "saturday", "sunday"]
    ymd = (on or date.today()).strftime("%Y%m%d")

    service_ids = set()
    with open(path or CALENDAR_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not (r["start_date"].strip() <= ymd <= r["end_date"].strip()):
                continue
            for day in filter:
                if r[day].strip() == "1":
                    service_ids.add(r["service_id"].strip())
                    continue
    filtered_trips, _ = trips_from_services(service_ids, set(), trips_path)
    return filtered_trips
