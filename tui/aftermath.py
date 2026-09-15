"""Compare the records held before and after a fortnight."""

from belief.harvest import plan as harvest_plan
from belief.rations import plan as ration_plan
from tui.render import actor_name


def follow_through(before: dict, after: dict, log=()) -> list[str]:
    out = []
    groups = {g['id']: g for g in after.get('groups', ())}
    for record in log:
        if record.get('turn') != before.get('turn'):
            continue
        action = record.get('action', {})
        kind = action.get('_t')
        group = groups.get(action.get('group_id'))
        if kind == 'RulePetition':
            out.extend(record.get('receipt', ()))
        elif kind in {'Allocate', 'PayArrears', 'SendToHarvest'} and group:
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
    return ["People and orders carried into this fortnight:", *out,
            "Payments above are receipts; the new roll also reflects other events."]


def lines(before: dict, after: dict, log=()) -> list[str]:
    out = [f"Court records · turns {before.get('turn', '?')}→{after.get('turn', '?')}."]
    out.extend(follow_through(before, after, log))
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
