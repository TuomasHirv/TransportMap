# Test fixtures

Hand-built synthetic GTFS feeds. The real feed in `backend/data/` is unusable as a
test input (`stop_times.csv` is ~982 MB / 11 M rows) and is gitignored, so nothing
here is derived from it — but the column layouts, the UTF-8 BOM on `stop_times.csv`,
the space-padded empty `parent_station` values and the `24:xx:xx` after-midnight
times all mirror it exactly.

**Every stop and every trip below exists to pin one specific behaviour.** All numbers
in this file were produced by running the actual code, not estimated. If you change a
coordinate or a time, re-derive the tables here.

```
network/    the main feed: stops, stop_times, trips, calendar, routes, land
unsorted/   stop_times.csv only, with two trips' rows interleaved
```

Load them through the fixtures in [`../conftest.py`](../conftest.py) rather than by
path, so the reference dates below are applied for you.

---

## Reference dates

The calendar window is `20260831`–`20261024`. `build_datamodel` falls back to
`date.today()`, which would silently empty every timetable once that window passes, so
tests pass `on=` explicitly (`conftest.REFERENCE_DATES`):

| day_type | date | weekday | prev-day flag |
|---|---|---|---|
| `weekday` | 2026-09-02 | Wednesday | Tuesday |
| `saturday` | 2026-09-05 | Saturday | Friday |
| `sunday` | 2026-09-06 | Sunday | Saturday |

---

## `network/stops.csv` — 30 rows

`load_stops()` returns **29** coords: `ST1` is `location_type=1` and is dropped as a
station rather than a boarding point. `parents == {"P_A": "ST1", "P_B": "ST1"}`.

Only **27** of those 29 end up in `Timetable.stops` — a stop enters the timetable only
by being served by a trip. `Z1` and `X1` are served by nothing.

| stop_id | name | lat | lon | pins |
|---|---|---|---|---|
| `A1` | Alfaranta | 60.171 | 24.918 | Line A west end |
| `A2` | Beetakuja | 60.171 | 24.929 | 609 m from `A1` → **no** footpath |
| `HUB_N` | `Töölö, Keskus` | 60.171 | 24.940 | quoted name with comma + umlauts |
| `A3` | Deltatori | 60.171 | 24.951 | |
| `A4` | Epsilonranta | 60.171 | 24.962 | outside the land polygon ("sea") |
| `B1` | Zetalahti | 60.164 | 24.940 | Line B south end |
| `HUB_S` | `Keskus, etelä` | 60.169 | 24.940 | 222.6 m → **167 s** walk to `HUB_N` |
| `B2` | Eetantie | 60.174 | 24.940 | |
| `B3` | Ääninen | 60.179 | 24.940 | |
| `T2` | `Eetantie (vastapäätä)` | 60.174 | 24.9405 | 27.7 m from `B2` → 21 s raw, **clamped to 60 s** |
| `C1` | Iotakatu | 60.179 | 24.943 | 166 m → **125 s** walk from `B3` |
| `C2` | Kappalanmäki | 60.179 | 24.954 | |
| `C3` | Lambdaniemi | 60.179 | 24.965 | reached in **round 2** (ride A → walk to `T2` → ride C); "sea" |
| `ST1` | Myy-asema | 60.170 | 24.9545 | `location_type=1` → **dropped by `load_stops`** |
| `P_A` | `Myy-asema, laituri 1` | 60.170 | 24.950 | 498 m from `P_B` — **past the 400 m radius** |
| `P_B` | `Myy-asema, laituri 2` | 60.170 | 24.959 | linked to `P_A` **only** by the same-parent override |
| `D1` | Nyytori | 60.165 | 24.950 | Line D |
| `E1` | Ksitie | 60.165 | 24.959 | Line E; "sea" |
| `F1` | Theetaniemi | 60.1798 | 24.9668 | **134 m from `C3` → 100 s**; next nearest stop is 714 m away |
| `F2` | Khiiranta | 60.1798 | 24.9780 | 620 m from `F1` — a ride hop, **no** footpath |
| `F3` | Psiilahti | 60.1798 | 24.9890 | needs **round 3**; nothing within 400 m |
| `W1` | Omikronpää | 60.160 | 24.900 | walk chain, no footpath to anything outside it |
| `W2` | Piikuja | 60.160 | 24.9063 | 349 m hops → **262 s** |
| `W3` | Rhoranta | 60.160 | 24.9126 | `W1↔W3` = 524 s ≤ 600 → **closure creates it** |
| `W4` | Sigmalahti | 60.160 | 24.9189 | `W1↔W4` = 786 s > 600 → closure must **not** |
| `L1` | Tautori | 60.165 | 24.930 | loop terminus, positions `[0, 4]` |
| `L2` | Ypsilonpuisto | 60.165 | 24.920 | **visited twice**, positions `[1, 3]` |
| `L3` | Fiikuja | 60.157 | 24.928 | loop turn point |
| `Z1` | Omegasaari | 60.300 | 25.300 | served by nothing → **never in `tt.stops`** |
| `X1` | Ei liikennettä | 60.171 | 24.9401 | 6 m from `HUB_N`, served by nothing — see *Known quirks* |

The whole **L line is deliberately footpath-free**, and the **W chain is deliberately
isolated** from every other cluster, so closure assertions on them cannot be
contaminated by a neighbour.

---

## Footpaths — the complete weekday table

18 undirected edges, after `build_footpaths` (400 m radius, `min_transfer=60`) *and*
`close_footpaths` (transitive closure capped at `MAX_WALK_SECONDS=600`). This is the
whole graph — anything not listed must be **absent**.

| a | b | seconds | how it arises |
|---|---|---|---|
| `B2` | `T2` | **60** | 27.7 m, raw 21 s → **clamped to `min_transfer`** |
| `A3` | `P_A` | 93 | direct |
| `C3` | `F1` | 100 | direct — the only link between line C and line F |
| `B3` | `C1` | 125 | direct |
| `A4` | `P_B` | 150 | direct |
| `HUB_N` | `HUB_S` | 167 | direct |
| `B2` | `HUB_N` | 251 | direct |
| `HUB_N` | `T2` | 252 | direct |
| `W1` | `W2` | 262 | direct |
| `W2` | `W3` | 262 | direct |
| `W3` | `W4` | 262 | direct |
| `P_A` | `P_B` | **375** | 498 m apart — **same-parent override**, not the radius |
| `B2` | `HUB_S` | 418 | closure via `HUB_N` (251 + 167) |
| `HUB_S` | `T2` | 419 | closure via `HUB_N` (167 + 252) |
| `A3` | `P_B` | 468 | closure via `P_A` (93 + 375) |
| `W1` | `W3` | **524** | closure via `W2` (262 + 262) — under the 600 s cap |
| `W2` | `W4` | 524 | closure via `W3` |
| `A4` | `P_A` | 525 | closure via `P_B` (150 + 375) |

Must be **absent**: `W1↔W4` (786 s > 600 s cap), `A1↔A2` (609 m > 400 m),
`F1↔F2` (620 m), `L1/L2/L3` to anything, `HUB_N↔X1` (`X1` is not in `tt.stops`),
everything touching `Z1`.

Adding line F shifted `build_footpaths`' global mean latitude from 60.16875 to 60.16994;
every second in this table was re-measured afterwards and none of them moved.

Assert derived walk seconds with a small tolerance (`abs=2`) — they come from
`round(d / WALK_SPEED)` over a float projection. The **60 s** clamp is exact.

---

## `network/calendar.csv` — 7 services

| service_id | days | window | pins |
|---|---|---|---|
| `SVC_WED` | wednesday | 20260831–20261024 | the weekday service |
| `SVC_TUE` | tuesday **only** | 20260831–20261024 | prev-day for weekday |
| `SVC_SAT` | saturday | 20260831–20261024 | |
| `SVC_SUN` | sunday | 20260831–20261024 | |
| `SVC_FRI` | friday **only** | 20260831–20261024 | prev-day for saturday |
| `SVC_DAILY` | all seven | 20260831–20261024 | appears in all three day types |
| `SVC_EXPIRED` | wednesday | **20200101–20201231** | outside the window → always excluded |

`SVC_TUE` must be Tuesday-and-not-Wednesday: `service_id_for_day` `continue`s past the
prev-day check for any service already matched by the main day flag, so a
Tuesday+Wednesday service would never land in the prev-day set.

`service_id_for_day(day, on=REFERENCE_DATES[day])` returns:

| day | service_ids | prev_day_service_ids |
|---|---|---|
| weekday | `SVC_WED`, `SVC_DAILY` | `SVC_TUE` |
| saturday | `SVC_SAT`, `SVC_DAILY` | `SVC_FRI` |
| sunday | `SVC_SUN`, `SVC_DAILY` | `SVC_SAT` |

---

## `network/trips.csv` + `stop_times.csv` — 23 trips, 98 stop_time rows

Previous-day trips keep their **original trip_id** (they used to gain a `_prev` suffix).
That is deliberate: `finalize_timetable` names each route via
`trip_id_shortname[trip_id]`, and a suffixed id would miss that lookup and leave night
routes unnamed.

Patterns (a "route" is an *exact* stop sequence, per the RAPTOR paper):

| pattern | stops |
|---|---|
| A-out | `A1 A2 HUB_N A3 A4` |
| A-ret | `A4 A3 HUB_N A2 A1` |
| B | `B1 HUB_S B2 B3` |
| C | `T2 C1 C2 C3` |
| D | `D1 P_A` |
| E | `P_B E1` |
| L | `L1 L2 L3 L2 L1` |
| W | `W1 W2 W3 W4` |
| F | `F1 F2 F3` |

| trip_id | pattern | service | times | pins |
|---|---|---|---|---|
| `A_0800` | A-out | WED | 08:00 +4 min hops | baseline |
| `A_0805` | A-out | WED | 08:05 +2 min hops | **overtakes `A_0800`** → separate route |
| `A_0830` | A-out | WED | 08:30 +4 min | groups with `A_0800` |
| `A_R_0800` | A-ret | WED | 08:00 +4 min | same stop *set*, reversed → **its own route** |
| `B_0810` / `B_0840` | B | WED | 08:10 / 08:40, +3 min | transfer leg |
| `C_0820` / `C_0850` | C | WED | 08:20 / 08:50, +3 min | round-3 leg |
| `D_0800` | D | WED | 08:00 → 08:05 | |
| `E_0822` | E | WED | 08:22 → 08:27 | late enough to be **caught** after the `P_A→P_B` walk |
| `L_0800` | L | WED | 08:00 → 08:14 | loop |
| `W_0800` | W | WED | 08:00 +4 min | puts the W stops into `tt.stops` |
| `F_0833` | F | WED | 08:33 → 08:41 | **only catchable in round 3**, after riding C to `C3` and walking 100 s |
| `C_2350_TUE` | C | TUE | 23:50 → **24:35** | shifted −86400; still running at 00:05, so a night trip that can actually be **boarded** |
| `A_2350_WED` | A-out | WED | 23:50 → **24:06** | same-day trip whose times exceed 86400 |
| `B_2345_TUE` | B | TUE | 23:45 → **24:03** | shifted **−86400** (first dep `-900`) |
| `A_2200_TUE` | A-out | TUE | 22:00 → 22:16 | ends **before** 86400 → **must be dropped** |
| `A_1000_SAT` / `B_1010_SAT` | A-out / B | SAT | 10:00 / 10:10 | |
| `A_2350_FRI` | A-out | FRI | 23:50 → 24:06 | prev-day carry-over for **saturday** (first dep `-600`) |
| `A_1200_SUN` | A-out | SUN | 12:00 | |
| `B_1200_DAILY` | B | DAILY | 12:00 | present in **all three** day types |
| `A_0900_EXPIRED` | A-out | EXPIRED | 09:00 | present in **no** day type |

`parse_time("24:06:00") == 86760`.

### What each day type builds

| day | routes | trips | prev-day trips (first departure) |
|---|---|---|---|
| weekday | **10** | **17** | `B_2345_TUE` at `-900`, `C_2350_TUE` at `-600` |
| saturday | 2 | 4 | `A_2350_FRI` at `-600` |
| sunday | 2 | 2 | none (Saturday's trips end before midnight) |

On weekday the A-out pattern splits into **two** routes — `[A_0800, A_0830, A_2350_WED]`
and `[A_0805]` — because `A_0805` departs later and arrives earlier. A-ret is a third,
separate route. The C pattern stays **one** route: its three trips
(`-600`, `30000`, `31800`) are monotone at every stop.

Loop route: `positions("L2") == [1, 3]`, `positions("L1") == [0, 4]`.

---

## `network/routes.csv` — 7 rows

Supplies the short name riders actually see. Two hops:
`routename_to_shortname` gives route_id → short_name, then `tripname_to_shortname`
joins through `trips.csv` to give trip_id → short_name, which
`finalize_timetable` uses to name each `Route` (from the **first trip of the group**).

| route_id | short_name | pins |
|---|---|---|
| `A` | `1` | one name across **three** `Route` objects — the A-out overtaking split plus A-ret |
| `B` | `2` | |
| `C` | `3` | |
| `D` | `4H` | **two route_ids sharing a short name** — the real feed duplicates `H` the same way |
| `E` | `4H` | so anything keyed on the name merges lines D and E |
| `F` | `5` | |
| `L` | `6` | |
| `W` | *(no row)* | a route_id absent from routes.csv → `Route.short_name == ""` |

Consequences: `routename_to_shortname` → **7** entries; `tripname_to_shortname` → **22**
of the 23 trips, because its `if route_id in routename_shortname` guard drops `W_0800`;
and line W's route ends up unnamed, surfacing in the API as an `{"": ...}` key.

### `upcoming` — lines catchable within 15 minutes

`lines_nearby(tt, walkable_stops, at, at + 900)` → `{short_name: departure_second}`,
over the stops walkable from the source (round 0), **not** the whole reachable set.

| from | at | result |
|---|---|---|
| `A1` | 08:00 | `{"1": 28800}` |
| `HUB_N` (walks to `HUB_S`, `B2`, `T2`) | 08:00 | `{"1": 29280, "2": 29580}` — 08:08 and 08:13 |
| `A3` | 07:56 | `{"1": 29040}` — **08:04 via A-ret**, not the 08:11 A-out departure |
| `C3` | 08:15 | `{}` — `C3` is where line 3 **ends** |
| `D1` + `P_B` | 08:00 | `{"4H": 28800}` — D and E share a name; the earlier wins |
| `W1` | 08:00 | `{"": 28800}` — line W has no routes.csv row |
| `C1` | 00:00 | `{"3": 300}` — boards the previous-day night trip |

The A3 and C3 rows are regression pins: `lines_nearby` used to keep the *first*
departure it encountered rather than the earliest, and used to advertise boarding at a
route's final stop.

---

## `network/land.geojson`

Two disjoint CRS84 polygons, so `load_land()` returns a **MultiPolygon**:

- mainland `lon 24.890–24.955, lat 60.155–60.185`
- an island at `lon 24.975–24.995, lat 60.168–60.176`

`A4`, `C3`, `P_B` and `E1` (lon ≥ 24.959) fall in the sea, so `build_bands`'
`intersection(land)` genuinely clips instead of being a no-op: for the reference
journey below, the 1800 s band loses **3 056 569 m²** compared with `land=None`.

---

## Reference journeys (weekday timetable)

From `A1` at 08:00 with a 1800 s budget — **15 stops**:

| stop | arrival | how |
|---|---|---|
| `A1` | 08:00:00 | source |
| `A2` | 08:04:00 | ride A |
| `HUB_N` | 08:08:00 | ride A |
| `HUB_S` | 08:10:47 | walk 167 s from `HUB_N` |
| `A3` | 08:11:00 | ride `A_0805` |
| `B2` | 08:12:11 | ride B from `HUB_S` … then walk |
| `T2` | 08:12:12 | walk 60 s from `B2` |
| `P_A` | 08:12:33 | walk 93 s from `A3` |
| `A4` | 08:13:00 | ride `A_0805` |
| `P_B` | 08:15:30 | **walk 375 s — the same-parent override** |
| `B3` | 08:19:00 | ride B |
| `C1` | 08:21:05 | walk 125 s from `B3` |
| `C2` | 08:26:00 | ride C |
| `E1` | 08:27:00 | ride `E_0822` — reachable **only** via the `P_A→P_B` override |
| `C3` | 08:29:00 | ride C — **round 2** (ride A, walk to `T2`, ride C) |

With a 1700 s budget `C3` drops out.

### Rounds — from `A1` @08:00 with a **3600 s** budget

`max_rounds` only bites once line F is in play; everything else settles by round 2.

| max_rounds | stops | newly reached |
|---|---|---|
| 1 | 10 | `A1 A2 A3 A4 HUB_N HUB_S B2 T2 P_A P_B` — one ride plus footpath relaxation |
| 2 | 16 | `B3 C1 C2 C3 E1 F1` |
| **3** | **18** | **`F2 F3`** — only reachable by ride A → walk → ride C → walk 100 s → ride F |
| 4 | 18 | nothing; the scan has converged |

`F1` 08:30:40, `F2` 08:37:00, `F3` 08:41:00.

### Night trip — from `C1` at `at=0` with a 2400 s budget

The one journey that boards a **previous-day** trip. `C_2350_TUE` passes `C1` at
00:05 and `C3` at 00:35:

| stop | arrival |
|---|---|
| `C1` | 00:00:00 (source) |
| `B3` | 00:02:05 (walk 125 s) |
| `C2` | 00:20:00 |
| `C3` | 00:35:00 |
| `F1` | 00:36:40 (walk 100 s) |

`B_2345_TUE` is deliberately *not* boardable — its last departure is at `-180`, and
the endpoints reject `at < 0`. It exists to pin the −86400 shift itself.

Other useful sources:

- `D1` @08:00/1800 s → 6 stops, ending `E1` at 08:27 — the pure D → walk → E journey.
- `W1` @08:00/1800 s → exactly `W1 W2 W3 W4`; nothing leaks in or out.
- `L1` @08:00/1800 s → `L1 L2 L3`; `L1` stays at 08:00 because the loop's return at
  08:14 does not improve on the source time.
- Anything far offshore (e.g. `(59.0, 20.0)`) → no walkable stops.

---

## `unsorted/stop_times.csv`

`parse_routes` groups rows with `itertools.groupby`, which only groups *adjacent* rows.
This file interleaves `A_0800` and `A_0805`, so parsing it yields **10 single-event
groups instead of 2 five-event trips** — silently, with no error. It exists to document
that contiguity is a hard input requirement. (The real feed does satisfy it: 22 367
trips with 0 breaks across a 500 k-row sample.)

---

## Known quirks the fixtures deliberately expose

These are pinned so a future test makes a deliberate decision about them.

1. **`getNearby` scans `tt.coords`, not `tt.stops`.** It walks every coordinate,
   including stops no trip serves. `X1` sits 6 m from `HUB_N` and is served by nothing:
   `reachable(tt, coords["HUB_N"], …)` returns it at 08:00:04 even though
   `"X1" not in tt.stops`. `Z1` pins the complement — it is correctly absent from
   `tt.stops` and, being 30 km away, never surfaces.
2. **`reachable` has an inconsistent return type.** It returns `{}` (a dict) when no
   stop is within walking range of the source, but a `set` of `(stop, seconds_left,
   name)` triples otherwise. Both happen to iterate empty, so the API endpoints work.
3. **`tt.transfer_time` is never populated.** It is a `defaultdict(int)`, so the
   boarding penalty at every stop is 0.
