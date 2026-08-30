from contextlib import asynccontextmanager
from typing import Annotated
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
log = logging.getLogger("uvicorn.error")

from .models import Timetable
from .raptor import build_data_model, reachable

from .config import STOPS_PATH, STOP_TIMES_PATH
TT = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global TT
    log.info("Building data model from %s %s", STOPS_PATH, STOP_TIMES_PATH)
    TT = build_data_model()
    log.info("loaded %d stops, %d routes", len(TT.stops), len(TT.routes))
    yield

app = FastAPI(title="Transport Map", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

def get_timetable():
    if TT is None:
        raise HTTPException(503, "timetable not loaded")
    return TT

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
        {"stop_id": s, "lat": tt.coords[s][0], "lon": tt.coords[s][1],
         "seconds_left": left, "arrival": at + budget - left}
        for s, left in result.items()
    ]