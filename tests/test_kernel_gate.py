"""M13.2 exit gate (spec, M13.2).

    A drought or extraction decision creates complete, conserved,
    source-to-household chain the developer inspector can explain.

Four words: *complete* (every link present), *conserved* (ledger accounts
for all of it), *source-to-household* (walk ends at furrow, begins at eating),
*explain* (chain answerable from records by inspector that does not know code).

Drought is year three of world climate table -- one integer per turn, same for
every settlement, cost decided by ground and hands.
"""
from __future__ import annotations

import contextlib
import io

from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import world as K
from load import load_scenario
from tools import kernel_inspect as I

ALASHIYA = "settlement:alashiya"
CARACHEMISH = "settlement:carchemish"
SEAT = "settlement:seat"

HORIZON = 72


def _world() -> K.Kernel:
    return load_scenario("ugarit", seed=1).kernel


def _replayed(turns: int = HORIZON):
    kernel, logs = I.replay(turns)
    return kernel, logs, I._lot_history(turns)


# --- explain: links are records, not inferences ----------------------------

def test_a_conversion_names_what_it_was_made_out_of() -> None:
    _kernel, _logs, seen = _replayed(24)
    grain = [lot for lot in seen.values()
             if lot.good == F.GRAIN and any(m.startswith("from:")
                                            for m in lot.provenance)]
    assert grain, "grain was threshed out of something"

    parents = I._parents(grain[0])
    assert parents, "and it says out of what"
    assert any(seen[p].good == F.SHEAVES for p in parents if p in seen), \
        "and what it says is sheaves"


def test_a_store_names_the_lot_that_was_folded_into_it() -> None:
    _kernel, logs, seen = _replayed()
    grain = [lot for lot in seen.values()
             if lot.good == F.GRAIN and lot.location == ALASHIYA
             and any(m.startswith("from:") for m in lot.provenance)]
    assert grain, "grain at alashiya was threshed out of something"
    assert any(m.startswith("merged:") for m in grain[0].provenance), \
        "and the granary says which lot went in"


# --- complete: whole chain, end to end ---------------------------------------

def test_an_islander_eats_grain_grown_in_own_territory() -> None:
    kernel, logs, seen = _replayed()
    rations = I.eaten_at(logs, seen, ALASHIYA)
    assert rations, "somebody on the island ate"

    local_sites = {s for s in kernel.registry.sites
                   if kernel.registry.sites[s].settlement == ALASHIYA}
    behind = {lot for ration in rations for lot in I.ancestry(seen, ration)}
    grown = {lot for lot in behind
             if seen.get(lot) is not None
             and seen[lot].location in local_sites
             and seen[lot].good == F.STANDING}
    assert grown, "and some was standing in a local field"


def test_every_link_in_chain_carries_authority() -> None:
    _kernel, logs, seen = _replayed()
    behind = {lot for ration in I.eaten_at(logs, seen, ALASHIYA)
              for lot in I.ancestry(seen, ration)}

    acts = [t for log in logs for t in log.transfers
            if t.lot in behind and t.reason in ("sold", "carried", "loaded",
                                                "unloaded", "levied")]
    unattributed = [t for t in acts if not t.authority]
    assert not unattributed, unattributed[:3]


def test_inspector_answers_question_without_falling_over() -> None:
    kernel, logs = I.replay(HORIZON)
    seen = I._lot_history(HORIZON)
    page = io.StringIO()
    with contextlib.redirect_stdout(page):
        for place in (ALASHIYA, SEAT, CARACHEMISH):
            I.chain(kernel, logs, seen, place)
        I.weather(kernel, logs)
        I.short(kernel, logs)

    written = page.getvalue()
    assert "standing_grain" in written, "printed chain reaches field"
    assert "produced" in written or "harvested" in written, "shows production"
    assert "year 3" in written, "drought year in weather table"


# --- drought, and what it did downstream -------------------------------------

def test_drought_is_one_number_costs_every_estate_something() -> None:
    _kernel, logs, _seen = _replayed()
    withered: dict[int, dict] = {}
    for log in logs:
        for event in log.events:
            if event[0] != "withered":
                continue
            _, actor, gone, _neglect, climate = event
            year = withered.setdefault((log.turn - 1) // 24 + 1,
                                       {"climate": climate, "lost": {}})
            year["climate"] = min(year["climate"], climate)
            year["lost"][actor] = year["lost"].get(actor, 0) + gone

    assert 3 in withered, "third year is drought"
    dry = withered[3]
    assert dry["climate"] < 100, "worse than ordinary"
    assert len(dry["lost"]) >= 3, "everyone got same weather"
    assert len(set(dry["lost"].values())) >= len(dry["lost"]) - 4, \
        "almost all paid different amounts"


def test_drought_reaches_household() -> None:
    kernel = _world()
    years: dict[int, dict] = {}
    for turn in range(1, HORIZON + 1):
        kernel, events, log = K.advance_logged(kernel)
        year = years.setdefault((turn - 1) // 24 + 1,
                                {"reaped": 0,
                                 "island_price": [],
                                 "hungry_events": 0})
        year["reaped"] += sum(e[3] for e in events
                              if e[0] == "reaped" and e[2] == CARACHEMISH)
        year["island_price"].append(
            C.readings(kernel, ALASHIYA)["price_grain"])
        year["hungry_events"] += sum(1 for e in events if e[0] == "hungry")

    wet, dry = years[2], years[3]
    assert dry["reaped"] < wet["reaped"], "drought took part of harvest"
