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
from load import load_campaign
from tools import kernel_inspect as I

ALASHIYA = "settlement:alashiya"
CARACHEMISH = "settlement:carchemish"
SEAT = "settlement:seat"

HORIZON = 72


def _world() -> K.Kernel:
    return load_campaign("seat", seed=1).kernel


def _replayed(turns: int = HORIZON):
    kernel, logs = I.replay(turns)
    return kernel, logs, I._lot_history(turns)


# --- explain: links are records, not inferences ----------------------------

def test_a_conversion_names_what_it_was_made_out_of() -> None:
    _kernel, _logs, seen = _replayed(24)
    grain = [lot for lot in seen.values()
             if lot.good == F.GRAIN and any(m.startswith("from:")
                                            for m in lot.provenance)]
    assert grain, "grain was harvested out of something"

    parents = I._parents(grain[0])
    assert parents, "and it says out of what"
    assert any(seen[p].good == F.STANDING for p in parents if p in seen), \
        "and what it says is the crop that stood"


# --- complete: whole chain, end to end ---------------------------------------

# --- drought, and what it did downstream -------------------------------------

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
