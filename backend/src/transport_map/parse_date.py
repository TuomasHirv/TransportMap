import csv
from datetime import date

from .config import CALENDAR_PATH, TRIPS_PATH

DAY_FLAG = {"weekday": "wednesday", "saturday": "saturday", "sunday": "sunday"}
PREV_DAY_FLAG = {"weekday": "tuesday", "saturday": "friday", "sunday": "saturday"}
def service_id_for_day(day_type, on=None):
    filter = DAY_FLAG[day_type]
    prev_filter = PREV_DAY_FLAG[day_type]
    ymd = (on or date.today()).strftime("%Y%m%d")

    service_ids = set()
    prev_day_service_ids = set()
    with open(CALENDAR_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not (r["start_date"].strip() <= ymd <= r["end_date"].strip()):
                continue
            if r[filter].strip() == "1":
                service_ids.add(r["service_id"].strip())
                continue
            if r[prev_filter].strip() == "1":
                prev_day_service_ids.add(r["service_id"].strip())
    return service_ids, prev_day_service_ids


def trips_from_services(service_ids, prev_day_service_ids):
    with open(TRIPS_PATH, newline="", encoding="utf-8-sig") as fh:
        accepted_trips = set()
        prev_accepted_trips = set()
        for r in csv.DictReader(fh):
            if r["service_id"].strip() in service_ids:
                accepted_trips.add(r["trip_id"].strip())
                continue
            if r["service_id"].strip() in prev_day_service_ids:
                prev_accepted_trips.add(r["trip_id"].strip())
        return accepted_trips, prev_accepted_trips
