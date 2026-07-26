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
GIFT_COST = 1

HELP = """  commands (a leading ':' is optional)
    stack | lists | stores | archive | relations | oaths   switch screen
    read <i>                 read a letter in full            (2 hours)
    reply <i> <intent>       answer it with a free-text intent        (2 hours)
    dictate <i>              write the reply yourself, ending with '.' (2 hours)
    inspect granary|seed     count it yourself; see the true number   (1 hour)
    search <word>            search the archive               (1 hour)
    alloc <group> <qa>       set what a group is paid  (effect next turn)
    pri <group> <group>..    set the pay-down order
    eat <qa>                 move seed grain into the granary now
    gift <actor> <good> <n>  send goods to a correspondent        (1 hour)
    end                      end the fortnight
    save <path>              write a save file
    help  |  quit

  Plain English is tried through the deterministic pre-parser, then Ollama.
  Run with --no-ai to keep command mode only."""


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


def _raw_tablet() -> str:
    print("  Dictate the tablet. A line containing only '.' seals the text.")
    lines = []
    while True:
        line = input("  tablet> ")
        if line == ".":
            return "\n".join(lines)
        lines.append(line)


def run(scenario: str = "ugarit", seed: int = 8814402919, no_ai: bool = False) -> None:
    from ai.client import OllamaClient
    from ai.composer import compose, raw_draft, split_draft
    from ai.parser import action_cost, parse

    world = load_scenario(scenario, seed)
    log: list[dict] = []
    ai_log: list[dict] = []
    client = None if no_ai else OllamaClient(ai_log, f"saves/{scenario}/ai_cache")
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

        def desk_reply(letter_id: str, intent: str, hours_left: int,
                       raw: bool = False) -> int:
            if hours_left < REPLY_COST:
                print(f"  not hours enough. a reply is {REPLY_COST}; you have {hours_left}.")
                return 0
            item = next((x for x in project(world)["stack"] if x["id"] == letter_id), None)
            if item is None:
                print("  no such item to answer.")
                return 0
            try:
                draft = (raw_draft(_raw_tablet(), item["sender"]) if raw else
                         compose(item["sender"], intent, item["facts"], seed,
                                 world.date.absolute, client))
            except (EOFError, KeyboardInterrupt):
                print("\n  (the unfinished tablet is burned)")
                return REPLY_COST
            while True:
                print("\n" + render.desk_screen(item["sender"], intent, draft))
                try:
                    choice = input("\n  desk> ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n  (the draft is burned)")
                    return REPLY_COST
                if choice in ("burn", "b"):
                    print("  the clay is wetted and returned to the bin.")
                    return REPLY_COST
                if choice in ("dictate", "d"):
                    try:
                        draft = raw_draft(_raw_tablet(), item["sender"])
                    except (EOFError, KeyboardInterrupt):
                        print("\n  (the unfinished tablet is burned)")
                        return REPLY_COST
                    continue
                if choice in ("split", "s"):
                    parts = split_draft(draft, item["sender"])
                    if not parts:
                        print("  Yabninu: I find no two separable topics in this tablet.")
                        continue
                    if hours_left < REPLY_COST * 2:
                        print("  two tablets need four hours; there is not time enough.")
                        continue
                    for part in parts:
                        commit(A.DictateReply(
                            letter_id, intent, part.text, part.profile,
                            part.score.total, part.score.violations))
                    print("  two tablets are sealed and given to two couriers.")
                    return REPLY_COST * 2
                if choice in ("send", "y"):
                    evs = commit(A.DictateReply(
                        letter_id, intent, draft.text, draft.profile,
                        draft.score.total, draft.score.violations))
                    if any(isinstance(event, A.LetterSent) for event in evs):
                        print("  the tablet is sealed and given to a courier.")
                    return REPLY_COST
                print("  choose send, split, dictate, or burn.")

        search_results = None
        end = False
        while not end:
            b = project(world)
            left = max(0, b["attention"] - spent)
            active = b["archive"] if screen == "archive" else b["stack"]
            if screen == "archive":
                print(render.archive_screen(b, search_results))
            elif screen == "relations":
                print(render.relations_screen(b))
            elif screen == "oaths":
                print(render.oaths_screen(b))
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
            command_mode = line.startswith(":")
            if command_mode:
                line = line[1:]
            parts = line.split()
            verb, args = parts[0].lower(), parts[1:]

            if verb in ("stack", "lists", "stores", "archive", "relations", "oaths"):
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
                save(path, seed, scenario, turns, log, world, ai_log)
                print(f"  saved to {path}")
            elif verb in ("end", "e"):
                end = True
            elif verb == "read" and len(args) == 1:
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
            elif verb == "reply" and len(args) >= 2:
                lid = _resolve(args[0], search_results if search_results is not None else active)
                if lid is None:
                    print("  no such item to answer.")
                elif left < REPLY_COST:
                    print(f"  not hours enough. a reply is {REPLY_COST}; you have {left}.")
                else:
                    spent += desk_reply(lid, " ".join(args[1:]), left)
            elif verb == "dictate" and len(args) == 1:
                lid = _resolve(args[0], search_results if search_results is not None else active)
                if lid is None:
                    print("  no such item to answer.")
                elif left < REPLY_COST:
                    print(f"  not hours enough. a reply is {REPLY_COST}; you have {left}.")
                else:
                    spent += desk_reply(lid, "raw dictation", left, raw=True)
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
            elif verb == "gift" and len(args) == 3:
                if left < GIFT_COST:
                    print("  no hour remains to seal and dispatch a gift.")
                else:
                    try:
                        events = commit(A.SendGift(
                            args[0], args[1], int(args[2])))
                        spent += GIFT_COST
                        sent = next(
                            (e for e in events if isinstance(e, A.GiftSent)), None)
                        if sent:
                            print(
                                f"  gift {sent.gift_id} leaves; expected turn "
                                f"{sent.arrival_turn}.")
                    except (ValueError, TypeError) as ex:
                        print(f"  {ex}")
            else:
                if command_mode:
                    print(f"  don't understand command: {line!r}  (try ':help')")
                    continue
                result = parse(line, b, left, seed, world.date.absolute, client)
                if result.unavailable:
                    print("  the model is unavailable. use ':' commands (try ':help').")
                elif result.question:
                    if left:
                        spent += 1
                        print(f"  Yabninu: {result.question}")
                    else:
                        print("  Yabninu has no audience hour left to clarify.")
                else:
                    cost = sum(action_cost(action) for action in result.actions)
                    proceed = cost <= left
                    if proceed and cost > 3:
                        answer = input(f"  That is {cost} hours of your {left}. Proceed? [y/N] ")
                        proceed = answer.lower().startswith("y")
                    if not proceed:
                        print(f"  not hours enough. that would take {cost}; you have {left}.")
                        continue
                    used = 0
                    for action in result.actions:
                        try:
                            needed = action_cost(action)
                            if used + needed > left:
                                print("  the remaining actions do not fit in the audience.")
                                break
                            if isinstance(action, A.EndTurn):
                                end = True
                            elif isinstance(action, A.ReadLetter):
                                item = next(x for x in b["stack"] if x["id"] == action.letter_id)
                                print("\n" + render.letter_full(item))
                                commit(action)
                                used += action_cost(action)
                            elif isinstance(action, A.DictateReply):
                                used += desk_reply(action.letter_id, action.intent, left - used)
                            else:
                                evs = commit(action)
                                used += action_cost(action)
                                if isinstance(action, A.SendGift):
                                    sent = next(
                                        (e for e in evs if isinstance(e, A.GiftSent)),
                                        None)
                                    if sent:
                                        print(f"  gift {sent.gift_id} is dispatched.")
                                if isinstance(action, A.InspectLedger):
                                    event = next((e for e in evs if isinstance(e, A.LedgerInspected)), None)
                                    if event:
                                        print(f"  you count {render.fmt_good('grain', event.true_value)}.")
                        except ValueError as ex:
                            print(f"  {ex}")
                            break
                    spent += used


if __name__ == "__main__":
    argv = [arg for arg in sys.argv[1:] if arg != "--no-ai"]
    sc = argv[0] if argv else "ugarit"
    sd = int(argv[1]) if len(argv) > 1 else 8814402919
    run(sc, sd, "--no-ai" in sys.argv)
