"""Thin rivers to 1 cell. Recompute all routes via A* respecting terrain."""
import sys, math, heapq, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"

STEP_LON, STEP_LAT = 0.0400, 0.0675
WEST, NORTH = 21.00, 41.00
LAND_LEG, SEA_LEG = 98, 170

COST_LAND = {"~": 9999, "≈": 1.0, "^": 100, ",": 0.8, ".": 1.0, ":": 2.0, ";": 2.0}
COST_SEA  = {"~": 1.0, ",": 5.0, ".": 5.0, "≈": 3.0}

def lon(c): return WEST + c * STEP_LON
def lat(r): return NORTH - r * STEP_LAT

def haversine(lon1, lat1, lon2, lat2):
    R = 6371; dl = math.radians(lon2-lon1); dr = math.radians(lat2-lat1)
    a = math.sin(dr/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── Zhang-Suen thinning ──
def thin_dict(bin_dict, H, W):
    g = bin_dict.copy()
    nbr = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    changed = True
    while changed:
        changed = False
        for sub in range(2):
            remove = []
            for r in range(H):
                for c in range(W):
                    if not g.get((r,c), 0): continue
                    p = [g.get((r+dr,c+dc), 0) for dr,dc in nbr]
                    B = sum(p)
                    if B < 2 or B > 6: continue
                    A = sum(1 for i in range(8) if p[i]==0 and p[(i+1)%8]==1)
                    if A != 1: continue
                    if sub == 0:
                        if not (p[0]*p[2]*p[4]==0 and p[2]*p[4]*p[6]==0): continue
                    else:
                        if not (p[0]*p[2]*p[6]==0 and p[0]*p[4]*p[6]==0): continue
                    remove.append((r,c))
            for (r,c) in remove:
                g[(r,c)] = 0
                changed = True
    return {(r,c) for (r,c),v in g.items() if v}

# ── A* ──
def astar(grid, cost_map, start, end):
    H,W = len(grid), len(grid[0])
    sr,sc = start; er,ec = end
    def h(r,c): return math.hypot(c-ec, r-er)
    oq = [(0, sr, sc)]
    g = {(sr,sc):0}; f = {(sr,sc):h(sr,sc)}
    cf = {}
    while oq:
        _,r,c = heapq.heappop(oq)
        if (r,c) == (er,ec):
            p = [(c,r)]
            while (r,c) in cf:
                r,c = cf[(r,c)]
                p.append((c,r))
            p.reverse(); return p
        for dr,dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr,nc = r+dr, c+dc
            if nr<0 or nr>=H or nc<0 or nc>=W: continue
            cm = cost_map.get(grid[nr][nc], 9999)
            if cm >= 9999: continue
            mc = cm * (1.4 if dr and dc else 1.0)
            ng = g[(r,c)] + mc
            if (nr,nc) in g and ng >= g[(nr,nc)]: continue
            cf[(nr,nc)] = (r,c); g[(nr,nc)] = ng
            fv = ng + h(nr,nc); f[(nr,nc)] = fv
            heapq.heappush(oq, (fv, nr, nc))
    return None

def path_km(path):
    if not path or len(path)<2: return 0
    return sum(haversine(lon(c1),lat(r1),lon(c2),lat(r2))
               for (c1,r1),(c2,r2) in zip(path, path[1:]))

def main():
    text = SRC.read_text(encoding="utf-8")
    import tomllib
    data = tomllib.loads(text)
    grid = list(data["terrain"]["rows"])
    H,W = len(grid), len(grid[0])
    print(f"Grid {W}×{H}")

    palus = {p["id"]:p for p in data["places"] if p.get("kind")=="alu"}

    # Ensure grid holds all places
    max_col = max(p["col"]+2 for p in data["places"])
    max_row = max(p["row"]+2 for p in data["places"])
    extra_cols = max(0, max_col - W)
    extra_rows = max(0, max_row - H)
    if extra_cols or extra_rows:
        print(f"Pad grid: +{extra_cols} cols, +{extra_rows} rows")
        new_grid = [list(row) for row in grid]
        if extra_cols:
            new_grid = [row + [":"]*extra_cols for row in new_grid]
        if extra_rows:
            new_grid += [[":"] * len(new_grid[0]) for _ in range(extra_rows)]
        grid = ["".join(row) for row in new_grid]
        H, W = len(grid), len(grid[0])
        print(f"New grid: {W}×{H}")
    else:
        new_grid = [list(row) for row in grid]

    # ── 1. Fix place coordinates in sea ──
    for p in data["places"]:
        r, c = p["row"], p["col"]
        if 0 <= r < H and 0 <= c < W and new_grid[r][c] == "~":
            # Nudge to nearest non-sea cell within radius 8
            best = None
            for dr in range(-8, 9):
                for dc in range(-8, 9):
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < H and 0 <= nc < W and new_grid[nr][nc] != "~":
                        dist = math.hypot(dr, dc)
                        if best is None or dist < best[0]:
                            best = (dist, nr, nc)
            if best:
                _, nr, nc = best
                print(f"  nudge {p['id']:15s} ({c},{r})→({nc},{nr})")
                p["row"], p["col"] = nr, nc
                p["_row"], p["_col"] = nr, nc
    print("  coordinates fixed")

    # ── 2. Thin rivers ──
    bin0 = {(r,c): grid[r][c]=="≈" for r in range(H) for c in range(W)}
    skel = thin_dict(bin0, H, W)
    orig = sum(1 for v in bin0.values() if v)
    print(f"River cells: {orig} → {len(skel)}")

    new_grid = [list(row) for row in grid]
    nbr8 = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    for r in range(H):
        for c in range(W):
            if bin0.get((r,c)) and (r,c) not in skel:
                cnt = {}
                for dr,dc in nbr8:
                    nr,nc=r+dr,c+dc
                    if 0<=nr<H and 0<=nc<W and grid[nr][nc]!="≈":
                        cnt[grid[nr][nc]] = cnt.get(grid[nr][nc],0)+1
                new_grid[r][c] = max(cnt, key=cnt.get) if cnt else ","

    # ── 2. Recompute all routes ──
    def coastal(pid):
        p = palus[pid]
        r, c = p["row"], p["col"]
        if r >= len(new_grid) or c >= len(new_grid[0]) or r<0 or c<0:
            return False  # outside grid = not coastal (assume land)
        return new_grid[r][c]=="~"

    pairs = set()
    for r in data.get("routes",[]):
        a,b = r["a"],r["b"]
        pairs.add((a,b))

    # Also intra-region pairs
    regs = {}
    for pid,p in palus.items():
        regs.setdefault(p["region"],[]).append(pid)
    for r,pids in regs.items():
        sp = sorted(pids)
        for i in range(len(sp)-1):
            pairs.add((sp[i], sp[i+1]))

    route_toml = ""
    done = set()
    for a,b in sorted(pairs):
        key = tuple(sorted([a,b]))
        if key in done: continue
        done.add(key)
        if a not in palus or b not in palus: continue
        pa,pb = palus[a], palus[b]
        ar,ac = pa["row"],pa["col"]; br,bc = pb["row"],pb["col"]

        # Try land A*
        path = astar(new_grid, COST_LAND, (ar,ac), (br,bc))
        km = None; mode = "land"
        if path:
            km = path_km(path)
        if not path or km is None:
            path = astar(new_grid, COST_SEA, (ar,ac), (br,bc))
            if path:
                km = path_km(path); mode = "sea"
        if not path or km is None or km < 1:
            km = max(10, haversine(lon(ac),lat(ar),lon(bc),lat(br)) * 1.25)
            mode = "sea" if (coastal(a) or coastal(b)) else "land"

        leg_km = LAND_LEG if mode=="land" else SEA_LEG
        legs = max(1, round(km/leg_km))
        risk = int(40 + km // (3 if mode=="land" else 6))
        seasonal = mode=="sea"
        route_toml += (f"[[routes]]\na = \"{a}\"\nb = \"{b}\"\n"
                       f"legs = {legs}\nmode = \"{mode}\"\n"
                       f"seasonal = {'true' if seasonal else 'false'}\nrisk = {risk}\n")

    print(f"Routes: {len(done)}")

    # ── 3. Write ──
    # Update terrain rows
    rows_match = re.search(r'rows = \[.*?\]', text, re.DOTALL)
    if rows_match:
        nr_str = "rows = [\n" + "\n".join(f"  '{''.join(row)}'," for row in new_grid) + "\n]"
        text = text[:rows_match.start()] + nr_str + text[rows_match.end():]

    # Replace everything from [[routes]] to [[sites]] with new routes + preserve sites onward
    route_section = re.search(r'(\[\[routes\]\].*?)(?=\[\[sites\]\])', text, re.DOTALL)
    if route_section:
        text = text[:route_section.start()] + route_toml + "\n" + text[route_section.end():]
        print("Routes section replaced")
    else:
        # fallback: find [[sites]] and insert before it
        sites_pos = text.find("\n[[sites]]")
        if sites_pos >= 0:
            text = text[:sites_pos] + "\n" + route_toml + text[sites_pos:]
        else:
            text += "\n" + route_toml

    SRC.write_text(text, encoding="utf-8")
    print("Done. Run: python3 tools/gen_detail.py")

if __name__ == "__main__":
    main()
