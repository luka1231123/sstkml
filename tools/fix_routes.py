#!/usr/bin/env python3
"""Recompute route modes via Bresenham line terrain analysis.

Mode determined by terrain crossed: sea if >30% sea cells, river if >20% river
cells (and neither endpoint in sea), else land.
Legs/risk recalculated from haversine distance + terrain.
"""
import math, re, tomllib

ROOT = "/Users/rexvlapt/Programming/sttkml/content"
TOML = f"{ROOT}/world.toml"

STEP_LON = 0.040
STEP_LAT = 0.0675
ORIGIN_LON = 21.00
ORIGIN_LAT = 41.00


def lon(col): return ORIGIN_LON + col * STEP_LON
def lat(row): return ORIGIN_LAT - row * STEP_LAT


def haversine(lon1, lat1, lon2, lat2):
    R = 6371
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def bresenham(c0, r0, c1, r1):
    """All cells on straight line (c0,r0)→(c1,r1), endpoints included."""
    cells = []
    dc, dr = abs(c1 - c0), abs(r1 - r0)
    sc = 1 if c1 >= c0 else -1
    sr = 1 if r1 >= r0 else -1
    err = dc - dr
    ci, ri = c0, r0
    while True:
        cells.append((ci, ri))
        if (ci, ri) == (c1, r1):
            break
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            ci += sc
        if e2 < dc:
            err += dc
            ri += sr
    return cells


def classify_mode(grid, c0, r0, c1, r1):
    """Classify route mode by terrain along Bresenham line."""
    cells = bresenham(c0, r0, c1, r1)
    if not cells:
        return "land"
    counts = {"~": 0, "≈": 0, ";": 0, ",": 0, ".": 0, "^": 0, ":": 0}
    for c, r in cells:
        ch = grid[r][c]
        counts[ch] = counts.get(ch, 0) + 1
    total = len(cells)
    sea_ratio = counts["~"] / total
    river_ratio = (counts["≈"] + counts[";"]) / total

    if sea_ratio > 0.30:
        return "sea"
    if river_ratio > 0.20:
        return "river"
    return "land"


def main():
    raw = open(TOML, "rb").read()
    data = tomllib.loads(raw.decode())
    grid = data["terrain"]["rows"]

    alus = {p["id"]: p for p in data["places"] if p.get("kind") == "alu"}
    print(f"Alus: {len(alus)}")

    routes = data.get("routes", [])
    print(f"Existing routes: {len(routes)}")

    changes = {"land": 0, "sea": 0, "river": 0}
    seen = set()
    new_routes = []
    for r in routes:
        a_id, b_id = r["a"], r["b"]
        pair = (a_id, b_id)
        if pair in seen:
            continue
        seen.add(pair)
        if a_id not in alus or b_id not in alus:
            new_routes.append(r)
            continue
        a, b = alus[a_id], alus[b_id]
        mode = classify_mode(grid, a["col"], a["row"], b["col"], b["row"])

        km = haversine(lon(a["col"]), lat(a["row"]), lon(b["col"]), lat(b["row"]))
        leg_km = 98 if mode == "land" else 170
        detour = 1.25 if mode == "land" else 1.0
        dist = km * detour
        legs = max(1, round(dist / leg_km))
        risk = int(40 + dist // (3 if mode == "land" else 6))
        seasonal = mode != "land"

        old_mode = r.get("mode", "?")
        if old_mode != mode:
            changes[old_mode] = changes.get(old_mode, 0) - 1
            changes[mode] = changes.get(mode, 0) + 1

        new_routes.append({
            "a": a_id,
            "b": b_id,
            "legs": legs,
            "mode": mode,
            "seasonal": seasonal,
            "risk": risk,
        })

    print(f"Mode changes: {changes}")

    # Count by mode
    modes = {}
    for r in new_routes:
        m = r["mode"]
        modes[m] = modes.get(m, 0) + 1
    print(f"New mode counts: {modes}")

    # ── Write back ──
    out = raw.decode()
    # Build new routes TOML
    route_lines = []
    for r in new_routes:
        route_lines.append(f"[[routes]]")
        route_lines.append(f'a = "{r["a"]}"')
        route_lines.append(f'b = "{r["b"]}"')
        route_lines.append(f'legs = {r["legs"]}')
        route_lines.append(f'mode = "{r["mode"]}"')
        route_lines.append(f'seasonal = {"true" if r["seasonal"] else "false"}')
        route_lines.append(f'risk = {r["risk"]}')

    new_routes_text = "\n".join(route_lines) + "\n"

    # Remove all existing [[routes]] sections
    lines = out.split("\n")
    clean_lines = []
    skip = False
    for line in lines:
        if line.startswith("[[routes]]"):
            skip = True
        elif skip and line.startswith("[[") and "routes" not in line:
            skip = False
        elif not skip and line.startswith("[[") and line.strip() != "[[routes]]":
            skip = False
        if not skip:
            clean_lines.append(line)

    # Also handle the case where routes are the last section
    out = "\n".join(clean_lines)
    # Remove trailing whitespace
    out = out.rstrip() + "\n\n"
    # Append new routes
    out += new_routes_text

    open(TOML, "w").write(out)
    print("Written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
