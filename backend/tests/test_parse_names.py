"""Tier 2 -- routes.csv -> the short names shown on the map.

Two hops: route_id -> route_short_name from routes.csv, then trip_id -> short_name by
joining through trips.csv. `finalize_timetable` uses the second one to name each Route.
"""

import pytest

from transport_map import parse_names
from transport_map.parse_names import routename_to_shortname, tripname_to_shortname


@pytest.fixture
def routes_csv(network_dir):
    return network_dir / "routes.csv"


@pytest.fixture
def trips_csv(network_dir):
    return network_dir / "trips.csv"


class TestRouteNameToShortName:
    def test_maps_every_row(self, route_shortnames):
        assert route_shortnames == {
            "A": "1",
            "B": "2",
            "C": "3",
            "D": "4H",
            "E": "4H",
            "F": "5",
            "L": "6",
        }

    def test_a_route_absent_from_the_file_is_simply_missing(self, route_shortnames):
        """Line W has trips but no routes.csv row -- the feed is allowed to be sparse."""
        assert "W" not in route_shortnames

    def test_two_route_ids_may_share_a_short_name(self, route_shortnames):
        """The real feed does this too (it duplicates "H"), so anything keyed on the
        short name merges the two lines."""
        assert route_shortnames["D"] == route_shortnames["E"] == "4H"

    def test_values_are_stripped_strings(self, route_shortnames):
        assert all(v == v.strip() and isinstance(v, str) for v in route_shortnames.values())

    def test_quoted_long_names_containing_commas_do_not_shift_columns(self, routes_csv):
        """Line D's long name is "Nyytori - Myy-asema, laituri 1" -- an unquoted parser
        would read "4H" out of the wrong field."""
        assert routename_to_shortname(routes_csv)["D"] == "4H"


class TestTripNameToShortName:
    def test_joins_trips_to_their_line(self, trip_shortnames):
        assert trip_shortnames["A_0800"] == "1"
        assert trip_shortnames["B_0810"] == "2"
        assert trip_shortnames["F_0833"] == "5"

    def test_every_trip_of_a_line_gets_the_same_name(self, trip_shortnames):
        a_trips = {k: v for k, v in trip_shortnames.items() if k.startswith("A_")}
        assert len(a_trips) == 11
        assert set(a_trips.values()) == {"1"}

    def test_drops_trips_whose_route_is_not_in_routes_csv(self, trip_shortnames):
        """W_0800 is a real trip, but line W has no routes.csv row, so the join skips
        it and its Route ends up with an empty short_name."""
        assert "W_0800" not in trip_shortnames
        assert len(trip_shortnames) == 23  # 24 trips in the feed, minus W_0800

    def test_night_trips_are_included(self, trip_shortnames):
        """Prev-day trips keep their original trip_id precisely so this lookup hits."""
        assert trip_shortnames["C_2350_TUE"] == "3"
        assert trip_shortnames["B_2345_TUE"] == "2"

    def test_an_empty_mapping_drops_everything(self, trips_csv):
        assert tripname_to_shortname({}, trips_csv) == {}

    def test_unknown_route_ids_in_the_mapping_are_harmless(self, trips_csv):
        assert tripname_to_shortname({"NOPE": "9"}, trips_csv) == {}


class TestPathArguments:
    def test_explicit_paths_are_used(self, routes_csv, trips_csv):
        names = routename_to_shortname(routes_csv)
        assert len(tripname_to_shortname(names, trips_csv)) == 23

    def test_falls_back_to_the_module_constants(self, monkeypatch, routes_csv, trips_csv):
        """The constants are imported by value, so they must be patched on parse_names
        itself -- patching config.NAMES_PATH would have no effect."""
        monkeypatch.setattr(parse_names, "NAMES_PATH", routes_csv)
        monkeypatch.setattr(parse_names, "TRIPS_PATH", trips_csv)
        names = routename_to_shortname()
        assert len(names) == 7
        assert len(tripname_to_shortname(names)) == 23
