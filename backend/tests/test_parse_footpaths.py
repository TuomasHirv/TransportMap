"""Tier 2 -- load_stops(): stops.csv -> (parents, stop_names, coords)."""

import pytest

from transport_map import parse_footpaths
from transport_map.parse_footpaths import load_stops


class TestLoadStops:
    def test_returns_three_aligned_mappings(self, stops_data):
        parents, names, coords = stops_data
        assert set(names) == set(coords)
        assert set(parents) <= set(coords)

    def test_drops_station_rows(self, stops_data):
        """ST1 is location_type=1 -- a station, not a boarding point."""
        _, names, coords = stops_data
        assert "ST1" not in coords
        assert "ST1" not in names
        assert len(coords) == 29  # 30 rows in the file, one of them ST1

    def test_keeps_stops_no_trip_serves(self, stops_data):
        """load_stops reads geography only; whether a trip calls there is not its job."""
        _, _, coords = stops_data
        assert "Z1" in coords
        assert "X1" in coords

    def test_parents_only_for_rows_that_declare_one(self, stops_data):
        parents, _, _ = stops_data
        assert parents == {"P_A": "ST1", "P_B": "ST1"}

    def test_space_padded_parent_is_not_a_parent(self, stops_data):
        """Most rows carry a single space in parent_station, exactly like the real feed."""
        parents, _, _ = stops_data
        assert "A1" not in parents
        assert " " not in parents.values()

    def test_coordinates_are_floats(self, stops_data):
        _, _, coords = stops_data
        lat, lon = coords["A1"]
        assert isinstance(lat, float) and isinstance(lon, float)
        assert (lat, lon) == (60.171, 24.918)

    @pytest.mark.parametrize(
        ("stop_id", "name"),
        [
            ("HUB_N", "Töölö, Keskus"),
            ("B3", "Ääninen"),
            ("HUB_S", "Keskus, etelä"),
            ("P_A", "Myy-asema, laituri 1"),
        ],
    )
    def test_names_survive_quoting_and_utf8(self, stops_data, stop_id, name):
        """Names contain commas (so they are quoted) and Finnish umlauts."""
        _, names, _ = stops_data
        assert names[stop_id] == name

    def test_every_fixture_line_is_present(self, stops_data):
        _, _, coords = stops_data
        assert {"A1", "B1", "C1", "D1", "E1", "F1", "W1", "L1"} <= set(coords)


class TestPathArgument:
    def test_explicit_path_is_used(self, network_dir):
        _, _, coords = load_stops(network_dir / "stops.csv")
        assert len(coords) == 29

    def test_falls_back_to_the_module_constant(self, monkeypatch, network_dir):
        """The constant is imported by value, so patch it on parse_footpaths itself --
        patching config.STOPS_PATH would have no effect."""
        monkeypatch.setattr(parse_footpaths, "STOPS_PATH", network_dir / "stops.csv")
        _, _, coords = load_stops()
        assert len(coords) == 29
