import csv
from collections import defaultdict
from itertools import groupby

from transport_map.models import Timetable

stop_times_file_path = "fakeStopTimes.csv"



def parse_time(unprocessed_time):
    """Parses a time string that is given to it to seconds INT."""
    time_list = unprocessed_time.split(":")
    # time_list is 0: hours 1: minutes 2: seconds STRING
    time_seconds = (int(time_list[0])*3600) + (int(time_list[1])*60) + int(time_list[2])
    return(time_seconds)

def parse_routes(ARR, DEP, STOP, TRIP, reader):
    """Groups the stops in to a dict of a list of tuples.
    KEY: trip_id = [(arrival_time, departure_time, stop_id), ... for all stops]"""
    trips = [
    (tid, [(parse_time(r[ARR]), parse_time(r[DEP]), r[STOP])
           for r in group])
    for tid, group in groupby(reader, key=lambda r: r[TRIP])
    ]
    return trips

def build_patterns(trips):
    patterns = defaultdict(list)
    for trip_id, events in trips:
        seq = tuple(e[2] for e in events)
        stoptimes = [(a, d) for a, d, _ in events]
        patterns[seq].append((trip_id, stoptimes))
    return patterns

def split_overtaking(n_stops, trips):
    """Partition a pattern's trips into maximal non-overtaking groups."""
    trips = sorted(trips, key=lambda t: t[1][0][1])
    groups = []
    for trip_id, st in trips:
        for g in groups:
            last = g[-1][1]
            if all(last[i][0] <= st[i][0] and last[i][1] <= st[i][1]
                   for i in range(n_stops)):
                g.append((trip_id, st))
                break
        else:
            groups.append([(trip_id, st)])
    return groups


def finalize_timetable(patterns):
    tt = Timetable()
    trip_index = {}
    n = 0
    for seq, pattern_trips in patterns.items():
        for group in split_overtaking(len(seq), pattern_trips):
            rid = f"r{n}"
            n += 1
            tt.add_route(rid, seq, [st for _, st in group])
            for i, (trip_id, _) in enumerate(group):
                trip_index[(rid, i)] = trip_id
    tt.finalize()
    return tt

def create_timetable ():
    """Reads the given file and returns the patterns of trips"""
    with open(stop_times_file_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        cols = {name: i for i, name in enumerate(next(reader))}

        ARR, DEP, STOP, TRIP = (cols[c] for c in (
            "arrival_time", 
            "departure_time", 
            "stop_id", 
            "trip_id"))

        trips = parse_routes(ARR, DEP, STOP, TRIP, reader)
        patterns = build_patterns(trips)
        tt = finalize_timetable(patterns)
        return tt




