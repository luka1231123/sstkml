"""The kernel inspector can trace produced grain to its source crop."""
from __future__ import annotations

from engine.kernel import farm as F
from tools import kernel_inspect as I


# --- explain: links are records, not inferences ----------------------------

def test_a_conversion_names_what_it_was_made_out_of() -> None:
    seen = I._lot_history(8)
    grain = [lot for lot in seen.values()
             if lot.good == F.GRAIN and any(m.startswith("from:")
                                            for m in lot.provenance)]
    assert grain, "grain was harvested out of something"

    parents = I._parents(grain[0])
    assert parents, "and it says out of what"
    assert any(seen[p].good == F.STANDING for p in parents if p in seen), \
        "and what it says is the crop that stood"
