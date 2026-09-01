"""Tier 0 -- pure helpers, no I/O and no fixtures.

`parse_time` and `metres` are called by almost every other module, so a fault here
would surface as a confusing failure much further up. They are tested first for that
reason.
"""

import pytest

from transport_map.shared_func import hm, metres, parse_time, to_latlon, to_xy


class TestParseTime:
    @pytest.mark.parametrize(
        ("text", "seconds"),
        [
            ("00:00:00", 0),
            ("00:00:01", 1),
            ("00:01:00", 60),
            ("01:00:00", 3600),
            ("08:05:00", 29100),
            ("23:59:59", 86399),
        ],
    )
    def test_within_the_day(self, text, seconds):
        assert parse_time(text) == seconds

    @pytest.mark.parametrize(
        ("text", "seconds"),
        [
            ("24:00:00", 86400),
            ("24:06:00", 86760),
            ("25:30:00", 91800),
            ("29:59:59", 107999),
        ],
    )
    def test_after_midnight_keeps_counting(self, text, seconds):
        """GTFS encodes a trip that runs past midnight as 24:xx rather than 00:xx."""
        assert parse_time(text) == seconds

    def test_midnight_boundary_is_exactly_a_day(self):
        assert parse_time("24:00:00") - parse_time("00:00:00") == 86400


class TestMetres:
    def test_zero_distance(self):
        assert metres((60.171, 24.918), (60.171, 24.918)) == 0

    def test_symmetric(self):
        a, b = (60.171, 24.940), (60.169, 24.940)
        assert metres(a, b) == pytest.approx(metres(b, a))

    def test_known_fixture_pair(self):
        """HUB_N <-> HUB_S, the fixture feed's reference walking distance."""
        assert metres((60.171, 24.940), (60.169, 24.940)) == pytest.approx(222.6, abs=0.5)

    def test_one_degree_of_latitude(self):
        assert metres((60.0, 24.0), (61.0, 24.0)) == pytest.approx(111320, abs=1)

    def test_longitude_is_compressed_at_this_latitude(self):
        """A degree of longitude is roughly half a degree of latitude near 60 N."""
        lat_m = metres((60.17, 24.94), (60.18, 24.94))
        lon_m = metres((60.17, 24.94), (60.17, 24.95))
        assert lon_m < lat_m
        assert lon_m / lat_m == pytest.approx(0.497, abs=0.01)

    def test_grows_with_separation(self):
        near = metres((60.170, 24.940), (60.171, 24.940))
        far = metres((60.170, 24.940), (60.175, 24.940))
        assert far > near


class TestProjection:
    def test_round_trip_at_fixture_precision(self):
        """The fixtures use 5 decimal places, which survives the round trip exactly."""
        for lat, lon in [(60.171, 24.918), (60.16, 24.9063), (60.1798, 24.9668)]:
            assert to_latlon(*to_xy(lat, lon)) == (lat, lon)

    def test_round_trip_is_lossy_beyond_five_decimals(self):
        """to_latlon rounds to 5 dp -- about 1 m of latitude. Documented, not a bug."""
        assert to_latlon(*to_xy(60.1712345, 24.9187654)) == (60.17123, 24.91877)

    def test_x_tracks_longitude_and_y_tracks_latitude(self):
        x0, y0 = to_xy(60.170, 24.940)
        x_east, y_east = to_xy(60.170, 24.950)
        x_north, y_north = to_xy(60.180, 24.940)
        assert x_east > x0 and y_east == pytest.approx(y0)
        assert y_north > y0 and x_north == pytest.approx(x0)

    def test_metres_per_degree_matches_metres_helper(self):
        x0, y0 = to_xy(60.17, 24.94)
        x1, y1 = to_xy(60.17, 24.95)
        assert abs(x1 - x0) == pytest.approx(metres((60.17, 24.94), (60.17, 24.95)), rel=1e-3)


class TestHm:
    @pytest.mark.parametrize(("h", "m", "seconds"), [(0, 0, 0), (8, 0, 28800), (8, 5, 29100)])
    def test_converts_to_seconds(self, h, m, seconds):
        assert hm(h, m) == seconds

    def test_agrees_with_parse_time(self):
        assert hm(8, 5) == parse_time("08:05:00")
