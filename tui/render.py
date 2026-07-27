"""ASCII rendering of Belief (spec Part 9). Reads only the projected dict.

Plain terminal output for M1 -- Textual arrives when tabs and scrolling earn
their weight (M2+). Numbers show in display units with a remainder, the way the
tablets do it. No colour dependency; glyphs and words carry the meaning.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

_CONTENT = Path(__file__).parent.parent / "content"
_LETTERS = tomllib.loads((_CONTENT / "corpus" / "letters.toml").read_text())
_ACTORS = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]


def actor_name(actor: str, house: dict | None = None) -> str:
    """Correspondents are named in actors.toml; a successor who took the seat
    mid-run is only named in the house, so fall back to it rather than printing
    a person id at the player."""
    if actor in _ACTORS:
        return _ACTORS[actor]
    if house:
        for person in house.get("members", ()):
            if person["id"] == actor:
                return person["name"]
    return actor


def letter_summary(topic: str) -> str:
    return _LETTERS.get(topic, {}).get("summary", topic)


def letter_body(sender: str, topic: str, facts: dict) -> str:
    tpl = _LETTERS.get(topic, {}).get("template")
    if tpl is None:
        return f"(a letter from {actor_name(sender)} concerning {topic})"
    fields = dict(facts)
    fields.setdefault("sender", actor_name(sender))
    try:
        return tpl.format(**fields)
    except KeyError:
        return tpl        # missing fact placeholder: show the raw template


# Display units, authored in content/goods.toml since M8 (spec 6.2).
_GOODS = tomllib.loads((_CONTENT / "goods.toml").read_text())
_DISPLAY = {
    good: (spec["display_unit"], int(spec.get("per_display", 1)))
    for good, spec in _GOODS.items()
}


def fmt_good(good: str, amount: int) -> str:
    """The large unit with a remainder, the way the tablets do it: bronze is
    counted in talents and shekels, grain in parisu and qa (spec 6.2)."""
    unit = _DISPLAY.get(good)
    if unit is None or unit[1] <= 1:
        return f"{amount:,}"
    name, per = unit
    base = _GOODS.get(good, {}).get("unit", "qa")
    return f"{amount // per:,} {name} {amount % per} {base}"


def _bar(value: int, total: int, width: int = 10) -> str:
    filled = 0 if total <= 0 else min(width, value * width // total)
    return "▓" * filled + "░" * (width - filled)


_ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
          "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx")


def _num(i: int) -> str:
    return _ROMAN[i] if i < len(_ROMAN) else str(i + 1)


def header(b: dict) -> str:
    title = f"{actor_name(b['actor'], b.get('house')).upper()} OF {b['scenario'].upper()}"
    sea = "OPEN" if b["sea_open"] else "SHUT"
    return (f"  {title} · {b['date']} · sea: {sea}\n"
            f"  audience  {_bar(b['attention'], b['attention_base'])}  "
            f"{b['attention']} / {b['attention_base']}     "
            f"unrest {b['unrest']}   legitimacy {b['legitimacy']}")


def stack_screen(b: dict) -> str:
    """The Stack: the morning's pile, as it stands (spec 9.1)."""
    stack = b["stack"]
    unread = sum(1 for it in stack if not it["read"])
    lines = [f"  THE STACK — {len(stack)} on the pile, {unread} unread", ""]
    if not stack:
        lines.append("    (nothing has come. the harbour is quiet.)")
    for i, it in enumerate(stack):
        dim = " " if not it["read"] else "·"
        label = f"{_num(i)}."
        lines.append(f"  {it['freshness']} {label:<5}{actor_name(it['sender']):<34}"
                     f"{letter_summary(it['topic'])[:34]:<34} {dim}")
    return "\n".join(lines)


def searchable_text(it: dict) -> str:
    body = letter_body(it["sender"], it["topic"], it["facts"])
    return f"{actor_name(it['sender'])} {letter_summary(it['topic'])} {body}".lower()


def archive_screen(b: dict, matches: list | None = None) -> str:
    """Every document received, by received turn only -- it cannot sort by the
    senders' own dates, which share no epoch (spec 6.17)."""
    items = b["archive"] if matches is None else matches
    lines = ["  THE ARCHIVE — sorted by the turn it reached your hand", ""]
    if matches is not None:
        lines[0] = f"  THE ARCHIVE — {len(items)} document(s) found"
    if not items:
        lines.append("    (nothing found.)")
    for it in items:
        r = "read" if it["read"] else "    "
        lines.append(f"  {it['freshness']} [turn {it['received_turn']:>3}] {r}  "
                     f"{actor_name(it['sender']):<32}{letter_summary(it['topic'])[:28]:<28} {it['id']}")
    lines.append("\n  open one with:  read <id>        search with:  search <word>")
    return "\n".join(lines)


def letter_full(it: dict, body: str | None = None) -> str:
    """`body` is the Voicer's text when it is ready (M7); without it the
    authored template stands, which is the game with the model off."""
    who = actor_name(it["sender"])
    if body is None:
        body = letter_body(it["sender"], it["topic"], it["facts"])
    return f"  ── {who} ──\n\n  " + body.replace("\n", "\n  ") + "\n"


def desk_screen(recipient: str, intent: str, draft) -> str:
    score = draft.score
    checks = (
        ("address", score.address_ok),
        ("prostration", score.prostration_ok),
        ("self-designation", score.self_designation_ok),
        ("one topic", score.topic_count <= 1),
    )
    lines = [
        f"  THE DESK — to {actor_name(recipient)}",
        f"  intent: {intent}   source: {draft.source}",
        "",
        "  " + draft.text.replace("\n", "\n  "),
        "",
        "  PROTOCOL  " + "  ".join(f"{'✓' if ok else '✗'} {name}" for name, ok in checks),
        f"  score {score.total} / 1000",
    ]
    if score.violations:
        lines.append("  Yabninu warns: " + ", ".join(score.violations))
    else:
        lines.append("  Yabninu: the forms are in order, my lord.")
    lines.append("\n  [send] [split] [dictate] [burn]")
    return "\n".join(lines)


def lists_screen(b: dict) -> str:
    """The payroll. The most important screen in the game (spec 9.3)."""
    lines = ["  RATION LISTS, in the order they are paid", ""]
    lines.append(f"    {'group':<28}{'heads':>6}{'ration':>7}{'allocated':>11}"
                 f"{'owed wk':>9}  loyalty")
    by_id = {g["id"]: g for g in b["groups"]}
    order = b["priority"] + [g["id"] for g in b["groups"] if g["id"] not in b["priority"]]
    for gid in order:
        g = by_id[gid]
        weeks = g["arrears_weeks"]
        mark = " " if weeks == 0 else ("!" if weeks < 4 else "#")
        lines.append(f"  {mark} {g['name']:<28}{g['size']:>6}{g['entitlement']:>7}"
                     f"{g['allocated']:>11}{weeks:>9}  {g['loyalty']}")
    return "\n".join(lines)


BLOCKS = " ▁▂▃▄▅▆▇█"


def sparkline(series: list, width: int = 24) -> str:
    """24 fortnights, one column each (spec 9.4). Scaled to the window's own
    range, so what it shows is the shape of the year, not the size of the pile."""
    values = list(series)[-width:]
    if not values:
        return ""
    low, high = min(values), max(values)
    if high == low:
        return BLOCKS[4] * len(values)
    step = len(BLOCKS) - 1
    return "".join(
        BLOCKS[(value - low) * step // (high - low)] for value in values)


def stores_screen(b: dict) -> str:
    """Spec 9.3 tab 3. The melt ledger sits among the metals with no emphasis,
    because the whole design of 6.5 is that nothing announces it."""
    history = b.get("store_history", {})
    lines = ["  STORES", ""]
    for good in b["stores"]:
        spark = sparkline(history.get(good, []))
        lines.append(f"    {good:<14}{fmt_good(good, b['stores'][good]):>28}"
                     f"   {spark}")
    metal = b.get("metal")
    if metal:
        lines.append("")
        lines.append(f"    {'in circulation':<14}"
                     f"{fmt_good('bronze', metal['bronze_in_circulation']):>28}")
        lines.append(f"    {'melted to date':<14}"
                     f"{fmt_good('bronze', metal['melt_ledger']):>28}")
    return "\n".join(lines)


def justice_screen(b: dict) -> str:
    """The command-mode form of the court. The windowed game draws the room."""
    petitions = b.get("justice", {}).get("petitions", [])
    lines = ["  THE COURT OF JUSTICE", ""]
    if not petitions:
        lines.append("    no one waits for a judgement.")
        return "\n".join(lines)
    for index, petition in enumerate(petitions):
        lines.append(
            f"  {index + 1}. {actor_name(petition['petitioner'], b.get('house'))}"
            f" against {actor_name(petition['against'], b.get('house'))}"
            f" — {petition['kind']}, {petition['waiting']} fortnights waiting")
        precedent = petition.get("precedent")
        if precedent:
            lines.append(
                f"     cites {precedent['document_ref']}: "
                f"{precedent['verdict']} in an earlier {precedent['kind']} case")
        if petition["heard"]:
            lines.append(f"     claim: {petition['claim_text']}")
            lines.append(f"     answer: {petition['counter_text']}")
        else:
            lines.append("     (neither man has been heard)")
    lines.append(
        "\n  hear <case>  (1 hour)    rule <case> for|against|split|defer")
    return "\n".join(lines)


def land_screen(b: dict) -> str:
    """What the ruler can find out about his own fields, which is not much.

    No yield, no forecast, no index. A reading, a memory, and his own orders.
    """
    land = b.get("land")
    if not land:
        return "  THE LAND — (this house holds no estates.)"
    lines = ["  THE LAND — the gauge, last year's floor, and your standing orders", ""]
    lines.append(f"    the river gauge stands at {land['gauge']}")
    lines.append(f"    last year's threshing floor   "
                 f"{fmt_good('grain', land['last_harvest']):>28}")
    lines.append(f"    the year before               "
                 f"{fmt_good('grain', land['previous_harvest']):>28}")
    lines.append(f"    due ordered                  "
                 f"{land['land_due_rate']:>5}/1000; last taken "
                 f"{fmt_good('grain', land['last_land_due'])}")
    lines.append("")
    seed, ground = land["seed_in_store"], land["seed_in_ground"]
    want = land["seed_recommended"]
    # The store reads nought for most of the year because the seed is in the
    # ground, which is not a shortage. Only flag it when the fields are bare.
    # Flag a real shortfall, not the spoilage a full store loses between the
    # threshing floor and the sowing.
    short = "!" if not ground and seed * 20 < want * 19 else " "
    lines.append(f"  {short} seed in store                 "
                 f"{fmt_good('grain', seed):>28}")
    lines.append(f"    seed in the ground            "
                 f"{fmt_good('grain', ground):>28}")
    lines.append(f"    the sowing asks for            "
                 f"{fmt_good('grain', want):>28}")
    lines.append("")
    supplied, needed = land["labour_days_this_turn"], land["labour_days_needed"]
    lines.append(f"    hands on the land this fortnight  {supplied:,} days "
                 f"against {needed:,} the season asks")
    if land["hands_to_the_fields"]:
        who = ", ".join(land["hands_to_the_fields"])
        lines.append(f"    ordered to the fields: {who}")
    if land["corvee_days"]:
        lines.append(f"    corvee raised this season: {land['corvee_days']:,} days")
        if land.get("works_days"):
            lines.append(f"    of which given to the works: "
                         f"{land['works_days']:,} days")
    lines.append("")
    for estate in land["estates"]:
        note = f"   hands {estate['hands'] // 10}%"
        if estate["irrigated"]:
            note += f"; canal at {estate['canal_condition']}"
        lines.append(f"    {estate['name']:<44}{note}")
    lines.append("\n  order hands to the fields with:  harvest <group>")
    return "\n".join(lines)


def troops_screen(b: dict) -> str:
    """The army, which is one page long and always will be (D25).

    No strengths of anybody else's, no readiness figure, no assessment. Where
    the men are, what they were told to do, and which musters have been demanded
    of him and read. A summons he has not read is not here.
    """
    troops = b.get("troops") or {}
    if not troops:
        return "  TROOPS\n\n    you have no formations."
    lines = ["  TROOPS — where they stand and what they were told", ""]
    for f in troops["formations"]:
        lines.append(f"    {f['name']:<34}{f['strength']:>5} men   "
                     f"{f['task']:<9} at {f['place']}")
    lines.append("")
    for place, strength in sorted(troops["garrisons"].items()):
        lines.append(f"    holding {place:<26}{strength:>5} men")
    for summons in troops["summons"]:
        lines.append("")
        state = "OVERDUE" if summons["overdue"] else f"by turn {summons['due_turn']}"
        lines.append(f"    summoned under {summons['oath_id']}: "
                     f"{summons['required']} men to {summons['place']}, {state}")
        lines.append(f"      mustered there: {summons['mustered']} men")
    lines.append("\n  order them with:  assign <formation> "
                 "garrison|watch|harvest|campaign [place]")
    return "\n".join(lines)


def relations_screen(b: dict) -> str:
    lines = ["  KNOWN WORLD — claims, gifts, and obligations", ""]
    for relation in b["relations"]:
        theirs = relation["their_status_claim"]
        status = relation["status_claim"]
        if theirs != status:
            status = f"{status} / they say {theirs}"
        obligation = relation["obligation"]
        debt = (f"they owe {obligation}" if obligation >= 0
                else f"we owe {-obligation}")
        lines.append(f"  {actor_name(relation['other'])}")
        lines.append(
            f"      esteem {relation['esteem']}; status {status}; {debt}")
        if relation["best_known_rival_gift"]:
            source = relation["known_rival_gift_source"] or "another court"
            lines.append(
                f"      compares gifts against {relation['best_known_rival_gift']} "
                f"received by {actor_name(source)}")
        if relation["seeking_patron"]:
            lines.append("      ! word has come: they are seeking another patron")
    return "\n".join(lines)


def house_screen(b: dict) -> str:
    """Tab 5 (spec 9.3). The family as a small tree, the queen mother apart."""
    house = b.get("house")
    if not house:
        return "  THE HOUSE — (no house is recorded.)"
    members = {p["id"]: p for p in house["members"]}
    ruler = members.get(house["ruler"])
    lines = [f"  THE HOUSE — regnal year {b['regnal_year']}, "
             f"reign {house['reigns']} of this run", ""]

    def person_line(p: dict, indent: str) -> str:
        marks = []
        if p["heir_rank"]:
            marks.append(f"heir {p['heir_rank']}")
        if p.get("named_heir"):
            marks.append("NAMED HEIR")
        if p.get("post"):
            marks.append(p["post"])
        if p["expecting"]:
            marks.append("with child")
        if p["married_to_court"]:
            marks.append(f"at the court of {actor_name(p['married_to_court'])}")
        width = max(4, 30 - len(indent))
        if not p["alive"]:
            return f"{indent}{p['name']:<{width}} died in turn {p['died_turn']}"
        note = ("   " + ", ".join(marks)) if marks else ""
        return (f"{indent}{p['name']:<{width}}{p['age_years']:>3}  "
                f"{p['health']:<16}{note}")

    if ruler:
        lines.append(person_line(ruler, "  "))
        spouse = members.get(ruler["spouse"] or "")
        if spouse:
            lines.append(person_line(spouse, "  ├─ "))
        children = [p for p in house["members"]
                    if p["father"] == ruler["id"] and p["alive"]]
        for i, child in enumerate(children):
            stem = "  └─ " if i == len(children) - 1 else "  ├─ "
            lines.append(person_line(child, stem))

    # The queen mother has her own block because she is an institution, not a
    # relative (spec 6.10).
    mother = next((p for p in house["members"] if p["is_queen_mother"]), None)
    if mother:
        lines.append("")
        lines.append("  THE QUEEN MOTHER'S HOUSE")
        lines.append(person_line(mother, "  "))
        if mother["alive"] and mother["agenda"]:
            lines.append(f"      she is understood to want: {mother['agenda']}")

    shown = {house["ruler"]}
    if ruler:
        shown.add(ruler.get("spouse"))
        shown.update(p["id"] for p in house["members"]
                     if p["father"] == ruler["id"])
    shown.update(p["id"] for p in house["members"] if p["is_queen_mother"])
    kin = [p for p in house["members"]
           if p["alive"] and p["id"] not in shown]
    if kin:
        lines.append("")
        lines.append("  KIN AT COURT")
        for person in kin:
            lines.append(person_line(person, "  "))

    # The queen mother has her own block above; she is not listed twice.
    buried = [p for p in house["members"]
              if not p["alive"] and not p["is_queen_mother"]]
    if buried:
        lines.append("")
        lines.append("  THOSE WHO ARE GONE")
        for person in buried:
            lines.append(person_line(person, "    "))

    if house["omens"]:
        lines.append("")
        lines.append("  OMENS TAKEN")
        for omen in house["omens"]:
            state = "published" if omen["published"] else "suppressed"
            defied = ", and defied" if omen["defied"] else ""
            subject = f" ({omen['subject']})" if omen["subject"] else ""
            lines.append(f"    {omen['id']:<5} turn {omen['turn']:>3}  "
                         f"{omen['question']}{subject}: {omen['reported']}"
                         f"  [{state}{defied}]")
    lines.append(
        "\n  ask for a forecast with:  "
        "omen harvest | omen death <person> | omen route")
    return "\n".join(lines)


def oaths_screen(b: dict) -> str:
    lines = ["  OATH TABLETS — the clauses the court has recorded", ""]
    for oath in b["oaths"]:
        state = ("dissolved" if oath["dissolved"]
                 else "LAPSED — nobody is bound" if oath["lapsed"] else "sworn")
        lines.append(
            f"  {oath['id']}  ({state})  before {', '.join(oath['gods'])}")
        lines.append(
            f"      parties: {', '.join(actor_name(p) for p in oath['parties'])}")
        if oath["lapsed"]:
            lines.append(f"      it was sworn by {actor_name(oath['sworn_by'])},"
                         " who is dead.  swear it again with:  swear "
                         f"{oath['id']}")
        for clause in oath["clauses"]:
            args = ", ".join(
                f"{key}={value}" for key, value in sorted(clause["args"].items()))
            lines.append(f"      · {clause['kind']}({args})")
    if not b["oaths"]:
        lines.append("    (no oath tablet is held in this archive.)")
    return "\n".join(lines)


def tablets_screen(b: dict, query: str | None = None) -> str:
    """The tablet house (spec 6.17): the permanent record, including the
    documents that were already here when the king sat down.

    Sorted by `received_turn` and nothing else, so the predecessor archive --
    which carries negative turns -- sits above everything the player has lived
    through. Search costs an hour, which is why the query line says so.
    """
    index = b.get("archive_index") or {}
    lines = [f"  THE TABLET HOUSE — {index.get('size', 0)} tablets", ""]
    if query is None:
        for q in index.get("searched", []):
            lines.append(f"  you asked for: '{q}'")
        lines.append("")
        lines.append("  search it with:  tablets <word> [<word>...]   (costs an hour)")
        lines.append("  open one with:   tablet <ref>")
        return "\n".join(lines)
    hits = (index.get("hits") or {}).get(query, [])
    lines[0] = f"  THE TABLET HOUSE — {len(hits)} tablet(s) answer to '{query}'"
    if not hits:
        lines.append("    (the keeper looks, and finds nothing of that.)")
    for hit in hits:
        # The sender's own date, in the sender's own calendar. Shown as written
        # and never converted, because there is nothing to convert it to.
        lines.append(
            f"  [{hit['ref']}]  {hit.get('dated_as') or 'undated':<38} "
            f"{hit['kind'].replace('_', ' ')}")
        lines.append(f"        {hit.get('title') or ''}")
    lines.append("\n  open one with:  tablet <ref>")
    return "\n".join(lines)


def tablet_full(hit: dict, body: str) -> str:
    who = f" — {actor_name(hit['sender'])}" if hit.get("sender") else ""
    return (f"  ── [{hit['ref']}]{who} ──\n"
            f"  {hit.get('dated_as') or 'undated'}\n\n  "
            + body.replace("\n", "\n  ") + "\n")


def plague_screen(b: dict) -> str:
    """What the palace knows about the sickness, which is very little.

    No counts of the sick, because nobody counts the sick. A count of the
    buried, because somebody does count graves. And a list of the offerings the
    king has made, in the order he made them, with NO indication of whether any
    of them was the right one -- see spec 6.12. Do not add a verdict column.
    """
    p = b.get("plague") or {}
    if not p:
        return "  There is no word of sickness."
    lines = ["  THE SICKNESS", ""]
    if p.get("sickness_at_seat"):
        lines.append("  There is sickness in the city.")
    else:
        lines.append("  There is no sickness in the city that anyone has reported.")
    if p.get("burials_at_seat"):
        lines.append(f"  The gravediggers' count stands at {p['burials_at_seat']}.")
    closed = p.get("quarantined") or []
    if closed:
        lines.append("  Closed against: " + ", ".join(closed)
                     + "   (open again with:  open <place>)")
    else:
        lines.append("  No road or harbour is closed.  (close one with:  close <place>)")
    offerings = p.get("offerings_made") or []
    if offerings:
        lines.append("")
        lines.append("  Offerings made, in order:")
        for oath_id in offerings:
            lines.append(f"    · against {oath_id}")
        lines.append("  What the gods made of them is not written anywhere.")
    else:
        lines.append("")
        lines.append("  No offering has been made.  (make one with:  expiate <oath> [qa])")
    return "\n".join(lines)


def events_lines(events, court) -> list[str]:
    """Diegetic footer lines for what the turn's advance surfaced."""
    from engine import actions as A
    out = []
    arrivals = [e for e in events if isinstance(e, A.LetterArrived)]
    if arrivals:
        senders = ", ".join(sorted({actor_name(e.sender) for e in arrivals}))
        out.append(f"  A courier has come. On the pile now: {senders}.")
    for e in events:
        if isinstance(e, A.RiteSkipped):
            out.append(f"  The temple records that the rite '{e.rite_id}' was not kept.")
        elif isinstance(e, A.GiftSent):
            out.append(
                f"  Gift {e.gift_id} leaves for {actor_name(e.recipient)}.")
        elif isinstance(e, A.GiftJudged):
            out.append(
                f"  Word comes that gift {e.gift_id} reached "
                f"{actor_name(e.recipient)}.")
        elif isinstance(e, A.PatronSought):
            out.append(
                f"  A merchant whispers: {actor_name(e.actor)} seeks another patron.")
        elif isinstance(e, A.PlagueBegan) and e.place_id == court.seat:
            # Sickness at the seat is directly observable. A foreign authored
            # introduction is World truth and stays off this court report until
            # a traveller or correspondent actually brings word of it.
            out.append("  There is sickness in the city. Men are lying in the "
                       "streets by the customs house.")
        elif isinstance(e, A.PlagueDeaths) and e.place_id == court.seat:
            out.append(f"  The gravediggers have taken {e.dead} more.")
        elif isinstance(e, A.OathExpiated):
            # Note what is NOT here: whether it worked. Nobody at court knows,
            # so nobody at court can say (spec 6.12).
            out.append(f"  The offering is made against {e.oath_id}. "
                       "The god does not answer.")
        elif isinstance(e, A.QuarantineSet):
            out.append(
                f"  The way to {e.place_id} is open again." if e.lifted
                else f"  The way to {e.place_id} is closed. Nothing comes in "
                     "from there, including word.")
        elif isinstance(e, A.Sown):
            short = e.recommended_qa - e.seed_qa
            out.append(
                f"  The sowing is done: {fmt_good('grain', e.seed_qa)} into the ground."
                + (f" It is {fmt_good('grain', short)} short of the rate."
                   if short > 0 else ""))
        elif isinstance(e, A.Threshed):
            out.append(
                f"  The threshing floor is counted: {fmt_good('grain', e.qa)}.")
        elif isinstance(e, A.LandDueTaken):
            out.append(
                f"  At {e.rate} in a thousand, the due brings "
                f"{fmt_good('grain', e.taken)} to the crown.")
        elif isinstance(e, A.MerchantWithdrew):
            out.append(
                f"  Word comes that {actor_name(e.actor)} is clearing "
                "his cargoes elsewhere.")
        elif isinstance(e, A.CorveeRaised):
            out.append(f"  The levy is called: {e.days:,} days of labour.")
        # Finishing is announced; progress is not, and a fortnight in which the
        # men did nothing is not announced either. A building site is a thing
        # you can walk to and look at, so the fortnight report has no business
        # narrating it (D19). The opening of a new granary, on the other hand,
        # is a day the city keeps.
        elif isinstance(e, A.WorkFinished):
            out.append(f"  {e.what} is finished." if not e.built
                       else f"  {e.what} stands open. Nobody is over it yet.")
        # The house, unlike the melt ledger, is announced. A death in the
        # family is not a number on a page nobody reads; it is the loudest
        # thing that happens in a fortnight.
        elif isinstance(e, A.ChildBorn):
            what = "a daughter" if e.sex == "f" else "a son"
            out.append(f"  {what} is born to the house, and lives.")
        elif isinstance(e, A.HouseMemberDied):
            out.append(f"  {e.name} is dead, in the {e.age_years}th year. "
                       "The house is in mourning.")
        elif isinstance(e, A.RulerSucceeded):
            out.append(f"  {e.name} takes the seat. It is the first year of "
                       "his reign, and the scribes begin the count again.")
            if e.contested:
                out.append(f"  {e.rivals} other claim(s) were heard. "
                           "Not everyone in the house is content.")
            out.append("  Every oath sworn by the dead king has lapsed with "
                       "him. Nobody is bound. See the oath tablets.")
        elif isinstance(e, A.SuccessionFailed):
            out.append("  There is no heir. The seat is empty and the "
                       "household looks at the door.")
        elif isinstance(e, A.OmenLeaked):
            out.append("  What the diviner said is being repeated in the "
                       "lower town, and not as you told it.")
    # Deliberately absent: anything at all about the melt ledger. Spec 6.5 --
    # "Nothing announces this. No warning, no alert, no colour change." The
    # number is on the STORES tab if the player looks, and that is the whole
    # mechanic. Do not add a line here.
    return out
