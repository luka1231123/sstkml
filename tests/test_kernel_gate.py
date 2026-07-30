"""The M13.2 exit gate (spec, M13.2).

    A drought or extraction decision creates a complete, conserved,
    source-to-household chain that the developer inspector can explain.

Four words in that sentence are doing work, and there is a test below for each.

*Complete* means every link is present: ground, crop, sheaves, grain, bargain,
cargo, crossing, bargain again, ration. *Conserved* means the ledger accounts
for all of it, which `test_kernel_carry` holds separately and this leans on.
*Source-to-household* means the walk ends at a furrow and begins at somebody
eating, rather than at a settlement's aggregate store. And *explain* is the one
that is easy to miss: the chain has to be answerable out of records, by an
inspector that does not know how the code works, rather than reconstructed by a
developer who does. A join inferred from "these two things happened on the same
turn in the same phase" would satisfy the first three and fail the fourth.

The drought is not a scripted crisis and is not authored for this test. It is
year three of the world's climate table -- one integer per turn, the same for
every settlement in the region -- and what it costs each of them is decided by
how much ground they had and what they did with their hands.
"""
from __future__ import annotations

import contextlib
import io

from engine.kernel import carry as C
from engine.kernel import farm as F
from engine.kernel import world as K
from load_kernel import load_kernel
from tools import kernel_inspect as I

ALASHIYA = "settlement:alashiya_port"
ARI = "settlement:ari"
MAHADU = "settlement:mahadu"
ARI_FIELDS = "site:ari_fields"

# Long enough to cross the drought year and see the harvest after it. Year one
# is ordinary, year two is wet, year three is when the rains fail.
HORIZON = 72


def _replayed(turns: int = HORIZON):
    kernel, logs = I.replay(turns)
    return kernel, logs, I._lot_history(turns)


# --- explain: the links are records, not inferences ----------------------------

def test_a_conversion_names_what_it_was_made_out_of() -> None:
    """Threshing is a sink and a source side by side. The link has to be written.

    Without it the two are only adjacent in the ledger, and an inspector joining
    them would be guessing from a shared turn and phase -- which is exactly the
    reconstruction this gate exists to refuse.
    """
    _kernel, _logs, seen = _replayed(24)
    grain = [lot for lot in seen.values()
             if lot.good == F.GRAIN and any(m.startswith("from:")
                                            for m in lot.provenance)]
    assert grain, "grain was threshed out of something"

    parents = I._parents(grain[0])
    assert parents, "and it says out of what"
    assert any(seen[p].good == F.SHEAVES for p in parents if p in seen), \
        "and what it says is sheaves"


def test_a_store_names_the_cargo_that_was_folded_into_it() -> None:
    """A granary is a mixture, and which lots went in is the record of that."""
    _kernel, logs, seen = _replayed()
    landed = {t.lot for log in logs for t in log.transfers
              if t.reason == "unloaded"}
    holding = [lot for lot in seen.values()
               if lot.location == ALASHIYA
               and landed & set(I._parents(lot))]
    assert holding, "a cargo that landed on the island is inside a granary there"
    assert any(m.startswith("merged:") for m in holding[0].provenance), \
        "and the granary says which lot went into it, not merely what it holds"


# --- complete: the whole chain, end to end -------------------------------------

def test_an_islander_eats_grain_grown_at_ari() -> None:
    """The gate itself, walked rather than asserted.

    Every step of this is a record the inspector reads: the ration is a
    `consumed` transfer, the granary names the cargo folded into it, the cargo
    names the lot it was split from, that lot was `sold` at Ari, and its
    provenance runs back through threshing and reaping to standing crop on
    `site:ari_fields`. Nothing here knows what a merchant is.
    """
    _kernel, logs, seen = _replayed()
    rations = I.eaten_at(logs, seen, ALASHIYA)
    assert rations, "somebody on the island ate"

    behind = {lot for ration in rations for lot in I.ancestry(seen, ration)}
    grown = {lot for lot in behind
             if seen.get(lot) is not None
             and seen[lot].location == ARI_FIELDS
             and seen[lot].good == F.STANDING}
    assert grown, "and some of it was standing in a field at Ari"

    # And the crossing is in the middle of it, not bypassed.
    crossed = {t.lot for log in logs for t in log.transfers
               if t.reason in ("carried", "unloaded")}
    assert behind & crossed, "it came by sea and road, and the ledger says so"


def test_every_link_in_the_chain_carries_an_authority() -> None:
    """Spec 11.1: a distant act links to an authority and an order or policy."""
    _kernel, logs, seen = _replayed()
    behind = {lot for ration in I.eaten_at(logs, seen, ALASHIYA)
              for lot in I.ancestry(seen, ration)}

    acts = [t for log in logs for t in log.transfers
            if t.lot in behind and t.reason in ("sold", "carried", "loaded",
                                                "unloaded", "levied")]
    assert acts, "goods changed hands and moved"
    unattributed = [t for t in acts if not t.authority]
    assert not unattributed, unattributed[:3]


def test_the_inspector_answers_the_question_without_falling_over() -> None:
    """The gate names the inspector, so the inspector is part of the gate.

    Held on the rendering rather than only on the traversal: a walk that is
    correct and unprintable does not answer the question the gate asks, which
    is whether a developer can be shown the chain.
    """
    kernel, logs = I.replay(HORIZON)
    seen = I._lot_history(HORIZON)
    page = io.StringIO()
    with contextlib.redirect_stdout(page):
        for place in (ALASHIYA, MAHADU, ARI):
            I.chain(kernel, logs, seen, place)
        I.weather(kernel, logs)
        I.short(kernel, logs)

    written = page.getvalue()
    assert ARI_FIELDS in written, "the printed chain reaches the inland ground"
    assert "sold" in written and "carried" in written, "and shows the crossing"
    assert "unloaded" in written, "and where the cargo came ashore"
    assert "year 3" in written, "and the drought year is in the weather table"


# --- the drought, and what it did downstream -----------------------------------

def test_the_drought_is_one_number_and_it_costs_every_estate_something() -> None:
    """Not a scripted event: the same weather, different consequences."""
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

    assert 3 in withered, "the third year is the one the rains fail in"
    dry = withered[3]
    assert dry["climate"] < 100, "and it is a worse year than an ordinary one"
    assert len(dry["lost"]) >= 3, "everyone in the region got the same weather"
    assert len(set(dry["lost"].values())) == len(dry["lost"]), \
        "and no two of them paid the same, because no two farm the same ground"


def test_the_drought_reaches_a_household_across_the_water() -> None:
    """The chain the gate is about, measured rather than walked.

    Ari absorbs the first year of it out of a granary, which is what a granary
    is for and why the signal downstream is a dearer year rather than a famine.
    But it does reach: less standing crop means less spare, less spare means
    less sold, less sold means less landed, and the island's grain never gets
    cheap again that year.
    """
    kernel = load_kernel()
    years: dict[int, dict] = {}
    for turn in range(1, HORIZON + 1):
        kernel, events, log = K.advance_logged(kernel)
        year = years.setdefault((turn - 1) // 24 + 1,
                                {"reaped": 0, "sold": 0, "landed": 0,
                                 "island_price": []})
        year["reaped"] += sum(e[3] for e in events
                              if e[0] == "reaped" and e[2] == ARI)
        year["sold"] += sum(c.quantity for c in log.contracts if c.place == ARI)
        year["landed"] += sum(e[4] for e in events if e[0] == "landed"
                              and e[2] == ALASHIYA and e[3] == C.GRAIN)
        year["island_price"].append(C.readings(kernel, ALASHIYA)["price_grain"])

    wet, dry = years[2], years[3]
    assert dry["reaped"] < wet["reaped"], "the drought took part of Ari's harvest"
    assert dry["sold"] < wet["sold"], "so the inland town had less to spare"
    assert min(dry["island_price"]) > min(wet["island_price"]), \
        "and grain on the island never came back down that year"
    assert dry["landed"] > 0, "the crossing did not stop; it carried less"
