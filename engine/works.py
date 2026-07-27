"""Building and repair: the corvée's second use (spec 6.21, M12).

The city (6.18) gave the player a machine that decays. This gives him the one
thing he can do about it, and makes doing it expensive in the only currency that
matters.

**Days come out of the same pool as the harvest.** `Court.corvee_days` is what
the crown called up this season; `Court.works_days` is what a building site took
out of it, and `land.labour_supplied` sees the difference. A wall raised in the
sowing fortnights is a wall raised out of next year's grain, and the bill lands
a year later with nothing to connect it to (6.4).

**Materials are eaten as the work proceeds.** Four hundred men on a site are
four hundred men who have to be fed, so the material cost of a wall is grain --
the same grain the granary is holding against the year the harvest fails. Call
the men off halfway and what they ate is gone: an abandoned project is a loss,
never a refund, and that is what makes starting one a decision.

**Work only happens in the right season**, and nothing says so. A player who
commissions a quay in the rains watches a number not move for four fortnights.
The absence of an explanation is the mechanic (D19), exactly as everywhere else.
"""
from __future__ import annotations

import dataclasses

from engine import actions as A
from engine.core import in_range
from engine.state import Institution, Project, World


def _rules(world: World) -> dict:
    return world.works_rules


def cost_per_1000(world: World) -> dict[str, int]:
    return dict(world.works_materials)


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
        institutions[institution_id] = Institution(
            id=institution_id, name=project.name, kind=project.kind,
            place=project.place, condition=project.condition_target,
            capacity=project.capacity)
        built = True
    projects = {k: v for k, v in court.projects.items() if k != project.id}
    return (dataclasses.replace(
        world, court=dataclasses.replace(
            court, institutions=institutions, projects=projects)),
        [A.WorkFinished(project.id, institution_id, project.name, built)])


def step(world: World) -> tuple[World, list]:
    """A7c: the men work, or they do not, and nothing explains which."""
    court = world.court
    if not court.projects:
        return world, []
    if not working_season(world):
        return world, []

    rules = _rules(world)
    rate = rules.get("days_per_fortnight", 400)
    per_1000 = cost_per_1000(world)
    stores = dict(court.stores)
    events: list = []
    projects = dict(court.projects)
    works_days = court.works_days
    available = max(0, court.corvee_days - works_days)

    for key in sorted(projects):
        project = projects[key]
        if available <= 0:
            break
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

    world = dataclasses.replace(
        world, court=dataclasses.replace(
            court, stores=stores, projects=projects, works_days=works_days))

    # Completion last, so a project that finished this fortnight has already
    # paid for the fortnight that finished it.
    for key in sorted(world.court.projects):
        project = world.court.projects[key]
        if project.days_done >= project.days_needed:
            world, done = _finish(world, project)
            events.extend(done)
    return world, events
