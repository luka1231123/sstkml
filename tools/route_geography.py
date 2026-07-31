#!/usr/bin/env python3
"""Decide which routes exist, and lay each one on the ground it crosses.

Two things were wrong with the routes this replaces. They were straight lines
between two dots, which put the Ugarit-Carchemish road over the Jebel Ansariye
and the Babylon road through open desert. And there were too many of them,
every pair within reach having its own, so the map drew a cobweb in which no
single road could be followed.

So: the network first. Roads are the relative neighbourhood graph of the
settlements that share a landmass -- a road runs between two places when there
is no third place both are nearer to. Lanes are the Gabriel graph of the ports,
which is looser, because an island needs more ways off it. On top of both sit
the trunk routes, the ones the period is about, which no graph over distances
would ever find. Then anything still cut off is joined to the rest.

Then the ground. Each route is a least-cost path over the terrain grid: sown
ground and river valleys are cheap, dry ground middling, marsh and desert dear,
upland dearest, sea impassable. A lane is the same search with the costs
inverted. The path is written into `content/world.toml` as
`path = [col, row, ...]`, simplified only as far as the drawn line still
matches the walked one, and `legs` and `risk` are recomputed from the distance
and the ground actually crossed.
"""

import heapq
import math
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/world.toml"

BLOCKED = 10 ** 6

# What a fortnight of travel is worth, and how much ground it covers.
KM_PER_LEG = {"land": 98, "river": 130, "sea": 170}

# Cost per kilometre of crossing a cell, by mode and glyph. A road follows the
# valley: river cells are the cheapest land there is, because that is where the
# fords, the wells and the villages are.
COST = {
    "land":  {",": 10, "≈": 9, ".": 16, ";": 45, ":": 50, "^": 70, "~": BLOCKED},
    "river": {"≈": 10, "~": 12, ",": BLOCKED, ".": BLOCKED, ";": BLOCKED,
              ":": BLOCKED, "^": BLOCKED},
    "sea":   {"~": 10, "≈": 12, ",": BLOCKED, ".": BLOCKED, ";": BLOCKED,
              ":": BLOCKED, "^": BLOCKED},
}

# How dangerous the ground is to cross, per kilometre, by glyph. Desert and
# upland are where a caravan is robbed or lost; the valley is where it is not.
# The open sea is the safest per kilometre and the most dangerous per crossing,
# which is what a low rate over a long distance says. These are calibrated to
# the risks the map was authored with -- roughly two fifths a point per land
# kilometre and a sixth per sea one -- because the odds a letter comes home are
# balance, and this tool is not the place to change them.
PERIL = {",": 0.20, "≈": 0.20, ".": 0.45, ";": 0.70, ":": 1.10, "^": 1.00,
         "~": 0.17}

# A port is any settlement with open water this close -- about twenty-two
# kilometres, a morning's cart to the beach. Wide enough that Athens and Tiryns
# are ports, which they were; not so wide that Megiddo becomes one.
PORT_REACH = (6, 3)

# How far from either end the ground is crossable whatever it is: the quay, the
# beach, the gate and the track out of it.
APPROACH = (4, 2)

# How far apart two places may be and still count as neighbours. Beyond this
# nobody walks it as one road; they walk it as three, through the places in
# between, which is what the neighbour graph is for.
NEIGHBOUR_KM = 420

# How far a ship goes without making land. Wider than a road, because it is.
LANE_KM = 750

SIMPLIFY = 1.6          # cells; Douglas-Peucker tolerance for the stored path

# The routes the period is about, which no graph over distances would find:
# they exist because of who was at either end, not because of what lay between.
TRUNKS = (
    # The Euphrates road, and the Assyrian road east of it.
    ("carchemish", "emar", "land"), ("emar", "mari", "land"),
    ("mari", "babylon", "land"), ("emar", "halab", "land"),
    ("assur", "nineveh", "land"), ("assur", "babylon", "land"),
    ("assur", "mari", "land"), ("nineveh", "harran", "land"),
    ("babylon", "nippur", "land"), ("nippur", "uruk", "land"),
    ("uruk", "ur", "land"), ("babylon", "kish", "land"),
    ("babylon", "dur_kurigalzu", "land"),
    # Hatti to the sea, and Hatti to Syria.
    ("hattusa", "kanesh", "land"), ("hattusa", "tarhuntassa", "land"),
    ("hattusa", "carchemish", "land"), ("kanesh", "lawazantiya", "land"),
    ("lawazantiya", "tarsa", "land"), ("tarsa", "mukish", "land"),
    ("hattusa", "sapinuwa", "land"), ("hattusa", "arinna", "land"),
    ("apasa", "hattusa", "land"), ("wilusa", "apasa", "land"),
    # Ugarit's own, which is the whole game.
    ("seat", "mukish", "land"), ("seat", "halab", "land"),
    ("seat", "carchemish", "land"), ("seat", "amurru", "land"),
    ("seat", "alashiya", "sea"), ("seat", "kadesh", "land"),
    ("mukish", "halab", "land"), ("halab", "carchemish", "land"),
    # The coast road: Sumur to Gaza, and the Way of Horus into Egypt.
    ("amurru", "byblos", "land"), ("byblos", "sidon", "land"),
    ("sidon", "tyre", "land"), ("tyre", "akko", "land"),
    ("akko", "megiddo", "land"), ("megiddo", "yafa", "land"),
    ("yafa", "ashkelon", "land"), ("ashkelon", "gaza", "land"),
    ("gaza", "tjaru", "land"), ("tjaru", "egypt", "land"),
    # The inland road: Damascus, the Beqaa, and the Jordan.
    ("kadesh", "damascus", "land"), ("damascus", "hazor", "land"),
    ("hazor", "megiddo", "land"), ("megiddo", "shechem", "land"),
    ("shechem", "jerusalem", "land"), ("jerusalem", "lachish", "land"),
    ("lachish", "gaza", "land"), ("gezer", "jerusalem", "land"),
    # The Nile, which is one road from the delta to the cataract.
    ("egypt", "per_bastet", "land"), ("per_bastet", "iunu", "land"),
    ("iunu", "memphis", "land"), ("memphis", "khemenu", "river"),
    ("khemenu", "per_medjed", "river"), ("per_medjed", "abdju", "river"),
    ("abdju", "waset", "river"), ("waset", "abw", "river"),
    ("sau", "iunu", "river"), ("hut_herib", "per_bastet", "land"),
    ("hut_nesut", "khemenu", "river"),
    # The lanes that carried the metal, and the ones the letters name.
    ("alashiya", "egypt", "sea"), ("alashiya", "tarsa", "sea"),
    ("alashiya", "byblos", "sea"), ("alashiya", "knossos", "sea"),
    ("knossos", "kydonia", "sea"), ("knossos", "pylos", "sea"),
    ("knossos", "mycenae", "sea"), ("knossos", "millawanda", "sea"),
    ("knossos", "egypt", "sea"), ("kydonia", "pylos", "sea"),
    ("wilusa", "millawanda", "sea"), ("wilusa", "iolcos", "sea"),
    ("wilusa", "athens", "sea"), ("millawanda", "apasa", "land"),
    ("mycenae", "tiryns", "land"), ("mycenae", "korinthos", "land"),
    ("mycenae", "argos", "land"), ("argos", "tiryns", "land"),
    ("tiryns", "lerna", "land"), ("lerna", "sparta", "land"),
    ("sparta", "pylos", "land"), ("korinthos", "athens", "land"),
    ("athens", "thebes_gr", "land"), ("thebes_gr", "orchomenos", "land"),
    ("orchomenos", "iolcos", "land"), ("iolcos", "dimini", "land"),
    ("pylos", "mycenae", "sea"), ("athens", "millawanda", "sea"),
    ("byblos", "egypt", "sea"), ("seat", "byblos", "sea"),
)


def load():
    text = SRC.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    return text, data


def geometry(terrain):
    """Cell size in kilometres, at the middle latitude of the map."""
    grid = terrain["rows"]
    mid = terrain["north"] - len(grid) * terrain["step_lat"] / 2
    km_col = terrain["step_lon"] * 111.32 * math.cos(math.radians(mid))
    km_row = terrain["step_lat"] * 110.57
    return grid, km_col, km_row


def search(grid, cost, km_col, km_row, start, goal, approach_span=None):
    """A* from start to goal over the cost table. Returns cells, or None.

    The ground around each endpoint is exempt from the cost table: a port sits
    on land and a road ends in a city, so a few cells at either end are always
    crossable. Without that a lane cannot leave its own quay.
    """
    H, W = len(grid), len(grid[0])
    diag = math.hypot(km_col, km_row)
    cheapest = min(v for v in cost.values() if v < BLOCKED)

    span = approach_span or APPROACH

    def approach(cell):
        return any(abs(cell[0] - end[0]) <= span[0]
                   and abs(cell[1] - end[1]) <= span[1]
                   for end in (start, goal))

    def heuristic(cell):
        dc, dr = abs(cell[0] - goal[0]), abs(cell[1] - goal[1])
        return cheapest * math.hypot(dc * km_col, dr * km_row)

    seen = {start: 0.0}
    came: dict = {}
    queue = [(heuristic(start), start)]
    while queue:
        _, cell = heapq.heappop(queue)
        if cell == goal:
            path = [cell]
            while cell in came:
                cell = came[cell]
                path.append(cell)
            return path[::-1]
        here = seen[cell]
        c, r = cell
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == dr == 0:
                    continue
                n = (c + dc, r + dr)
                if not (0 <= n[0] < W and 0 <= n[1] < H):
                    continue
                km = (diag if dc and dr
                      else km_col if dc else km_row)
                rate = cost.get(grid[n[1]][n[0]], BLOCKED)
                if approach(n):
                    rate = min(rate, cheapest)
                if rate >= BLOCKED:
                    continue
                step = here + rate * km
                if step < seen.get(n, float("inf")):
                    seen[n] = step
                    came[n] = cell
                    heapq.heappush(queue, (step + heuristic(n), n))
    return None


def simplify(path, tolerance):
    """Douglas-Peucker. The drawn road bends where the ground bends, not every
    cell, and the file is a tenth the size."""
    if len(path) < 3:
        return list(path)
    (x0, y0), (x1, y1) = path[0], path[-1]
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy) or 1.0
    worst, at = 0.0, 0
    for i, (x, y) in enumerate(path[1:-1], 1):
        far = abs(dy * x - dx * y + x1 * y0 - y1 * x0) / span
        if far > worst:
            worst, at = far, i
    if worst <= tolerance:
        return [path[0], path[-1]]
    return simplify(path[:at + 1], tolerance)[:-1] + simplify(path[at:],
                                                              tolerance)


def bresenham(a, b):
    """Every cell a straight run passes through — the same walk `tui/atlas.py`
    does when it draws one, so what is checked here is what gets drawn."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 >= x0 else -1
    sy = 1 if y1 >= y0 else -1
    error = dx - dy
    cells = []
    while True:
        cells.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return cells
        doubled = 2 * error
        if doubled > -dy:
            error -= dy
            x0 += sx
        if doubled < dx:
            error += dx
            y0 += sy


def faithful(grid, cost, turns, start, goal, span):
    """Whether the straight runs between the kept turns stay on passable
    ground. A simplified road that cuts the corner of a bay is a road drawn
    over open water."""
    for a, b in zip(turns, turns[1:]):
        for c, r in bresenham(a, b):
            if (abs(c - start[0]) <= span[0] and abs(r - start[1]) <= span[1]) \
               or (abs(c - goal[0]) <= span[0] and abs(r - goal[1]) <= span[1]):
                continue
            if cost.get(grid[r][c], BLOCKED) >= BLOCKED:
                return False
    return True


def landmasses(grid):
    """Which body of land each cell belongs to, so a road is never proposed
    between two places with open water between them."""
    H, W = len(grid), len(grid[0])
    label: dict[tuple[int, int], int] = {}
    count = 0
    for r0 in range(H):
        for c0 in range(W):
            if grid[r0][c0] == "~" or (c0, r0) in label:
                continue
            count += 1
            stack = [(c0, r0)]
            label[(c0, r0)] = count
            while stack:
                c, r = stack.pop()
                for dc in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        n = (c + dc, r + dr)
                        if (0 <= n[0] < W and 0 <= n[1] < H
                                and n not in label
                                and grid[n[1]][n[0]] != "~"):
                            label[n] = count
                            stack.append(n)
    return label


def relative_neighbours(candidates, km):
    """The relative neighbourhood graph: keep a-b unless some third place is
    nearer to both ends than they are to each other."""
    nodes = sorted({i for pair in candidates for i in pair})
    kept = set()
    for a, b in sorted(candidates):
        span = km(a, b)
        if not any(km(a, c) < span and km(b, c) < span
                   for c in nodes if c not in (a, b)):
            kept.add((a, b))
    return sorted(kept)


def gabriel_neighbours(candidates, km):
    """The Gabriel graph: keep a-b unless some third place lies inside the
    circle that has a-b for its diameter. Looser than the neighbourhood graph,
    which is what an archipelago needs."""
    nodes = sorted({i for pair in candidates for i in pair})
    kept = set()
    for a, b in sorted(candidates):
        span = km(a, b) ** 2
        if not any(km(a, c) ** 2 + km(b, c) ** 2 < span
                   for c in nodes if c not in (a, b)):
            kept.add((a, b))
    return sorted(kept)


def components(nodes, pairs):
    """The pieces the route graph falls into."""
    near: dict[str, set[str]] = {i: set() for i in nodes}
    for a, b in pairs:
        near.setdefault(a, set()).add(b)
        near.setdefault(b, set()).add(a)
    seen, parts = set(), []
    for start in nodes:
        if start in seen:
            continue
        stack, part = [start], []
        seen.add(start)
        while stack:
            i = stack.pop()
            part.append(i)
            for j in near[i]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        parts.append(part)
    return parts


def measure(grid, path, km_col, km_row):
    """Kilometres walked, and the peril of the ground walked over."""
    km, peril = 0.0, 0.0
    for (c0, r0), (c1, r1) in zip(path, path[1:]):
        step = math.hypot((c1 - c0) * km_col, (r1 - r0) * km_row)
        km += step
        peril += step * PERIL.get(grid[r1][c1], 0.5)
    return km, peril


def main():
    text, data = load()
    grid, km_col, km_row = geometry(data["terrain"])
    H, W = len(grid), len(grid[0])
    places = {p["id"]: p for p in data["places"]}
    alus = {i: p for i, p in places.items() if p.get("kind") == "alu"}

    def spot(pid):
        p = places[pid]
        return (p["col"], p["row"])

    # ── Ports ─────────────────────────────────────────────────────────────
    def is_port(p):
        if p.get("harbour"):
            return True
        c, r = p["col"], p["row"]
        return any(grid[r + dr][c + dc] == "~"
                   for dc in range(-PORT_REACH[0], PORT_REACH[0] + 1)
                   for dr in range(-PORT_REACH[1], PORT_REACH[1] + 1)
                   if 0 <= r + dr < H and 0 <= c + dc < W)

    ports = sorted(i for i, p in alus.items() if is_port(p))
    print(f"Ports: {len(ports)}")

    # ── The pairs to route ────────────────────────────────────────────────
    def km_between(a, b):
        (c0, r0), (c1, r1) = spot(a), spot(b)
        return math.hypot((c1 - c0) * km_col, (r1 - r0) * km_row)

    land = landmasses(grid)
    pairs: dict[tuple[str, str], dict] = {}

    def add(a, b, mode):
        if a == b or (a, b) in pairs or (b, a) in pairs:
            return False
        pairs[(a, b)] = {"a": a, "b": b, "mode": mode}
        return True

    # The road network is the relative neighbourhood graph of the settlements
    # that share a landmass: a road exists between two places when there is no
    # third place that both are nearer to. That is what a road system looks
    # like from the air -- a mesh of short local links with no long line
    # cutting across a dozen others -- and it is what the map could not draw
    # while every pair within reach had its own line.
    every = sorted(alus)
    same = {(a, b) for a in every for b in every
            if a < b and land.get(spot(a)) == land.get(spot(b))
            and km_between(a, b) <= NEIGHBOUR_KM}
    roads = relative_neighbours(same, km_between)
    for a, b in roads:
        add(a, b, "land")
    print(f"Roads from the neighbour graph: {len(roads)}")

    # Lanes are the Gabriel graph of the ports, which is the same idea held
    # more loosely -- an island needs more ways off it than a town needs out of
    # it, and the Aegean is islands.
    reachable = {(a, b) for a in ports for b in ports
                 if a < b and km_between(a, b) <= LANE_KM}
    lanes = gabriel_neighbours(reachable, km_between)
    added = sum(add(a, b, "sea") for a, b in lanes)
    print(f"Lanes from the port graph: {len(lanes)} ({added} new)")

    # The great roads and the standing lanes. A neighbour graph knows nothing
    # about who writes to whom: it will not put the Euphrates road between
    # Carchemish and Emar, or the Way of Horus across Sinai, because there is
    # always some nearer third place. These are the ones the period is about.
    # A trunk named a place that has since been demoted to a palace centre ends
    # at the Alu whose king it answers to: the road to Kish is the road to
    # Babylon, and if both ends resolve to the same Alu there is no road left
    # to lay.
    def owner(pid):
        place = places.get(pid, {})
        return pid if place.get("kind") == "alu" else place.get("alu", pid)

    trunk = 0
    for first, second, mode in TRUNKS:
        a, b = owner(first), owner(second)
        if a == b:
            continue
        trunk += add(a, b, mode)
        # The neighbour graph may have found this pair already and called it a
        # road. The trunk knows better -- Waset to Abdju is the river, and the
        # river is the whole reason the two are one country.
        pairs[(a, b) if (a, b) in pairs else (b, a)]["mode"] = mode
    print(f"Trunk routes: {trunk} new")

    # Nothing may be an island unless it is one, and an island still gets a
    # boat. Join every remaining piece of the graph to its nearest neighbour
    # until one court can reach them all.
    joined = 0
    while True:
        parts = components(sorted(alus), pairs)
        if len(parts) < 2:
            break
        parts.sort(key=len, reverse=True)
        rest = {i for part in parts[1:] for i in part}
        km, a, b = min((km_between(a, b), a, b)
                       for a in parts[0] for b in rest)
        add(a, b, "sea" if a in ports and b in ports else "land")
        joined += 1
    print(f"Joins to keep the world one piece: {joined}")

    # ── Lay each route on the ground ──────────────────────────────────────
    out, failed, changed = [], [], 0
    for (a, b), route in sorted(pairs.items()):
        start, goal = spot(a), spot(b)
        best = None
        # Try the mode it claims first, then fall back: a lane that cannot be
        # sailed is a road, and a road that cannot be walked is a lane.
        order = [route.get("mode", "land")]
        order += [m for m in ("land", "sea", "river") if m not in order]
        # A wider approach for a place that sits back from its own water:
        # Mycenae is not on the shore, but ships still come to Mycenae. The
        # mode is exhausted before the next one is tried, or the Nile road
        # would come out as a road: the river is there, it is just further from
        # the gate than four cells.
        for mode in order:
            for span in (APPROACH, (10, 5), (22, 11)):
                path = search(grid, COST[mode], km_col, km_row, start, goal,
                              span)
                if path is not None:
                    best = (mode, path, span)
                    break
            if best:
                break
        if best is None:
            failed.append((a, b))
            continue
        mode, path, span = best
        km, peril = measure(grid, path, km_col, km_row)
        legs = max(1, round(km / KM_PER_LEG[mode]))
        risk = min(1000, int(40 + peril))
        # Simplify as far as the drawn line still matches the walked one.
        kept = path
        tolerance = SIMPLIFY
        while tolerance >= 0.25:
            trial = simplify(path, tolerance)
            if faithful(grid, COST[mode], trial, start, goal, span):
                kept = trial
                break
            tolerance /= 2
        if route.get("mode") != mode or route.get("legs") != legs:
            changed += 1
        out.append({
            "a": a, "b": b, "legs": legs, "mode": mode,
            # A sea lane shuts outside the sailing window; a road does not.
            "seasonal": mode != "land",
            "risk": risk,
            "path": [n for cell in kept for n in cell],
        })

    if failed:
        print(f"  no path for {len(failed)}: {failed[:6]}")
    print(f"Routes: {len(out)} laid, {changed} with a new mode or length")

    # ── Write ─────────────────────────────────────────────────────────────
    blocks = []
    for r in out:
        path = ", ".join(str(n) for n in r["path"])
        blocks.append(
            "[[routes]]\n"
            f'a = "{r["a"]}"\n'
            f'b = "{r["b"]}"\n'
            f'legs = {r["legs"]}\n'
            f'mode = "{r["mode"]}"\n'
            f'seasonal = {"true" if r["seasonal"] else "false"}\n'
            f'risk = {r["risk"]}\n'
            f'path = [{path}]\n')
    body = "\n".join(blocks)

    first = text.find("[[routes]]")
    if first < 0:
        text = text.rstrip() + "\n\n" + body
    else:
        tail = re.search(r'^\[(?!\[routes\]\])', text[first:], re.MULTILINE)
        end = first + tail.start() if tail else len(text)
        text = text[:first] + body + text[end:]
    SRC.write_text(text, encoding="utf-8")

    steps = sorted(r["legs"] for r in out)
    print(f"legs: min {steps[0]} median {steps[len(steps)//2]} max {steps[-1]}")
    print("Written.")


if __name__ == "__main__":
    main()
