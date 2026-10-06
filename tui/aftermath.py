"""A short fortnight briefing with its complete records underneath."""

from belief.facts import facts
from belief.harvest import plan as harvest_plan
from belief.rations import plan as ration_plan
from tui.render import actor_name

_SAID = {
    "Allocate": "you set the rations of {group}",
    "PayArrears": "you paid the arrears of {group}",
    "SendToHarvest": "you gave field orders to {group}",
    "RulePetition": "you gave judgement in a claim",
    "FinanceTrade": "you bought grain at the quay",
    "DispatchLetter": "you sent a tablet to {who}",
    "SendGift": "you sent a gift to {who}",
    "ReceiveCohort": "you answered the people at the gate",
    "RaiseCorvee": "you called up corvée labour",
    "SetLandDue": "you changed the land due",
    "AssignTroops": "you gave the troops new orders",
}

_PLEDGES = {"bread": "Bread in reserve", "wages": "No unpaid worker",
            "justice": "Claims heard on time"}


def receipts(before: dict, after: dict, log=()) -> list[str]:
    """What the king ordered last fortnight, in plain words, for the briefing."""
    groups = {g["id"]: g["name"] for g in after.get("groups", ())}
    out = []
    for record in log:
        act = record.get("action", {})
        if record.get("turn") == before.get("turn") and act.get("_t") in _SAID:
            out.append(_SAID[act["_t"]].format(
                group=groups.get(act.get("group_id"), act.get("group_id")),
                who=actor_name(act.get("recipient", ""), after.get("house"))))
    return out


def follow_through(before: dict, after: dict, log=()) -> list[str]:
    out = []
    groups = {g['id']: g for g in after.get('groups', ())}
    for record in log:
        if record.get('turn') != before.get('turn'):
            continue
        action = record.get('action', {})
        kind = action.get('_t')
        group = groups.get(action.get('group_id'))
        out.extend(record.get('receipt', ()))
        if kind == 'AssignTroops':
            formation = next((f for f in after.get('troops', {}).get('formations', ())
                              if f['id'] == action.get('formation_id')), None)
            if formation:
                out.append(f"New muster roll: {formation['name']}, {formation['strength']:,} men, "
                           f"{formation['task']} at {formation['place'].replace('_', ' ')}.")
        elif kind == 'SendToHarvest' and group:
            out.append(f"Field roll: {group['name']} "
                       f"{'are at the fields' if group.get('at_fields') else 'have returned'}; "
                       f"{group.get('labour_now', 0):,} available person-days.")
        elif kind in {'Allocate', 'PayArrears'} and group:
            label = {'Allocate': 'Ration order', 'PayArrears': 'Debt payment',
                     'SendToHarvest': 'Field order'}[kind]
            out.append(f"{label} for {group['name']}: the new roll records "
                       f"{group.get('arrears_qa', 0):,} qa unpaid.")
    previous = {p['id'] for p in before.get('justice', {}).get('petitions', ())}
    for petition in after.get('justice', {}).get('petitions', ()):
        if petition['id'] in previous:
            who = actor_name(petition['petitioner'], after.get('house'))
            out.append(f"Still waiting: {who}, {petition.get('waiting', 0)} fortnights. "
                       "The Court can still hear this claim.")
    if not out:
        return []
    return ["Your orders and outstanding claims:", *out]


def brief(before: dict, after: dict, log=()) -> list[str]:
    """Lead with changed stakes, actual outcomes, and the next useful door.

    All quantities come from the court's records. A stock increase is never
    called a harvest, nor a field loss called food received.
    """
    out = [f"FORTNIGHT {after.get('turn', '?')} · What changed"]
    if after.get("ended"):
        out.append(after.get("end_reason") or "This reign has ended.")
        out.append("The final account and order receipts remain below.")
        return out
    prior_vows = {record["id"] for record in before.get("pledge_history", ())}
    resolved = [record for record in after.get("pledge_history", ())
                if record["id"] not in prior_vows]
    if resolved:
        vow = resolved[-1]
        label = _PLEDGES.get(vow["kind"], vow["kind"])
        out.append(f"Royal pledge {vow['status']}: {label}; "
                   f"{vow['kept']} of {vow['checked']} closing accounts kept.")
    else:
        vow = after.get("royal_pledge")
        prior = before.get("royal_pledge") or {}
        if vow:
            duration = vow["due_turn"] - vow["start_turn"]
            newly_missed = (vow["kept"] < vow["checked"]
                            and prior.get("kept", 0) == prior.get("checked", 0))
            if newly_missed:
                out.append("Royal pledge: a closing account was missed; "
                           "the six-account vow cannot now be kept.")
            elif vow["checked"] in {1, duration - 1}:
                label = _PLEDGES.get(vow["kind"], vow["kind"])
                left = max(0, vow["due_turn"] - after.get("turn", 0))
                out.append(f"Royal pledge: {label}, {vow['kept']}/{duration} kept; "
                           f"{left} closing account{'s' if left != 1 else ''} left.")
    grain = after.get("stores", {}).get("grain", 0)
    previous_grain = before.get("stores", {}).get("grain", 0)
    need = sum(g.get("size", 0) * g.get("entitlement", 0)
               for g in after.get("groups", ()))
    free = max(0, grain - after.get("ration_reserved", 0))
    cover = (f"{free // need} full payrolls" if need
             else "no dependent payroll")
    out.append(f"Grain {grain:,} qa ({grain - previous_grain:+,}); {cover}.")
    current = facts(after)
    urgent = [fact for fact in current if fact.get("urgency", 0) >= 2]
    if urgent:
        strongest = urgent[0]
        reason = strongest.get("why", ())
        concern = (reason[0] if strongest.get("id") == "grain" and reason
                   else strongest["say"])
        out.append("Needs attention: " + concern + ".")
    movements = sorted(after.get("flows", {}).get("grain", ()),
                       key=lambda flow: abs(flow.get("qty", 0)), reverse=True)
    if movements:
        out.append("Main movements: " + "; ".join(
            f"{flow.get('cause', 'recorded use')} {flow.get('qty', 0):+,} qa"
            for flow in movements[:2]) + ".")

    old_debt = sum(g.get("arrears_qa", 0) for g in before.get("groups", ()))
    debt = sum(g.get("arrears_qa", 0) for g in after.get("groups", ()))
    if debt or old_debt:
        behind = sum(g.get("arrears_qa", 0) > 0 for g in after.get("groups", ()))
        out.append(f"Ration debt {debt:,} qa ({debt - old_debt:+,}); "
                   f"{behind} groups still owed. Storehouse [t].")

    # Quiet successes stay quiet; a purchase or a newly blocked keeper earns
    # a line. Unchanged standing-mandate status remains in the full record.
    previous_mandate = set(before.get("mandate_report", ()))
    for report in after.get("mandate_report", ()):
        if ("reserve is covered" not in report
                and report not in previous_mandate):
            out.append(report)
            break

    old_members = {p["id"]: p for p in before.get("house", {}).get("members", ())}
    lost = [p for p in after.get("house", {}).get("members", ())
            if not p.get("alive", True) and old_members.get(p["id"], {}).get("alive", False)]
    if lost:
        out.append("Death at court: " + ", ".join(p["name"] for p in lost)
                   + ". Review the household in Palace [j].")
    old_ruler = before.get("house", {}).get("ruler")
    new_ruler = after.get("house", {}).get("ruler")
    if old_ruler and new_ruler and old_ruler != new_ruler:
        out.append(f"Succession: {actor_name(new_ruler, after.get('house'))} now rules. "
                   "Check inherited oaths in Shrine [v].")

    prior_accounts = set(before.get("governance", {}).get("receipts", ()))
    out.extend(entry for entry in after.get("governance", {}).get("receipts", ())
               if entry not in prior_accounts)

    orders = [record for record in log
              if record.get("turn") == before.get("turn")
              and record.get("action", {}).get("_t") != "EndTurn"]
    outcomes = [line for record in orders for line in record.get("receipt", ())]
    if outcomes:
        for record in orders[:3]:
            receipt = record.get("receipt", ())
            if receipt:
                first = receipt[0].splitlines()[0].split(". ", 1)[0].rstrip(".")
                out.append("Order: " + first + ".")
        if len(orders) > 3:
            out.append(f"{len(orders) - 3} more orders; complete receipts below.")
    elif orders:
        said = receipts(before, after, log)
        if said:
            out.append("Your orders: " + "; ".join(said[:2]) + ".")

    old_post = {item["id"] for item in before.get("stack", ())}
    post = [item for item in after.get("stack", ())
            if item["id"] not in old_post and not item.get("read")]
    if post:
        senders = list(dict.fromkeys(actor_name(item.get("sender", ""), after.get("house"))
                                    for item in post))
        out.append(f"New post: {len(post)} tablet{'s' if len(post) != 1 else ''} "
                   f"from {', '.join(senders[:2])}"
                   + (" and others" if len(senders) > 2 else "") + ". Scribes [s].")

    if urgent:
        strongest = urgent[0]
        if strongest.get("act"):
            out.append("Next: " + strongest["act"][0] + ".")
    elif post:
        out.append("Next: read the new tablets in Scribes [s].")
    else:
        pending = after.get("justice", {}).get("petitions", ())
        if pending:
            oldest = max(pending, key=lambda case: case.get("waiting", 0))
            who = actor_name(oldest.get("petitioner", ""), after.get("house"))
            out.append(f"Next: hear {who}'s waiting claim in Court.")
        else:
            out.append("No urgent matter reported. Read the remaining accounts in Hall.")
    return out


def record_lines(before: dict, after: dict, log=()) -> list[str]:
    """The full comparison, retained as evidence beneath the briefing."""
    out = [f"Court records · turns {before.get('turn', '?')}→{after.get('turn', '?')}."]
    out.extend(follow_through(before, after, log))
    out.extend(after.get("mandate_report", ()))
    old_entries = set(before.get("governance", {}).get("receipts", ()))
    out.extend(entry for entry in after.get("governance", {}).get("receipts", ())
               if entry not in old_entries)
    old_grain = before.get("stores", {}).get("grain", 0)
    new_grain = after.get("stores", {}).get("grain", 0)
    out.append(f"Granary reports {old_grain:,}→{new_grain:,} qa "
               f"({new_grain - old_grain:+,}).")
    out.append("Rations · keeper's queue estimate → payroll now:")
    predicted = {g['id']: g for g in ration_plan(before)['groups']}
    debts = []
    for group in after.get("groups", ()):
        old = predicted.get(group["id"])
        if old is None:
            continue
        debt = group.get("arrears_qa", 0)
        if debt or old.get("arrears_qa") or old["next_arrears"]:
            debts.append(f"{group['name']}: arrears {old.get('arrears_qa', 0):,} qa; "
                       f"expected {old['next_arrears']:,}, recorded {debt:,} qa.")
    out.extend(debts or ["No ration arrears expected or recorded."])
    out.append("Queue estimate excluded arrivals, spoilage and other uses.")
    harvest = harvest_plan(before)
    if harvest["remaining"] and harvest["standing"] is not None:
        recorded = after.get("land", {}).get("harvest_pool_standing")
        if recorded is not None:
            estimated = max(0, harvest["standing"] - harvest["before"] * harvest["rate"])
            out.append(f"Shared fields: {harvest['standing']:,} qa standing; "
                       f"capacity estimate leaves {estimated:,}; count now {recorded:,} qa.")
            out.append("A fall in standing crop includes losses; it is not grain received.")
            if harvest["remaining"] == 1:
                out.append("Harvest window closed. Check the labour roll for returned hands.")
    previous = {item["id"]: item for item in before.get("outbox", ())}
    for letter in after.get("outbox", ()):
        old = previous.get(letter["id"], {})
        if letter.get("status") != old.get("status"):
            out.append(f"Tablet {letter['id']}: {letter.get('status', 'sent')}; "
                       f"reply expected turn {letter.get('expected_reply_turn', '?')}.")
    return out


def lines(before: dict, after: dict, log=()) -> list[str]:
    return brief(before, after, log) + [
        "", "FULL RECORD · scroll for receipts and comparisons", "",
    ] + record_lines(before, after, log)
