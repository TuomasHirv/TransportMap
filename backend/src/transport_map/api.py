import gc
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .build_datamodel import build_datamodel
from .config import (
    CALENDAR_PATH,
    LAND_GEOJSON,
    NAMES_PATH,
    STOP_TIMES_PATH,
    STOPS_PATH,
    TRIPS_PATH,
)
from .draw_isochrone import build_bands, to_geojson
from .load_geojson import load_land
from .models import Timetable
from .nearby_routes import lines_nearby
from .parse_date import filter_out_monday_thursday
from .parse_footpaths import load_stops
from .parse_names import routename_to_shortname, tripname_to_shortname
from .parse_routes import parse_routes_to_trips
from .raptor import reachable

log = logging.getLogger("uvicorn.error")


DayType = Literal["weekday", "saturday", "sunday"]
TIMETABLES: dict[str, Timetable] = {}

Geography = None

import resource

def mem(label):
    try:
        rss = 0
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) / 1000      # kB -> MB
                    break
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
        log.info("MEM %-22s rss %6.1f MB | peak %6.1f MB", label, rss, peak)
    except Exception as exc:
        log.warning("MEM %s unavailable: %s", label, exc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Loading land.geojson from: %s", Path(*LAND_GEOJSON.parts[-3:]))
    global Geography
    mem("start")
    Geography = load_land()
    mem("Geography loaded")
    log.info("Building datamodel from %s, %s, %s, %s, %s",
             Path(*STOPS_PATH.parts[-3:]),
             Path(*STOP_TIMES_PATH.parts[-3:]),
             Path(*CALENDAR_PATH.parts[-3:]),
             Path(*TRIPS_PATH.parts[-3:]),
             Path(*NAMES_PATH.parts[-3:])
             )
    t0 = time.perf_counter()
    #Loading data that isn't affected by day type
    #all_trips contains Arrival-, Departure time and the stop in question.
    #routename_shortname is a dict of route_id to shortname of the transportation.
    #parents has stop_id -> parent_id
    #stop_names has stop_id -> stop_name.
    #coords has stop_id -> (lat, lon) of the stop.
    allowed_trips, prev_allowed_trips = filter_out_monday_thursday()
    mem("Day filters")
    log.info("tid not in monday or thursday: %s", len(allowed_trips))
    all_trips = parse_routes_to_trips(allowed_trips, prev_allowed_trips)
    mem("Trips found")
    allowed_trips = None
    route_id_shortname = routename_to_shortname()
    mem("Route id shortnames")
    log.info("route_id -> shortname lenght: %s", len(route_id_shortname))
    keep = {tid for tid, _ in all_trips}
    trip_id_shortname = tripname_to_shortname(route_id_shortname, keep)
    route_id_shortname = None
    keep = None
    gc.collect()
    mem("trip id shortnames")
    log.info("trip_id -> shortname lenght: %s", len(trip_id_shortname))
    parents, stop_names, coords = load_stops()
    mem("load_stops")

    log.info("Read in %.2fs", time.perf_counter() - t0)
    for day in ["weekday", "saturday", "sunday"]:
        log.info("Building for: %s", day)
        TIMETABLES[day] = build_datamodel(all_trips, parents, stop_names, coords,
                                          trip_id_shortname, day)
        mem(day)
        log.info("loaded %d stops, %d routes", 
                 len(TIMETABLES[day].stops), 
                 len(TIMETABLES[day].routes))
    mem("TTs built")
    all_trips = None
    route_id_shortname = None
    trip_id_shortname = None
    gc.collect()
    mem("End")
    yield

app = FastAPI(title="Transport Map", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

def get_timetable(day: DayType = "weekday") -> Timetable:
    if not TIMETABLES:
        raise HTTPException(503, "timetables not loaded")
    return TIMETABLES[day]

Timetabledep = Annotated[Timetable, Depends(get_timetable)]


@app.get("/isochrone")
def isochrone(tt: Timetabledep, lat: float, lon: float, at: int,
              budget: int = 1800, max_rounds: int = 8):
    if not 0 <= at < 30 * 3600:
        raise HTTPException(422, "at must be seconds after midnight")
    if budget <= 0:
        raise HTTPException(422, "budget must be positive")
    log.info("isochrone called with max_rounds: %s", max_rounds)
    result, walkable_stops = reachable(tt, (lat, lon), at, budget, max_rounds)
    stops = []
    isochrone_stops = []
    for s, left, name in result:
        stops.append(
            {"stop_name": name, 
            "lat": tt.coords[s][0], 
            "lon": tt.coords[s][1],
            "seconds_left": left, 
            "arrival": at + budget - left
            })
        isochrone_stops.append((
            tt.coords[s][0],
            tt.coords[s][1],
            budget - left
        ))
    thresholds = tuple(t for t in (600, 1200, 1800) if t <= budget) or (budget,)


    nearby_routes = lines_nearby(tt, walkable_stops, at, at + 900)
    log.info("nearby_routes: %s", nearby_routes)
    for key in nearby_routes:
        log.info("This route %s leaves at %s", key, nearby_routes[key])
    log.info("Creating geojson")
    t0 = time.perf_counter()
    geojson = to_geojson(build_bands(isochrone_stops, Geography, thresholds))
    log.info("%d stops -> geojson in %.2fs", len(stops), time.perf_counter() - t0)
    
    return {"stops": stops, "bands": geojson, "upcoming": nearby_routes}
