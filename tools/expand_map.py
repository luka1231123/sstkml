"""Double terrain resolution to fit all settlements; add routes for all.

Approach: read world.toml as text, do targeted replacements.
Terrain: each cell → 2x2 block, step halved.
Coordinates: all col/row doubled.
Routes: generated for unreachable settlements + intra-region links.
"""

import sys, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"


def lon(col): return 21.00 + col * 0.040  # halved step
def lat(row): return 41.00 - row * 0.0675  # halved step


def haversine(lon1, lat1, lon2, lat2):
    R = 6371
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def is_sea(grid, col, row):
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[0]):
        return True
    return grid[row][col] == "~"


def route_mode(grid, a, b):
    """land / sea / river."""
    a_sea = is_sea(grid, a["col"], a["row"])
    b_sea = is_sea(grid, b["col"], b["row"])
    if not a_sea and not b_sea:
        return "land"
    if a_sea and b_sea:
        steps = max(abs(b["col"] - a["col"]), abs(b["row"] - a["row"]), 1)
        river_count = 0
        for i in range(steps + 1):
            c = int(a["col"] + (b["col"] - a["col"]) * i / steps)
            r = int(a["row"] + (b["row"] - a["row"]) * i / steps)
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] == "≈":
                river_count += 1
        return "river" if river_count > steps * 0.3 else "sea"
    return "sea"


def make_route(grid, a, b):
    km = haversine(lon(a["col"]), lat(a["row"]), lon(b["col"]), lat(b["row"]))
    mode = route_mode(grid, a, b)
    leg_km = 98 if mode == "land" else 170
    detour = 1.25 if mode == "land" else 1.0
    dist = km * detour
    legs = max(1, round(dist / leg_km))
    risk = int(40 + dist // (3 if mode == "land" else 6))
    return mode, legs, risk


def main():
    text = SRC.read_text(encoding="utf-8")

    # ── 1. Parse terrain & places via tomllib ──
    import tomllib
    data = tomllib.loads(text)
    terrain = data["terrain"]
    grid = list(terrain["rows"])
    H, W = len(grid), len(grid[0])

    # Build lookup for places
    places_by_id = {}
    for p in data["places"]:
        p["_col"] = p["col"]
        p["_row"] = p["row"]
        places_by_id[p["id"]] = p
    alus = {pid: p for pid, p in places_by_id.items() if p.get("kind") == "alu"}

    # ── 2. Expand terrain ──
    new_rows = []
    for row_str in grid:
        expanded = "".join(c * 2 for c in row_str)
        new_rows.append(expanded)
        new_rows.append(expanded)
    print(f"Terrain: {W}×{H} → {W*2}×{H*2}")

    # Replace terrain rows in text
    # Find the rows array
    rows_match = re.search(
        r'^rows = \[(?:[^\]]*)\]', text, re.MULTILINE | re.DOTALL)
    if rows_match:
        new_rows_str = "rows = [\n" + "\n".join(
            f"  '{r}'," for r in new_rows) + "\n]"
        text = text[:rows_match.start()] + new_rows_str + text[rows_match.end():]
        print("  terrain rows replaced")
    else:
        print("  WARN: could not find terrain rows")

    # Update step values
    text = re.sub(r'step_lon = [\d.]+', 'step_lon = 0.0400', text)
    text = re.sub(r'step_lat = [\d.]+', 'step_lat = 0.0675', text)

    # ── 3. Double place col/row ──
    for pid, p in places_by_id.items():
        old_col, old_row = p["_col"], p["_row"]
        new_col, new_row = old_col * 2, old_row * 2

        # Find this place's block and replace col/row values
        # Use a pattern that matches the id line then finds col/row
        col_pat = re.compile(
            rf'(^id = "{pid}"\n(?:(?!^\[|^id = ).*\n)*?^col = ){old_col}(?!\d)',
            re.MULTILINE)
        text = col_pat.sub(rf'\g<1>{new_col}', text)

        row_pat = re.compile(
            rf'(^id = "{pid}"\n(?:(?!^\[|^id = ).*\n)*?^row = ){old_row}(?!\d)',
            re.MULTILINE)
        text = row_pat.sub(rf'\g<1>{new_row}', text)

    print(f"Places: col/row doubled for {len(places_by_id)} entries")

    # ── 4. Build connectivity graph ──
    import tomllib
    data2 = tomllib.loads(text)
    routes_existing = {(r["a"], r["b"]): r for r in data2.get("routes", [])}
    routes_existing.update({(r["b"], r["a"]): r for r in data2.get("routes", [])})
    connected = set()
    for r in data2.get("routes", []):
        connected.add(r["a"])
        connected.add(r["b"])

    new_route_list = []
    new_route_toml = ""

    def add_route(a_id, b_id):
        key = (a_id, b_id)
        if key in routes_existing or (b_id, a_id) in routes_existing:
            return
        if a_id not in alus or b_id not in alus:
            return
        a = alus[a_id]
        b = alus[b_id]
        mode, legs, risk = make_route(grid, a, b)
        dist = haversine(lon(a["_col"]*2), lat(a["_row"]*2),
                         lon(b["_col"]*2), lat(b["_row"]*2))
        seasonal = mode != "land"
        nrt = (f"\n[[routes]]\na = \"{a_id}\"\nb = \"{b_id}\"\n"
               f"legs = {legs}\nmode = \"{mode}\"\n"
               f"seasonal = {'true' if seasonal else 'false'}\nrisk = {risk}\n")
        new_route_list.append((a_id, b_id, mode, legs, risk, dist))
        routes_existing[key] = True
        connected.add(a_id)
        connected.add(b_id)
        return nrt

    # Connect each disconnected alu to nearest connected
    disconnected = [pid for pid in alus if pid not in connected]
    print(f"Disconnected alus: {len(disconnected)}")

    for pid in disconnected:
        best = None
        best_dist = float("inf")
        for tid in connected:
            if tid not in alus:
                continue
            a, b = alus[pid], alus[tid]
            d = haversine(lon(a["_col"]*2), lat(a["_row"]*2),
                          lon(b["_col"]*2), lat(b["_row"]*2))
            if d < best_dist:
                best_dist = d
                best = tid
        if best:
            nrt = add_route(pid, best)
            if nrt:
                new_route_toml += nrt
                print(f"  {pid:20s} ↔ {best:20s}  km={best_dist:.0f}")

    # Intra-region chain
    region_places = {}
    for pid, p in alus.items():
        region_places.setdefault(p["region"], []).append(pid)

    for r, pids in region_places.items():
        sorted_pids = sorted(pids, key=lambda pid: (
            alus[pid]["_row"], alus[pid]["_col"]))
        for i in range(len(sorted_pids) - 1):
            a_id, b_id = sorted_pids[i], sorted_pids[i + 1]
            if (a_id, b_id) not in routes_existing and (b_id, a_id) not in routes_existing:
                a, b = alus[a_id], alus[b_id]
                d = haversine(lon(a["_col"]*2), lat(a["_row"]*2),
                              lon(b["_col"]*2), lat(b["_row"]*2))
                if d < 500:  # skip very far intra-region pairs
                    nrt = add_route(a_id, b_id)
                    if nrt:
                        new_route_toml += nrt

    print(f"New routes: {len(new_route_list)}")

    # ── 5. Append new routes to world.toml ──
    if new_route_toml:
        # Find insertion point: after last blank line before EOF or before next section
        # Simplest: find the last [[routes]] and insert after it
        last_route_idx = text.rfind("\n[[routes]]\n")
        if last_route_idx < 0:
            # No routes section? Add at end
            text += "\n" + new_route_toml
        else:
            # Find where this route block ends (next blank line + section or EOF)
            after = text[last_route_idx:]
            next_section = re.search(r'\n\n\[', after)
            if next_section:
                insert_at = last_route_idx + next_section.start()
            else:
                insert_at = len(text)
            text = text[:insert_at] + new_route_toml + text[insert_at:]
        print("  routes appended")

    SRC.write_text(text, encoding="utf-8")
    print("\nDone. Run: python3 tools/gen_detail.py")


if __name__ == "__main__":
    main()
