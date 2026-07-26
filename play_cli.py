"""Interactive controller (command mode). The M1+M2 game, playable end to end.

Holds the World, drives the turn pipeline, projects Belief, renders it, and
turns typed commands into Actions. Everything reachable here is reachable
headlessly (session.play), so the game plays with no model and no GUI.

Attention is enforced here, in Phase C: reading a letter costs hours, and the
pile is longer than the budget. Triage is the game.
"""
from __future__ import annotations

import sys

from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from tui import render

READ_COST = 2
REPLY_COST = 2
INSPECT_COST = 1
SEARCH_COST = 1

HELP = """  commands (a leading ':' is optional)
    stack | lists | stores | archive   switch screen
    read <i>                 read a letter in full            (2 hours)
    reply <i> <intent>       answer it: reassure|refuse|promise|warn  (2 hours)
    inspect granary|seed     count it yourself; see the true number   (1 hour)
    search <word>            search the archive               (1 hour)
    alloc <group> <qa>       set what a group is paid  (effect next turn)
    pri <group> <group>..    set the pay-down order
    eat <qa>                 move seed grain into the granary now
    end                      end the fortnight
    save <path>              write a save file
    help  |  quit"""


def _resolve(token: str, stack: list) -> str | None:
    """Map a Stack token (roman numeral, index, or letter id) to a letter id."""
    token = token.lower()
    romans = {render._num(i): it["id"] for i, it in enumerate(stack)}
    if token in romans:
        return romans[token]
    if token.isdigit():
        i = int(token) - 1
        return stack[i]["id"] if 0 <= i < len(stack) else None
    for it in stack:
        if it["id"].lower() == token:
            return it["id"]
    return None


def run(scenario: str = "ugarit", seed: int = 8814402919) -> None:
    world = load_scenario(scenario, seed)
    log: list[dict] = []
    turns = 0
    screen = "stack"
    print("\n  SAY TO THE KING, MY LORD\n")

    while True:
        world, events = advance(world)
        turns += 1
        b = project(world)
        spent = 0
        print("\n" + "═" * 78)
        print(render.header(b))
        for ln in render.events_lines(events, world.court):
            print(ln)
        print()

        def commit(action):
            nonlocal world
            world, evs = apply(world, action)
            log.append({"turn": world.date.absolute, "action": A.to_dict(action)})
            return evs

        search_results = None
        end = False
        while not end:
            b = project(world)
            left = max(0, b["attention"] - spent)
            active = b["archive"] if screen == "archive" else b["stack"]
            if screen == "archive":
                print(render.archive_screen(b, search_results))
            else:
                print({"stack": render.stack_screen, "lists": render.lists_screen,
                       "stores": render.stores_screen}[screen](b))
            try:
                line = input(f"\n  [{left}h] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  (the tablet is set aside)")
                return
            if not line:
                continue
            if line.startswith(":"):
                line = line[1:]
            parts = line.split()
            verb, args = parts[0].lower(), parts[1:]

            if verb in ("stack", "lists", "stores", "archive"):
                screen = verb
                if verb != "archive":
                    search_results = None
            elif verb == "help":
                print(HELP)
            elif verb in ("quit", "q", "exit"):
                print("  (the tablet is set aside)")
                return
            elif verb == "save":
                from session import save
                path = args[0] if args else "save.json"
                save(path, seed, scenario, turns, log, world)
                print(f"  saved to {path}")
            elif verb in ("end", "e"):
                end = True
            elif verb == "read" and args:
                lid = _resolve(args[0], search_results if search_results is not None else active)
                if lid is None:
                    print("  no such item on the pile.")
                elif left < READ_COST:
                    print(f"  not hours enough. reading is {READ_COST}; you have {left}.")
                else:
                    it = next(x for x in b["stack"] if x["id"] == lid)
                    print("\n" + render.letter_full(it))
                    commit(A.ReadLetter(lid))
                    spent += READ_COST
            elif verb == "inspect" and args:
                if args[0].lower() not in ("granary", "seed"):
                    print("  inspect what? 'granary' or 'seed'.")
                elif left < INSPECT_COST:
                    print(f"  no hour to spare for counting.")
                else:
                    evs = commit(A.InspectLedger(args[0].lower()))
                    spent += INSPECT_COST
                    iv = next((e for e in evs if isinstance(e, A.LedgerInspected)), None)
                    if iv:
                        print(f"  you count it yourself. it holds {render.fmt_good('grain', iv.true_value)}.")
            elif verb == "search" and args:
                if left < SEARCH_COST:
                    print("  no hour to spare for the archive.")
                else:
                    kw = " ".join(args).lower()
                    search_results = [it for it in b["archive"]
                                      if kw in render.searchable_text(it)]
                    spent += SEARCH_COST
                    screen = "archive"
                    print(f"  the scribe searches. {len(search_results)} found.")
            elif verb == "reply" and len(args) == 2:
                lid = _resolve(args[0], search_results if search_results is not None else active)
                if lid is None:
                    print("  no such item to answer.")
                elif left < REPLY_COST:
                    print(f"  not hours enough. a reply is {REPLY_COST}; you have {left}.")
                else:
                    evs = commit(A.DictateReply(lid, args[1].lower()))
                    spent += REPLY_COST
                    if any(isinstance(e, A.LetterSent) for e in evs):
                        print("  the tablet is sealed and given to a courier.")
            elif verb == "alloc" and len(args) == 2:
                try:
                    commit(A.Allocate(args[0], int(args[1])))
                except (ValueError, TypeError) as ex:
                    print(f"  {ex}")
            elif verb == "pri" and args:
                try:
                    commit(A.SetPriority(tuple(args)))
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb == "eat" and len(args) == 1:
                try:
                    commit(A.EatSeed(int(args[0])))
                except ValueError:
                    print("  eat needs an integer qa.")
            else:
                print(f"  don't understand: {line!r}  (try 'help')")


if __name__ == "__main__":
    sc = sys.argv[1] if len(sys.argv) > 1 else "ugarit"
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 8814402919
    run(sc, sd)
