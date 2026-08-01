def slug(actor: str) -> str:
    return actor.split(":", 1)[1] if actor.startswith("person:") else actor


def canonical(world, actor: str) -> str:
    if actor in world.relations:
        return actor
    person = f"person:{actor}"
    return person if person in world.relations else actor
