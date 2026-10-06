"""Palace accounts. Goods are issued from existing stores, never minted here."""
from __future__ import annotations

import dataclasses
from engine import actions as A, seat, revenue, troops

TITLES = {"mycenaean": "The workshop account", "egyptian": "Temple and province", "hittite": "The royal service"}
SUMMARY = {
    "mycenaean": "Issue bronze tools or give the palace craftsmen grain. The workshop account closes every six fortnights.",
    "egyptian": "Endow the temple from the granary, or raise the provincial assessment and collect the grain before this account closes.",
    "hittite": "Keep a royal contingent on campaign for three closing accounts, or provision the garrison from the granary. Men on campaign do not defend the capital.",
}


def _cfg(world, key, default):
    return world.governance_config.get(key, default)


def _kind(world):
    kind = str(_cfg(world, "kind", ""))
    return kind if kind in TITLES else ""


def _due(world):
    if world.court.governance_due:
        return world.court.governance_due
    return max(0, world.court_content_from) + max(3, int(_cfg(world, "cycle", 6)))


def _cohort(world, group):
    return next((c for c in world.kernel.registry.cohorts.values()
                 if c.roll_id == group and c.people > 0
                 and c.settlement == world.kernel.seat_goods.seat
                 and not c.in_transit), None)


def _grain_quota(world):
    legacy = max(1, int(_cfg(world, "grain_quota", 12000)))
    if world.opening_rules_version == 0:
        return legacy
    group_key, default_group = {
        "mycenaean": ("craft_group", "smiths_palace"),
        "egyptian": ("temple_group", "cult_baal"),
        "hittite": ("military_group", "garrison_mahadu"),
    }.get(_kind(world), ("", ""))
    cohort = _cohort(world, str(_cfg(world, group_key, default_group)))
    need = cohort.people * cohort.ration_per_head * 3 if cohort else 0
    return max(12000, legacy, need)


def _options(world):
    kind = _kind(world)
    grain = _grain_quota(world)
    bronze = max(1, int(_cfg(world, "bronze_quota", 600)))
    minimum = max(1, int(_cfg(world, "muster_min", 100)))
    options = []
    def add(key, label, description, good="", amount=0, group="", reason=""):
        if group and _cohort(world, group) is None:
            reason = "No living households on this roll are at the capital."
        if good and seat.available(world).get(good, 0) < amount:
            reason = f"The unreserved stores lack {amount:,} {good}."
        if world.court.governance_status != "open":
            reason = "An order is already recorded for this account."
        if world.date.absolute < world.court_content_from:
            reason = "This account opens after the recorded reign."
        options.append({"id": key, "label": label, "description": description,
                        "detail": description, "cost_good": good, "cost_amount": amount,
                        "available": not reason, "reason": reason, "group": group})
    if kind == "mycenaean":
        add("tools", "Issue bronze tools", f"Issue {bronze:,} shekels of bronze for new workshop tools. The metal leaves royal stores and increases equipment in use.", "bronze", bronze)
        add("workers", "Pay the craftsmen", f"Give {grain:,} qa grain to the craft households. Their reserve feeds them; this does not erase old ration debts.", "grain", grain, str(_cfg(world, "craft_group", "smiths_palace")))
        add("defer", "Leave the account unpaid", "Record no payment. At account closure, standing falls by 12 and anger rises by 8.")
    elif kind == "egyptian":
        add("temple", "Endow the temple", f"Give {grain:,} qa grain to the temple households. The grain leaves the royal granary and enters their food reserve.", "grain", grain, str(_cfg(world, "temple_group", "cult_baal")))
        new_rate = min(1000, world.court.land_due_rate + 50)
        add("assessment", "Raise the provincial assessment", f"Raise the land due from {world.court.land_due_rate}/1000 to {new_rate}/1000. Collect {grain:,} qa in actual land dues before turn {_due(world)}. Outside harvest this may fail. The higher rate remains until changed in Land.", reason="The assessment is already at its limit." if new_rate == world.court.land_due_rate else "")
        add("remission", "Remit the provincial due", "Lower the land due by 50/1000, until changed in Land. Forfeit 12 standing. This closes the account without a temple endowment.")
    elif kind == "hittite":
        service_place = str(_cfg(world, "service_place", world.court.seat))
        service_name = world.places[service_place].name if service_place in world.places else service_place
        candidates = [f for f in world.court.formations if troops.capable(f) >= minimum]
        service = ("three consecutive closing musters" if world.opening_rules_version == 1
                   else "three closing accounts")
        recall = (" A missed muster resets the count. After three consecutive musters, you may recall them without losing this account."
                  if world.opening_rules_version == 1 else "")
        add("muster", "Call the royal contingent", f"Send the largest ready formation on campaign to {service_name}. Record at least {minimum} ready men there at {service} before turn {_due(world)}. They cease defending the capital and remain on campaign until reassigned.{recall}", reason="No formation has enough ready men." if not candidates else "")
        add("supply", "Provision the garrison", f"Give {grain:,} qa grain to the garrison households. The grain becomes their food reserve. Troop assignments remain as ordered.", "grain", grain, str(_cfg(world, "military_group", "garrison_mahadu")))
        add("defer", "Withhold royal service", "Record no troops or grain. At account closure, standing falls by 12 and anger rises by 8.")
    return options


def project(world):
    kind = _kind(world)
    if not kind:
        return {}
    court = world.court
    options = _options(world)
    due = _due(world)
    progress = ""
    if court.governance_order == "muster":
        consecutive = " consecutive" if world.opening_rules_version == 1 else ""
        progress = f"{court.governance_progress}/3{consecutive} closing musters recorded"
    elif court.governance_order == "assessment":
        progress = f"{court.governance_progress:,}/{_grain_quota(world):,} qa land dues collected"
    summary = SUMMARY[kind]
    if kind == "hittite" and world.opening_rules_version == 1:
        place = str(_cfg(world, "service_place", world.court.seat))
        name = world.places[place].name if place in world.places else place
        summary = f"Record three consecutive closing musters at {name}, or provision the garrison. Men on campaign do not defend the capital."
    return {"kind": kind, "culture": kind, "title": TITLES[kind], "summary": summary,
            "cycle_due": due, "cycle_status": court.governance_status,
            "order": court.governance_order, "progress": progress,
            "last_result": court.governance_last[-1] if court.governance_last else "No account has closed.",
            "receipts": list(court.governance_last), "failures": court.governance_failures,
            "stakes": "Account met: +6 standing. Unpaid: -12 standing, +8 anger."
                + (" Remission costs 12 standing when ordered." if kind == "egyptian" else ""),
            "source": "royal account", "certainty": "counted", "as_of_turn": world.date.absolute,
            "orders": options, "options": options}


def describe(belief, kind):
    """Use only the account already reported to the player."""
    account = belief.get("governance", {})
    item = next((o for o in account.get("orders", ()) if o["id"] == kind), None)
    if item is None:
        return ["No such order is listed in this account."]
    return [item["label"], item["description"], "Cost: 1 court hour.",
            "One order may be recorded in each account."]


def order(world, choice):
    kind = _kind(world)
    if not kind:
        raise ValueError("this court has no special royal account")
    option = next((o for o in _options(world) if o["id"] == choice), None)
    if option is None:
        raise ValueError("choose an order listed in the royal account")
    if not option["available"]:
        raise ValueError(option["reason"])
    events = []
    status = "served"
    progress = 0
    detail = option["description"]
    if option["cost_good"]:
        if choice == "tools":
            stores = seat.held(world)
            stores["bronze"] -= option["cost_amount"]
            world = seat.put(world, stores, reason_down="expended", authority=world.court.actor)
            metals = world.court.metals
            ceiling = (metals.in_service_ceiling or metals.bronze_in_circulation) + option["cost_amount"]
            in_service = metals.bronze_in_circulation + option["cost_amount"]
            world = dataclasses.replace(world, court=dataclasses.replace(world.court,
                metals=dataclasses.replace(metals, bronze_in_circulation=in_service,
                                           in_service_ceiling=ceiling)))
        else:
            cohort = _cohort(world, option["group"])
            world = seat.pay(world, "grain", option["cost_amount"], cohort.id, authority=world.court.actor)
    elif choice == "assessment":
        world, more = revenue.set_land_due(world, min(1000, world.court.land_due_rate + 50))
        events += more
        status = "pending"
    elif choice == "muster":
        formation = max((f for f in world.court.formations if troops.capable(f) >= int(_cfg(world, "muster_min", 100))), key=lambda f: (troops.capable(f), f.id))
        world, more = troops.assign(world, A.AssignTroops(formation.id, "campaign", str(_cfg(world, "service_place", world.court.seat))))
        events += more
        status = "pending"
    else:
        status = "refused"
        court = world.court
        if choice == "remission":
            new_rate = max(0, court.land_due_rate - 50)
            if new_rate != court.land_due_rate:
                world, more = revenue.set_land_due(world, new_rate)
                events += more
            world = dataclasses.replace(world, court=dataclasses.replace(world.court, legitimacy=max(0, court.legitimacy - 12)))
        # Refusal is charged when the account closes, exactly once.
    court = dataclasses.replace(world.court, governance_due=_due(world), governance_status=status,
                                governance_order=choice, governance_progress=progress,
                                governance_land_seen=world.court.land_due_in_progress)
    world = dataclasses.replace(world, court=court)
    return world, events + [A.GovernanceRecorded(kind, choice, detail)]


def step(world):
    kind = _kind(world)
    now = world.date.absolute
    if not kind or now < world.court_content_from:
        return world, []
    court = world.court
    due = _due(world)
    progress = court.governance_progress
    status = court.governance_status
    if status == "pending" and court.governance_order == "assessment":
        # The harvest receipt counts grain that actually reached the crown.
        # Foreign obligations may transfer title while grain is still abroad;
        # those promises are not grain collected in this account.
        current = court.land_due_in_progress
        seen = court.governance_land_seen
        progress += max(0, current - seen) if current >= seen else current
        if progress >= _grain_quota(world):
            status = "served"
    elif status == "pending" and court.governance_order == "muster":
        ready = sum(troops.capable(f) for f in court.formations
                    if f.task == "campaign" and f.place == str(_cfg(world, "service_place", court.seat)))
        if ready >= int(_cfg(world, "muster_min", 100)):
            progress += 1
        elif world.opening_rules_version == 1:
            progress = 0
        if progress >= 3:
            status = "served"
    if now < due:
        return dataclasses.replace(world, court=dataclasses.replace(court,
            governance_due=due, governance_status=status, governance_progress=progress,
            governance_land_seen=world.court.land_due_in_progress)), []
    served = status == "served"
    remitted = court.governance_order == "remission"
    standing = 6 if served else (0 if remitted else -12)
    anger = 0 if served or remitted else 8
    result = f"Turn {now}: {TITLES[kind].lower()} {'met' if served else 'not met'}; standing {standing:+d}, anger {anger:+d}."
    if remitted:
        result = f"Turn {now}: provincial remission recorded; 12 standing forfeited when ordered."
    history = (court.governance_last + (result,))[-6:]
    court = dataclasses.replace(court, governance_due=due + max(3, int(_cfg(world, "cycle", 6))),
        governance_status="open", governance_order="", governance_progress=0, governance_last=history,
        governance_land_seen=world.court.land_due_in_progress,
        governance_failures=court.governance_failures + int(not served),
        legitimacy=max(0, min(1000, court.legitimacy + standing)),
        unrest=max(0, min(1000, court.unrest + anger)))
    return dataclasses.replace(world, court=court), [A.GovernanceAccountClosed(kind, served, result)]
