from engine.state import World


def result(world: World) -> dict:
    seat = world.kernel.seat_goods.seat
    history = world.population_history
    current = world.kernel.people(seat)
    return {
        "chosen_alu": world.chosen_alu,
        "seed": world.seed,
        "fortnights": world.ended_turn if world.ended else world.date.absolute,
        "reigns": world.court.reigns,
        "population_start": history[0] if history else current,
        "population_end": current,
        "shocks": [shock.kind for shock in world.shocks],
        "cause": world.end_reason,
        "ended": world.ended,
        # These are material receipts and living reserves, not a hidden score.
        "court_judgements": len(world.court.rulings),
        "grain_awarded": sum(r.amount for r in world.court.rulings.values()
                             if r.good == "grain"),
        "household_grain": sum(
            lot.quantity for lot in world.kernel.book.at(seat)
            if lot.good == "grain" and lot.owner in world.kernel.registry.cohorts),
        "ration_arrears": sum(c.shortfall for c in world.kernel.cohorts_of(seat)
                              if c.roll_id),
    }
