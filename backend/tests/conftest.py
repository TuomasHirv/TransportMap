"""Shared pytest fixtures for the Transport-Map backend.

Everything here runs against the hand-built synthetic GTFS feed in
``fixtures/network/``.  Each stop and trip in that feed exists to pin one
specific behaviour -- see ``fixtures/README.md`` for the expected values and
how they were derived.
"""

from datetime import date
from pathlib import Path

import pytest

from transport_map.build_datamodel import build_datamodel
from transport_map.load_geojson import load_land
from transport_map.parse_footpaths import load_stops
from transport_map.parse_names import routename_to_shortname, tripname_to_shortname
from transport_map.parse_routes import parse_routes_to_trips

FIXTURES = Path(__file__).parent / "fixtures"
NETWORK = FIXTURES / "network"
UNSORTED = FIXTURES / "unsorted"

STOPS_CSV = NETWORK / "stops.csv"
STOP_TIMES_CSV = NETWORK / "stop_times.csv"
TRIPS_CSV = NETWORK / "trips.csv"
CALENDAR_CSV = NETWORK / "calendar.csv"
ROUTES_CSV = NETWORK / "routes.csv"
LAND_GEOJSON = NETWORK / "land.geojson"

# The fixture calendar is only valid 20260831..20261024.  Passing these dates as
# `on=` keeps assertions correct forever; without them build_datamodel falls back
# to date.today() and every trip silently disappears once the window passes.
REFERENCE_DATES = {
    "weekday": date(2026, 9, 2),    # Wednesday
    "saturday": date(2026, 9, 5),
    "sunday": date(2026, 9, 6),
}


@pytest.fixture(scope="session")
def network_dir():
    """Directory holding the synthetic feed (stops/stop_times/trips/calendar/land)."""
    return NETWORK


@pytest.fixture(scope="session")
def unsorted_dir():
    """Feed whose stop_times.csv interleaves two trips, breaking groupby contiguity."""
    return UNSORTED


@pytest.fixture(scope="session")
def reference_dates():
    """day_type -> the date the fixture calendar window is evaluated against."""
    return dict(REFERENCE_DATES)


@pytest.fixture(scope="session")
def stops_data():
    """(parents, stop_names, coords) -- the station row ST1 is already dropped."""
    return load_stops(STOPS_CSV)


@pytest.fixture(scope="session")
def raw_trips():
    """[(trip_id, [(arrival, departure, stop_id), ...]), ...], not yet day-filtered."""
    return parse_routes_to_trips(STOP_TIMES_CSV)


@pytest.fixture(scope="session")
def route_shortnames():
    """{route_id: route_short_name} straight from the fixture routes.csv."""
    return routename_to_shortname(ROUTES_CSV)


@pytest.fixture(scope="session")
def trip_shortnames(route_shortnames):
    """{trip_id: route_short_name}. Line W is absent -- it has no routes.csv row."""
    return tripname_to_shortname(route_shortnames, TRIPS_CSV)


@pytest.fixture(scope="session")
def build_timetable(raw_trips, stops_data, trip_shortnames):
    """Factory: ``build_timetable("saturday")`` -> a fresh Timetable for that day."""
    parents, stop_names, coords = stops_data

    def _build(day_type="weekday"):
        return build_datamodel(
            raw_trips, parents, stop_names, coords, trip_shortnames, day_type,
            on=REFERENCE_DATES[day_type],
            calendar_path=CALENDAR_CSV,
            trips_path=TRIPS_CSV,
        )

    return _build


@pytest.fixture(scope="session")
def weekday_tt(build_timetable):
    """Shared weekday Timetable. Treat as read-only; use build_timetable to mutate."""
    return build_timetable("weekday")


@pytest.fixture(scope="session")
def land():
    """Fixture land geometry, already projected to metres by load_land()."""
    return load_land(LAND_GEOJSON)


@pytest.fixture
def api_client(build_timetable, land):
    """TestClient wired to the fixture feed.

    TestClient is deliberately not used as a context manager, so the app's
    lifespan (which would read the real 982 MB feed) never runs; the module
    globals it would populate are injected here instead and restored after.
    """
    from fastapi.testclient import TestClient

    from transport_map import api

    saved_timetables, saved_geography = dict(api.TIMETABLES), api.Geography
    api.TIMETABLES.clear()
    for day in REFERENCE_DATES:
        api.TIMETABLES[day] = build_timetable(day)
    api.Geography = land
    try:
        yield TestClient(api.app)
    finally:
        api.TIMETABLES.clear()
        api.TIMETABLES.update(saved_timetables)
        api.Geography = saved_geography
