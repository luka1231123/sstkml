#!/usr/bin/env python3
"""Repair content/world.toml after the resolution doubling.

Three fixes:
  1. `[[sites]]` col/row were never doubled by tools/expand_map.py (it keyed on
     the `id = ` line, and sites have no id), so all 187 sites sit at half
     scale in the north-west quadrant. Double them.
  2. The doubling left sea glyphs inland — in the Western Desert, the
     Peloponnese, the Euphrates valley. Any water with no way to the ocean that
     is not a named lake becomes ground again.
  3. The rivers came through the doubling as 89 disconnected fragments. Erase
     every one and redraw each named river from real waypoints.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"

RIVER = "≈"
SEA = "~"

# Real courses, north to mouth, in (lon, lat). Sea cells are never overwritten,
# so a course that runs into water simply ends in a mouth.
COURSES = {
    "nile": [(32.90, 24.09), (32.88, 24.65), (32.75, 25.30), (32.64, 25.70),
             (32.10, 26.20), (31.75, 26.55), (31.30, 26.90), (31.18, 27.18),
             (30.85, 27.90), (30.75, 28.45), (30.85, 29.10), (31.10, 29.60),
             (31.22, 30.05)],
    "nile_rosetta": [(31.22, 30.05), (31.10, 30.40), (30.85, 30.80),
                     (30.55, 31.15), (30.40, 31.55)],
    "nile_damietta": [(31.22, 30.05), (31.35, 30.45), (31.55, 30.90),
                      (31.75, 31.20), (31.85, 31.55)],
    "murat": [(41.60, 38.95), (40.60, 38.90), (39.60, 38.80), (38.75, 38.75)],
    "euphrates": [(38.75, 38.75), (38.55, 38.20), (38.48, 37.58), (38.20, 37.20), (38.02, 36.83),
                  (38.05, 36.40), (38.12, 36.05), (38.60, 35.75),
                  (39.30, 35.30), (40.10, 34.80), (40.89, 34.55),
                  (41.60, 34.30), (42.40, 33.90), (42.83, 33.64),
                  (43.50, 33.40), (44.24, 33.06), (44.42, 32.54),
                  (44.90, 32.00), (45.30, 31.60), (45.64, 31.32),
                  (46.10, 30.96), (46.52, 30.60)],
    "tigris": [(40.22, 37.91), (40.90, 37.60), (41.60, 37.30), (42.30, 36.90),
               (43.15, 36.36), (43.26, 35.46), (43.60, 34.80), (44.00, 34.00),
               (44.36, 33.31), (44.90, 32.90), (45.40, 32.70), (45.82, 32.51),
               (46.40, 32.10), (46.52, 31.90)],
    "balikh": [(39.03, 36.86), (39.02, 36.50), (38.80, 36.10), (38.42, 35.93)],
    "khabur": [(40.80, 37.00), (40.87, 36.67), (40.75, 36.20), (40.60, 35.60),
               (40.42, 34.72)],
    "orontes": [(36.25, 34.10), (36.45, 34.40), (36.52, 34.57), (36.72, 34.90),
                (36.72, 35.14), (36.75, 35.60), (36.75, 35.95), (36.60, 36.20),
                (36.35, 36.35), (36.15, 36.20), (35.95, 36.09)],
    "jordan": [(35.63, 33.25), (35.59, 33.02), (35.57, 32.72), (35.55, 32.30),
               (35.53, 31.90), (35.55, 31.55)],
    "great_zab": [(44.30, 36.90), (43.90, 36.30), (43.60, 35.90),
                  (43.18, 35.97)],
    "little_zab": [(45.00, 36.00), (44.30, 35.50), (43.60, 35.25),
                   (43.33, 35.25)],
    "diyala": [(45.50, 34.40), (45.00, 33.90), (44.50, 33.35), (44.38, 33.28)],
    "maeander": [(30.50, 38.00), (29.50, 37.90), (28.50, 37.85),
                 (27.70, 37.75), (27.15, 37.66)],
    "hermus": [(29.00, 38.70), (28.00, 38.60), (27.20, 38.55), (26.80, 38.55)],
    "sangarius": [(31.50, 39.70), (30.80, 40.10), (30.40, 40.60),
                  (30.65, 41.00)],
    "peneios": [(21.40, 39.75), (22.00, 39.72), (22.40, 39.80), (22.70, 39.88)],
    "litani": [(35.95, 33.85), (35.75, 33.60), (35.40, 33.35), (35.20, 33.27)],
    "pyramus": [(36.90, 37.60), (36.30, 37.00), (35.85, 36.55)],
    "sarus": [(35.60, 38.00), (35.40, 37.30), (34.95, 36.72)],
    "halys": [(38.10, 39.30), (37.00, 39.20), (36.00, 39.00), (35.20, 39.10),
              (34.60, 39.60), (34.62, 40.02), (35.00, 40.40), (35.50, 40.90),
              (35.80, 41.00)],
}

# A fragment smaller than this that no redrawn course touches is doubling
# debris, not a stream.
SPECK = 8

# Water with no way to the ocean. Anything in this list is a real lake and
# stays; every other landlocked sea patch is doubling debris and becomes
# ground. (lon_min, lon_max, lat_min, lat_max)
LAKES = [
    (32.0, 43.5, 12.0, 30.2),   # Red Sea, Gulf of Suez, Gulf of Aqaba
    (26.5, 30.0, 40.0, 41.0),   # Sea of Marmara
    (42.2, 43.5, 38.2, 38.9),   # Lake Van
    (33.0, 33.9, 38.4, 39.1),   # Tuz Golu
    (30.3, 31.1, 29.2, 29.6),   # Lake Moeris, the Faiyum
    (35.3, 35.7, 31.1, 31.9),   # the Dead Sea
]


def main():
    text = SRC.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    terrain = data["terrain"]
    grid = [list(r) for r in terrain["rows"]]
    H, W = len(grid), len(grid[0])
    west, north = terrain["west"], terrain["north"]
    step_lon, step_lat = terrain["step_lon"], terrain["step_lat"]

    def cell(lon, lat):
        return int(round((lon - west) / step_lon)), int(round((north - lat) / step_lat))

    # ── 1. Sites: double col/row ──────────────────────────────────────────
    site_count = 0

    def double_site_block(m):
        nonlocal site_count
        site_count += 1
        block = m.group(0)
        block = re.sub(r'^col = (\d+)$',
                       lambda n: f"col = {int(n.group(1)) * 2}", block,
                       flags=re.MULTILINE)
        block = re.sub(r'^row = (\d+)$',
                       lambda n: f"row = {int(n.group(1)) * 2}", block,
                       flags=re.MULTILINE)
        return block

    text = re.sub(r'^\[\[sites\]\]\n(?:(?!^\[).*\n?)*', double_site_block,
                  text, flags=re.MULTILINE)
    print(f"Sites: col/row doubled for {site_count} blocks")

    # ── 2. Landlocked sea ─────────────────────────────────────────────────
    # The doubling left sea glyphs in the Western Desert, the Peloponnese and
    # the Euphrates valley. Anything that cannot reach the ocean and is not a
    # named lake goes back to being ground.
    sea = {(c, r) for r in range(H) for c in range(W) if grid[r][c] == SEA}
    seen, filled = set(), 0
    for start in sea:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            c, r = stack.pop()
            comp.append((c, r))
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c + dc, r + dr)
                if n in sea and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if any(c == 0 or c == W - 1 or r == 0 or r == H - 1 for c, r in comp):
            continue                              # opens onto the map edge
        lons = [west + c * step_lon for c, _ in comp]
        lats = [north - r * step_lat for _, r in comp]
        if any(a <= min(lons) and max(lons) <= b and c <= min(lats)
               and max(lats) <= d for a, b, c, d in LAKES):
            continue                              # a real lake
        for c, r in comp:
            ring = [grid[r + dr][c + dc]
                    for dr in (-2, -1, 0, 1, 2) for dc in (-2, -1, 0, 1, 2)
                    if 0 <= r + dr < H and 0 <= c + dc < W
                    and grid[r + dr][c + dc] not in (SEA, RIVER)]
            grid[r][c] = max(set(ring), key=ring.count) if ring else "."
            filled += 1
    print(f"Landlocked sea filled: {filled} cells")

    # ── 3. Rivers ─────────────────────────────────────────────────────────
    # Erase first. The old courses do not lie on the new ones, so painting over
    # them would leave every river braided into two channels.
    wiped = 0
    for r in range(H):
        for c in range(W):
            if grid[r][c] != RIVER:
                continue
            ring = [grid[r + dr][c + dc]
                    for dr in (-3, -2, -1, 0, 1, 2, 3)
                    for dc in (-3, -2, -1, 0, 1, 2, 3)
                    if 0 <= r + dr < H and 0 <= c + dc < W
                    and grid[r + dr][c + dc] not in (SEA, RIVER)]
            grid[r][c] = max(set(ring), key=ring.count) if ring else "."
            wiped += 1
    print(f"Old river cells erased: {wiped}")

    drawn = set()
    for name, pts in COURSES.items():
        painted = 0
        for (lon_a, lat_a), (lon_b, lat_b) in zip(pts, pts[1:]):
            ca, ra = cell(lon_a, lat_a)
            cb, rb = cell(lon_b, lat_b)
            steps = max(abs(cb - ca), abs(rb - ra), 1) * 2
            for i in range(steps + 1):
                c = int(round(ca + (cb - ca) * i / steps))
                r = int(round(ra + (rb - ra) * i / steps))
                if not (0 <= r < H and 0 <= c < W):
                    continue
                if grid[r][c] == SEA:
                    continue
                grid[r][c] = RIVER
                drawn.add((c, r))
                painted += 1
        print(f"  {name:16s} {painted:4d} cells")

    # Drop debris: river fragments too small to be a stream that no course uses.
    cells = {(c, r) for r in range(H) for c in range(W) if grid[r][c] == RIVER}
    seen, removed = set(), 0
    for start in cells:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            c, r = stack.pop()
            comp.append((c, r))
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    n = (c + dc, r + dr)
                    if n in cells and n not in seen:
                        seen.add(n)
                        stack.append(n)
        if len(comp) <= 2 or (len(comp) < SPECK and not (set(comp) & drawn)):
            for c, r in comp:
                # Debris sits on ground that was sown or dry before the river
                # was painted over it; give it back as dry.
                grid[r][c] = "."
                removed += 1
    print(f"Debris cells cleared: {removed}")

    new_rows = "rows = [\n" + "\n".join(
        f'    "{"".join(r)}",' for r in grid) + "\n]"
    text = re.sub(r'^rows = \[(?:[^\]]*)\]', lambda _: new_rows, text,
                  count=1, flags=re.MULTILINE | re.DOTALL)

    SRC.write_text(text, encoding="utf-8")
    print("Written.")


if __name__ == "__main__":
    main()
