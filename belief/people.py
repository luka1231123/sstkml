"""Who is speaking, in plain words: name, role, side, and what they want."""
import tomllib
from pathlib import Path

from engine.actors import slug

_CONTENT = Path(__file__).parent.parent / "content"
_CARDS = tomllib.loads((_CONTENT / "personas.toml").read_text())
_NAMES = tomllib.loads((_CONTENT / "actors.toml").read_text())["names"]
_SIDES = tomllib.loads((_CONTENT / "sides.toml").read_text())
_ID = {name: key for key, name in _NAMES.items()}


def sides() -> dict[str, dict]:
    return _SIDES


def tag(actor_id: str) -> dict:
    """The tag of an actor id, or of the name actors.toml gives one."""
    key = slug(_ID.get(actor_id, actor_id))
    card = _CARDS.get(key, {})
    name, _, role = _NAMES.get(key, key.replace("_", " ")).partition(",")
    return {"name": card.get("name", name.strip()), "role": card.get("role", role.strip()),
            "wants": card.get("wants", ""), "side": card.get("side", "")}


def line(actor_id: str) -> str:
    """One line: "Abdi-Anu, a shipwright · Merchants · wants to be paid what the palace owes"."""
    t = tag(actor_id)
    parts = [f"{t['name']}, {t['role']}" if t["role"] else t["name"],
             sides().get(t["side"], {}).get("name", ""),
             "wants " + t["wants"] if t["wants"] else ""]
    return " · ".join(part for part in parts if part)
