import csv
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from sys import intern
import sys
import shutil


DAY_IN_SECONDS = 86400

# Most of this file is reused functions from the main system.
# Its aim is to filter out the data that isn't needed in trips.txt and stop_times.txt
# It also renames the curled files into .csv from .txt


def parse_time(unprocessed_time):
    """Parses a time string that is given to it to seconds INT."""
    time_list = unprocessed_time.split(":")
    # time_list is 0: hours 1: minutes 2: seconds STRING
    time_seconds = (int(time_list[0])*3600) + (int(time_list[1])*60) + int(time_list[2])
    return(time_seconds)


def trips_from_services(service_ids, prev_day_service_ids, path=None):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        accepted_trips = set()
        prev_accepted_trips = set()
        for r in csv.DictReader(fh):
            if r["service_id"].strip() in service_ids:
                accepted_trips.add(r["trip_id"].strip())
                continue
            if r["service_id"].strip() in prev_day_service_ids:
                prev_accepted_trips.add(r["trip_id"].strip())
        return accepted_trips, prev_accepted_trips

def filter_out_monday_thursday(path=None, trips_path=None):
    """Trips worth reading from stop_times.csv: those on a service running inside the
    calendar window on one of the five days the three day types consult. Monday and
    Thursday are the two that are never needed, hence the name."""
    filter = ["wednesday",  "saturday", "sunday"]
    prev_filter = ["tuesday", "friday"]

    service_ids = set()
    prev_service_ids = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            for day in filter:
                if r[day].strip() == "1":
                    service_ids.add(r["service_id"].strip())
                    continue
            for prev_day in prev_filter:
                if r[prev_day].strip() == "1":
                        prev_service_ids.add(r["service_id"].strip())
                        continue
    filtered_trips, prev_accepted_trips = trips_from_services(service_ids, prev_service_ids, trips_path)
    return filtered_trips, prev_accepted_trips


def parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips, prev_allowed_trips):
    """Groups the stops into a list of (trip_id, stops) tuples.
    (trip_id, ((arrival_time, departure_time, stop_id), ... for all stops))
    Trips in allowed_trips are kept whole; trips only in prev_allowed_trips
    are kept only if they run past midnight."""
    to_time = lru_cache(maxsize=None)(parse_time)
    trips = set()
    night = 0

    for tid, group in groupby(reader, key=lambda r: r[TRIP]):
        full = tid in allowed_trips
        if not full and tid not in prev_allowed_trips:
            continue

        events = tuple((to_time(r[ARR]), to_time(r[DEP]), intern(r[STOP]))
                       for r in group)

        if full:
            trips.add(tid)
        elif events[-1][0] >= DAY_IN_SECONDS:
            trips.add(tid)
            night += 1
    print("Night trips added:", night)
    print("Trips added:", len(trips))
    return trips

def parse_routes_to_trips(allowed_trips: set, prev_allowed_trips: set, path=None):
    """Reads the given file and returns the patterns of trips"""
    with open(path , newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}

        ARR, DEP, STOP, TRIP = (cols[c] for c in (
            "arrival_time", 
            "departure_time", 
            "stop_id", 
            "trip_id"))

        trips = parse_routes(reader, ARR, DEP, STOP, TRIP, allowed_trips, prev_allowed_trips)
        return trips


STOP_TIMES = "stop_times"
CALENDAR   = "calendar"
TRIPS      = "trips"
STOPS      = "stops"
ROUTES     = "routes"


def trim_feed(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    print("Started feeding with src and dst :", src, dst)
    filtered_trips, prev_accepted_trips = filter_out_monday_thursday(src / f"{CALENDAR}.txt", src / f"{TRIPS}.txt")
    keep = parse_routes_to_trips(filtered_trips, prev_accepted_trips, src / f"{STOP_TIMES}.txt")
    print("Amount of kept trip_ids", len(keep))
    with open(src / f"{STOP_TIMES}.txt", newline="", encoding="utf-8-sig") as fin, \
        open(dst/ f"{STOP_TIMES}.csv", "w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)

        header = next(reader)
        writer.writerow(header)
        TRIP = header.index("trip_id")

        for row in reader:
            if row[TRIP] not in keep:
                continue
            writer.writerow(row)
    print("stop_times.csv written")
    with open(src / f"{TRIPS}.txt", newline="", encoding="utf-8-sig") as fin, \
        open(dst / f"{TRIPS}.csv", "w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)

        header = next(reader)
        writer.writerow(header)
        TRIP = header.index("trip_id")

        for row in reader:
            if row[TRIP] not in keep:
                continue
            writer.writerow(row)
    print("trips.csv written")
    shutil.copyfile(src / f"{CALENDAR}.txt", dst / f"{CALENDAR}.csv")
    shutil.copyfile(src / f"{ROUTES}.txt", dst / f"{ROUTES}.csv")
    shutil.copyfile(src / f"{STOPS}.txt", dst / f"{STOPS}.csv")
    print("Rest of the files have been copied with .csv")

if __name__ == "__main__":
    trim_feed(Path(sys.argv[1]), Path(sys.argv[2]))