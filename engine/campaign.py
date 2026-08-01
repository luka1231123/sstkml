from engine.state import World


def result(world: World) -> dict:
    seat = f"settlement:{world.chosen_alu}"
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
    }
