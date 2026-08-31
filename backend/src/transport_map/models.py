from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass
class Route:
    """A set of trips sharing the *exact* same stop sequence (paper's def.)."""
 
    id: str
    stops: list[str]
    # trips[t][i] = (arrival, departure) of trip t at the i-th stop of the route.
    trips: list[list[tuple[int, int]]] = field(default_factory=list)
 
    # index built by Timetable.finalize()
    _stop_pos: dict[str, list[int]] = field(default_factory=dict, repr=False)
    _deps: list[list[int]] = field(default_factory=list, repr=False)
 
    def positions(self, stop: str) -> list[int]:
        """All indices at which `stop` occurs (a loop route may repeat one)."""
        return self._stop_pos.get(stop, [])
 
    def earliest_trip(self, pos: int, time: int) -> int | None:
        """Index of the first trip departing position `pos` at or after `time`."""
        deps = self._deps[pos]
        t = bisect_left(deps, time)
        return t if t < len(deps) else None
 
 
class Timetable:
    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.stops: set[str] = set()
        # stop -> list of (route_id, position within that route)
        self.routes_by_stop: dict[str, list[tuple[str, int]]] = defaultdict(list)
        # stop -> list of (stop, walking seconds); must be transitively closed
        self.footpaths: dict[str, list[tuple[str, int]]] = defaultdict(list)
        # minimum time to change vehicles at a stop
        self.transfer_time: dict[str, int] = defaultdict(int)
        # Coordinates for every stop: {(stop_id): (latitude, longitude)}
        self.coords: dict[str] = {}
        # Stop names by stop_id.
        self.stop_names: dict[str] = {}
 
    # -- construction ------------------------------------------------------
 
    def add_route(self, route_id: str, stops: Sequence[str],
                  trips: Iterable[Sequence[tuple[int, int]]]) -> None:
        trips = [list(t) for t in trips]
        for t in trips:
            assert len(t) == len(stops), "trip must have one event per route stop"
        self.routes[route_id] = Route(route_id, list(stops), trips)
        self.stops.update(stops)
 
    def add_footpath(self, a: str, b: str, seconds: int, both: bool = True) -> None:
        self.footpaths[a].append((b, seconds))
        if both:
            self.footpaths[b].append((a, seconds))
        self.stops.update((a, b))
 
    def finalize(self) -> Timetable:
        """Build the scan indices. Call once, after all routes are added."""
        self.routes_by_stop = defaultdict(list)
        for r in self.routes.values():
            # non-overtaking assumption: sort trips by departure at first stop
            r.trips.sort(key=lambda tr: tr[0][1])
            r._stop_pos = defaultdict(list)
            for i, s in enumerate(r.stops):
                r._stop_pos[s].append(i)
                self.routes_by_stop[s].append((r.id, i))
            r._deps = [[tr[i][1] for tr in r.trips] for i in range(len(r.stops))]
        # every stop can always "walk" to itself in zero time
        for s in self.stops:
            if not any(q == s for q, _ in self.footpaths[s]):
                self.footpaths[s].append((s, 0))
        return self

