from contextlib import asynccontextmanager
from typing import Annotated, Literal
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
log = logging.getLogger("uvicorn.error")

from .models import Timetable
from .raptor import reachable
from .build_datamodel import build_data_model

from .config import STOPS_PATH, STOP_TIMES_PATH, CALENDAR_PATH,TRIPS_PATH

DayType = Literal["weekday", "saturday", "sunday"]
TIMETABLES: dict[str, Timetable] = {}

TT = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global TT
    log.info("Building datamodel from %s %s %s %s", STOPS_PATH, STOP_TIMES_PATH, CALENDAR_PATH, TRIPS_PATH)
    for day in ["weekday", "saturday", "sunday"]:
        log.info("Building for: %s", day)
        TIMETABLES[day] = build_data_model(day)
        log.info("loaded %d stops, %d routes", len(TIMETABLES[day].stops), len(TIMETABLES[day].routes))
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