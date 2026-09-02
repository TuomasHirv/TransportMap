"""Tier 4 -- `lines_nearby`: which lines you can catch by walking from here.

This is what the API returns as `upcoming`. It takes the walkable stops that
`reachable` hands back, so the tests pass a synthetic list rather than going through
`getNearby` -- that keeps each case exact and independent of the 400 m radius.

Result shape: {route_short_name: departure_second}.
"""

import pytest

from transport_map.nearby_routes import lines_nearby
from transport_map.raptor import getNearby
from transport_map.shared_func import hm

EIGHT_AM = hm(8, 0)
QUARTER_HOUR = 900


def upcoming(tt, walkable, at=EIGHT_AM, window=QUARTER_HOUR):
    return lines_nearby(tt, walkable, at, at + window)


@pytest.fixture
def coords(stops_data):
    return stops_data[2]


class TestBasicShape:
    def test_maps_short_name_to_departure_second(self, weekday_tt):
        assert upcoming(weekday_tt, [("A1", 0)]) == {"1": 28800}

    def test_collects_every_walkable_stop(self, weekday_tt):
        """Standing at HUB_N you can also walk to HUB_S and B2, which are on line 2."""
        walkable = [("HUB_N", 0), ("HUB_S", 167), ("B2", 251), ("T2", 252)]
        assert upcoming(weekday_tt, walkable) == {"1": hm(8, 8), "2": hm(8, 13)}

    def test_no_walkable_stops_gives_nothing(self, weekday_tt):
        assert upcoming(weekday_tt, []) == {}

    def test_a_stop_no_trip_serves_contributes_nothing(self, weekday_tt):
        """X1 has coordinates but no trips; routes_by_stop is a defaultdict, so this
        must be a quiet no-op rather than a KeyError."""
        assert upcoming(weekday_tt, [("X1", 0)]) == {}
        assert "X1" not in weekday_tt.stops

    def test_matches_what_reachable_hands_the_endpoint(self, weekday_tt, coords):
        """The real call path: reachable's second return value feeds straight in."""
        walkable = getNearby(weekday_tt, coords["HUB_N"])
        assert upcoming(weekday_tt, walkable) == {"1": hm(8, 8), "2": hm(8, 13)}


class TestHorizon:
    def test_a_departure_exactly_on_the_horizon_counts(self, weekday_tt):
        """A_0800 leaves A1 at 08:00; a window ending exactly then still includes it."""
        assert lines_nearby(weekday_tt, [("A1", 0)], 28000, 28800) == {"1": 28800}

    def test_one_second_short_of_it_does_not(self, weekday_tt):
        assert lines_nearby(weekday_tt, [("A1", 0)], 28000, 28799) == {}

    def test_nothing_in_the_next_quarter_hour(self, weekday_tt):
        """By 09:00 the morning departures are gone and the next is 09:30."""
        assert upcoming(weekday_tt, [("A1", 0)], at=hm(9, 0)) == {}

    def test_a_wider_window_finds_more(self, weekday_tt):
        narrow = upcoming(weekday_tt, [("T2", 0)], at=hm(8, 0), window=900)
        wide = upcoming(weekday_tt, [("T2", 0)], at=hm(8, 0), window=3600)
        assert "3" not in narrow  # line C leaves T2 at 08:20, past 08:15
        assert wide["3"] == hm(8, 20)


class TestWalkingTime:
    def test_the_walk_delays_when_you_can_board(self, weekday_tt):
        """ready = at + walk_secs, so a long walk can miss an otherwise catchable trip."""
        assert upcoming(weekday_tt, [("A1", 0)]) == {"1": 28800}
        assert upcoming(weekday_tt, [("A1", 600)]) == {}

    def test_a_walk_that_still_arrives_in_time_keeps_the_line(self, weekday_tt):
        assert upcoming(weekday_tt, [("HUB_N", 400)]) == {"1": hm(8, 8)}


class TestEarliestDepartureWins:
    """Regression: the original kept the FIRST departure it happened to see, so it
    could advertise a bus later than the one actually leaving."""

    def test_reports_the_soonest_departure_across_routes_at_one_stop(self, weekday_tt):
        """Three Route objects are named "1" at A3 -- the two halves of the overtaking
        A-out split (departing 08:12 and 08:11) and A-ret (departing 08:04). The
        answer must be 08:04."""
        assert upcoming(weekday_tt, [("A3", 0)], at=hm(7, 56)) == {"1": hm(8, 4)}

    def test_reports_the_soonest_departure_across_walkable_stops(self, weekday_tt):
        """Line 1 is catchable at HUB_N (08:08) and, after a walk, at A3 (08:11).
        Stop order in the walkable list must not change the answer."""
        forward = upcoming(weekday_tt, [("HUB_N", 0), ("A3", 300)])
        reversed_ = upcoming(weekday_tt, [("A3", 300), ("HUB_N", 0)])
        assert forward == reversed_ == {"1": hm(8, 8)}

    def test_two_lines_sharing_a_short_name_merge_to_the_earlier(self, weekday_tt):
        """Routes D and E are both called "4H", as two real HSL routes share "H"."""
        assert weekday_tt.routes["r5"].short_name == weekday_tt.routes["r6"].short_name == "4H"
        merged = upcoming(weekday_tt, [("D1", 0), ("P_B", 0)], window=2000)
        assert merged == {"4H": hm(8, 0)}  # D_0800 at 08:00 beats E_0822 at 08:22


class TestTerminusIsNotBoardable:
    """Regression: a route's last stop was offered as a departure, but you can only
    get off there."""

    def test_the_final_stop_of_a_line_is_not_advertised(self, weekday_tt):
        """C3 is where line 3 ends. Its arrival at 08:29 is not a departure."""
        assert weekday_tt.routes["r4"].stops[-1] == "C3"
        assert upcoming(weekday_tt, [("C3", 0)], at=hm(8, 15)) == {}

    def test_the_same_line_is_still_offered_mid_route(self, weekday_tt):
        assert upcoming(weekday_tt, [("C2", 0)], at=hm(8, 15)) == {"3": hm(8, 26)}

    def test_a_loop_route_is_boardable_at_its_repeated_stop(self, weekday_tt):
        """L1 is both the first and last stop of the loop. Position 0 is a real
        departure, so the line is still offered."""
        assert weekday_tt.routes["r7"].stops == ["L1", "L2", "L3", "L2", "L1"]
        assert upcoming(weekday_tt, [("L1", 0)]) == {"6": hm(8, 0)}


class TestMissingShortName:
    def test_a_route_with_no_routes_csv_row_appears_under_an_empty_key(self, weekday_tt):
        """Line W has trips but no routes.csv entry, so its Route short_name is "".
        The dict is keyed by name, so it surfaces to the client as {"": ...}."""
        assert weekday_tt.routes["r8"].short_name == ""
        assert upcoming(weekday_tt, [("W1", 0)]) == {"": 28800}


class TestDayTypes:
    def test_saturday_has_its_own_departures(self, build_timetable):
        saturday = build_timetable("saturday")
        assert upcoming(saturday, [("A1", 0)], at=hm(10, 0)) == {"1": hm(10, 0)}

    def test_saturday_is_empty_at_the_weekday_rush(self, build_timetable):
        assert upcoming(build_timetable("saturday"), [("A1", 0)]) == {}

    def test_a_previous_day_night_trip_is_catchable_after_midnight(self, weekday_tt):
        """C_2350_TUE ran Tuesday 23:50 and is still going at 00:05 on Wednesday."""
        assert upcoming(weekday_tt, [("C1", 0)], at=0, window=900) == {"3": 300}
