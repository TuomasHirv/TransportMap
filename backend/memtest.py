import logging
logging.basicConfig(level=logging.INFO)

from transport_map.parse_routes import parse_routes_to_trips
# from transport_map.<your calendar module> import <your set builder>

allowed = ...          # <- the one line to fill in

trips = parse_routes_to_trips(allowed)
print(f"trips: {len(trips)}")

for path in ("/sys/fs/cgroup/memory.peak",
             "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
             "/sys/fs/cgroup/memory.current"):
    try:
        with open(path) as fh:
            print(f"{path.rsplit('/', 1)[-1]}: {int(fh.read()) / 1e6:.1f} MB")
        break
    except OSError:
        continue