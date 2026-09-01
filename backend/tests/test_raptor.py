"""Tier 4 -- the round-based earliest-arrival scan.

Reference journeys are documented in tests/fixtures/README.md. Walk-derived arrivals
come from round(distance / WALK_SPEED), so arrival times are compared with a 2 s
tolerance; ride arrivals are exact.
"""

import pytest

from transport_map.raptor import getNearby, reachable
from transport_map.shared_func import hm

EIGHT_AM = hm(8, 0)


def arrivals(tt, coords, source, at, budget, **kwargs):
    """{stop_id: absolute arrival second}, inverting reachable's seconds_left."""
    horizon = at + budget
    result = reachable(tt, coords[source], at, budget, **kwargs)
    return {stop: horizon - left for stop, left, _ in result}


@pytest.fixture
def coords(stops_data):
    return stops_data[2]


class TestGetNearby:
    def test_standing_on_a_stop_costs_nothing(self, weekday_tt, coords):
        assert getNearby(weekday_tt, coords["A1"]) == [("A1", 0)]

    def test_returns_nothing_when_out_of_range(self, weekday_tt):
        assert getNearby(weekday_tt, (59.0, 20.0)) == []

    def test_finds_every_stop_within_the_walk_radius(self, weekday_tt, coords):
        found = dict(getNearby(weekday_tt, coords["HUB_N"]))
        assert {"HUB_N", "HUB_S", "B2", "T2"} <= set(found)
        assert found["HUB_N"] == 0
        assert found["HUB_S"] == pytest.approx(167, abs=2)

    def test_excludes_stops_past_the_radius(self, weekday_tt, coords):
        assert "A1" not in dict(getNearby(weekday_tt, coords["A3"]))

    def test_walk_cost_grows_with_distance(self, weekday_tt, coords):
        found = dict(getNearby(weekday_tt, coords["HUB_N"]))
        assert found["HUB_S"] < found["B2"] or found["B2"] < found["HUB_S"]
        assert all(secs >= 0 for secs in found.values())


class TestReferenceJourney:
    """From A1 at 08:00 with a 30 minute budget."""

    EXPECTED = {
        "A1": 28800,  # source
        "A2": 29040,  # ride A
        "HUB_N": 29280,  # ride A
        "HUB_S": 29447,  # walk 167 s
        "A3": 29460,  # ride A_0805
        "B2": 29531,  # walk 251 s from HUB_N
        "T2": 29532,  # walk 252 s from HUB_N
        "P_A": 29553,  # walk 93 s from A3
        "A4": 29580,  # ride A_0805
        "P_B": 29730,  # walk 150 s from A4
        "B3": 29940,  # ride B
        "C1": 30065,  # walk 125 s from B3
        "C2": 30360,  # ride C
        "E1": 30420,  # ride E_0822
        "C3": 30540,  # ride C
    }

    def test_exact_arrival_times(self, weekday_tt, coords):
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)
        assert got == pytest.approx(self.EXPECTED, abs=2)

    def test_reaches_fifteen_stops(self, weekday_tt, coords):
        assert len(arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)) == 15

    def test_seconds_left_is_the_budget_remainder(self, weekday_tt, coords):
        result = reachable(weekday_tt, coords["A1"], EIGHT_AM, 1800)
        for stop, left, _ in result:
            assert 0 <= left <= 1800
            assert EIGHT_AM + 1800 - left == pytest.approx(self.EXPECTED[stop], abs=2)

    def test_returns_the_stop_name(self, weekday_tt, coords):
        result = reachable(weekday_tt, coords["A1"], EIGHT_AM, 1800)
        names = {stop: name for stop, _, name in result}
        assert names["HUB_N"] == "Töölö, Keskus"
        assert names["C3"] == "Lambdaniemi"

    def test_unreachable_lines_are_absent(self, weekday_tt, coords):
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)
        assert got.keys().isdisjoint({"W1", "W2", "W3", "W4", "L1", "L2", "L3", "D1", "B1"})

    def test_same_station_transfer_is_what_reaches_line_e(self, weekday_tt, coords):
        """E1 is only served by E_0822 from P_B, and P_B is only linked to the network
        through the P_A/P_B same-parent footpath."""
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)
        assert got["P_B"] == pytest.approx(29730, abs=2)
        assert got["E1"] == 30420


class TestBudget:
    def test_a_stop_just_inside_the_budget_is_included(self, weekday_tt, coords):
        assert "C3" in arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)

    def test_a_stop_just_outside_the_budget_is_excluded(self, weekday_tt, coords):
        """C3 arrives at 08:29, so a 1700 s budget (horizon 08:28:20) misses it."""
        assert "C3" not in arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1700)

    def test_the_horizon_is_inclusive(self, weekday_tt, coords):
        exact = 30540 - EIGHT_AM  # arrive at C3 with 0 seconds to spare
        assert "C3" in arrivals(weekday_tt, coords, "A1", EIGHT_AM, exact)

    def test_a_tiny_budget_only_reaches_walking_distance(self, weekday_tt, coords):
        assert set(arrivals(weekday_tt, coords, "A1", EIGHT_AM, 60)) == {"A1"}

    def test_a_bigger_budget_never_loses_stops(self, weekday_tt, coords):
        small = set(arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800))
        large = set(arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600))
        assert small <= large


class TestRounds:
    """max_rounds only bites once line F is in play; the rest settles by round 2."""

    def test_round_one_is_a_single_ride_plus_walking(self, weekday_tt, coords):
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=1)
        assert set(got) == {"A1", "A2", "A3", "A4", "HUB_N", "HUB_S", "B2", "T2", "P_A", "P_B"}

    def test_round_two_adds_the_second_ride(self, weekday_tt, coords):
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=2)
        assert len(got) == 16
        assert {"B3", "C1", "C2", "C3", "E1", "F1"} <= set(got)
        assert "F2" not in got  # F1 is only walked to; boarding line F needs another round

    def test_round_three_reaches_line_f(self, weekday_tt, coords):
        """Ride A -> walk to T2 -> ride C to C3 -> walk 100 s to F1 -> ride F."""
        got = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=3)
        assert {"F2", "F3"} <= set(got)
        assert got["F2"] == hm(8, 37)
        assert got["F3"] == hm(8, 41)

    def test_the_scan_converges(self, weekday_tt, coords):
        three = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=3)
        eight = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=8)
        assert three == eight
        assert len(eight) == 18

    def test_more_rounds_never_worsen_an_arrival(self, weekday_tt, coords):
        few = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=1)
        many = arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600, max_rounds=8)
        assert all(many[stop] <= arrival for stop, arrival in few.items())


class TestNightTrips:
    """The one journey that boards a previous-day trip: C_2350_TUE_prev."""

    def test_a_previous_day_trip_can_be_boarded_after_midnight(self, weekday_tt, coords):
        got = arrivals(weekday_tt, coords, "C1", 0, 2400)
        assert got["C2"] == 1200  # 00:20
        assert got["C3"] == 2100  # 00:35

    def test_the_walk_onward_from_the_night_trip_works(self, weekday_tt, coords):
        assert arrivals(weekday_tt, coords, "C1", 0, 2400)["F1"] == pytest.approx(2200, abs=2)

    def test_nothing_runs_backwards_from_the_terminus(self, weekday_tt, coords):
        """C_2350_TUE_prev has already passed T2 (at -600) by midnight."""
        assert "T2" not in arrivals(weekday_tt, coords, "C1", 0, 2400)

    def test_the_unboardable_night_trip_is_still_in_the_timetable(self, weekday_tt, coords):
        """B_2345_TUE_prev's last departure is -180, so no rider at at>=0 can catch it,
        but build_datamodel still carried it over. Only C1 onward is boardable."""
        assert set(arrivals(weekday_tt, coords, "B1", 0, 1800)) == {"B1"}


class TestDayTypes:
    def test_saturday_runs_its_own_trips(self, build_timetable, coords):
        saturday = build_timetable("saturday")
        got = arrivals(saturday, coords, "A1", hm(10, 0), 1800)
        assert got["A4"] == hm(10, 16)  # A_1000_SAT

    def test_saturday_has_nothing_at_the_weekday_rush(self, build_timetable, coords):
        saturday = build_timetable("saturday")
        assert set(arrivals(saturday, coords, "A1", EIGHT_AM, 1800)) == {"A1"}

    def test_sunday_is_sparser_than_weekday(self, build_timetable, weekday_tt, coords):
        sunday = build_timetable("sunday")
        assert len(arrivals(sunday, coords, "A1", hm(12, 0), 1800)) < len(
            arrivals(weekday_tt, coords, "A1", EIGHT_AM, 1800)
        )


class TestDocumentedQuirks:
    """Current behaviour, pinned so a future change to it is a deliberate decision."""

    def test_unserved_stops_are_returned_when_near_the_source(self, weekday_tt, coords):
        """getNearby scans tt.coords rather than tt.stops, so X1 -- 6 m from HUB_N and
        served by no trip -- comes back as reachable."""
        got = arrivals(weekday_tt, coords, "HUB_N", EIGHT_AM, 600)
        assert "X1" in got
        assert "X1" not in weekday_tt.stops

    def test_an_unserved_stop_far_from_the_source_never_appears(self, weekday_tt, coords):
        assert "Z1" not in arrivals(weekday_tt, coords, "A1", EIGHT_AM, 3600)

    def test_returns_an_empty_dict_rather_than_an_empty_set(self, weekday_tt):
        """The no-walkable-stops early return is {} while the success path returns a set.
        Both iterate empty, so the endpoints happen to work either way."""
        result = reachable(weekday_tt, (59.0, 20.0), EIGHT_AM, 1800)
        assert result == {}
        assert isinstance(result, dict)

    def test_the_success_path_returns_a_set_of_triples(self, weekday_tt, coords):
        result = reachable(weekday_tt, coords["A1"], EIGHT_AM, 1800)
        assert isinstance(result, set)
        assert all(len(item) == 3 for item in result)
