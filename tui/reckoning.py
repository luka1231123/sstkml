"""A year's decisions from public rulings and the ruler's current records."""

from tui.render import actor_name


def lines(b: dict, year: int = 1) -> list[str]:
    justice = b.get("justice", {})
    rulings = [r for r in justice.get("rulings", ())
               if (year - 1) * 24 < r["turn"] <= year * 24]
    out = [f"YEAR {year} · THE REIGN YOU ARE MAKING",
           f"Current records as of {b.get('date', '')} (turn {b.get('turn', '?')}).",
           "Your seal has changed whose hands hold the palace's goods."]
    if not rulings:
        out.append("No court claims were ruled on this year.")
    for ruling in rulings:
        who = actor_name(ruling["petitioner"], b.get("house"))
        out.append(f"Turn {ruling['turn']}: {who} — {ruling['amount']:,} "
                   f"{ruling['good']}; {ruling['verdict']} the claim.")
    out.append("WHAT THE NEXT YEAR INHERITS")
    debt = sum(g.get("arrears_qa", 0) for g in b.get("groups", ()))
    out.append(f"Ration arrears now: {debt:,} qa. Reported grain: "
               f"{b.get('stores', {}).get('grain', 0):,} qa.")
    pending = justice.get("petitions", ())
    for case in pending:
        out.append(f"Still waiting: {actor_name(case['petitioner'], b.get('house'))} "
                   f"— {case['kind']}, {case['waiting']} fortnights.")
    if not pending:
        out.append("No court claim currently waits for judgement.")
    for letter in b.get("outbox", ()):
        out.append(f"Your tablet {letter['id']}: {letter.get('status', 'sent')}.")
    out.append("Next: compare the new ration queue, revisit unpaid claims, and read the post.")
    out.append("The reign continues. These are records, not a score or a prediction.")
    return out
