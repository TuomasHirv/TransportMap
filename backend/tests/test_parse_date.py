"""Tier 2 -- calendar.csv / trips.csv filtering into (today's, yesterday's) services."""

from datetime import date

import pytest

from transport_map import parse_date
from transport_map.parse_date import (
    DAY_FLAG,
    PREV_DAY_FLAG,
    service_id_for_day,
    trips_from_services,
)


@pytest.fixture
def calendar(network_dir):
    return network_dir / "calendar.csv"


@pytest.fixture
def trips_csv(network_dir):
    return network_dir / "trips.csv"


class TestServiceIdForDay:
    @pytest.mark.parametrize(
        ("day", "services", "prev"),
        [
            ("weekday", {"SVC_WED", "SVC_DAILY"}, {"SVC_TUE"}),
            ("saturday", {"SVC_SAT", "SVC_DAILY"}, {"SVC_FRI"}),
            ("sunday", {"SVC_SUN", "SVC_DAILY"}, {"SVC_SAT"}),
        ],
    )
    def test_each_day_type(self, calendar, reference_dates, day, services, prev):
        assert service_id_for_day(day, reference_dates[day], calendar) == (services, prev)

    def test_weekday_means_wednesday(self):
        assert DAY_FLAG["weekday"] == "wednesday"
        assert PREV_DAY_FLAG["weekday"] == "tuesday"

    def test_prev_day_service_must_not_also_run_today(self, calendar, reference_dates):
        """service_id_for_day `continue`s after the main-day match, so a service running
        both Tuesday and Wednesday would never reach the prev-day set. SVC_DAILY is
        exactly that case."""
        services, prev = service_id_for_day("weekday", reference_dates["weekday"], calendar)
        assert "SVC_DAILY" in services
        assert "SVC_DAILY" not in prev

    def test_a_service_appears_in_at_most_one_set(self, calendar, reference_dates):
        services, prev = service_id_for_day("weekday", reference_dates["weekday"], calendar)
        assert services & prev == set()

    def test_unknown_day_type_raises(self, calendar):
        with pytest.raises(KeyError):
            service_id_for_day("caturday", date(2026, 9, 2), calendar)


class TestDateWindow:
    @pytest.mark.parametrize(
        ("on", "expected"),
        [
            (date(2026, 8, 30), set()),  # one day before start_date
            (date(2026, 8, 31), {"SVC_WED", "SVC_DAILY"}),  # start_date, inclusive
            (date(2026, 10, 24), {"SVC_WED", "SVC_DAILY"}),  # end_date, inclusive
            (date(2026, 10, 25), set()),  # one day after end_date
        ],
    )
    def test_window_is_inclusive_at_both_ends(self, calendar, on, expected):
        assert service_id_for_day("weekday", on, calendar)[0] == expected

    def test_expired_service_is_never_returned(self, calendar, reference_dates):
        """SVC_EXPIRED runs on wednesdays but its window closed in 2020."""
        for day, on in reference_dates.items():
            services, prev = service_id_for_day(day, on, calendar)
            assert "SVC_EXPIRED" not in services | prev

    def test_the_date_only_gates_the_window_not_the_weekday(self, calendar):
        """`on` is checked against start_date/end_date only -- the day-of-week comes from
        day_type. Passing a Monday with day_type="weekday" still returns Wednesday
        services. Documented behaviour, and why build_datamodel needs `on` threaded."""
        monday = date(2026, 8, 31)
        assert monday.strftime("%A") == "Monday"
        assert service_id_for_day("weekday", monday, calendar)[0] == {"SVC_WED", "SVC_DAILY"}


class TestTripsFromServices:
    def test_splits_trips_by_which_set_their_service_is_in(self, trips_csv):
        accepted, prev = trips_from_services({"SVC_WED"}, {"SVC_TUE"}, trips_csv)
        assert "A_0800" in accepted
        assert "B_2345_TUE" in prev
        assert accepted & prev == set()

    def test_weekday_accepts_the_wed_and_daily_trips(self, calendar, trips_csv, reference_dates):
        services, prev = service_id_for_day("weekday", reference_dates["weekday"], calendar)
        accepted, prev_accepted = trips_from_services(services, prev, trips_csv)
        assert len(accepted) == 15  # 14 on SVC_WED plus B_1200_DAILY
        assert prev_accepted == {"A_2200_TUE", "B_2345_TUE", "C_2350_TUE"}

    def test_daily_service_trips_are_accepted_every_day(self, calendar, trips_csv, reference_dates):
        for day, on in reference_dates.items():
            services, prev = service_id_for_day(day, on, calendar)
            accepted, _ = trips_from_services(services, prev, trips_csv)
            assert "B_1200_DAILY" in accepted

    def test_expired_trip_is_never_accepted(self, calendar, trips_csv, reference_dates):
        for day, on in reference_dates.items():
            services, prev = service_id_for_day(day, on, calendar)
            accepted, prev_accepted = trips_from_services(services, prev, trips_csv)
            assert "A_0900_EXPIRED" not in accepted | prev_accepted

    def test_unmatched_services_yield_nothing(self, trips_csv):
        assert trips_from_services(set(), set(), trips_csv) == (set(), set())


class TestPathArguments:
    def test_falls_back_to_the_module_constants(self, monkeypatch, network_dir, reference_dates):
        monkeypatch.setattr(parse_date, "CALENDAR_PATH", network_dir / "calendar.csv")
        monkeypatch.setattr(parse_date, "TRIPS_PATH", network_dir / "trips.csv")
        services, prev = service_id_for_day("weekday", reference_dates["weekday"])
        assert services == {"SVC_WED", "SVC_DAILY"}
        assert len(trips_from_services(services, prev)[0]) == 15
