"""Tier 2 -- parse_routes_to_trips(): stop_times.csv -> [(trip_id, ((arr, dep, stop), ...))].

Since the memory work the reader takes two sets: trips to keep whole, and previous-day
candidates kept only if they run past midnight. Each trip's events come back as a tuple
of tuples rather than a list so they cost less to hold.
"""

import pytest

from transport_map import parse_routes
from transport_map.parse_routes import DAY_IN_SECONDS, parse_routes_to_trips

UNSORTED_IDS = {"A_0800", "A_0805"}


class TestParseRoutesToTrips:
    def test_trip_count(self, raw_trips):
        """21 of the feed's 25 trips. The load-time filter drops the expired service,
        the monday/thursday-only one, and the two previous-day trips that never cross
        midnight -- all before any row is parsed."""
        assert len(raw_trips) == 21

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
        assert events == (
            (28800, 28800, "A1"),
            (29040, 29040, "A2"),
            (29280, 29280, "HUB_N"),
            (29520, 29520, "A3"),
            (29760, 29760, "A4"),
        )

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
        trips = parse_routes_to_trips(UNSORTED_IDS, set(), unsorted_dir / "stop_times.csv")
        assert len(trips) == 10
        assert all(len(events) == 1 for _, events in trips)
        assert [tid for tid, _ in trips[:4]] == ["A_0800", "A_0805", "A_0800", "A_0805"]

    def test_the_same_two_trips_parse_correctly_when_grouped(self, raw_trips):
        by_id = dict(raw_trips)
        assert len(by_id["A_0800"]) == 5
        assert len(by_id["A_0805"]) == 5


class TestPathArgument:
    def test_explicit_path_is_used(self, network_dir, every_trip_id):
        assert len(parse_routes_to_trips(every_trip_id, set(),
                                         network_dir / "stop_times.csv")) == 25

    def test_falls_back_to_the_module_constant(self, monkeypatch, network_dir,
                                               every_trip_id):
        monkeypatch.setattr(parse_routes, "STOP_TIMES_PATH", network_dir / "stop_times.csv")
        assert len(parse_routes_to_trips(every_trip_id, set())) == 25


class TestAllowedTrips:
    """The memory work: the reader is handed the set of trips worth keeping and skips
    every other trip's rows instead of building them and discarding them later."""

    def test_only_listed_trips_are_parsed(self, network_dir):
        trips = parse_routes_to_trips({"A_0800", "B_0810"}, set(),
                                      network_dir / "stop_times.csv")
        assert {tid for tid, _ in trips} == {"A_0800", "B_0810"}

    def test_an_empty_set_parses_nothing(self, network_dir):
        assert parse_routes_to_trips(set(), set(), network_dir / "stop_times.csv") == []

    def test_passing_every_id_loads_everything(self, network_dir, every_trip_id):
        assert len(parse_routes_to_trips(every_trip_id, set(),
                                         network_dir / "stop_times.csv")) == 25

    def test_ids_that_are_not_in_the_feed_are_harmless(self, network_dir):
        trips = parse_routes_to_trips({"A_0800", "NOPE"}, set(),
                                      network_dir / "stop_times.csv")
        assert [tid for tid, _ in trips] == ["A_0800"]

    def test_skipped_trips_are_not_materialised(self, network_dir, every_trip_id):
        """The whole point: a filtered read must cost less than an unfiltered one."""
        one = parse_routes_to_trips({"A_0800"}, set(), network_dir / "stop_times.csv")
        every = parse_routes_to_trips(every_trip_id, set(),
                                      network_dir / "stop_times.csv")
        assert len(one) == 1
        assert sum(len(ev) for _, ev in one) < sum(len(ev) for _, ev in every)

    def test_the_filter_is_what_excludes_the_expired_trip(self, raw_trips, unfiltered_trips):
        ids, all_ids = {t for t, _ in raw_trips}, {t for t, _ in unfiltered_trips}
        assert all_ids - ids == {
            "A_0900_EXPIRED",    # calendar window closed in 2020
            "A_1100_MON_THU",    # runs only on the two unconsulted days
            "A_2200_TUE",        # previous-day, but ends before midnight
            "A_1200_FRI",        # previous-day, but ends before midnight
        }


class TestMemoryRepresentation:
    def test_events_are_tuples_not_lists(self, raw_trips):
        """Tuples are immutable and smaller; nothing downstream mutates them."""
        _, events = raw_trips[0]
        assert isinstance(events, tuple)
        assert all(isinstance(e, tuple) for e in events)

    def test_stop_ids_are_interned(self, raw_trips):
        """sys.intern means every mention of a stop shares one string object rather
        than one per stop_time row -- 11 M rows of duplicated ids otherwise."""
        by_id = dict(raw_trips)
        a = next(s for _, _, s in by_id["A_0800"] if s == "HUB_N")
        b = next(s for _, _, s in by_id["A_R_0800"] if s == "HUB_N")
        assert a is b

    def test_repeated_times_parse_to_equal_values(self, raw_trips):
        """parse_time is memoised per read; the cache must not change what it returns."""
        by_id = dict(raw_trips)
        assert by_id["A_0800"][0][0] == by_id["A_0800"][0][1] == 28800
        assert by_id["L_0800"][0][0] == 28800  # a different trip, same clock string

    @pytest.mark.parametrize(("trip", "index", "seconds"),
                             [("A_2350_WED", -1, 86760), ("C_2350_TUE", -1, 88500)])
    def test_after_midnight_times_survive_memoisation(self, raw_trips, trip, index, seconds):
        assert dict(raw_trips)[trip][index][0] == seconds


class TestPreviousDayTripsAreStrippedByTime:
    """The feature: a previous-day service is consulted only for trips that spill past
    midnight into the day being built, so the reader keeps just those and skips the rest
    of that service's day entirely."""

    @pytest.fixture
    def stop_times(self, network_dir):
        return network_dir / "stop_times.csv"

    def test_a_candidate_crossing_midnight_is_kept(self, stop_times):
        """B_2345_TUE runs 23:45 -> 24:03, so Wednesday morning needs it."""
        trips = parse_routes_to_trips(set(), {"B_2345_TUE"}, stop_times)
        assert [tid for tid, _ in trips] == ["B_2345_TUE"]
        assert dict(trips)["B_2345_TUE"][-1][0] == 86580  # 24:03

    def test_a_candidate_ending_before_midnight_is_dropped(self, stop_times):
        """A_2200_TUE ends at 22:16. Nothing on Wednesday can ever board it, so its
        rows are never parsed -- this is the whole saving."""
        assert parse_routes_to_trips(set(), {"A_2200_TUE"}, stop_times) == []

    @pytest.mark.parametrize(
        ("trip", "kept"),
        [
            ("B_2345_TUE", True),    # tuesday, 24:03
            ("C_2350_TUE", True),    # tuesday, 24:35
            ("A_2200_TUE", False),   # tuesday, 22:16
            ("A_2350_FRI", True),    # friday, 24:06
            ("A_1200_FRI", False),   # friday, 12:16
        ],
    )
    def test_both_previous_day_flags_are_time_filtered(self, stop_times, trip, kept):
        """tuesday and friday both feed prev_filter. Each needs a kept and a dropped
        case, or one of them could be removed from the list unnoticed."""
        trips = parse_routes_to_trips(set(), {trip}, stop_times)
        assert bool(trips) is kept

    def test_a_trip_in_the_whole_set_is_kept_regardless_of_its_times(self, stop_times):
        """The time check applies only to previous-day candidates. A_2200_TUE ends well
        before midnight but survives when asked for whole."""
        trips = parse_routes_to_trips({"A_2200_TUE"}, set(), stop_times)
        assert [tid for tid, _ in trips] == ["A_2200_TUE"]

    def test_membership_of_the_whole_set_wins(self, stop_times):
        """A trip in both sets takes the whole-trip branch, which is what makes Saturday
        (a current-day flag and sunday's previous-day flag) work."""
        trips = parse_routes_to_trips({"A_1200_FRI"}, {"A_1200_FRI"}, stop_times)
        assert [tid for tid, _ in trips] == ["A_1200_FRI"]

    def test_an_empty_candidate_set_drops_every_previous_day_trip(self, stop_times,
                                                                  every_trip_id):
        whole_only = parse_routes_to_trips(every_trip_id - {"B_2345_TUE"}, set(), stop_times)
        assert "B_2345_TUE" not in {tid for tid, _ in whole_only}

    def test_the_midnight_boundary_is_inclusive(self, stop_times):
        """The check is `events[-1][0] >= 86400`, so a last arrival of exactly 24:00:00
        counts as crossing. A_2350_WED ends at 24:06 and B_2345_TUE at 24:03; both are
        over the line, while 23:59 trips are not."""
        assert parse_routes_to_trips(set(), {"A_2350_WED"}, stop_times)
        assert dict(parse_routes_to_trips(set(), {"A_2350_WED"}, stop_times))[
            "A_2350_WED"][-1][0] >= DAY_IN_SECONDS
        assert parse_routes_to_trips(set(), {"A_1100_MON_THU"}, stop_times) == []

    def test_the_two_sets_together_are_what_conftest_loads(self, allowed_trips, raw_trips):
        """End to end: the fixture pipeline is the lifespan's pipeline."""
        whole, prev = allowed_trips
        ids = {tid for tid, _ in raw_trips}
        assert ids == whole | {"B_2345_TUE", "C_2350_TUE", "A_2350_FRI"}
        assert ids.isdisjoint({"A_2200_TUE", "A_1200_FRI"})
