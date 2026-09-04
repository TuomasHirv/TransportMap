"""Tier 3 -- assembling parsed CSV rows into a scannable Timetable.

The densest module in the package: pattern grouping, the non-overtaking split,
footpath generation, transitive closure, and the previous-day night-trip carry-over.
Expected values come from tests/fixtures/README.md.
"""

import pytest

from transport_map.build_datamodel import (
    DAY_IN_SECONDS,
    build_datamodel,
    build_footpaths,
    build_patterns,
    close_footpaths,
    create_timetable,
    split_overtaking,
)
from transport_map.models import Timetable


def undirected(tt):
    """{frozenset({a, b}): seconds} -- footpaths are symmetric, so compare them that way."""
    return {frozenset((a, b)): s for a, vs in tt.footpaths.items() for b, s in vs if a != b}


# --------------------------------------------------------------------------- patterns


class TestBuildPatterns:
    def test_groups_trips_sharing_a_stop_sequence(self):
        patterns = build_patterns(
            [
                ("t1", [(0, 0, "A"), (60, 60, "B")]),
                ("t2", [(300, 300, "A"), (360, 360, "B")]),
            ]
        )
        assert list(patterns) == [("A", "B")]
        assert [tid for tid, _ in patterns[("A", "B")]] == ["t1", "t2"]

    def test_reversed_sequence_is_a_different_pattern(self):
        """Order matters: A->B and B->A are separate routes, per the RAPTOR paper."""
        patterns = build_patterns(
            [("out", [(0, 0, "A"), (60, 60, "B")]), ("ret", [(0, 0, "B"), (60, 60, "A")])]
        )
        assert set(patterns) == {("A", "B"), ("B", "A")}

    def test_a_subsequence_is_a_different_pattern(self):
        patterns = build_patterns(
            [
                ("long", [(0, 0, "A"), (1, 1, "B"), (2, 2, "C")]),
                ("short", [(0, 0, "A"), (1, 1, "C")]),
            ]
        )
        assert set(patterns) == {("A", "B", "C"), ("A", "C")}

    def test_drops_the_stop_id_from_the_stoptimes(self):
        patterns = build_patterns([("t1", [(10, 20, "A")])])
        assert patterns[("A",)] == [("t1", [(10, 20)])]

    def test_empty_input(self):
        assert build_patterns([]) == {}


# ------------------------------------------------------------------- overtaking split


class TestSplitOvertaking:
    def test_monotone_trips_stay_in_one_group(self):
        trips = [("first", [(0, 0), (100, 100)]), ("second", [(50, 50), (150, 150)])]
        assert len(split_overtaking(2, trips)) == 1

    def test_an_overtaking_trip_starts_a_new_group(self):
        """RAPTOR assumes trips on a route do not overtake; violators are split out."""
        slow = ("slow", [(0, 0), (100, 100), (200, 200)])
        fast = ("fast", [(10, 10), (60, 60), (110, 110)])
        assert len(split_overtaking(3, [slow, fast])) == 2

    def test_a_later_trip_can_rejoin_the_first_group(self):
        slow = ("slow", [(0, 0), (100, 100), (200, 200)])
        fast = ("fast", [(10, 10), (60, 60), (110, 110)])
        late = ("late", [(300, 300), (400, 400), (500, 500)])
        groups = split_overtaking(3, [slow, fast, late])
        assert len(groups) == 2
        assert [t for t, _ in groups[0]] == ["slow", "late"]
        assert [t for t, _ in groups[1]] == ["fast"]

    def test_groups_are_ordered_by_departure(self):
        trips = [("b", [(100, 100)]), ("a", [(0, 0)])]
        assert [t for t, _ in split_overtaking(1, trips)[0]] == ["a", "b"]

    def test_identical_times_do_not_count_as_overtaking(self):
        """The comparison is <=, so a duplicate schedule shares the group."""
        twin = [(0, 0), (100, 100)]
        assert len(split_overtaking(2, [("x", twin), ("y", list(twin))])) == 1

    def test_single_trip(self):
        assert len(split_overtaking(1, [("only", [(0, 0)])])) == 1


class TestCreateTimetable:
    def test_splits_an_overtaking_pattern_into_two_routes(self):
        tt = create_timetable(
            [
                ("slow", [(0, 0, "A"), (100, 100, "B"), (200, 200, "C")]),
                ("fast", [(10, 10, "A"), (60, 60, "B"), (110, 110, "C")]),
            ],
            {"slow": "1", "fast": "1"},
        )
        assert len(tt.routes) == 2
        assert all(r.stops == ["A", "B", "C"] for r in tt.routes.values())

    def test_finalizes_the_result(self):
        tt = create_timetable([("t", [(0, 0, "A"), (60, 60, "B")])], {"t": "1"})
        assert tt.routes_by_stop["A"] == [("r0", 0)]


class TestRouteNaming:
    """finalize_timetable names each route from the first trip of its group."""

    def test_names_a_route_from_its_trips(self):
        tt = create_timetable([("t", [(0, 0, "A"), (60, 60, "B")])], {"t": "550"})
        assert tt.routes["r0"].short_name == "550"

    def test_both_halves_of_an_overtaking_split_keep_the_line_name(self):
        """Splitting for the non-overtaking assumption is an internal detail -- a rider
        still sees one line."""
        tt = create_timetable(
            [
                ("slow", [(0, 0, "A"), (100, 100, "B"), (200, 200, "C")]),
                ("fast", [(10, 10, "A"), (60, 60, "B"), (110, 110, "C")]),
            ],
            {"slow": "1", "fast": "1"},
        )
        assert len(tt.routes) == 2
        assert {r.short_name for r in tt.routes.values()} == {"1"}

    def test_an_unmapped_trip_yields_an_empty_name(self):
        """A route_id absent from routes.csv never reaches trip_id_shortname."""
        tt = create_timetable([("t", [(0, 0, "A"), (60, 60, "B")])], {})
        assert tt.routes["r0"].short_name == ""

    def test_the_name_comes_from_the_earliest_trip_in_the_group(self):
        """Groups are sorted by first departure, so group[0] is the earliest trip."""
        tt = create_timetable(
            [
                ("later", [(300, 300, "A"), (400, 400, "B")]),
                ("earlier", [(100, 100, "A"), (200, 200, "B")]),
            ],
            {"earlier": "first", "later": "second"},
        )
        assert tt.routes["r0"].short_name == "first"


# -------------------------------------------------------------------------- footpaths


class TestBuildFootpaths:
    def test_links_stops_inside_the_walking_radius(self, weekday_tt):
        assert undirected(weekday_tt)[frozenset(("HUB_N", "HUB_S"))] == pytest.approx(167, abs=2)

    def test_clamps_very_short_walks_to_min_transfer(self, weekday_tt):
        """B2 <-> T2 is 27.7 m, about 21 s of walking, but changing vehicles costs 60 s."""
        assert undirected(weekday_tt)[frozenset(("B2", "T2"))] == 60

    def test_same_station_platforms_are_linked_beyond_the_radius(self, weekday_tt):
        """P_A and P_B are 498 m apart -- past MAX_WALK_METERS -- but share parent ST1."""
        assert undirected(weekday_tt)[frozenset(("P_A", "P_B"))] == pytest.approx(375, abs=2)

    def test_stops_beyond_the_radius_are_not_linked(self, weekday_tt):
        edges = undirected(weekday_tt)
        assert frozenset(("A1", "A2")) not in edges  # 609 m
        assert frozenset(("F1", "F2")) not in edges  # 620 m

    def test_only_serves_stops_that_are_in_the_timetable(self, weekday_tt):
        """Z1 and X1 have coordinates but no trips, so they get no footpaths."""
        touched = {s for edge in undirected(weekday_tt) for s in edge}
        assert "Z1" not in touched
        assert "X1" not in touched

    def test_footpaths_are_symmetric(self, weekday_tt):
        for a, vs in weekday_tt.footpaths.items():
            for b, secs in vs:
                assert (a, secs) in weekday_tt.footpaths[b]

    def test_returns_the_number_of_pairs_created(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B"], [[(0, 0), (60, 60)]], "1")
        tt.coords = {"A": (60.170, 24.940), "B": (60.171, 24.940)}
        tt.finalize()
        assert build_footpaths(tt, {}) == 1

    def test_isolated_stop_gets_no_neighbours(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B"], [[(0, 0), (60, 60)]], "1")
        tt.coords = {"A": (60.170, 24.940), "B": (60.400, 25.400)}
        tt.finalize()
        assert build_footpaths(tt, {}) == 0


class TestFootpathTable:
    """The complete weekday footpath graph. Anything absent here must stay absent."""

    EDGES = [
        ("B2", "T2", 60),
        ("A3", "P_A", 93),
        ("C3", "F1", 100),
        ("B3", "C1", 125),
        ("A4", "P_B", 150),
        ("HUB_N", "HUB_S", 167),
        ("B2", "HUB_N", 251),
        ("HUB_N", "T2", 252),
        ("W1", "W2", 262),
        ("W2", "W3", 262),
        ("W3", "W4", 262),
        ("P_A", "P_B", 375),
        ("B2", "HUB_S", 418),
        ("HUB_S", "T2", 419),
        ("A3", "P_B", 468),
        ("W1", "W3", 524),
        ("W2", "W4", 524),
        ("A4", "P_A", 525),
    ]

    @pytest.mark.parametrize(("a", "b", "seconds"), EDGES)
    def test_edge(self, weekday_tt, a, b, seconds):
        # derived seconds come from round(distance / WALK_SPEED); the 60 s clamp is exact
        tolerance = 0 if seconds == 60 else 2
        assert undirected(weekday_tt)[frozenset((a, b))] == pytest.approx(seconds, abs=tolerance)

    def test_there_are_no_other_edges(self, weekday_tt):
        assert len(undirected(weekday_tt)) == len(self.EDGES)

    def test_the_loop_line_has_no_footpaths(self, weekday_tt):
        touched = {s for edge in undirected(weekday_tt) for s in edge}
        assert touched.isdisjoint({"L1", "L2", "L3"})


class TestCloseFootpaths:
    def test_two_hops_within_the_cap_are_added(self, weekday_tt):
        """W1->W2->W3 is 524 s, under MAX_WALK_SECONDS, so the closure links W1 to W3."""
        assert undirected(weekday_tt)[frozenset(("W1", "W3"))] == pytest.approx(524, abs=2)

    def test_three_hops_past_the_cap_are_not_added(self, weekday_tt):
        """W1->W4 would be 786 s, over the 600 s limit."""
        assert frozenset(("W1", "W4")) not in undirected(weekday_tt)

    def test_strips_the_self_footpaths_finalize_added(self, weekday_tt):
        for stop, neighbours in weekday_tt.footpaths.items():
            assert all(other != stop for other, _ in neighbours)

    def test_keeps_the_shortest_of_several_paths(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B", "C"], [[(0, 0), (1, 1), (2, 2)]], "1")
        tt.add_footpath("A", "B", 100)
        tt.add_footpath("B", "C", 100)
        tt.add_footpath("A", "C", 500)  # direct but slower than walking via B
        tt.finalize()
        assert dict(close_footpaths(tt).footpaths["A"])["C"] == 200

    def test_is_transitive_over_a_chain(self):
        tt = Timetable()
        tt.add_route("r0", ["A", "B", "C"], [[(0, 0), (1, 1), (2, 2)]], "1")
        tt.add_footpath("A", "B", 100)
        tt.add_footpath("B", "C", 100)
        tt.finalize()
        assert dict(close_footpaths(tt).footpaths["A"])["C"] == 200


# ------------------------------------------------------------------ full assembly


class TestBuildDatamodel:
    def test_weekday_shape(self, weekday_tt):
        assert len(weekday_tt.routes) == 10
        assert sum(len(r.trips) for r in weekday_tt.routes.values()) == 17
        assert len(weekday_tt.stops) == 27

    @pytest.mark.parametrize(("day", "routes", "trips"), [("saturday", 2, 4), ("sunday", 2, 2)])
    def test_other_day_types_are_smaller(self, build_timetable, day, routes, trips):
        tt = build_timetable(day)
        assert len(tt.routes) == routes
        assert sum(len(r.trips) for r in tt.routes.values()) == trips

    def test_carries_coords_and_names_through(self, weekday_tt):
        assert weekday_tt.coords["A1"] == (60.171, 24.918)
        assert weekday_tt.stop_names["HUB_N"] == "Töölö, Keskus"

    def test_unserved_stops_never_enter_the_timetable(self, weekday_tt):
        assert "Z1" not in weekday_tt.stops
        assert "X1" not in weekday_tt.stops
        assert "Z1" in weekday_tt.coords  # geography still knows about it

    def test_station_rows_never_enter_the_timetable(self, weekday_tt):
        assert "ST1" not in weekday_tt.stops
        assert "ST1" not in weekday_tt.coords

    def test_the_overtaking_pattern_became_two_routes(self, weekday_tt):
        out = ["A1", "A2", "HUB_N", "A3", "A4"]
        a_out = [r for r in weekday_tt.routes.values() if r.stops == out]
        assert len(a_out) == 2
        assert sorted(len(r.trips) for r in a_out) == [1, 3]

    def test_the_reversed_direction_is_its_own_route(self, weekday_tt):
        back = ["A4", "A3", "HUB_N", "A2", "A1"]
        assert len([r for r in weekday_tt.routes.values() if r.stops == back]) == 1

    def test_the_loop_route_survives_intact(self, weekday_tt):
        loop = next(r for r in weekday_tt.routes.values() if r.stops.count("L2") == 2)
        assert loop.stops == ["L1", "L2", "L3", "L2", "L1"]
        assert loop.positions("L2") == [1, 3]


class TestNightTrips:
    def _c_route(self, tt):
        return next(r for r in tt.routes.values() if r.stops == ["T2", "C1", "C2", "C3"])

    def test_previous_day_trips_are_shifted_back_a_day(self, weekday_tt):
        """A Tuesday trip running past midnight becomes Wednesday's early morning."""
        first_departures = sorted(
            t[0][1] for r in weekday_tt.routes.values() for t in r.trips if t[0][1] < 0
        )
        assert first_departures == [-900, -600]

    def test_the_shift_is_exactly_one_day(self, weekday_tt, raw_trips):
        original = dict(raw_trips)["C_2350_TUE"]
        shifted = next(t for t in self._c_route(weekday_tt).trips if t[0][1] < 0)
        assert [(a, d) for a, d, _ in original] == [
            (a + DAY_IN_SECONDS, d + DAY_IN_SECONDS) for a, d in shifted
        ]

    def test_a_previous_day_trip_that_ends_before_midnight_is_dropped(self, weekday_tt):
        """A_2200_TUE is an accepted Tuesday trip but finishes at 22:16, so carrying it
        into Wednesday would be wrong -- only trips still running past 24:00 survive."""
        a_out_trips = [
            t
            for r in weekday_tt.routes.values()
            if r.stops == ["A1", "A2", "HUB_N", "A3", "A4"]
            for t in r.trips
        ]
        assert all(t[0][1] >= 0 for t in a_out_trips)
        assert len(a_out_trips) == 4  # A_0800, A_0805, A_0830, A_2350_WED

    def test_same_day_trips_keep_their_past_midnight_times(self, weekday_tt):
        """A_2350_WED runs Wednesday 23:50 -> 24:06 and is not shifted."""
        ends = [t[-1][0] for r in weekday_tt.routes.values() for t in r.trips]
        assert max(ends) == 86760

    def test_the_night_trip_does_not_split_its_pattern(self, weekday_tt):
        """The three C trips stay monotone, so line C remains a single route."""
        route = self._c_route(weekday_tt)
        assert [t[0][1] for t in route.trips] == [-600, 30000, 31800]

    def test_saturday_carries_friday_night(self, build_timetable):
        saturday = build_timetable("saturday")
        assert [t[0][1] for r in saturday.routes.values() for t in r.trips if t[0][1] < 0] == [-600]

    def test_sunday_carries_nothing(self, build_timetable):
        """Saturday's trips all finish before midnight, so there is nothing to carry."""
        sunday = build_timetable("sunday")
        assert [t[0][1] for r in sunday.routes.values() for t in r.trips if t[0][1] < 0] == []


class TestPreFilteredInput:
    """build_datamodel no longer checks the calendar window itself -- service_id_for_day
    matches on the day flag alone. It relies on all_trips having been filtered at load
    time by filter_out_monday_thursday, which is what conftest and the app's lifespan both
    do. These tests pin that contract from both sides."""

    def test_pre_filtered_input_excludes_the_expired_trip(self, weekday_tt):
        departures = {t[0][1] for r in weekday_tt.routes.values() for t in r.trips}
        assert 32400 not in departures  # A_0900_EXPIRED would depart at 09:00
        assert sum(len(r.trips) for r in weekday_tt.routes.values()) == 17

    def test_unfiltered_input_lets_the_expired_trip_through(
        self, unfiltered_trips, stops_data, trip_shortnames, network_dir
    ):
        """The documented consequence of moving the window to the load layer: handed
        every trip in the feed, build_datamodel builds one more than it should. This is
        why the pre-filter is not optional."""
        parents, stop_names, coords = stops_data
        tt = build_datamodel(
            unfiltered_trips, parents, stop_names, coords, trip_shortnames, "weekday",
            calendar_path=network_dir / "calendar.csv",
            trips_path=network_dir / "trips.csv",
        )
        departures = {t[0][1] for r in tt.routes.values() for t in r.trips}
        assert 32400 in departures  # A_0900_EXPIRED, out of window since 2020
        assert sum(len(r.trips) for r in tt.routes.values()) == 18

    def test_a_monday_thursday_trip_never_appears_either_way(
        self, weekday_tt, unfiltered_trips, stops_data, trip_shortnames, network_dir
    ):
        """Belt and braces: even unfiltered, SVC_MON_THU matches no day flag."""
        parents, stop_names, coords = stops_data
        tt = build_datamodel(
            unfiltered_trips, parents, stop_names, coords, trip_shortnames, "weekday",
            calendar_path=network_dir / "calendar.csv",
            trips_path=network_dir / "trips.csv",
        )
        for timetable in (weekday_tt, tt):
            departures = {t[0][1] for r in timetable.routes.values() for t in r.trips}
            assert 39600 not in departures  # A_1100_MON_THU would depart at 11:00


class TestDateFiltering:
    def test_the_expired_service_is_absent_from_every_day(self, build_timetable):
        """A_0900_EXPIRED would be the only 09:00 departure if the window were ignored."""
        for day in ("weekday", "saturday", "sunday"):
            tt = build_timetable(day)
            departures = {t[0][1] for r in tt.routes.values() for t in r.trips}
            assert 32400 not in departures

    def test_the_daily_service_runs_on_every_day_type(self, build_timetable):
        for day in ("weekday", "saturday", "sunday"):
            tt = build_timetable(day)
            b_route = next(r for r in tt.routes.values() if r.stops == ["B1", "HUB_S", "B2", "B3"])
            assert 43200 in [t[0][1] for t in b_route.trips]  # B_1200_DAILY at 12:00
