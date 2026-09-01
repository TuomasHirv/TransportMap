"""Tier 2 -- land.geojson -> a shapely geometry projected to metres."""

from transport_map import load_geojson
from transport_map.load_geojson import load_land
from transport_map.shared_func import to_xy


class TestLoadLand:
    def test_merges_the_features_into_one_geometry(self, land):
        """The fixture has two disjoint polygons, so the union is a MultiPolygon."""
        assert land.geom_type == "MultiPolygon"
        assert len(land.geoms) == 2

    def test_is_valid_and_non_empty(self, land):
        assert land.is_valid
        assert not land.is_empty
        assert land.area > 0

    def test_is_projected_to_metres_not_degrees(self, land):
        """Coordinates come back as metres, so they dwarf any lat/lon value."""
        minx, miny, maxx, maxy = land.bounds
        assert minx > 1_000_000
        assert miny > 1_000_000

    def test_projection_matches_the_shared_helper(self, land):
        """load_geojson and draw_isochrone must agree, or bands land in the wrong place."""
        minx, miny, _, _ = land.bounds
        x, y = to_xy(60.155, 24.890)  # the mainland polygon's south-west corner
        assert minx == round(x, 3) or abs(minx - x) < 1
        assert abs(miny - y) < 1

    def test_contains_the_mainland_stops_and_excludes_the_sea(self, land, stops_data):
        from shapely.geometry import Point

        _, _, coords = stops_data
        assert land.contains(Point(*to_xy(*coords["HUB_N"])))
        assert land.contains(Point(*to_xy(*coords["W1"])))
        assert not land.contains(Point(*to_xy(*coords["A4"])))
        assert not land.contains(Point(*to_xy(*coords["C3"])))


class TestPathArgument:
    def test_explicit_path_is_used(self, network_dir):
        assert load_land(network_dir / "land.geojson").geom_type == "MultiPolygon"

    def test_accepts_a_string_path(self, network_dir):
        assert load_land(str(network_dir / "land.geojson")).area > 0

    def test_falls_back_to_the_module_constant(self, monkeypatch, network_dir):
        monkeypatch.setattr(load_geojson, "LAND_GEOJSON", network_dir / "land.geojson")
        assert load_land().geom_type == "MultiPolygon"
