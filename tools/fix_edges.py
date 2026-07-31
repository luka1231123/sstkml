#!/usr/bin/env python3
"""Extend terrain south + east naturally. No random noise.

Extends from the last real rows/cols of the 600×238 grid.
Rivers continue as needed for southern settlements.
East padding becomes sea (~) — ocean east of Mediterranean.
"""
import re
import tomllib

ROOT = "/Users/rexvlapt/Programming/sttkml/content"
TOML = f"{ROOT}/world.toml"

RIVER = "≈"


def _reachable_from(grid, r, c, target_r):
    """BFS from (c,r) upward to find earliest river cell reachable via ≈ path."""
    seen = set()
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in seen:
            continue
        seen.add((cr, cc))
        if cr <= target_r:
            return cc  # found a path to target row
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = cr+dr, cc+dc
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]):
                if grid[nr][nc] == RIVER:
                    stack.append((nr, nc))
    return None


def main() -> int:
    raw = open(TOML, "rb").read()
    data = tomllib.loads(raw.decode())

    grid = [list(row) for row in data["terrain"]["rows"]]
    H, W = len(grid), len(grid[0])
    pad_cols = W - 600  # 38
    pad_rows = H - 238  # 14
    print(f"{W}×{H}, pad_cols={pad_cols}, pad_rows={pad_rows}")

    # ── 0. Reset padding to clean state ──
    for r in range(H):
        for c in range(W):
            if r >= 238 or c >= 600:
                grid[r][c] = ":"

    # ── 1. East extension: cols 600→W ──
    # Last real column is 599. Copy it eastward with shift.
    for c in range(600, W):
        src = min(599, c - 2)
        dist = c - 599
        shift_amp = min(3, dist // 2)
        for r in range(H):
            shift = ((r * 7 + c * 3) % (shift_amp * 2 + 1)) - shift_amp
            sr = max(0, min(H - 1, r + shift))
            grid[r][c] = grid[sr][src]

    # ── 2. South extension: rows 238→H ──
    # Last real row is 237. Copy it southward.
    for r in range(238, H):
        src = max(0, r - 2)
        dist = r - 238
        shift_amp = min(2, dist // 3)
        for c in range(W):
            shift = ((c * 11 + r * 5) % (shift_amp * 2 + 1)) - shift_amp
            sc = max(0, min(W - 1, c + shift))
            grid[r][c] = grid[src][sc]

    # ── 3. Draw Nile from last real river cells to southern settlements ──
    # Find southern settlements below original grid
    southern = {}
    for p in data["places"]:
        if p.get("kind") == "alu" and p["row"] >= 238:
            southern[p["id"]] = (p["row"], p["col"])
    print(f"Southern settlements: {len(southern)}")

    # List: abw at (250, 296) — the southernmost
    if "abw" in southern:
        target_r, target_c = southern["abw"]
        # Find nearest river cell above row 238 within reasonable column range
        candidates = []
        for r in range(220, 238):
            for c in range(max(0, target_c - 20), min(W, target_c + 20)):
                if grid[r][c] == RIVER:
                    dist = abs(c - target_c) + (target_r - r) * 0.5
                    candidates.append((dist, r, c))
        candidates.sort()
        if candidates:
            _, sr, sc = candidates[0]
            print(f"  River source for abw: ({sc},{sr})")
            # Bresenham line from source to abw
            cr, cc = sr, sc
            dr = target_r - sr
            dc = target_c - sc
            step_r = 1 if dr >= 0 else -1
            step_c = 1 if dc >= 0 else -1
            dr, dc = abs(dr), abs(dc)
            err = dr - dc
            while True:
                if grid[cr][cc] not in (RIVER, ";"):
                    grid[cr][cc] = RIVER
                if (cr, cc) == (target_r, target_c):
                    break
                e2 = 2 * err
                if e2 > -dc:
                    err -= dc
                    cr += step_r
                if e2 < dr:
                    err += dr
                    cc += step_c

    # Similarly connect waset (226, 292) if river not reaching it
    if "waset" in southern or True:
        for pid, (target_r, target_c) in southern.items():
            if grid[target_r][target_c] == "≈":
                continue
            # BFS up to find nearest river
            found = _reachable_from(grid, target_r, target_c, target_r - 3)
            if found is not None:
                continue  # already connected
            # Draw from nearest river cell above
            candidates = []
            for r in range(target_r - 20, target_r):
                for c in range(max(0, target_c - 20), min(W, target_c + 20)):
                    if grid[r][c] == RIVER:
                        dist = abs(c - target_c) + (target_r - r) * 0.5
                        candidates.append((dist, r, c))
            if not candidates:
                continue
            _, sr, sc = candidates[0]
            cr, cc = sr, sc
            dr = target_r - sr
            dc = target_c - sc
            step_r = 1 if dr >= 0 else -1
            step_c = 1 if dc >= 0 else -1
            dr_abs, dc_abs = abs(dr), abs(dc)
            err = dr_abs - dc_abs
            while True:
                if grid[cr][cc] not in (RIVER, ";"):
                    grid[cr][cc] = RIVER
                if (cr, cc) == (target_r, target_c):
                    break
                e2 = 2 * err
                if e2 > -dc_abs:
                    err -= dc_abs
                    cr += step_r
                if e2 < dr_abs:
                    err += dr_abs
                    cc += step_c

    # ── 4. Verify ──
    river_total = sum(1 for row in grid for ch in row if ch in RIVER)
    print(f"River cells: {river_total}")

    # Check all settlements
    alus = [p for p in data["places"] if p.get("kind") == "alu"]
    bad = [p for p in alus if grid[p["row"]][p["col"]] == ":"]
    print(f"Settlements on desert: {len(bad)}")

    # ── 5. Write ──
    out = raw.decode()
    terrain_start = out.index("rows = [")
    terrain_end = out.index("\n]", terrain_start) + 2

    new_rows = "rows = [\n"
    for i, row in enumerate(grid):
        quoted = "".join(row)
        new_rows += f'    "{quoted}",\n'
    new_rows += "]"

    out = out[:terrain_start] + new_rows + out[terrain_end:]

    open(TOML, "w").write(out)
    print("Written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
