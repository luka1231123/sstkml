"""Archived M8 balance tests (spec 10.4).

Obsolete since C4: the crown's fields crossed to the kernel, so the court's
mirror has no grain income and a scripted run drains to zero whatever the
payroll does. The balance target survives as a design claim, but its honest
form needs the kernel-side feed that C5 re-points. Until then these two tests
assert an economy the court no longer has.

Kept verbatim, assertions included, so the claim is not lost: when the feed
lands, un-archive and adjust the numbers, not the intent.
"""
from __future__ import annotations

from tools.balance import run as balance_run


def test_the_deficit_is_survivable_by_cutting_and_fatal_by_drifting():
    prudent = balance_run("prudent", 72)["rows"]
    passive = balance_run("passive", 72)["rows"]

    # Drifting empties the granary and maxes unrest: the deficit is real.
    assert any(row["grain"] == 0 for row in passive)
    assert max(row["unrest"] for row in passive) > 900

    # Cutting the payroll to fit survives, at a visible and bounded price.
    assert all(row["grain"] > 0 for row in prudent)
    assert max(row["unrest"] for row in prudent) < 600, (
        "letting one group go must not saturate unrest (see recompute_unrest)")
    assert prudent[-1]["grain"] > 0, "the last turn still feeds the court"


def test_the_army_becomes_unreplaceable_in_a_well_run_court():
    """M8's stated target: a run where the army becomes unreplaceable and the
    player never noticed. It has to happen in a court that is doing well --
    a court in ruins has stopped commissioning bronze."""
    rows = balance_run("prudent", 72)["rows"]
    pinched = next(r for r in rows if r["chariotry"] < 1000)
    assert 30 < pinched["turn"] < 65, f"pinched at turn {pinched['turn']}"
    assert pinched["grain"] > 0 and pinched["unrest"] < 600, (
        "the squeeze must arrive while the court still looks healthy")
    assert rows[-1]["chariotry"] < 700
    assert rows[-1]["melt"] > 0
