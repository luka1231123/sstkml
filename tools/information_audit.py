"""Find court-known records without a complete dossier path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from belief import catalog
from belief.project import project
from engine.tick import advance
from load import load_campaign


def findings(belief: dict) -> list[str]:
    out = []
    required = {"id", "source", "as_of_turn", "certainty"}
    for kind, item in catalog.records(belief):
        missing = required - item.keys()
        if missing:
            out.append(f"{kind}:{item.get('id', '?')} missing {', '.join(sorted(missing))}")
    return out


def main() -> int:
    world, _ = advance(load_campaign("seat", 1))
    problems = findings(project(world))
    print("\n".join(problems) if problems else "information access: complete")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
