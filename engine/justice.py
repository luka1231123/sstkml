"""Court petitions with immediate, visible stakes.

A case is one decision, not a knowledge tax followed by a hidden correctness
test. The petitioner names the crown good at stake; the Court shows the award
and unrest consequence of every verdict before the player spends the hour.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat
from engine.state import Petition, Ruling, World

VERDICTS = ("for", "against", "split")
NEW_SITUATIONS = frozenset({"sick_bread", "campaign_families", "work_crew", "gift_and_bowl"})


def _amount(values: tuple[tuple[str, int], ...]) -> int:
    return int(dict(values).get("amount", 0))


def consequence(petition: Petition, verdict: str) -> tuple[str, int, int]:
    """Return ``(good, award, unrest_delta)`` for one visible verdict."""
    if verdict not in VERDICTS:
        raise ValueError("verdict must be for, against, or split")
    claim = _amount(petition.claim)
    counter = _amount(petition.counterclaim)
    if verdict == "for":
        return petition.good, claim, petition.unrest_for
    if verdict == "against":
        return petition.good, counter, petition.unrest_against
    if verdict == "split":
        return petition.good, (claim + counter) // 2, petition.unrest_split
    raise AssertionError("unreachable verdict")


def beneficiary(world: World, petition: Petition) -> str:
    """The living body receiving grain on behalf of a named legal claimant.

    Named injury and widow disputes retain their legal identity and receipts,
    while their food joins actual local household reserves. The replay cutoff
    leaves all transfers in older saved timelines exactly as they were.
    """
    if (petition.petitioner in world.kernel.registry.cohorts
            or petition.good != "grain"
            or world.date.absolute < getattr(world, "court_content_from", 0)):
        return petition.petitioner
    craft_claims = {"injury_quarry", "injury_quarry_balance", "shipwright_bread"}
    dependent_claims = {"widows_ration", "widows_ration_balance"}
    if petition.id not in craft_claims | dependent_claims:
        return petition.petitioner
    local = [c for c in world.kernel.cohorts_of(world.kernel.seat_goods.seat)
             if c.people > 0 and not c.in_transit]
    if petition.id in craft_claims:
        # General craft households encompass the independent injured worker;
        # a palace workshop is the fallback if the city has no separate body.
        relevant = sorted((c for c in local if c.kind == "craft"),
                          key=lambda c: (bool(c.roll_id), c.id))
    else:
        relevant = sorted((c for c in local if c.roll_id == "palace_dependents"),
                          key=lambda c: c.id)
        if not relevant:
            relevant = sorted((c for c in local if c.kind == "household"),
                              key=lambda c: c.id)
    return relevant[0].id if relevant else petition.petitioner


def rule(world: World, petition_id: str, verdict: str) -> tuple[World, list]:
    petition = world.court.petitions.get(petition_id)
    if petition is None:
        raise ValueError(f"no such petition: {petition_id}")
    good, amount, unrest_delta = consequence(petition, verdict)
    recipient = beneficiary(world, petition)
    if amount > seat.available(world).get(good, 0):
        raise ValueError(f"the crown does not hold {amount:,} {good}")

    petitions = dict(world.court.petitions)
    petitions.pop(petition.id)
    if amount:
        world = seat.pay(
            world, good, amount, recipient,
            authority=world.court.actor)
        if petition.id.startswith("court:arrears:"):
            world = _settle_arrears(world, petition.petitioner, amount)

    before = world.court.unrest
    unrest = max(0, min(1000, before + unrest_delta))
    rulings = dict(world.court.rulings)
    rulings[petition.id] = Ruling(petition.id, petition.petitioner, verdict,
                                good, amount, world.date.absolute)
    court = dataclasses.replace(
        world.court, petitions=petitions, rulings=rulings, unrest=unrest)
    world = dataclasses.replace(world, court=court)
    events: list = [A.PetitionRuled(
        petition.id, verdict, recipient, good, amount,
        unrest - before)]
    if unrest != before:
        events.append(A.UnrestChanged(
            unrest - before, f"judgement in {petition.kind}"))
    return world, events


def _settle_arrears(world: World, cohort_id: str, amount: int) -> World:
    """A ration restitution is eaten and clears exactly that recorded debt.

    This is the same material outcome as paying arrears in the ration room,
    with a court receipt. Any amount above the debt still belongs to the
    recipient as a food reserve; a pending petition cannot create fresh debt.
    """
    cohort = world.kernel.registry.cohorts.get(cohort_id)
    if cohort is None:
        return world
    paid = min(amount, cohort.shortfall)
    book = world.kernel.book
    remaining = paid
    for lot in book.owned_by(cohort_id):
        if (lot.good != "grain" or remaining <= 0
                or lot.location != world.kernel.seat_goods.seat):
            continue
        take = min(remaining, lot.free)
        if take:
            book = book.consume(lot.id, take, "consumed")
            remaining -= take
    actually_paid = paid - remaining
    cohorts = dict(world.kernel.registry.cohorts)
    cohorts[cohort_id] = dataclasses.replace(
        cohort, shortfall=max(0, cohort.shortfall - actually_paid))
    registry = dataclasses.replace(world.kernel.registry, cohorts=cohorts)
    kernel = dataclasses.replace(world.kernel, registry=registry, book=book)
    return dataclasses.replace(world, kernel=kernel)


def _remember(world: World, beneficiary: str) -> str:
    """People cite the public receipt, rather than an invisible favour score."""
    records = [r for r in world.court.rulings.values()
               if r.petitioner == beneficiary and r.good == "grain"]
    if not records:
        return "This household has no earlier grain judgement."
    last = max(records, key=lambda r: (r.turn, r.case_id))
    ago = world.date.absolute - last.turn
    return (f"Your last judgement for us was {last.verdict}: {last.amount:,} qa, "
            f"{ago} fortnights ago. That receipt remains in the archive.")


def _recurring_cases(world: World, petitions: dict[str, Petition]) -> tuple[Petition, ...]:
    """A small audience drawn from real households and their changing ledger.

    Every request has a material cause. There is no crisis roll or endless
    scripted queue: healthy, paid households do not keep claiming a debt.
    Receipts impose a cooldown per issue, and one household cannot monopolize
    the audience by presenting several versions of its claim at once.
    """
    now = world.date.absolute
    recurring_count = sum(key.startswith("court:") for key in petitions)
    if now < 4 or now % 3 or recurring_count >= 3:
        return ()
    place = world.kernel.seat_goods.seat
    cohorts = [c for c in world.kernel.cohorts_of(place)
               if c.people > 0 and not c.in_transit]
    pending = {p.petitioner for p in petitions.values()}
    candidates: list[tuple[int, Petition]] = []
    treasury = seat.available(world).get("grain", 0)
    payroll = sum(c.ration() for c in cohorts if c.roll_id)
    new_content = now >= getattr(world, "court_content_from", 0)
    away = sorted((f for f in world.court.formations
                   if f.task == "campaign" and f.place != world.court.seat
                   and f.strength > 0), key=lambda f: f.id)
    active_works = sorted((p for p in world.court.projects.values()
                           if p.place == world.court.seat
                           and p.days_done > 0 and p.days_done < p.days_needed),
                          key=lambda p: p.id)
    recent_gifts = sorted((g for g in world.court.treasury_gifts_sent
                           if now - 6 <= g.sent_turn <= now and g.quantity > 0),
                         key=lambda g: (g.sent_turn, g.id))

    def add(cohort, issue: str, claim: int, counter: int, urgency: int,
            kind: str, argument: str, response: str, *, cooldown: int = 12):
        prefix = f"court:{issue}:{cohort.id}:"
        prior = [r for key, r in world.court.rulings.items()
                 if key.startswith(prefix)]
        if cohort.id in pending or claim <= 0:
            return
        if prior and now - max(r.turn for r in prior) < cooldown:
            return
        name = cohort.representative or cohort.name or cohort.kind.replace("_", " ")
        group = cohort.name or cohort.kind.replace("_", " ")
        text = (f"At filing, {name} spoke for {group} ({cohort.people:,} people): "
                f"{argument} {_remember(world, cohort.id)}")
        if issue in NEW_SITUATIONS:
            earlier = sorted((r for r in world.court.rulings.values()
                              if r.petitioner == cohort.id and r.good == "grain"),
                             key=lambda r: (r.turn, r.case_id))
            memory = (f" Last ruling: {earlier[-1].amount:,} qa, "
                      f"{now - earlier[-1].turn} fortnights ago." if earlier else "")
            text = f"{name}, for {group}: {argument}{memory}"
            response += " Full grant pays the request; split pays half; refusal pays nothing."
            if urgency >= 300:
                response += " After 3 fortnights, waiting costs 1 unrest for at most 6 more."
        case = Petition(
            id=f"{prefix}{now}", petitioner=cohort.id,
            against=world.court.actor, kind=kind,
            claim=(("amount", claim),), counterclaim=(("amount", min(claim, counter)),),
            good="grain", unit="qa of grain", claim_text=text,
            counter_text=(f"The storekeeper: {response} At filing the free crown "
                          f"store held {treasury:,} qa. A grant comes out of it."),
            unrest_for=-min(16, 4 + urgency // 100),
            unrest_against=min(18, 2 + urgency // 80),
            unrest_split=-2 if counter else 1, unrest_arrival=0,
            arrived_turn=now, waiting_unrest=1 if urgency >= 300 else 0,
            grace=3)
        candidates.append((urgency, case))

    for cohort in cohorts:
        ration = cohort.ration()
        if ration <= 0:
            continue
        tenure = world.kernel.tenure_of(cohort)
        own_food = sum(lot.free for lot in world.kernel.book.owned_by(cohort.id)
                       if lot.good == "grain" and lot.location == place)
        if new_content:
            if (cohort.infected > 0 and own_food < ration * 2
                    and cohort.shortfall < ration):
                claim = max(1, min(ration, cohort.infected * cohort.ration_per_head * 2))
                add(cohort, "sick_bread", claim, 0, 410,
                    "bread at the sickbed",
                    f"Sickness has reached our households. We ask {claim:,} qa "
                    "to keep bread beside the sickbeds, before arrears swallow us.",
                    "The same grain feeds healthy workers. This is household "
                    "food, not a cure; an award leaves the ordinary roll unchanged.",
                    cooldown=18)
            if cohort.kind == "garrison" and away:
                formation = away[0]
                destination = world.places.get(formation.place)
                where = destination.name if destination else formation.place
                claim = max(1, min(ration, formation.strength * cohort.ration_per_head))
                add(cohort, "campaign_families", claim, 0, 260,
                    "the soldiers' empty chairs",
                    f"{formation.name} is on campaign at {where}. Grant "
                    f"{claim:,} qa as reserve bread for our households here.",
                    "The army already draws its ration. Family reserves cost "
                    "grain needed for the muster. Paying does not recall the troops.",
                    cooldown=24)
            if cohort.corvee > 0 and active_works and cohort.hunger == 0:
                project = active_works[0]
                claim = max(1, min(ration // 2,
                                   cohort.corvee * cohort.ration_per_head // 12))
                add(cohort, "work_crew", claim, 0, 220,
                    "bread before the last brick",
                    f"{project.name} is under way: {project.days_done:,} of "
                    f"{project.days_needed:,} days done. Our levy has given "
                    f"{cohort.corvee:,} days this season. We ask {claim:,} qa "
                    "of reserve bread for the households behind those hands.",
                    "Giving crew households grain leaves less for the work's "
                    "supplies. A grant does not advance the project or levy more days.",
                    cooldown=24)
            if (cohort.roll_id and 0 <= cohort.allowance < ration and recent_gifts):
                gift = recent_gifts[-1]
                recipient = world.kernel.registry.persons.get(gift.recipient)
                if recipient is None:
                    recipient = world.kernel.registry.persons.get(f"person:{gift.recipient}")
                relation = world.relations.get(gift.recipient)
                destination = world.places.get(relation.place) if relation else None
                who = recipient.name if recipient else (destination.name if destination else "a foreign court")
                claim = ration - cohort.allowance
                add(cohort, "gift_and_bowl", claim, 0, 840,
                    "a royal gift, a worker's bowl",
                    f"You sent {gift.quantity:,} {gift.good} to {who} while "
                    f"our ration ceiling stands at {cohort.allowance:,} qa "
                    f"against {ration:,} owed. Put {claim:,} qa in our own reserve.",
                    "A foreign gift can keep an ally or repay a promise. This "
                    "award supplements household grain; it neither retracts "
                    "the gift nor raises the standing ration ceiling.",
                    cooldown=18)
        if cohort.roll_id and cohort.shortfall >= ration:
            claim = min(cohort.shortfall, ration * 3)
            add(cohort, "arrears", claim, 0,
                500 + min(500, cohort.hunger * 60), "the ration roll returns",
                f"Our roll records {cohort.shortfall:,} qa still unpaid. We ask "
                f"{claim:,} now. Awards feed us and clear that much recorded "
                "arrears immediately; any grain beyond the debt stays ours.",
                "Refuse a new award and leave the debt on the roll, or split "
                "the claim and pay half. A judgement does not change the "
                "standing ration allowance.")
        if not cohort.roll_id and cohort.hunger and own_food < ration * 2:
            claim = ration * 2 - own_food
            add(cohort, "household_food", claim, 0,
                350 + min(450, cohort.hunger * 70), "households before the empty bin",
                f"We have endured {cohort.hunger} hungry fortnights and hold "
                f"{own_food:,} qa ourselves. Grant {claim:,} qa to bring our "
                "own reserve to two meals. It belongs to us and feeds our people.",
                "A split award gives half the request while keeping grain "
                "for the palace roll. Refusal spends nothing and leaves "
                "the households to their existing food supply.")
        if cohort.corvee >= cohort.people * 3 and not cohort.hunger:
            claim = max(1, min(ration, cohort.corvee * cohort.ration_per_head // 12))
            add(cohort, "corvee_bread", claim, 0, 180,
                "the workers' second table",
                f"The labour ledger records {cohort.corvee:,} days already "
                f"levied from us this season. We ask {claim:,} qa of reserve "
                "bread for the households that gave those days.",
                "The ordinary roll still feeds workers. A split gives half "
                "as additional household grain; refusal retains the "
                "public reserve.", cooldown=24)
        if (tenure == "subsistence" and cohort.kind == "field_labour"
                and world.court.land_due_rate > world.court.land_due_base + 20):
            extra = world.court.land_due_rate - world.court.land_due_base
            claim = max(1, ration * min(200, extra) // 100)
            add(cohort, "land_relief", claim, 0,
                240 + min(200, cohort.hunger * 40), "the villages count the king's share",
                f"The land due stands at {world.court.land_due_rate}/1000, "
                f"against the customary {world.court.land_due_base}/1000. "
                f"Return {claim:,} qa to our own grain reserve. This is relief "
                "for the heavier share; it does not change next harvest's rate.",
                "The heavier due supplies the city's obligations. A split "
                "returns half; refusal spends no grain and leaves the "
                "heavier share in force.", cooldown=24)
        if (not cohort.roll_id and cohort.hunger == 0 and cohort.grievance < 500
                and treasury > max(1, payroll) * 8
                and world.date.fortnight in (12, 15, 18)):
            add(cohort, "good_year", ration, 0, 70,
                "a share in a good year",
                f"We are fed today. We ask {ration:,} qa for a household "
                "reserve before the next lean season. A prosperous crown "
                "can share its security; the grain will be ours, not lost.",
                "Keeping the grain preserves the crown's freedom to meet "
                "foreign demands and a poor harvest. No debt is owed here.", cooldown=24)
    if not candidates:
        return ()
    # Urgency first; a stable identity resolves ties without a hidden RNG.
    candidates.sort(key=lambda item: (-item[0], item[1].id))
    return (candidates[0][1],)


def _still_live(world: World, petition: Petition) -> bool:
    """Withdraw a recurring claim when its measurable cause has disappeared.

    A claimant who is fed or repaid through another room has no continuing
    emergency debt merely because the king did not use the judgement button.
    Authored disputes and discretionary reserve requests retain their record.
    """
    if not petition.id.startswith("court:"):
        return True
    cohort = world.kernel.registry.cohorts.get(petition.petitioner)
    if cohort is None or cohort.people <= 0:
        return False
    issue = petition.id.split(":", 2)[1]
    if issue == "arrears":
        return cohort.shortfall > 0
    if issue == "household_food":
        own_food = sum(lot.free for lot in world.kernel.book.owned_by(cohort.id)
                       if lot.good == "grain"
                       and lot.location == world.kernel.seat_goods.seat)
        return cohort.hunger > 0 and own_food < cohort.ration() * 2
    if issue == "land_relief":
        return world.court.land_due_rate > world.court.land_due_base + 20
    if issue == "sick_bread":
        return cohort.infected > 0
    if issue == "campaign_families":
        return any(f.task == "campaign" and f.place != world.court.seat
                   and f.strength > 0 for f in world.court.formations)
    if issue == "work_crew":
        return any(p.place == world.court.seat and p.days_done < p.days_needed
                   for p in world.court.projects.values())
    if issue == "gift_and_bowl":
        return 0 <= cohort.allowance < cohort.ration()
    return True


def step(world: World) -> tuple[World, list]:
    """Bring authored cases into the hall and age the visible queue."""
    now = world.date.absolute
    petitions = {
        key: dataclasses.replace(value, waiting=value.waiting + 1)
        for key, value in world.court.petitions.items()
        if _still_live(world, value)}
    events: list = []
    arrival_unrest = sum(p.waiting_unrest for p in petitions.values()
                        if p.waiting > p.grace
                        and (not (p.id.startswith("court:")
                                  and p.id.split(":", 2)[1] in NEW_SITUATIONS)
                             or p.waiting <= p.grace + 6))
    for case in (*world.justice_cases, *_recurring_cases(world, petitions)):
        if case.id in petitions or case.id in world.court.rulings:
            continue
        if case.after_case:
            prior = world.court.rulings.get(case.after_case)
            if prior is None or now != prior.turn + case.delay:
                continue
            if not case.award_min <= prior.amount <= case.award_max:
                continue
            amount = max(0, _amount(case.claim) - prior.amount) if case.deduct_award else _amount(case.claim)
            case = dataclasses.replace(
                case, arrived_turn=now, claim=(("amount", amount),),
                claim_text=case.claim_text.format(paid=prior.amount, balance=amount, turn=prior.turn))
        elif case.arrived_turn != now:
            continue
        petitions[case.id] = case
        arrival_unrest += case.unrest_arrival
        events.append(A.PetitionArrived(
            case.id, case.petitioner, case.against, case.kind))
    before = world.court.unrest
    unrest = max(0, min(1000, before + arrival_unrest))
    court = dataclasses.replace(
        world.court, petitions=petitions, unrest=unrest)
    if unrest != before:
        events.append(A.UnrestChanged(
            unrest - before, "petitions arriving or waiting beyond their grace period"))
    return dataclasses.replace(world, court=court), events
