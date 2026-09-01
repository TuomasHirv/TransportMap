"""Tier 6 -- the FastAPI endpoints: wiring, validation and response shape.

The api_client fixture injects the fixture timetables and bypasses the app's lifespan,
so the real 982 MB feed is never touched.
"""

import pytest

from transport_map import api

# A1 at 08:00 with a 30 minute budget -- the reference journey from fixtures/README.md.
A1 = {"lat": 60.171, "lon": 24.918, "at": 28800, "budget": 1800}


class TestReachable:
    def test_returns_the_reference_journey(self, api_client):
        body = api_client.get("/reachable", params=A1).json()
        assert len(body) == 15

    def test_response_shape(self, api_client):
        body = api_client.get("/reachable", params=A1).json()
        assert set(body[0]) == {"stop_name", "lat", "lon", "seconds_left", "arrival"}

    def test_arrival_is_consistent_with_seconds_left(self, api_client):
        for stop in api_client.get("/reachable", params=A1).json():
            assert stop["arrival"] == A1["at"] + A1["budget"] - stop["seconds_left"]

    def test_coordinates_come_from_the_timetable(self, api_client):
        by_name = {s["stop_name"]: s for s in api_client.get("/reachable", params=A1).json()}
        assert (by_name["Lambdaniemi"]["lat"], by_name["Lambdaniemi"]["lon"]) == (60.179, 24.965)

    def test_names_are_returned_not_ids(self, api_client):
        names = {s["stop_name"] for s in api_client.get("/reachable", params=A1).json()}
        assert "Töölö, Keskus" in names
        assert "A1" not in names

    def test_seconds_left_is_within_the_budget(self, api_client):
        for stop in api_client.get("/reachable", params=A1).json():
            assert 0 <= stop["seconds_left"] <= A1["budget"]

    def test_an_unreachable_source_returns_empty(self, api_client):
        body = api_client.get("/reachable", params={**A1, "lat": 59.0, "lon": 20.0}).json()
        assert body == []

    def test_budget_defaults_to_half_an_hour(self, api_client):
        params = {k: v for k, v in A1.items() if k != "budget"}
        without = api_client.get("/reachable", params=params)
        assert without.json() == api_client.get("/reachable", params=A1).json()


class TestDaySelection:
    def test_defaults_to_weekday(self, api_client):
        default = api_client.get("/reachable", params=A1).json()
        weekday = api_client.get("/reachable", params={**A1, "day": "weekday"}).json()
        assert len(default) == len(weekday) == 15

    def test_saturday_uses_a_different_timetable(self, api_client):
        saturday = api_client.get("/reachable", params={**A1, "day": "saturday"}).json()
        assert len(saturday) == 1  # nothing runs at 08:00 on a Saturday

    def test_saturday_at_its_own_rush_hour(self, api_client):
        body = api_client.get("/reachable", params={**A1, "at": 36000, "day": "saturday"}).json()
        assert {s["stop_name"] for s in body} >= {"Alfaranta", "Epsilonranta"}

    @pytest.mark.parametrize("day", ["weekday", "saturday", "sunday"])
    def test_every_declared_day_is_served(self, api_client, day):
        assert api_client.get("/reachable", params={**A1, "day": day}).status_code == 200

    def test_an_unknown_day_is_rejected(self, api_client):
        response = api_client.get("/reachable", params={**A1, "day": "caturday"})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", "day"]


class TestValidation:
    @pytest.mark.parametrize("endpoint", ["/reachable", "/isochrone"])
    @pytest.mark.parametrize(
        ("params", "detail"),
        [
            ({"at": -1}, "at must be seconds after midnight"),
            ({"at": 108000}, "at must be seconds after midnight"),
            ({"budget": 0}, "budget must be positive"),
            ({"budget": -5}, "budget must be positive"),
        ],
    )
    def test_rejects_out_of_range_values(self, api_client, endpoint, params, detail):
        response = api_client.get(endpoint, params={**A1, **params})
        assert response.status_code == 422
        assert response.json()["detail"] == detail

    @pytest.mark.parametrize("at", [0, 107999])
    def test_accepts_the_edges_of_the_valid_window(self, api_client, at):
        """The window is 0 <= at < 30 h, which leaves room for after-midnight trips."""
        assert api_client.get("/reachable", params={**A1, "at": at}).status_code == 200

    @pytest.mark.parametrize("missing", ["lat", "lon", "at"])
    def test_required_parameters(self, api_client, missing):
        params = {k: v for k, v in A1.items() if k != missing}
        response = api_client.get("/reachable", params=params)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", missing]

    def test_non_numeric_coordinates_are_rejected(self, api_client):
        assert api_client.get("/reachable", params={**A1, "lat": "north"}).status_code == 422


class TestIsochrone:
    def test_returns_stops_and_bands(self, api_client):
        body = api_client.get("/isochrone", params=A1).json()
        assert set(body) == {"stops", "bands"}
        assert len(body["stops"]) == 15

    def test_stops_match_the_reachable_endpoint(self, api_client):
        assert (
            api_client.get("/isochrone", params=A1).json()["stops"]
            == api_client.get("/reachable", params=A1).json()
        )

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

    def test_an_unreachable_source_returns_no_bands(self, api_client):
        body = api_client.get("/isochrone", params={**A1, "lat": 59.0, "lon": 20.0}).json()
        assert body["stops"] == []
        assert body["bands"]["features"] == []


class TestTimetableDependency:
    def test_503_before_the_timetables_are_built(self, api_client):
        """get_timetable guards against requests arriving during startup."""
        saved = dict(api.TIMETABLES)
        api.TIMETABLES.clear()
        try:
            response = api_client.get("/reachable", params=A1)
            assert response.status_code == 503
            assert response.json() == {"detail": "timetables not loaded"}
        finally:
            api.TIMETABLES.update(saved)

    def test_recovers_once_they_are_loaded(self, api_client):
        assert api_client.get("/reachable", params=A1).status_code == 200
