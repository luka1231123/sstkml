"""Interactive terminal controller for the same model-backed court.

Holds the World, drives the turn pipeline, projects Belief, renders it, and
turns typed commands into Actions. Everything reachable here is reachable
headlessly through structured actions, while the playable court requires the
same lightweight local language model as the windowed desktop.

Attention is enforced here, in Phase C: reading a letter costs hours, and the
pile is longer than the budget. Triage is the game.
"""
from __future__ import annotations

import sys

from ai.parser import LETTER_ONLY_DIPLOMACY
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_scenario
from session import new_seed
from tui import render

READ_COST = 2
REPLY_COST = 2
INSPECT_COST = 1
SEARCH_COST = 1

HARVEST_COST = 1
CORVEE_COST = 1
WORKS_COST = 1
ASSIGN_COST = 1
DREDGE_COST = 1
OMEN_COST = 2
SWEAR_COST = 2
SEARCH_COST = 1       # spec 6.17: one hour per query, and it is a real hour
EXPIATE_COST = 2
QUARANTINE_COST = 1
SUPPRESS_COST = 2
HEAR_COST = 1


def _guard_player_action(action) -> None:
    """Keep compatibility actions out of every live terminal mutation path."""
    if isinstance(action, (A.SendGift, A.MarryAbroad)):
        raise ValueError(LETTER_ONLY_DIPLOMACY)


HELP = """  commands (a leading ':' is optional)
    stack | lists | stores | archive | relations | oaths | land | house
    plague | tablets | troops | justice
    read <i>                 read a letter in full            (2 hours)
    reply <i> <intent>       answer it with a free-text intent        (2 hours)
    dictate <i>              write the reply yourself, ending with '.' (2 hours)
    inspect granary|seed     count it yourself; see the true number   (1 hour)
    search <word>            search the archive               (1 hour)
    alloc <group> <qa>       set what a group is paid  (effect next turn)
    pri <group> <group>..    set the pay-down order
    eat <qa>                 move seed grain into the granary now
    gift | marry             write these as terms at World → Desk
    harvest <group>          order a group to the fields          (1 hour)
    recall <group>           send it back to its own work         (1 hour)
    corvee <days>            levy labour outside the lists; costs unrest (1 hour)
    assign <formation> <task> [place]
                             garrison | watch | harvest | campaign   (1 hour)
    dredge <estate> <days>   restore a canal, at low water only   (1 hour)
    build <kind> [place]     put something up; it eats corvee and grain (1 hour)
    repair <institution>     make a thing whole; cheaper than building (1 hour)
    abandon <work>           call the men off; what they ate is gone (1 hour)
    hear <case>              hear claim and counter-claim             (1 hour)
    rule <case> <verdict>    for | against | split | defer
    landdue <rate>           set the land due per thousand
    harbourdue <rate>        set the harbour due per thousand
    place <person> <post>    institution, governor:<place>,
                             command:<formation>, or court:<actor>
    dismiss <post>           leave that office vacant
    heir <person>            name one living son as heir
    omen harvest|route       ask the diviner about the year       (2 hours)
    omen death <person>      ask whether a man has long           (2 hours)
    hush <omen>              keep an omen off the record; it may leak (2 hours)
    defy <omen>              act against it; costs legitimacy either way
    swear <oath>             re-swear an oath that lapsed on a death (2 hours)
    tablets <word>..         search the tablet house, incl. what your
                             predecessors left                    (1 hour)
    tablet <ref>             read one out in full
    expiate <oath> [qa]      make an offering against one named oath (2 hours)
    close <place>            shut the road and harbour to a place  (1 hour)
    open <place>             open it again                         (1 hour)
    end                      end the fortnight
    save <path>              write a save file
    help  |  quit

  Plain English goes to the local court-language model, then through the
  exact action validator. Colon commands remain the direct structured path."""


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


def _resolve_petition(token: str, petitions: list[dict]) -> str | None:
    token = token.lower()
    if token.isdigit():
        index = int(token) - 1
        return petitions[index]["id"] if 0 <= index < len(petitions) else None
    return next(
        (petition["id"] for petition in petitions
         if petition["id"].lower() == token),
        None)


def _raw_tablet() -> str:
    print("  Dictate the tablet. A line containing only '.' seals the text.")
    lines = []
    while True:
        line = input("  tablet> ")
        if line == ".":
            return "\n".join(lines)
        lines.append(line)


def run(scenario: str = "ugarit", seed: int | None = None) -> None:
    from ai.client import (
        OllamaClient, model_status, required_model_message)
    from ai.composer import compose, raw_draft, split_draft
    from ai.parser import action_cost, parse
    from ai.voicer import Voicer

    if seed is None:
        seed = new_seed()
    ready, detail = model_status()
    if not ready:
        print(required_model_message(detail))
        return
    print(f"  seed {seed} — replay this same world with:  "
          f"./run.sh --cli {scenario} {seed}\n")
    world = load_scenario(scenario, seed)
    log: list[dict] = []
    ai_log: list[dict] = []
    client = OllamaClient(ai_log, f"saves/{scenario}/ai_cache")
    voicer = Voicer(client, seed)
    turns = 0
    screen = "stack"
    print("\n  SAY TO THE KING, MY LORD\n")

    while True:
        world, events = advance(world)
        turns += 1
        b = project(world)
        # Spec 8.7: bodies fill in Stack order behind the player, top first.
        # This returns immediately; nothing below ever waits on it.
        voicer.schedule(b["stack"], world.date.absolute)
        spent = 0
        print("\n" + "═" * 78)
        print(render.header(b))
        for ln in render.events_lines(events, world.court):
            print(ln)
        if voicer.note():
            print(voicer.note())
        print()

        def commit(action):
            nonlocal world
            _guard_player_action(action)
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
        tablet_query = None
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
            elif screen == "land":
                print(render.land_screen(b))
            elif screen == "house":
                print(render.house_screen(b))
            elif screen == "plague":
                print(render.plague_screen(b))
            elif screen == "troops":
                print(render.troops_screen(b))
            elif screen == "justice":
                print(render.justice_screen(b))
            elif screen == "tablets":
                print(render.tablets_screen(b, tablet_query))
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

            if verb in ("stack", "lists", "stores", "archive", "relations",
                        "oaths", "land", "house", "plague", "tablets",
                        "troops", "justice"):
                screen = verb
                if verb != "archive":
                    search_results = None
                if verb == "tablets" and not args:
                    tablet_query = None
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
                    print("\n" + render.letter_full(it, voicer.body(it)[0]))
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
            elif verb in ("harvest", "recall") and len(args) == 1:
                if left < HARVEST_COST:
                    print("  no hour remains to send the order out.")
                else:
                    try:
                        commit(A.SendToHarvest(args[0], verb == "harvest"))
                        spent += HARVEST_COST
                        print("  the order goes out to the fields."
                              if verb == "harvest" else
                              "  they are sent back to their own work.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "assign" and len(args) in (2, 3):
                if left < ASSIGN_COST:
                    print("  no hour remains to move men.")
                else:
                    try:
                        commit(A.AssignTroops(
                            args[0], args[1], args[2] if len(args) == 3 else ""))
                        spent += ASSIGN_COST
                        print("  the order is given. They march, or they stand,"
                              " where you have said.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "corvee" and len(args) == 1:
                if left < CORVEE_COST:
                    print("  no hour remains to summon the levy.")
                else:
                    try:
                        evs = commit(A.RaiseCorvee(int(args[0])))
                        spent += CORVEE_COST
                        raised = next(
                            (e for e in evs if isinstance(e, A.CorveeRaised)), None)
                        if raised:
                            print(f"  {raised.days:,} days are levied. "
                                  f"The villages are not glad of it.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb in ("build", "repair", "abandon") and args:
                if left < WORKS_COST:
                    print("  no hour remains to give the order.")
                else:
                    try:
                        if verb == "build":
                            order = A.BeginBuild(
                                args[0], args[1] if len(args) > 1
                                else world.court.seat)
                        elif verb == "repair":
                            order = A.BeginRepair(args[0])
                        else:
                            order = A.AbandonWork(args[0])
                        evs = commit(order)
                        spent += WORKS_COST
                        begun = next((e for e in evs
                                      if isinstance(e, A.WorkBegun)), None)
                        if begun:
                            print(f"  the men are called to {begun.what}: "
                                  f"{begun.days_needed:,} days of labour.")
                        off = next((e for e in evs
                                    if isinstance(e, A.WorkAbandoned)), None)
                        if off:
                            print(f"  they go home. {off.days_lost:,} days "
                                  f"and what they ate stay spent.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "hear" and len(args) == 1:
                petitions = b.get("justice", {}).get("petitions", [])
                petition_id = _resolve_petition(args[0], petitions)
                if petition_id is None:
                    print("  no such petition waits in the hall.")
                elif left < HEAR_COST:
                    print("  no hour remains to hear both men.")
                else:
                    try:
                        commit(A.HearPetition(petition_id))
                        spent += HEAR_COST
                        screen = "justice"
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "rule" and len(args) == 2:
                petitions = b.get("justice", {}).get("petitions", [])
                petition_id = _resolve_petition(args[0], petitions)
                if petition_id is None:
                    print("  no such petition waits in the hall.")
                else:
                    try:
                        commit(A.RulePetition(petition_id, args[1].lower()))
                        screen = "justice"
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb in ("landdue", "harbourdue") and len(args) == 1:
                try:
                    rate = int(args[0])
                    action = (A.SetLandDue(rate) if verb == "landdue"
                              else A.SetHarbourDue(rate))
                    commit(action)
                    name = "land" if verb == "landdue" else "harbour"
                    print(f"  the {name} due is proclaimed at {rate} "
                          "in a thousand.")
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb == "place" and len(args) == 2:
                try:
                    evs = commit(A.PlacePerson(args[0], args[1]))
                    placed = next(e for e in evs
                                  if isinstance(e, A.PersonPlaced))
                    note = (f"; {placed.displaced} is put out"
                            if placed.displaced else "")
                    print(f"  {placed.person_id} is given {placed.post}{note}.")
                    screen = "house"
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb == "dismiss" and len(args) == 1:
                try:
                    evs = commit(A.DismissPerson(args[0]))
                    gone = next(e for e in evs
                                if isinstance(e, A.PersonDismissed))
                    print(f"  {gone.person_id} is dismissed from {gone.post}.")
                    screen = "house"
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb in ("heir", "name_heir") and len(args) == 1:
                try:
                    commit(A.NameHeir(args[0]))
                    print(f"  {args[0]} is named before the house.")
                    screen = "house"
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb == "dredge" and len(args) == 2:
                if left < DREDGE_COST:
                    print("  no hour remains for the canal.")
                else:
                    try:
                        evs = commit(A.DredgeCanal(args[0], int(args[1])))
                        spent += DREDGE_COST
                        done = next(
                            (e for e in evs if isinstance(e, A.CanalDredged)), None)
                        if done:
                            print(f"  the channel is cleared; it stands at "
                                  f"{done.condition}.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "omen" and args:
                if left < OMEN_COST:
                    print(f"  the liver takes {OMEN_COST} hours to read.")
                else:
                    try:
                        evs = commit(A.ConsultDiviner(
                            args[0], args[1] if len(args) > 1 else ""))
                        spent += OMEN_COST
                        taken = next(
                            (e for e in evs if isinstance(e, A.OmenTaken)), None)
                        if taken:
                            print(f"  the diviner reads the liver and says: "
                                  f"{taken.reported}.   ({taken.omen_id})")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "hush" and len(args) == 1:
                if left < SUPPRESS_COST:
                    print("  there are not hours enough to keep it quiet.")
                else:
                    try:
                        evs = commit(A.SuppressOmen(args[0]))
                        spent += SUPPRESS_COST
                        if any(isinstance(e, A.OmenLeaked) for e in evs):
                            print("  it is kept from the record. by evening "
                                  "the whole quarter is repeating it.")
                        else:
                            print("  it is kept from the record.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "defy" and len(args) == 1:
                try:
                    evs = commit(A.DefyOmen(args[0]))
                    lost = next(
                        (e for e in evs if isinstance(e, A.OmenDefied)), None)
                    if lost:
                        print("  you act against the omen. the temple says "
                              "nothing, and says it loudly.")
                except ValueError as ex:
                    print(f"  {ex}")
            elif verb == "marry":
                print(f"  {LETTER_ONLY_DIPLOMACY}")
            elif verb == "tablets" and args:
                # Spec 6.17: keyword and tag, one hour per query. The hour is
                # the mechanic -- a king hunting a broken oath during an
                # epidemic is spending the attention the granary needed.
                if left < SEARCH_COST:
                    print("  the keeper has gone. it will keep until the morning.")
                else:
                    query = " ".join(args).lower()
                    commit(A.SearchArchive(query))
                    spent += SEARCH_COST
                    screen, tablet_query = "tablets", query
            elif verb == "tablet" and len(args) == 1:
                ref = args[0].upper()
                doc = next((d for d in world.documents if d.ref == ref), None)
                if doc is None:
                    print(f"  there is no tablet [{ref}] in the house.")
                else:
                    hit = {"ref": doc.ref, "sender": doc.sender,
                           "dated_as": doc.dated_as}
                    print(render.tablet_full(hit, doc.body))
            elif verb == "expiate" and args:
                if left < EXPIATE_COST:
                    print("  the offering cannot be made in the hours left.")
                else:
                    try:
                        offering = int(args[1]) if len(args) > 1 else 0
                        commit(A.Expiate(args[0], offering))
                        spent += EXPIATE_COST
                        # Deliberately no verdict, here or anywhere (6.12).
                        print("  the offering is made. the god does not answer.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb in ("close", "open") and len(args) == 1:
                if left < QUARANTINE_COST:
                    print("  there are no hours to send the order.")
                else:
                    try:
                        commit(A.Quarantine(args[0], lift=(verb == "open")))
                        spent += QUARANTINE_COST
                        print("  the road is open again." if verb == "open"
                              else "  the road is closed, and so is the harbour "
                                   "to that place. nothing comes from there now, "
                                   "including word.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "swear" and len(args) == 1:
                if left < SWEAR_COST:
                    print("  the oath needs hours and witnesses.")
                else:
                    try:
                        commit(A.SwearOath(args[0]))
                        spent += SWEAR_COST
                        print("  the gods are named again, and the tablet is sealed.")
                    except ValueError as ex:
                        print(f"  {ex}")
            elif verb == "gift":
                print(f"  {LETTER_ONLY_DIPLOMACY}")
            else:
                if command_mode:
                    print(f"  don't understand command: {line!r}  (try ':help')")
                    continue
                result = parse(line, b, left, seed, world.date.absolute, client)
                if result.unavailable:
                    print("  the court voice failed. retry, or use an exact ':' "
                          "command while the scribe recovers.")
                elif result.question:
                    if left:
                        spent += 1
                        print(f"  Yabninu: {result.question}")
                    else:
                        print("  Yabninu has no audience hour left to clarify.")
                else:
                    if any(isinstance(
                            action, (A.SendGift, A.MarryAbroad))
                           for action in result.actions):
                        print(f"  {LETTER_ONLY_DIPLOMACY}")
                        continue
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
                                print("\n" + render.letter_full(
                                    item, voicer.body(item)[0]))
                                commit(action)
                                used += action_cost(action)
                            elif isinstance(action, A.SendToHarvest):
                                commit(action)
                                used += action_cost(action)
                                print("  the order goes out to the fields."
                                      if action.to_fields else
                                      "  they are sent back to their own work.")
                            elif isinstance(action, A.DictateReply):
                                used += desk_reply(action.letter_id, action.intent, left - used)
                            else:
                                evs = commit(action)
                                used += action_cost(action)
                                if isinstance(action, A.InspectLedger):
                                    event = next((e for e in evs if isinstance(e, A.LedgerInspected)), None)
                                    if event:
                                        print(f"  you count {render.fmt_good('grain', event.true_value)}.")
                        except ValueError as ex:
                            print(f"  {ex}")
                            break
                    spent += used


if __name__ == "__main__":
    argv = sys.argv[1:]
    sc = argv[0] if argv else "ugarit"
    sd = int(argv[1]) if len(argv) > 1 else None
    run(sc, sd)
