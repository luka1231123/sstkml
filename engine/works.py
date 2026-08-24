"""Building and repair: the corvée's second use (spec 6.21, M12).

The city (6.18) gave the player a machine that decays. This gives him the one
thing he can do about it, and makes doing it expensive in the only currency that
matters.

**Days are the work budget.** `seat.corvee_days` reads what the crown called up
this season; `Court.works_days` prevents one levy being spent twice. Calling
the days costs unrest, while sites use them only at low water, when the fields
ask for no labour. The strategic draw is therefore time and stores, not a
hidden second harvest penalty.

**Supplies are consumed as the work proceeds.** Four hundred men on a site are
four hundred men who have to be fed, and different works wear different amounts
of tools and fittings. Call the men off halfway and what they ate and broke is
gone: an abandoned project is a loss, never a refund.

**Work only happens in the right season.** A quay commissioned in the rains
waits for low water. The Works roll names that immediate constraint without
inventing a completion date the future corvée and stores cannot support.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine import seat
from engine.core import in_range
from engine.state import Institution, Project, World


def _rules(world: World) -> dict:
    return world.works_rules


def cost_per_1000(world: World, kind: str = "") -> dict[str, int]:
    """Crew supplies plus the fittings peculiar to one kind of work."""
    rates = dict(world.works_materials)
    plan = world.works_plans.get(kind, {})
    for good, qty in plan.get("per_1000_days", {}).items():
        rates[good] = rates.get(good, 0) + int(qty)
    return rates


def material_cost(world: World, kind: str, days: int) -> dict[str, int]:
    return {
        good: qty * max(0, days) // 1000
        for good, qty in sorted(cost_per_1000(world, kind).items()) if qty
    }


def working_season(world: World) -> bool:
    """Whether mudbrick can go up this fortnight."""
    span = world.season.get(world.works_season)
    if not span:
        return True
    return in_range(world.date.fortnight, tuple(span))


def repair_days(world: World, inst: Institution) -> int:
    """What it would take to make this whole, at today's condition.

    Fixed when the order is given and never revised. The fabric goes on decaying
    while the men work, so a repair commissioned at 400 and finished eight
    fortnights later does not arrive at 1000 -- the player eats the difference,
    which is the cost of having left it so long.
    """
    per_point = max(1, _rules(world).get("repair_days_per_point", 3))
    return max(0, (1000 - inst.condition)) * per_point


def begin_build(world: World, action: A.BeginBuild) -> tuple[World, list]:
    plan = world.works_plans.get(action.kind)
    if plan is None:
        raise ValueError(f"nobody here knows how to build a {action.kind}")
    if action.place not in world.places:
        raise ValueError(f"unknown place: {action.place}")
    court = world.court
    seq = court.project_seq + 1
    project = Project(
        id=f"work{seq}", institution="", kind=action.kind, place=action.place,
        name=plan["name"], days_needed=int(plan["days"]),
        condition_target=int(plan["condition"]), capacity=int(plan["capacity"]),
        started_turn=world.date.absolute)
    projects = {**court.projects, project.id: project}
    return (dataclasses.replace(
        world, court=dataclasses.replace(
            court, projects=projects, project_seq=seq)),
        [A.WorkBegun(project.id, project.name, project.days_needed)])


def begin_repair(world: World, action: A.BeginRepair) -> tuple[World, list]:
    court = world.court
    inst = court.institutions.get(action.institution)
    if inst is None:
        raise ValueError(f"unknown institution: {action.institution}")
    if any(p.institution == inst.id for p in court.projects.values()):
        raise ValueError(f"the men are already at work on {inst.name}")
    days = repair_days(world, inst)
    if days <= 0:
        raise ValueError(f"{inst.name} wants nothing doing")
    seq = court.project_seq + 1
    project = Project(
        id=f"work{seq}", institution=inst.id, kind=inst.kind, place=inst.place,
        name=inst.name, days_needed=days, condition_target=1000,
        started_turn=world.date.absolute)
    projects = {**court.projects, project.id: project}
    return (dataclasses.replace(
        world, court=dataclasses.replace(
            court, projects=projects, project_seq=seq)),
        [A.WorkBegun(project.id, project.name, project.days_needed)])


def abandon(world: World, action: A.AbandonWork) -> tuple[World, list]:
    court = world.court
    project = court.projects.get(action.project)
    if project is None:
        raise ValueError(f"no such work: {action.project}")
    projects = {k: v for k, v in court.projects.items() if k != project.id}
    return (dataclasses.replace(
        world, court=dataclasses.replace(court, projects=projects)),
        [A.WorkAbandoned(project.id, project.name, project.days_done)])


def _afford(stores: dict, per_1000: dict[str, int], days: int) -> int:
    """The most of `days` the storehouse can actually feed. Integers throughout.

    Scaling days down to what the goods allow, rather than refusing outright,
    is what lets a short season still put a few hundred days into a wall.
    """
    for good, per in sorted(per_1000.items()):
        if per <= 0:
            continue
        have = stores.get(good, 0)
        days = min(days, have * 1000 // per)
    return max(0, days)


def status(world: World, project: Project) -> str:
    """The visible constraint that would stop the next day of work."""
    if not working_season(world):
        return "waiting for low water"
    available = max(0, seat.corvee_days(world) - world.court.works_days)
    if available <= 0:
        return "no corvée days remain"
    rates = cost_per_1000(world, project.kind)
    stores = seat.held(world)
    if _afford(stores, rates, min(available, 1000)) <= 0:
        short = [good for good, qty in sorted(rates.items())
                 if qty > 0 and stores.get(good, 0) * 1000 < qty]
        return "short of " + ", ".join(short or ("crew supplies",))
    return "able to move this fortnight"


def _finish(world: World, project: Project) -> tuple[World, list]:
    court = world.court
    institutions = dict(court.institutions)
    if project.institution:
        inst = institutions.get(project.institution)
        if inst is None:                       # torn down while the men worked
            return world, []
        bought = project.days_needed // max(
            1, _rules(world).get("repair_days_per_point", 3))
        institutions[inst.id] = dataclasses.replace(
            inst, condition=min(1000, inst.condition + bought))
        built = False
        institution_id = inst.id
    else:
        # Built and empty: no head, no group on the roll. It stands, it decays
        # faster than a minded one, and staffing it is a separate decision.
        institution_id = f"{project.kind}_{project.place}_{project.id}"
        plan = world.works_plans.get(project.kind, {})
        institutions[institution_id] = Institution(
            id=institution_id, name=project.name, kind=project.kind,
            place=project.place, condition=project.condition_target,
            capacity=project.capacity,
            upkeep=tuple(sorted(
                (good, int(qty))
                for good, qty in plan.get("upkeep", {}).items())))
        built = True
    projects = {k: v for k, v in court.projects.items() if k != project.id}
    return (dataclasses.replace(
        world, court=dataclasses.replace(
            court, institutions=institutions, projects=projects)),
        [A.WorkFinished(project.id, institution_id, project.name, built)])


def step(world: World) -> tuple[World, list]:
    """A7c: eligible projects spend this season's days and supplies."""
    court = world.court
    if not court.projects:
        return world, []
    if not working_season(world):
        return world, []

    rules = _rules(world)
    rate = rules.get("days_per_fortnight", 400)
    stores = seat.held(world)
    events: list = []
    projects = dict(court.projects)
    works_days = court.works_days
    available = max(0, seat.corvee_days(world) - works_days)

    for key in sorted(projects):
        project = projects[key]
        if available <= 0:
            break
        per_1000 = cost_per_1000(world, project.kind)
        days = min(rate, available, project.days_needed - project.days_done)
        days = _afford(stores, per_1000, days)
        if days <= 0:
            continue
        spent = dict(project.spent)
        for good, per in sorted(per_1000.items()):
            qty = per * days // 1000
            if qty:
                stores[good] = stores.get(good, 0) - qty
                spent[good] = spent.get(good, 0) + qty
                events.append(A.WorkMaterialConsumed(
                    project.id, good, qty))
        project = dataclasses.replace(
            project, days_done=project.days_done + days,
            spent=tuple(sorted(spent.items())))
        projects[key] = project
        available -= days
        works_days += days
        events.append(A.WorkProgressed(project.id, days, project.days_done,
                                       project.days_needed))

    world = seat.put(dataclasses.replace(
        world, court=dataclasses.replace(
            court, projects=projects, works_days=works_days)),
        stores, reason_down="expended")

    # Completion last, so a project that finished this fortnight has already
    # paid for the fortnight that finished it.
    for key in sorted(world.court.projects):
        project = world.court.projects[key]
        if project.days_done >= project.days_needed:
            world, done = _finish(world, project)
            events.extend(done)
    return world, events
