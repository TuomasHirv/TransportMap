import csv
from datetime import date

from .config import CALENDAR_PATH, TRIPS_PATH

DAY_FLAG = {"weekday": "wednesday", "saturday": "saturday", "sunday": "sunday"}

def service_id_for_day(day_type, on=None):
    filter = DAY_FLAG[day_type]
    ymd = (on or date.today()).strftime("%Y%m%d")

    service_ids = set()
    with open(CALENDAR_PATH, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r[filter].strip() != "1":
                continue
            if not (r["start_date"].strip() <= ymd <= r["end_date"].strip()):
                continue
            service_ids.add(r["service_id"].strip())
    return service_ids


def trips_from_services(service_ids):
    with open(TRIPS_PATH, newline="", encoding="utf-8-sig") as fh:
        return {r["trip_id"].strip() for r in csv.DictReader(fh)
                if r["service_id"].strip() in service_ids}
