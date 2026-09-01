import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .build_datamodel import build_datamodel
from .config import CALENDAR_PATH, LAND_GEOJSON, STOP_TIMES_PATH, STOPS_PATH, TRIPS_PATH
from .draw_isochrone import build_bands, to_geojson
from .load_geojson import load_land
from .models import Timetable
from .parse_footpaths import load_stops
from .parse_routes import parse_routes_to_trips
from .raptor import reachable

log = logging.getLogger("uvicorn.error")


DayType = Literal["weekday", "saturday", "sunday"]
TIMETABLES: dict[str, Timetable] = {}

Geography = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Loading land.geojson from: %s", LAND_GEOJSON)
    global Geography
    Geography = load_land()
    log.info("Building datamodel from %s %s %s %s", 
             STOPS_PATH, 
             STOP_TIMES_PATH, 
             CALENDAR_PATH, 
             TRIPS_PATH)
    t0 = time.perf_counter()
    all_trips = parse_routes_to_trips()
    parents, stop_names, coords = load_stops()
    log.info("Read in %.2fs", time.perf_counter() - t0)
    for day in ["weekday", "saturday", "sunday"]:
        log.info("Building for: %s", day)
        TIMETABLES[day] = build_datamodel(all_trips, parents, stop_names, coords, day)
        log.info("loaded %d stops, %d routes", 
                 len(TIMETABLES[day].stops), 
                 len(TIMETABLES[day].routes))
    yield

app = FastAPI(title="Transport Map", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

def get_timetable(day: DayType = "weekday") -> Timetable:
    if not TIMETABLES:
        raise HTTPException(503, "timetables not loaded")
    return TIMETABLES[day]

Timetabledep = Annotated[Timetable, Depends(get_timetable)]


@app.get("/reachable")
def reachable_endpoint(tt: Timetabledep, lat: float, lon: float, at: int, budget: int = 1800):
    """Stops reachable from (lat, lon) departing at `at`, within `budget` seconds."""
    print("reachable called latitude:", lat, "And longitude:", lon, "Time:", at, "Budget", budget)
    if not 0 <= at < 30 * 3600:
        raise HTTPException(422, "at must be seconds after midnight")
    if budget <= 0:
        raise HTTPException(422, "budget must be positive")

    result = reachable(tt, (lat, lon), at, budget)
    return [
        {"stop_name": name, "lat": tt.coords[s][0], "lon": tt.coords[s][1],
         "seconds_left": left, "arrival": at + budget - left}
        for s, left, name in result
    ]

@app.get("/isochrone")
def isochrone(tt: Timetabledep, lat: float, lon: float, at: int, budget: int = 1800):
    if not 0 <= at < 30 * 3600:
        raise HTTPException(422, "at must be seconds after midnight")
    if budget <= 0:
        raise HTTPException(422, "budget must be positive")

    result = reachable(tt, (lat, lon), at, budget)
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

    log.info("Creating geojson")
    t0 = time.perf_counter()
    geojson = to_geojson(build_bands(isochrone_stops, Geography, thresholds))
    log.info("%d stops -> geojson in %.2fs", len(stops), time.perf_counter() - t0)
    
    return {"stops": stops, "bands": geojson}
