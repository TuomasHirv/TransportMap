"""Tier 6 -- the FastAPI endpoint: wiring, validation and response shape.

/isochrone is the only endpoint; /reachable was removed once the frontend stopped
using it. The api_client fixture injects the fixture timetables and bypasses the app's
lifespan, so the real 982 MB feed is never touched.
"""

import pytest

from transport_map import api

# A1 at 08:00 with a 30 minute budget -- the reference journey from fixtures/README.md.
A1 = {"lat": 60.171, "lon": 24.918, "at": 28800, "budget": 1800}


class TestImportsCleanly:
    """Regression: api.py briefly did `import resource` at module scope, a Unix-only
    stdlib module, so importing the backend raised ModuleNotFoundError on Windows and
    the whole suite died at collection. CI runs on ubuntu and would not have caught it."""

    def test_the_api_module_imports_on_any_platform(self):
        import importlib

        assert importlib.import_module("transport_map.api") is api

    def test_no_platform_specific_stdlib_at_module_scope(self):
        """Checked statically so it fails on Linux CI too, not just where it breaks."""
        import ast
        import pathlib

        source = pathlib.Path(api.__file__).read_text(encoding="utf-8")
        top_level = {
            alias.name.split(".")[0]
            for node in ast.parse(source).body
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.parse(source).body
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
        }
        assert top_level.isdisjoint({"resource", "fcntl", "pwd", "grp", "termios"})


class TestStops:
    def test_returns_the_reference_journey(self, api_client):
        assert len(api_client.get("/isochrone", params=A1).json()["stops"]) == 15

    def test_stop_shape(self, api_client):
        stop = api_client.get("/isochrone", params=A1).json()["stops"][0]
        assert set(stop) == {"stop_name", "lat", "lon", "seconds_left", "arrival"}

    def test_arrival_is_consistent_with_seconds_left(self, api_client):
        for stop in api_client.get("/isochrone", params=A1).json()["stops"]:
            assert stop["arrival"] == A1["at"] + A1["budget"] - stop["seconds_left"]

    def test_coordinates_come_from_the_timetable(self, api_client):
        stops = api_client.get("/isochrone", params=A1).json()["stops"]
        by_name = {s["stop_name"]: s for s in stops}
        assert (by_name["Lambdaniemi"]["lat"], by_name["Lambdaniemi"]["lon"]) == (60.179, 24.965)

    def test_names_are_returned_not_ids(self, api_client):
        stops = api_client.get("/isochrone", params=A1).json()["stops"]
        names = {s["stop_name"] for s in stops}
        assert "Töölö, Keskus" in names
        assert "A1" not in names

    def test_seconds_left_is_within_the_budget(self, api_client):
        for stop in api_client.get("/isochrone", params=A1).json()["stops"]:
            assert 0 <= stop["seconds_left"] <= A1["budget"]

    def test_budget_defaults_to_half_an_hour(self, api_client):
        params = {k: v for k, v in A1.items() if k != "budget"}
        without = api_client.get("/isochrone", params=params).json()
        assert without["stops"] == api_client.get("/isochrone", params=A1).json()["stops"]


class TestUpcomingLines:
    """The `upcoming` field: lines catchable within 15 minutes of walking from here."""

    def test_is_present_in_every_response(self, api_client):
        assert "upcoming" in api_client.get("/isochrone", params=A1).json()

    def test_maps_line_name_to_departure_second(self, api_client):
        """From A1 at 08:00, line 1 (A_0800) departs at 08:00 exactly."""
        assert api_client.get("/isochrone", params=A1).json()["upcoming"] == {"1": 28800}

    def test_lists_every_line_within_walking_distance(self, api_client):
        """HUB_N can walk to HUB_S and B2 (line 2) as well as its own line 1."""
        hub = {**A1, "lat": 60.171, "lon": 24.940}
        assert api_client.get("/isochrone", params=hub).json()["upcoming"] == {
            "1": 28800 + 480,   # 08:08
            "2": 28800 + 780,   # 08:16
        }

    def test_keys_are_short_names_not_route_ids(self, api_client):
        upcoming = api_client.get("/isochrone", params=A1).json()["upcoming"]
        assert "1" in upcoming
        assert "A" not in upcoming

    def test_only_covers_the_next_fifteen_minutes(self, api_client):
        """The window is at + 900, independent of `budget`."""
        quiet = {**A1, "at": 28800 + 3600}  # 09:00, after the morning departures
        assert api_client.get("/isochrone", params=quiet).json()["upcoming"] == {}

    def test_the_window_does_not_widen_with_budget(self, api_client):
        small = api_client.get("/isochrone", params={**A1, "budget": 600}).json()
        large = api_client.get("/isochrone", params={**A1, "budget": 3600}).json()
        assert small["upcoming"] == large["upcoming"]

    def test_a_source_with_no_stops_nearby_has_none(self, api_client):
        offshore = {**A1, "lat": 59.0, "lon": 20.0}
        assert api_client.get("/isochrone", params=offshore).json()["upcoming"] == {}


class TestDaySelection:
    def test_defaults_to_weekday(self, api_client):
        default = api_client.get("/isochrone", params=A1).json()["stops"]
        weekday = api_client.get("/isochrone", params={**A1, "day": "weekday"}).json()["stops"]
        assert len(default) == len(weekday) == 15

    def test_saturday_uses_a_different_timetable(self, api_client):
        body = api_client.get("/isochrone", params={**A1, "day": "saturday"}).json()
        assert len(body["stops"]) == 1  # nothing runs at 08:00 on a Saturday
        assert body["upcoming"] == {}

    def test_saturday_at_its_own_rush_hour(self, api_client):
        params = {**A1, "at": 36000, "day": "saturday"}
        body = api_client.get("/isochrone", params=params).json()
        assert {s["stop_name"] for s in body["stops"]} >= {"Alfaranta", "Epsilonranta"}
        assert body["upcoming"] == {"1": 36000}  # A_1000_SAT at 10:00

    @pytest.mark.parametrize("day", ["weekday", "saturday", "sunday"])
    def test_every_declared_day_is_served(self, api_client, day):
        assert api_client.get("/isochrone", params={**A1, "day": day}).status_code == 200

    def test_an_unknown_day_is_rejected(self, api_client):
        response = api_client.get("/isochrone", params={**A1, "day": "caturday"})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", "day"]


class TestValidation:
    @pytest.mark.parametrize(
        ("params", "detail"),
        [
            ({"at": -1}, "at must be seconds after midnight"),
            ({"at": 108000}, "at must be seconds after midnight"),
            ({"budget": 0}, "budget must be positive"),
            ({"budget": -5}, "budget must be positive"),
        ],
    )
    def test_rejects_out_of_range_values(self, api_client, params, detail):
        response = api_client.get("/isochrone", params={**A1, **params})
        assert response.status_code == 422
        assert response.json()["detail"] == detail

    @pytest.mark.parametrize("at", [0, 107999])
    def test_accepts_the_edges_of_the_valid_window(self, api_client, at):
        """The window is 0 <= at < 30 h, which leaves room for after-midnight trips."""
        assert api_client.get("/isochrone", params={**A1, "at": at}).status_code == 200

    @pytest.mark.parametrize("missing", ["lat", "lon", "at"])
    def test_required_parameters(self, api_client, missing):
        params = {k: v for k, v in A1.items() if k != missing}
        response = api_client.get("/isochrone", params=params)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", missing]

    def test_non_numeric_coordinates_are_rejected(self, api_client):
        assert api_client.get("/isochrone", params={**A1, "lat": "north"}).status_code == 422

    def test_max_rounds_is_accepted(self, api_client):
        body = api_client.get("/isochrone", params={**A1, "max_rounds": 1}).json()
        assert len(body["stops"]) == 10  # one ride plus footpath relaxation

    def test_max_rounds_defaults_to_the_full_scan(self, api_client):
        default = api_client.get("/isochrone", params=A1).json()["stops"]
        explicit = api_client.get("/isochrone", params={**A1, "max_rounds": 8}).json()["stops"]
        assert default == explicit


class TestBands:
    @pytest.mark.parametrize(
        ("budget", "thresholds"),
        [
            (1800, [1800, 1200, 600]),
            (1200, [1200, 600]),
            (600, [600]),
            (3600, [1800, 1200, 600]),
        ],
    )
    def test_band_thresholds_follow_the_budget(self, api_client, budget, thresholds):
        body = api_client.get("/isochrone", params={**A1, "budget": budget}).json()
        assert [f["properties"]["max_seconds"] for f in body["bands"]["features"]] == thresholds

    def test_a_budget_below_the_smallest_threshold_falls_back_to_itself(self, api_client):
        """thresholds = (...) or (budget,) -- a 5 minute budget gets a single 300 s band."""
        body = api_client.get("/isochrone", params={**A1, "budget": 300}).json()
        assert [f["properties"]["max_seconds"] for f in body["bands"]["features"]] == [300]

    def test_bands_are_valid_geojson(self, api_client):
        bands = api_client.get("/isochrone", params=A1).json()["bands"]
        assert bands["type"] == "FeatureCollection"
        for feature in bands["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "MultiPolygon"


class TestSourceWithNothingNearby:
    """Regression: reachable()'s early return used to be a bare {} while the success
    path returned a 2-tuple, so unpacking it made this 500. Any rural or offshore
    click hit that path."""

    OFFSHORE = {**A1, "lat": 59.0, "lon": 20.0}

    def test_answers_200_not_500(self, api_client):
        assert api_client.get("/isochrone", params=self.OFFSHORE).status_code == 200

    def test_every_field_is_present_and_empty(self, api_client):
        body = api_client.get("/isochrone", params=self.OFFSHORE).json()
        assert body == {
            "stops": [],
            "bands": {"type": "FeatureCollection", "features": []},
            "upcoming": {},
        }


class TestResponseEnvelope:
    def test_carries_exactly_three_fields(self, api_client):
        assert set(api_client.get("/isochrone", params=A1).json()) == {
            "stops",
            "bands",
            "upcoming",
        }

    def test_reachable_endpoint_is_gone(self, api_client):
        """Removed once the frontend moved to /isochrone; it had been 500ing anyway."""
        assert api_client.get("/reachable", params=A1).status_code == 404


class TestTimetableDependency:
    def test_503_before_the_timetables_are_built(self, api_client):
        """get_timetable guards against requests arriving during startup."""
        saved = dict(api.TIMETABLES)
        api.TIMETABLES.clear()
        try:
            response = api_client.get("/isochrone", params=A1)
            assert response.status_code == 503
            assert response.json() == {"detail": "timetables not loaded"}
        finally:
            api.TIMETABLES.update(saved)

    def test_recovers_once_they_are_loaded(self, api_client):
        assert api_client.get("/isochrone", params=A1).status_code == 200
