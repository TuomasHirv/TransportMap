"""Tier 5 -- turning reachable stops into isochrone bands and GeoJSON.

Independent of Tiers 1-4: build_bands takes a plain [(lat, lon, travel_seconds)] list,
so most of this runs on synthetic input rather than a Timetable.
"""

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon

from transport_map.draw_isochrone import _polygons_only, build_bands, to_geojson
from transport_map.shared_func import to_xy

# One stop in the middle of the fixture mainland, reached instantly.
CENTRE = [(60.170, 24.920, 0)]


class TestPolygonsOnly:
    def test_passes_a_polygon_through(self):
        square = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        assert _polygons_only(square).geom_type == "Polygon"

    def test_passes_a_multipolygon_through(self):
        pair = MultiPolygon(
            [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(5, 5), (6, 5), (6, 6), (5, 6)]),
            ]
        )
        assert _polygons_only(pair).geom_type == "MultiPolygon"

    def test_keeps_only_the_polygons_in_a_collection(self):
        """intersection() can hand back stray lines and points alongside the areas."""
        square = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        mixed = GeometryCollection([square, LineString([(3, 3), (4, 4)]), Point(5, 5)])
        result = _polygons_only(mixed)
        assert result.geom_type == "Polygon"
        assert result.area == pytest.approx(4)

    def test_empty_geometry_is_none(self):
        assert _polygons_only(Polygon()) is None

    def test_a_collection_with_no_area_is_none(self):
        assert _polygons_only(GeometryCollection([LineString([(0, 0), (1, 1)])])) is None


class TestBuildBands:
    def test_returns_a_band_per_threshold(self):
        bands = build_bands(CENTRE, None, bands=(600, 1200, 1800))
        assert [t for t, _ in bands] == [1800, 1200, 600]

    def test_bands_are_ordered_largest_first(self):
        """to_geojson emits them in this order so the widest band draws underneath."""
        bands = build_bands(CENTRE, None, bands=(600, 1800, 1200))
        assert [t for t, _ in bands] == [1800, 1200, 600]

    def test_bands_nest(self):
        bands = dict(build_bands(CENTRE, None, bands=(600, 1200, 1800)))
        assert bands[600].area < bands[1200].area < bands[1800].area
        assert bands[1200].covers(bands[600].buffer(-1))

    def test_radius_shrinks_as_travel_time_grows(self):
        near = dict(build_bands([(60.170, 24.920, 0)], None, bands=(1800,)))[1800]
        far = dict(build_bands([(60.170, 24.920, 1200)], None, bands=(1800,)))[1800]
        assert far.area < near.area

    def test_a_stop_at_the_threshold_contributes_nothing(self):
        """The filter is `travel < t`, so a stop reached exactly at t adds no circle."""
        assert build_bands([(60.170, 24.920, 600)], None, bands=(600,)) == []

    def test_a_stop_past_the_threshold_is_excluded(self):
        assert build_bands([(60.170, 24.920, 900)], None, bands=(600,)) == []

    def test_no_stops_means_no_bands(self):
        assert build_bands([], None, bands=(600, 1200)) == []

    def test_overlapping_stops_merge_into_one_polygon(self):
        two = build_bands([(60.170, 24.920, 0), (60.1705, 24.9205, 0)], None, bands=(1800,))
        assert two[0][1].geom_type == "Polygon"

    def test_distant_stops_stay_separate(self):
        apart = build_bands([(60.170, 24.900, 1700), (60.170, 24.950, 1700)], None, bands=(1800,))
        assert apart[0][1].geom_type == "MultiPolygon"

    def test_land_clips_the_bands(self, land):
        unclipped = dict(build_bands(CENTRE, None, bands=(1800,)))[1800]
        clipped = dict(build_bands(CENTRE, land, bands=(1800,)))[1800]
        assert clipped.area < unclipped.area
        assert land.buffer(1).covers(clipped)

    def test_a_band_entirely_at_sea_is_dropped(self, land):
        """A stop far offshore has nothing to intersect, so the band disappears."""
        assert build_bands([(60.300, 25.300, 0)], land, bands=(600,)) == []

    def test_simplification_reduces_vertex_count(self):
        detailed = dict(build_bands(CENTRE, None, bands=(1800,), simplify_m=0))[1800]
        coarse = dict(build_bands(CENTRE, None, bands=(1800,), simplify_m=200))[1800]
        assert len(coarse.exterior.coords) < len(detailed.exterior.coords)


class TestBuildBandsWithRealJourney:
    """The end-to-end path: RAPTOR output -> bands, on the fixture network."""

    @pytest.fixture
    def journey(self, weekday_tt, stops_data):
        from transport_map.raptor import reachable

        coords = stops_data[2]
        return [
            (coords[stop][0], coords[stop][1], 1800 - left)
            for stop, left, _ in reachable(weekday_tt, coords["A1"], 28800, 1800)[0]
        ]

    def test_produces_three_nested_bands(self, journey, land):
        bands = build_bands(journey, land, bands=(600, 1200, 1800))
        assert [t for t, _ in bands] == [1800, 1200, 600]
        areas = [g.area for _, g in bands]
        assert areas[0] > areas[1] > areas[2]

    def test_clipping_removes_the_sea(self, journey, land):
        clipped = dict(build_bands(journey, land, bands=(1800,)))[1800]
        unclipped = dict(build_bands(journey, None, bands=(1800,)))[1800]
        assert unclipped.area - clipped.area > 1_000_000
        assert not clipped.contains(Point(*to_xy(60.171, 24.962)))  # A4 is offshore


class TestToGeoJson:
    @pytest.fixture
    def geojson(self, land):
        return to_geojson(build_bands(CENTRE, land, bands=(600, 1200, 1800)))

    def test_is_a_feature_collection(self, geojson):
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 3

    def test_properties_carry_both_units(self, geojson):
        assert [f["properties"] for f in geojson["features"]] == [
            {"max_seconds": 1800, "max_minutes": 30},
            {"max_seconds": 1200, "max_minutes": 20},
            {"max_seconds": 600, "max_minutes": 10},
        ]

    def test_geometry_is_always_multipolygon(self, geojson):
        """Even a single-polygon band is wrapped, so clients need only one code path."""
        assert all(f["geometry"]["type"] == "MultiPolygon" for f in geojson["features"])

    def test_coordinates_are_lon_lat_not_lat_lon(self, geojson):
        """GeoJSON is x,y -- longitude first. Getting this backwards puts Helsinki in
        the Arabian Sea, and nothing else in the pipeline would notice."""
        ring = geojson["features"][0]["geometry"]["coordinates"][0][0]
        lons = [lon for lon, _ in ring]
        lats = [lat for _, lat in ring]
        assert all(24 < lon < 26 for lon in lons)
        assert all(59 < lat < 61 for lat in lats)

    def test_rings_are_closed(self, geojson):
        for feature in geojson["features"]:
            for polygon in feature["geometry"]["coordinates"]:
                for ring in polygon:
                    assert ring[0] == ring[-1]

    def test_holes_are_preserved(self):
        """A ring of stops leaves an unreachable hole in the middle."""
        offsets = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        ring_of_stops = [
            (60.170 + 0.004 * dy, 24.920 + 0.008 * dx, 1500) for dx, dy in offsets
        ]
        bands = build_bands(ring_of_stops, None, bands=(1800,), simplify_m=1)
        polygons = to_geojson(bands)["features"][0]["geometry"]["coordinates"]
        assert any(len(rings) > 1 for rings in polygons)

    def test_empty_bands_give_an_empty_collection(self):
        assert to_geojson([]) == {"type": "FeatureCollection", "features": []}

    def test_output_is_json_serialisable(self, geojson):
        import json

        assert json.loads(json.dumps(geojson)) == geojson
