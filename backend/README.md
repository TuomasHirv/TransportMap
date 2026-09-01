# Transport Map — backend

A FastAPI service that answers "where can I get to from here, in this much time?" for a
public transport network, using [RAPTOR](https://www.microsoft.com/en-us/research/wp-content/uploads/2012/01/raptor_alenex.pdf)
(Delling, Pajor, Werneck) as a round-based one-to-all earliest-arrival scan.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /reachable?lat=&lon=&at=&budget=&day=` | Every stop reachable from the point, with its arrival time and remaining budget |
| `GET /isochrone?lat=&lon=&at=&budget=&day=` | The same stops, plus GeoJSON isochrone bands clipped to the coastline |

`at` is seconds after midnight (0 to 30 h, leaving room for trips that run past midnight),
`budget` is seconds, and `day` is `weekday`, `saturday` or `sunday`.

## Data

The service reads a GTFS-style feed from `data/`: `stops.csv`, `stop_times.csv`,
`trips.csv`, `calendar.csv`, plus a `land.geojson` coastline used to keep isochrones out
of the sea. Those files are gitignored — `stop_times.csv` alone is roughly 1 GB — so you
need to supply your own feed.

Timetables are built once per day type at startup. Trips are grouped into routes sharing
an identical stop sequence, split where they overtake, and walking transfers within 400 m
are generated and transitively closed up to a 10 minute walking limit. Tunables live in
`src/transport_map/config.py`.

## Running

```sh
uv sync
uv run uvicorn transport_map.api:app --reload
```

Startup parses the whole feed, which takes a while on a full-size dataset.

## Tests

```sh
uv run pytest
uv run ruff check src tests
```

The suite runs entirely against a small synthetic feed in `tests/fixtures/` and never
reads `data/`, so it works on a fresh clone. Every expected value in those tests is
documented and derived in [tests/fixtures/README.md](tests/fixtures/README.md).
