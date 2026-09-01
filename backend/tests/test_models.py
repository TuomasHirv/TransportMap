"""Tier 1 -- Route and Timetable as pure data structures.

Everything here builds its own Timetable by hand: no CSV, no fixtures. `earliest_trip`
and `positions` are the two primitives the RAPTOR scan leans on, so they are pinned
before anything that calls them.
"""

import pytest

from transport_map.models import Route, Timetable


def line(stops, trips):
    """A finalized single-route Timetable. trips are [(arrival, departure), ...]."""
    tt = Timetable()
    tt.add_route("r0", stops, trips)
    return tt.finalize()


class TestPositions:
    def test_each_stop_once(self):
        r = line(["S1", "S2", "S3"], [[(0, 0), (60, 60), (120, 120)]]).routes["r0"]
        assert r.positions("S1") == [0]
        assert r.positions("S2") == [1]
        assert r.positions("S3") == [2]

    def test_loop_route_reports_every_visit(self):
        """A route may call at the same stop twice; both indices must come back."""
        stops = ["L1", "L2", "L3", "L2", "L1"]
        r = line(stops, [[(0, 0), (60, 60), (120, 120), (180, 180), (240, 240)]]).routes["r0"]
        assert r.positions("L2") == [1, 3]
        assert r.positions("L1") == [0, 4]
        assert r.positions("L3") == [2]

    def test_unknown_stop_is_empty_not_an_error(self):
        r = line(["S1", "S2"], [[(0, 0), (60, 60)]]).routes["r0"]
        assert r.positions("NOPE") == []


class TestEarliestTrip:
    @pytest.fixture
    def route(self):
        # two trips departing S1 at t=10 and t=60
        return line(
            ["S1", "S2", "S3"],
            [[(0, 10), (100, 110), (200, 210)], [(50, 60), (150, 160), (250, 260)]],
        ).routes["r0"]

    def test_before_everything_picks_the_first_trip(self, route):
        assert route.earliest_trip(0, 0) == 0

    def test_exact_departure_is_catchable(self, route):
        """bisect_left: arriving exactly at the departure second still boards."""
        assert route.earliest_trip(0, 10) == 0
        assert route.earliest_trip(0, 60) == 1

    def test_one_second_late_takes_the_next_trip(self, route):
        assert route.earliest_trip(0, 11) == 1

    def test_after_the_last_departure_is_none(self, route):
        assert route.earliest_trip(0, 61) is None

    def test_uses_the_departures_at_that_position(self, route):
        """Position 1 departs at 110 and 160, not at 10 and 60."""
        assert route.earliest_trip(1, 111) == 1
        assert route.earliest_trip(1, 161) is None


class TestAddRoute:
    def test_rejects_a_trip_with_the_wrong_number_of_events(self):
        tt = Timetable()
        with pytest.raises(AssertionError, match="one event per route stop"):
            tt.add_route("r0", ["A", "B"], [[(0, 0)]])

    def test_registers_the_stops(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B"], [[(0, 0), (60, 60)]])
        assert tt.stops == {"A", "B"}

    def test_accepts_any_iterable_of_trips(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B"], iter([iter([(0, 0), (60, 60)])]))
        assert tt.routes["r0"].trips == [[(0, 0), (60, 60)]]


class TestFinalize:
    def test_sorts_trips_by_departure_from_the_first_stop(self):
        tt = line(
            ["A", "B"],
            [[(300, 300), (400, 400)], [(100, 100), (200, 200)], [(200, 200), (300, 300)]],
        )
        assert [t[0][1] for t in tt.routes["r0"].trips] == [100, 200, 300]

    def test_builds_the_departure_index_per_position(self):
        tt = line(["A", "B"], [[(0, 10), (100, 110)], [(50, 60), (150, 160)]])
        assert tt.routes["r0"]._deps == [[10, 60], [110, 160]]

    def test_indexes_routes_by_stop(self):
        tt = line(["A", "B", "C"], [[(0, 0), (60, 60), (120, 120)]])
        assert tt.routes_by_stop["B"] == [("r0", 1)]

    def test_a_loop_stop_is_indexed_at_every_position(self):
        tt = line(["A", "B", "A"], [[(0, 0), (60, 60), (120, 120)]])
        assert tt.routes_by_stop["A"] == [("r0", 0), ("r0", 2)]

    def test_adds_a_zero_cost_self_footpath(self):
        tt = line(["A", "B"], [[(0, 0), (60, 60)]])
        assert ("A", 0) in tt.footpaths["A"]
        assert ("B", 0) in tt.footpaths["B"]

    def test_does_not_duplicate_an_existing_self_footpath(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B"], [[(0, 0), (60, 60)]])
        tt.add_footpath("A", "A", 0, both=False)
        tt.finalize()
        assert tt.footpaths["A"].count(("A", 0)) == 1

    def test_is_idempotent(self):
        tt = line(["A", "B"], [[(0, 0), (60, 60)]])
        before = dict(tt.routes_by_stop)
        tt.finalize()
        assert dict(tt.routes_by_stop) == before

    def test_returns_self_for_chaining(self):
        tt = Timetable()
        tt.add_route("r0", ["A"], [[(0, 0)]])
        assert tt.finalize() is tt


class TestAddFootpath:
    def test_is_bidirectional_by_default(self):
        tt = Timetable()
        tt.add_footpath("A", "B", 120)
        assert ("B", 120) in tt.footpaths["A"]
        assert ("A", 120) in tt.footpaths["B"]

    def test_one_way_when_both_is_false(self):
        tt = Timetable()
        tt.add_footpath("A", "B", 120, both=False)
        assert ("B", 120) in tt.footpaths["A"]
        assert tt.footpaths["B"] == []

    def test_registers_both_endpoints_as_stops(self):
        tt = Timetable()
        tt.add_footpath("A", "B", 120)
        assert tt.stops == {"A", "B"}


class TestTimetableDefaults:
    def test_transfer_time_defaults_to_zero(self):
        """Nothing ever populates transfer_time, so every boarding penalty is 0."""
        assert Timetable().transfer_time["anything"] == 0

    def test_unknown_stop_has_no_footpaths(self):
        assert Timetable().footpaths["nowhere"] == []

    def test_a_bare_route_has_no_index_until_finalize(self):
        assert Route("r0", ["A", "B"]).positions("A") == []
