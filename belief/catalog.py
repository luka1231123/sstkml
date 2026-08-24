"""Court-known fields and their owning dossiers."""

KINDS = {
    "cohort": ("id", "name", "people", "households", "origin", "ethnicity",
               "status", "tenure", "place", "institution", "representative",
               "armed", "task", "path", "arrives", "labour_per_head",
               "labour", "ration_per_head",
               "ration", "allowance", "shortfall", "hunger", "grievance",
               "precedence", "corvee", "reaping", "infected", "recovered",
               "dead", "roll_id", "roll_place", "roll_function",
               "source", "as_of_turn", "certainty"),
    "formation": ("id", "name", "strength", "ready", "equipment_floor",
                  "replacement_rate", "task", "place", "commander", "source",
                  "as_of_turn", "certainty"),
    "institution": ("id", "name", "kind", "place", "head", "group",
                    "group_name", "condition", "inspected", "capacity",
                    "effective", "upkeep", "history", "source", "as_of_turn",
                    "certainty"),
    "project": ("id", "what", "kind", "place", "repair", "institution",
                "days_done", "days_needed", "days_remaining", "spent",
                "condition_target", "capacity", "started_turn", "source",
                "as_of_turn", "certainty"),
    "cargo": ("id", "good", "quantity", "reserved", "available", "owner",
              "holder", "location", "quality", "provenance", "source",
              "as_of_turn", "certainty"),
    "route": ("id", "name", "origin", "destination", "mode", "legs",
              "capacity", "risk", "strength", "tolls", "seasonal", "source",
              "as_of_turn", "certainty"),
    "movement": ("id", "route", "carrier", "origin", "destination",
                 "departed", "arrives", "remaining", "mode", "cargo", "news",
                 "source", "as_of_turn", "certainty"),
    "person": ("id", "name", "sex", "age_years", "health", "location",
               "spouse", "mother", "father", "heir_rank", "alive",
               "died_turn", "married_to_court", "is_queen_mother", "expecting",
               "faction", "agenda", "competence", "loyalty", "post",
               "interests", "named_heir", "source", "as_of_turn", "certainty"),
    "petition": ("id", "petitioner", "against", "kind", "waiting", "good",
                 "unit", "claim", "counterclaim", "claim_text",
                 "counter_text", "outcomes", "source",
                 "as_of_turn", "certainty"),
    "obligation": ("id", "kind", "party", "beneficiary", "authority", "good",
                   "quantity", "person_id", "destination", "created_turn",
                   "due_turn", "status", "source_letter", "history", "source",
                   "as_of_turn", "certainty"),
    "place": ("id", "name", "kind", "alu", "role", "rank", "power",
              "harbour", "col", "row", "source", "as_of_turn", "age_turns",
              "certainty"),
    "site": ("id", "name", "kind", "settlement", "alu", "function", "role",
             "region", "capacity", "extent", "holder", "harbour", "population",
             "col", "row", "source", "as_of_turn", "age_turns", "certainty"),
    "oath": ("id", "parties", "superior", "gods", "sworn_turn", "sworn_by",
             "dissolved", "lapsed", "binds_house", "clauses", "source",
             "as_of_turn", "certainty"),
    "rite": ("id", "fortnight", "hours", "requires", "skip_legitimacy",
             "skip_unrest", "source", "as_of_turn", "certainty"),
}

UNITS = {
    "people": "heads", "strength": "men", "ready": "men",
    "labour": "person-days", "labour_per_head": "days/head",
    "ration": "qa", "ration_per_head": "qa/head", "allowance": "qa",
    "shortfall": "qa", "grievance": "/1000", "condition": "/1000",
    "effective": "capacity", "replacement_rate": "/1000", "risk": "/1000",
    "quality": "/1000", "quantity": "native units", "reserved": "native units",
    "available": "native units", "corvee": "person-days",
    "days_done": "person-days", "days_needed": "person-days",
    "days_remaining": "person-days", "capacity": "native capacity",
    "hunger": "fortnights", "arrives": "turn",
    "departed": "turn", "remaining": "fortnights", "as_of_turn": "turn",
    "started_turn": "turn", "died_turn": "turn", "waiting": "fortnights",
    "created_turn": "turn", "due_turn": "turn",
}

LABELS = {
    "as_of_turn": "record dated", "labour_per_head": "labour per head",
    "ration_per_head": "ration per head", "equipment_floor": "bronze floor",
    "replacement_rate": "replacement capacity", "days_done": "work done",
    "days_needed": "work required", "days_remaining": "work remaining",
    "married_to_court": "married at", "is_queen_mother": "queen mother",
}


def label(key: str) -> str:
    return LABELS.get(key, key.replace("_", " "))


def order(kind: str, item: dict) -> tuple[str, ...]:
    first = KINDS.get(kind, ())
    return tuple(dict.fromkeys((*first, *item.keys())))


def records(belief: dict):
    groups = {
        "cohort": belief.get("cohorts", ()),
        "institution": belief.get("institutions", ()),
        "project": belief.get("projects", ()),
        "formation": belief.get("troops", {}).get("formations", ()),
        "cargo": belief.get("trade", {}).get("cargo", ()),
        "route": (*belief.get("trade", {}).get("routes", ()),
                  *belief.get("world_graph", {}).get("routes", ())),
        "movement": belief.get("trade", {}).get("movements", ()),
        "person": belief.get("house", {}).get("members", ()),
        "petition": belief.get("justice", {}).get("petitions", ()),
        "obligation": belief.get("obligations", ()),
        "place": belief.get("world_graph", {}).get("places", ()),
        "site": belief.get("world_graph", {}).get("sites", ()),
        "oath": belief.get("oaths", ()),
        "rite": belief.get("rites", ()),
    }
    for kind, items in groups.items():
        for item in items:
            yield kind, item
