"""Tier 2 -- parse_routes_to_trips(): stop_times.csv -> [(trip_id, [(arr, dep, stop)])]."""

from transport_map import parse_routes
from transport_map.parse_routes import parse_routes_to_trips


class TestParseRoutesToTrips:
    def test_trip_count(self, raw_trips):
        assert len(raw_trips) == 23

    def test_trip_ids_are_unique(self, raw_trips):
        """Each trip appears once, which only holds while the file stays grouped."""
        ids = [tid for tid, _ in raw_trips]
        assert len(set(ids)) == len(ids)

    def test_bom_is_stripped_from_the_header(self, raw_trips):
        """stop_times.csv starts with a UTF-8 BOM, exactly like the real feed."""
        ids = {tid for tid, _ in raw_trips}
        assert "A_0800" in ids
        assert not any(tid.startswith("﻿") for tid in ids)

    def test_events_are_arrival_departure_stop(self, raw_trips):
        events = dict(raw_trips)["A_0800"]
        assert events == [
            (28800, 28800, "A1"),
            (29040, 29040, "A2"),
            (29280, 29280, "HUB_N"),
            (29520, 29520, "A3"),
            (29760, 29760, "A4"),
        ]

    def test_times_are_parsed_to_integer_seconds(self, raw_trips):
        for arr, dep, stop in dict(raw_trips)["A_0800"]:
            assert isinstance(arr, int) and isinstance(dep, int)
            assert isinstance(stop, str)

    def test_events_keep_stop_sequence_order(self, raw_trips):
        stops = [s for _, _, s in dict(raw_trips)["A_R_0800"]]
        assert stops == ["A4", "A3", "HUB_N", "A2", "A1"]

    def test_after_midnight_times_exceed_a_day(self, raw_trips):
        """The night trips are what make the prev-day carry-over detectable."""
        assert dict(raw_trips)["A_2350_WED"][-1][0] == 86760
        assert dict(raw_trips)["C_2350_TUE"][-1][0] == 88500

    def test_loop_trip_repeats_a_stop(self, raw_trips):
        stops = [s for _, _, s in dict(raw_trips)["L_0800"]]
        assert stops == ["L1", "L2", "L3", "L2", "L1"]

    def test_reads_trips_of_differing_lengths(self, raw_trips):
        lengths = {tid: len(ev) for tid, ev in raw_trips}
        assert lengths["D_0800"] == 2
        assert lengths["F_0833"] == 3
        assert lengths["B_0810"] == 4
        assert lengths["A_0800"] == 5


class TestContiguityRequirement:
    def test_interleaved_rows_fragment_silently(self, unsorted_dir):
        """groupby only groups *adjacent* rows. A feed whose trips are interleaved
        parses into one group per row with no error at all -- this is why the real
        stop_times.csv must stay sorted by trip_id."""
        trips = parse_routes_to_trips(unsorted_dir / "stop_times.csv")
        assert len(trips) == 10
        assert all(len(events) == 1 for _, events in trips)
        assert [tid for tid, _ in trips[:4]] == ["A_0800", "A_0805", "A_0800", "A_0805"]

    def test_the_same_two_trips_parse_correctly_when_grouped(self, raw_trips):
        by_id = dict(raw_trips)
        assert len(by_id["A_0800"]) == 5
        assert len(by_id["A_0805"]) == 5


class TestPathArgument:
    def test_explicit_path_is_used(self, network_dir):
        assert len(parse_routes_to_trips(network_dir / "stop_times.csv")) == 23

    def test_falls_back_to_the_module_constant(self, monkeypatch, network_dir):
        monkeypatch.setattr(parse_routes, "STOP_TIMES_PATH", network_dir / "stop_times.csv")
        assert len(parse_routes_to_trips()) == 23
