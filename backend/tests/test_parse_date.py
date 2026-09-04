"""Tier 2 -- calendar.csv / trips.csv filtering into (today's, yesterday's) services.

Since the memory work the calendar's start_date/end_date window is applied by
`filter_out_monday_thursday` at load time, not by `service_id_for_day`. The two are tested
separately below, and `TestPreFilterIsWhatEnforcesTheWindow` pins how they combine.
"""

from datetime import date

import pytest

from transport_map import parse_date
from transport_map.parse_date import (
    DAY_FLAG,
    PREV_DAY_FLAG,
    filter_out_monday_thursday,
    service_id_for_day,
    trips_from_services,
)


@pytest.fixture
def calendar(network_dir):
    return network_dir / "calendar.csv"


@pytest.fixture
def trips_csv(network_dir):
    return network_dir / "trips.csv"


@pytest.fixture
def feed(calendar, trips_csv):
    """The two paths filter_out_monday_thursday needs, as keyword arguments."""
    return {"path": calendar, "trips_path": trips_csv}


class TestServiceIdForDay:
    @pytest.mark.parametrize(
        ("day", "services", "prev"),
        [
            ("weekday", {"SVC_WED", "SVC_DAILY", "SVC_EXPIRED"}, {"SVC_TUE"}),
            ("saturday", {"SVC_SAT", "SVC_DAILY"}, {"SVC_FRI"}),
            ("sunday", {"SVC_SUN", "SVC_DAILY"}, {"SVC_SAT"}),
        ],
    )
    def test_each_day_type(self, calendar, day, services, prev):
        assert service_id_for_day(day, calendar) == (services, prev)

    def test_weekday_means_wednesday(self):
        assert DAY_FLAG["weekday"] == "wednesday"
        assert PREV_DAY_FLAG["weekday"] == "tuesday"

    def test_matches_on_the_day_flag_only(self, calendar):
        """It no longer looks at start_date/end_date, so SVC_EXPIRED -- which runs on
        Wednesdays but whose window closed in 2020 -- comes back here. The window is
        enforced earlier, by filter_out_monday_thursday."""
        services, _ = service_id_for_day("weekday", calendar)
        assert "SVC_EXPIRED" in services

    def test_ignores_services_running_only_on_unconsulted_days(self, calendar):
        """SVC_MON_THU runs Monday and Thursday, neither of which is a day flag."""
        for day in ("weekday", "saturday", "sunday"):
            services, prev = service_id_for_day(day, calendar)
            assert "SVC_MON_THU" not in services | prev

    def test_prev_day_service_must_not_also_run_today(self, calendar):
        """service_id_for_day `continue`s after the main-day match, so a service running
        both Tuesday and Wednesday would never reach the prev-day set. SVC_DAILY is
        exactly that case."""
        services, prev = service_id_for_day("weekday", calendar)
        assert "SVC_DAILY" in services
        assert "SVC_DAILY" not in prev

    def test_a_service_appears_in_at_most_one_set(self, calendar):
        services, prev = service_id_for_day("weekday", calendar)
        assert services & prev == set()

    def test_unknown_day_type_raises(self, calendar):
        with pytest.raises(KeyError):
            service_id_for_day("caturday", calendar)


class TestFilterOutMondayThursday:
    """The memory feature. Returns two sets: services on a current-day flag, which are
    needed in full, and services only on a previous-day flag, which parse_routes keeps
    only if they run past midnight."""

    def test_returns_two_sets(self, feed):
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert isinstance(whole, set) and isinstance(prev, set)

    def test_current_day_flags_are_loaded_whole(self, feed):
        """wednesday, saturday and sunday are what DAY_FLAG asks for."""
        whole, _ = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert {"A_0800", "A_1000_SAT", "A_1200_SUN"} <= whole

    def test_previous_day_only_flags_become_candidates(self, feed):
        """tuesday and friday are only ever consulted for trips spilling past midnight,
        so they are held back for parse_routes to time-filter."""
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert {"B_2345_TUE", "C_2350_TUE", "A_2200_TUE"} <= prev   # SVC_TUE
        assert {"A_2350_FRI", "A_1200_FRI"} <= prev                 # SVC_FRI
        assert prev.isdisjoint(whole)

    def test_saturday_is_loaded_whole_despite_being_sundays_previous_day(self, feed):
        """Saturday is both a current-day flag (for the saturday timetable) and the
        previous-day flag for sunday. The current-day role wins, so its daytime trips
        survive -- otherwise Saturday afternoon would vanish."""
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert {"A_1000_SAT", "B_1010_SAT"} <= whole
        assert {"A_1000_SAT", "B_1010_SAT"}.isdisjoint(prev)

    def test_a_service_on_both_kinds_of_flag_is_loaded_whole(self, feed):
        """SVC_DAILY runs every day, so it matches wednesday and tuesday alike."""
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert "B_1200_DAILY" in whole
        assert "B_1200_DAILY" not in prev

    def test_drops_a_service_running_only_on_monday_and_thursday(self, feed):
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert "A_1100_MON_THU" not in whole | prev

    def test_drops_a_service_outside_the_calendar_window(self, feed):
        """This is the only place the window is checked."""
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert "A_0900_EXPIRED" not in whole | prev

    def test_the_counts(self, feed):
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert (len(whole), len(prev)) == (18, 5)   # of 25 trips in the feed

    @pytest.mark.parametrize(
        ("on", "counts"),
        [
            (date(2026, 8, 30), (0, 0)),    # day before start_date
            (date(2026, 8, 31), (18, 5)),   # start_date, inclusive
            (date(2026, 10, 24), (18, 5)),  # end_date, inclusive
            (date(2026, 10, 25), (0, 0)),   # day after end_date
        ],
    )
    def test_the_window_is_inclusive_at_both_ends(self, feed, on, counts):
        whole, prev = filter_out_monday_thursday(on=on, **feed)
        assert (len(whole), len(prev)) == counts

    @pytest.mark.parametrize("day", ["weekday", "saturday", "sunday"])
    def test_covers_everything_each_day_type_needs(self, feed, calendar, trips_csv, day):
        """The property that makes the optimisation safe: nothing a day type asks for
        may be missing from what was loaded. Editing either day list breaks this long
        before anyone notices a missing bus."""
        services, prev_services = service_id_for_day(day, calendar)
        accepted, prev_accepted = trips_from_services(services, prev_services, trips_csv)
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        # SVC_EXPIRED is the one thing service_id_for_day asks for that the window
        # legitimately withholds.
        assert (accepted | prev_accepted) - (whole | prev) <= {"A_0900_EXPIRED"}

    def test_defaults_to_today(self, feed):
        """Without `on` it uses date.today(), which is why the fixtures pass one."""
        whole, prev = filter_out_monday_thursday(**feed)
        assert isinstance(whole, set) and isinstance(prev, set)

    def test_honours_trips_path(self, calendar, trips_csv):
        """Without its own trips_path this reached straight past the fixture feed into
        data/trips.csv, which does not exist in CI."""
        whole, _ = filter_out_monday_thursday(on=date(2026, 9, 2), path=calendar,
                                              trips_path=trips_csv)
        assert whole

    def test_falls_back_to_the_module_constants(self, monkeypatch, calendar, trips_csv):
        monkeypatch.setattr(parse_date, "CALENDAR_PATH", calendar)
        monkeypatch.setattr(parse_date, "TRIPS_PATH", trips_csv)
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2))
        assert (len(whole), len(prev)) == (18, 5)


class TestPreFilterIsWhatEnforcesTheWindow:
    """How the halves combine. build_datamodel intersects the day-type trips with
    whatever was loaded, so the window only bites if the load was filtered."""

    def test_the_intersection_excludes_the_expired_trip(self, calendar, trips_csv, feed):
        services, prev_services = service_id_for_day("weekday", calendar)
        accepted, _ = trips_from_services(services, prev_services, trips_csv)
        whole, prev = filter_out_monday_thursday(on=date(2026, 9, 2), **feed)
        assert "A_0900_EXPIRED" in accepted                      # the day flag matches
        assert "A_0900_EXPIRED" not in accepted & (whole | prev)  # the window does not


class TestTripsFromServices:
    def test_splits_trips_by_which_set_their_service_is_in(self, trips_csv):
        accepted, prev = trips_from_services({"SVC_WED"}, {"SVC_TUE"}, trips_csv)
        assert "A_0800" in accepted
        assert "B_2345_TUE" in prev
        assert accepted & prev == set()

    def test_weekday_accepts_the_wed_and_daily_trips(self, calendar, trips_csv):
        services, prev = service_id_for_day("weekday", calendar)
        accepted, prev_accepted = trips_from_services(services, prev, trips_csv)
        # 14 on SVC_WED, B_1200_DAILY, and A_0900_EXPIRED -- the window is not applied here
        assert len(accepted) == 16
        assert prev_accepted == {"A_2200_TUE", "B_2345_TUE", "C_2350_TUE"}

    def test_daily_service_trips_are_accepted_every_day(self, calendar, trips_csv):
        for day in ("weekday", "saturday", "sunday"):
            services, prev = service_id_for_day(day, calendar)
            accepted, _ = trips_from_services(services, prev, trips_csv)
            assert "B_1200_DAILY" in accepted

    def test_a_monday_thursday_trip_is_never_accepted(self, calendar, trips_csv):
        for day in ("weekday", "saturday", "sunday"):
            services, prev = service_id_for_day(day, calendar)
            accepted, prev_accepted = trips_from_services(services, prev, trips_csv)
            assert "A_1100_MON_THU" not in accepted | prev_accepted

    def test_unmatched_services_yield_nothing(self, trips_csv):
        assert trips_from_services(set(), set(), trips_csv) == (set(), set())


class TestPathArguments:
    def test_falls_back_to_the_module_constants(self, monkeypatch, network_dir):
        monkeypatch.setattr(parse_date, "CALENDAR_PATH", network_dir / "calendar.csv")
        monkeypatch.setattr(parse_date, "TRIPS_PATH", network_dir / "trips.csv")
        services, prev = service_id_for_day("weekday")
        assert services == {"SVC_WED", "SVC_DAILY", "SVC_EXPIRED"}
        assert len(trips_from_services(services, prev)[0]) == 16
