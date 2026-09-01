from pathlib import Path

# Anchored to the backend root so the app no longer has to be started from backend/.
DATA_DIR = Path(__file__).parent.parent.parent / "data"

STOPS_PATH = DATA_DIR / "stops.csv"
STOP_TIMES_PATH = DATA_DIR / "stop_times.csv"
CALENDAR_PATH = DATA_DIR / "calendar.csv"
TRIPS_PATH = DATA_DIR / "trips.csv"
LAND_GEOJSON = DATA_DIR / "land.geojson"


WALK_SPEED = 1.33
DETOUR_PRICE = 1.3
MAX_WALK_METERS = 400
MAX_WALK_METERS_START = 400
MAX_WALK_SECONDS = 600
