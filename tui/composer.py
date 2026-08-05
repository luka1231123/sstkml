"""The king's clay-tablet desk.

The letter is built from visible pieces rather than from a hidden "posture":
an address, a recognition, the king's own one- or two-sentence matter, and a
seal.  Yabninu may correct the matter, but he does not choose what the king
means and he never silently replaces the other blocks.

The numeric protocol grade remains deterministic engine evidence.  What the
player sees is a short social reading of the selected forms and omissions.
"""
from __future__ import annotations

import dataclasses
import re
import textwrap

from ai.composer import Draft, fallback_text, raw_draft
from ai.grader import formula, grade_for, load_formulae, profile_for
from tui import render, style
from tui.grid import INDEX, Screen, Surface

C = INDEX

# Retained as a compatibility surface for the CLI and old saved actions.  The
# graphical desk no longer asks the player to choose one of these postures.
INTENTS = ("reassure", "refuse", "promise", "warn", "excuse", "request")
BLOCKS = ("address", "marker", "prostration", "wellbeing", "recognition",
          "matter", "terms", "precedent", "warning", "seal")
FOCI = BLOCKS

# Every piece a tablet can be built from, in the order they stand on the clay.
# Which of them a given recipient may receive comes from that profile's `blocks`
# list in `content/formulae.toml`, and each is a convention documented in
# `content/corpus/historical.toml`. `matter` is the player's own words and is
# never optional; the rest can be added, edited and taken off.
BLOCK_ORDER = ("address", "marker", "prostration", "wellbeing", "recognition",
               "matter", "terms", "precedent", "warning", "seal")
BLOCK_LABELS = {
    "address": "ADDRESS",
    "marker": "MESSAGE MARKER",
    "prostration": "PROSTRATION / GREETING",
    "wellbeing": "WELL-BEING",
    "recognition": "RECOGNITION",
    "matter": "MATTER · YOUR WORDS",
    "terms": "TERMS",
    "precedent": "PRECEDENT",
    "warning": "WARNING",
    "seal": "SEAL",
}
# Blocks the desk puts on a new tablet before the player touches it.
OPENING_BLOCKS = ("address", "marker", "recognition", "matter", "terms", "seal")
TERM_KINDS = (
    "gift", "request_good", "promise_good", "service",
    "marriage_proposal",
)
TERM_LABELS = {
    "gift": "GIFT",
    "request_good": "ASK FOR GOOD",
    "promise_good": "PROMISE GOOD",
    "service": "REQUEST SERVICE",
    "marriage_proposal": "MARRIAGE",
}
SEAL_IDS = ("palace", "royal", "")


@dataclasses.dataclass(frozen=True)
class BlockChoice:
    label: str
    text: str


def formulary(recipient: str, intent: str, seed: int, turn: int) -> Draft:
    """Compact deterministic recovery for non-desk callers."""
    profile_id = profile_for(recipient)
    text = fallback_text(recipient, intent, profile_id, seed, turn)
    return Draft(
        text=text, profile=profile_id,
        score=grade_for(text, profile_id, recipient=recipient),
        source="formulary")


def dictated(text: str, recipient: str) -> Draft:
    """The king's exact words, read against the recipient's known forms."""
    return raw_draft(text, recipient)


def block_choices(recipient: str) -> dict[str, tuple[BlockChoice, ...]]:
    """Return the pieces available at the desk for this recipient.

    The court form is the protocol-safe default.  The other forms are real
    choices rather than reskinned intentions: plain naming, asserted equality,
    omission, and an unsealed ending can all change how a tablet is received.
    """
    data = load_formulae()
    profile_id = profile_for(recipient, data)
    rule = formula(data, profile_id)
    name = render.actor_name(recipient)
    proper = rule["opening"].format(recipient=name)
    if rule.get("prostration"):
        proper += "\n" + rule["prostration"]
    gods = rule.get("deities", [])
    oath_line = (
        f"By {' and '.join(gods)}, what I have written I shall perform."
        if gods else "By the gods, what I have written I shall perform.")
    return {
        "marker": (BlockChoice("ROYAL WORD", "Message of Ammurapi, king of Ugarit."),),
        "prostration": (
            BlockChoice("SEVEN AND SEVEN",
                        rule.get("prostration")
                        or "At the feet of my lord, seven times and seven"
                           " times I fall."),
            BlockChoice("NONE", ""),
        ),
        "wellbeing": (
            BlockChoice("HIS HOUSE",
                        rule.get("wellbeing")
                        or "May it be well with you and with your house."),
            BlockChoice(
                "HOUSE AND HORSES",
                "May it be well with you, with your house, your wives, your"
                " sons and your horses. It is well with me."),
            BlockChoice("NONE", ""),
        ),
        "precedent": (
            BlockChoice(
                "QUOTE AND ANSWER",
                f"{rule.get('quotation_form', 'As to what you wrote me,'
                                               ' saying:')} \"…\""),
            BlockChoice("NONE", ""),
        ),
        "warning": (
            BlockChoice(
                "WRITE BACK",
                "Write to me when it is done, and write the count of the days"
                " spent."),
            BlockChoice(
                "BY THE SAME COURIER",
                "Send your answer with the same courier."),
            BlockChoice("NONE", ""),
        ),
        "terms": (BlockChoice("ATTACHED TERMS", ""),),
        "address": (
            BlockChoice("COURT FORM", proper),
            BlockChoice(
                "PLAIN NAME",
                f"To {name}: thus says Ammurapi, king of Ugarit."),
            BlockChoice(
                "AS BROTHER",
                f"To {name}, my brother: thus says Ammurapi, your brother."),
        ),
        "recognition": (
            BlockChoice("HEARD IN HALL", "Your words were heard in my hall."),
            BlockChoice(
                "SEAL RECEIVED",
                "Your tablet came beneath its seal and was read before me."),
            BlockChoice("NO RECOGNITION", ""),
        ),
        "seal": (
            BlockChoice(
                "PALACE SEAL",
                "Yabninu wrote it; the palace courier bears the sealed tablet."),
            BlockChoice(
                "KING'S OWN",
                "This is the word of Ammurapi beneath his seal."),
            BlockChoice("LEAVE UNSEALED", ""),
        ),
    }


def default_blocks() -> dict[str, int]:
    return {"address": 0, "recognition": 0, "seal": 0}


def permitted_blocks(recipient: str) -> tuple[str, ...]:
    """Which pieces this recipient's register allows, in tablet order."""
    rule = formula(load_formulae(), profile_for(recipient))
    allowed = set(rule.get("blocks", OPENING_BLOCKS))
    if "quotation" in allowed:
        allowed.add("precedent")
    if "instruction" in allowed:
        allowed.add("warning")
    allowed |= {"marker", "matter", "terms", "seal"}
    # Recognition is not a rank convention; it is the desk's own courtesy and
    # is offered everywhere the register does not forbid a greeting.
    if not rule.get("wellbeing_forbidden"):
        allowed.add("recognition")
    return tuple(name for name in BLOCK_ORDER if name in allowed)


def opening_order(recipient: str) -> tuple[str, ...]:
    """The pieces a fresh tablet starts with for this recipient."""
    allowed = permitted_blocks(recipient)
    start = [name for name in OPENING_BLOCKS if name in allowed]
    rule = formula(load_formulae(), profile_for(recipient))
    # A register that requires a piece starts with it laid out, so that the
    # player removes it deliberately rather than forgetting it.
    if rule.get("prostration") and "prostration" in allowed:
        start.insert(1, "prostration")
    if rule.get("wellbeing_required") and "wellbeing" in allowed:
        start.insert(1, "wellbeing")
    return tuple(name for name in BLOCK_ORDER if name in start)


def normalise_order(order, recipient: str) -> tuple[str, ...]:
    """Keep a saved block order legal: permitted pieces, tablet order, matter."""
    allowed = permitted_blocks(recipient)
    aliases = {"quotation": "precedent", "instruction": "warning"}
    kept = [aliases.get(name, name) for name in (order or ())]
    kept = [name for name in kept if name in allowed]
    for required in ("address", "marker", "matter", "terms", "seal"):
        if required not in kept:
            kept.append(required)
    return tuple(name for name in BLOCK_ORDER if name in kept)


def normalize_blocks(blocks: dict[str, int] | None,
                     recipient: str) -> dict[str, int]:
    choices = block_choices(recipient)
    # Every piece the register allows carries its first form until the player
    # picks another, so a block added to the tablet is never blank.
    selected = {name: 0 for name in permitted_blocks(recipient)}
    selected.update(default_blocks())
    selected.update(blocks or {})
    for name in list(selected):
        if name not in choices:
            selected.pop(name)
            continue
        selected[name] = int(selected[name]) % len(choices[name])
    return selected


def selected_blocks(recipient: str, blocks: dict[str, int] | None,
                    edits: dict[str, str] | None = None,
                    ) -> dict[str, BlockChoice]:
    """The chosen line for each block, with the player's own words winning.

    An edited block keeps its label so the desk still says which piece it is,
    and shows what the king actually dictated rather than the canned form.
    """
    choices = block_choices(recipient)
    picked = normalize_blocks(blocks, recipient)
    made = {name: choices[name][picked[name]] for name in picked}
    for name, text in (edits or {}).items():
        if name in choices and text.strip():
            label = made.get(name, choices[name][0]).label
            made[name] = BlockChoice(f"{label} · YOURS", text.strip())
    return made


def assemble(recipient: str, blocks: dict[str, int] | None, matter: str,
             source: str = "player", order=None,
             edits: dict[str, str] | None = None) -> Draft:
    """Press the pieces on this tablet, in their order, around the matter."""
    picked = selected_blocks(recipient, blocks, edits)
    laid = normalise_order(order or OPENING_BLOCKS, recipient)
    parts = [
        matter.strip() if name == "matter"
        else picked.get(name, BlockChoice("", "")).text.strip()
        for name in laid
    ]
    text = "\n".join(part for part in parts if part)
    made = raw_draft(text, recipient)
    return dataclasses.replace(made, source=source)


def sentence_count(text: str) -> int:
    """Count the player's compact matter without treating a blank as a line."""
    clean = " ".join(text.split())
    if not clean:
        return 0
    return len([
        part for part in re.findall(r"[^.!?]+(?:[.!?]+|$)", clean)
        if part.strip()])


def _term_value(term: object, field: str, default=""):
    if isinstance(term, dict):
        return term.get(field, default)
    return getattr(term, field, default)


def term_fields(builder: dict | None) -> tuple[str, ...]:
    """Editable fields carried by the currently chosen material term."""
    kind = str((builder or {}).get("kind") or TERM_KINDS[0])
    if kind in {"gift", "request_good", "promise_good"}:
        return ("kind", "good", "quantity", "due_turn")
    if kind == "service":
        return ("kind", "destination", "quantity", "due_turn")
    return ("kind", "person_id")


def term_summary(term: object) -> str:
    """One compact, replay-neutral reading of an explicit LetterTerm."""
    kind = str(_term_value(term, "kind", "term"))
    label = TERM_LABELS.get(kind, kind.replace("_", " ").upper())
    parts = [label]
    good = str(_term_value(term, "good"))
    person = str(_term_value(term, "person_id"))
    destination = str(_term_value(term, "destination"))
    quantity = _term_value(term, "quantity", 0)
    due = _term_value(term, "due_turn", 0)
    if good:
        parts.append(good.replace("_", " "))
    if person:
        parts.append(person.replace("_", " "))
    if type(quantity) is int and quantity:
        parts.append(f"{quantity:,}")
    if destination:
        parts.append("at " + destination.replace("_", " "))
    if type(due) is int and due:
        parts.append(f"due {due}")
    return " · ".join(parts)


def terms_summary(terms: tuple[object, ...] | list[object]) -> str:
    if not terms:
        return "none impressed"
    return "; ".join(term_summary(term) for term in terms)


def seal_id(recipient: str, blocks: dict[str, int] | None) -> str:
    """Material seal corresponding to the visible Seal block choice."""
    selected = normalize_blocks(blocks, recipient)
    return SEAL_IDS[selected["seal"] % len(SEAL_IDS)]


def scribe_expects(draft: Draft, intent: str = "reply") -> tuple[str, ...]:
    """Yabninu's concise social reading of deterministic protocol evidence."""
    lines = ["The recipient will receive these words as your answer."]
    score = draft.score
    if not score.address_ok:
        lines.append("The chosen address may be rejected.")
    elif draft.profile == "hatti.servant_to_lord":
        lines.append("The address keeps the Sun above Ugarit.")
    elif draft.profile == "peer.equal_to_equal":
        lines.append("The address claims equal kingship.")
    else:
        lines.append("The address names your kingship without submission.")
    if not score.prostration_ok:
        lines.append("No bow reaches the feet of the Sun.")
    if not score.self_designation_ok:
        lines.append("Your place beneath the recipient is left unstated.")
    if score.topic_count > 1:
        lines.append("More than one matter may be heard on this tablet.")
    readings = {
        "kinship_overreach": "\"Brother\" claims equal rank.",
        "excuse_and_request": "An excuse and a request share the same clay.",
        "wrong_oath_gods": "The oath invokes gods this court may reject.",
    }
    lines.extend(
        readings[violation]
        for violation in score.violations if violation in readings)
    return tuple(lines[:5])


def _wrapped(text: str, width: int) -> list[str]:
    out: list[str] = []
    for line in text.splitlines() or [""]:
        out.extend(textwrap.wrap(line, max(1, width)) or [""])
    return out


def _draw_block(surface: Surface, x: int, y: int, width: int,
                name: str, choice: BlockChoice, focused: bool,
                body_rows: int, command: str) -> int:
    """Draw one selectable piece and return the first row after it."""
    # Leave a few impressed wedges at the tablet's edge, never inside words.
    surface.fill(x + 1, y, max(0, width - 2), body_rows + 1,
                 " ", C["clay"], C["ink"])
    pointer = ">" if focused else " "
    surface.text(x, y, pointer, C["flame"] if focused else C["faint"], C["ink"])
    surface.text(x + 2, y, name.upper(), C["bone"], C["ink"])
    chip = f" {choice.label} "
    chip_x = max(x + 15, x + width - len(chip))
    surface.text(
        chip_x, y, chip,
        C["ink"] if focused else C["clay"],
        C["sand"] if focused else C["faint"])
    surface.link(x, y, width, max(1, body_rows + 1), command)
    rows = _wrapped(choice.text, max(8, width - 6)) if choice.text else [
        "— omitted —"]
    for offset, line in enumerate(rows[:body_rows]):
        colour = C["ash"] if not choice.text else C["clay"]
        surface.text(x + 4, y + 1 + offset, _short(line, width - 6),
                     colour, C["ink"])
    if len(rows) > body_rows and body_rows:
        surface.text(x + width - 2, y + body_rows, "…", C["ash"], C["ink"])
    return y + body_rows + 1


def _draw_bound(surface: Surface, x: int, y: int, width: int, rows: int,
                bound: tuple[str, ...]) -> int:
    """What the finished matter binds the crown to, read from its own words.

    Not a control. The player writes sentences; this reports what the tablet
    will oblige him to, so that a promise is seen before the seal goes on.
    """
    surface.fill(x + 1, y, max(0, width - 2), max(1, rows + 1),
                 " ", C["clay"], C["ink"])
    heading = "FINAL REVIEW" if bound else "FINAL REVIEW · NO ORDER PARSED"
    surface.text(x + 2, y, _short(heading, width - 4), C["bone"], C["ink"])
    for offset, line in enumerate(bound[:rows]):
        surface.text(x + 4, y + 1 + offset, _short(f"· {line}", width - 6),
                     C["gold"], C["ink"])
    if len(bound) > rows and rows:
        surface.text(x + width - 2, y + rows, "…", C["ash"], C["ink"])
    return y + max(1, rows) + 1


def _draw_terms(surface: Surface, x: int, y: int, width: int,
                terms: tuple[object, ...], builder: dict,
                focused: bool, term_focus: str) -> int:
    """Draw the structured marks separately from the king's prose."""
    surface.fill(x + 1, y, max(0, width - 2), 3,
                 " ", C["clay"], C["ink"])
    surface.text(x, y, ">" if focused else " ",
                 C["flame"] if focused else C["faint"], C["ink"])
    heading = f"TERMS · {len(terms)} IMPRESSED"
    if terms:
        heading += " · " + terms_summary(terms)
    else:
        heading += " · CANDIDATE BELOW"
    surface.text(x + 2, y, _short(heading, width - 2),
                 C["bone"], C["ink"])
    surface.link(x, y, width, 3, "block:terms")

    column = x + 3
    limit = x + width - 1
    for field in term_fields(builder):
        value = builder.get(field, "")
        if field == "kind":
            value = TERM_LABELS.get(str(value), str(value))
        elif field == "due_turn":
            value = "—" if not value else f"t{value}"
        elif field == "quantity":
            value = f"{int(value or 0):,}"
        else:
            value = str(value).replace("_", " ")
        label = {
            "quantity": "qty",
            "due_turn": "due",
            "person_id": "person",
            "destination": "at",
        }.get(field, field)
        if width < 48:
            label = {
                "kind": "k", "good": "g", "qty": "q",
                "due": "due", "person": "p", "at": "at",
            }.get(label, label)
        token = f"{label}:{value}"
        token = f"<{token}>" if field == term_focus else token
        if column + len(token) >= limit:
            break
        surface.text(column, y + 1, token,
                     C["gold"] if field == term_focus else C["clay"],
                     C["ink"])
        surface.link(column, y + 1, len(token), 1,
                     f"desk:term:focus:{field}")
        column += len(token) + 2

    controls = (
        ("←", "", "desk:term:value:previous"),
        ("→", "", "desk:term:value:next"),
        ("t", "", "desk:term:field:next"),
        ("+", "add", "desk:term:add"),
        ("-", "remove", "desk:term:remove"),
    )
    column = x + 3
    for key, label, command in controls:
        needed = len(key) + len(label) + 3
        if column + needed >= limit:
            break
        column += style.keycap(
            surface, column, y + 2, key, label,
            enabled=(bool(terms) if key == "-" else True),
            command=command) + 1
    return y + 3


def compose(item: dict, draft: Draft, intent: str = "reply",
            dictating: bool = False, cursor: bool = True,
            house: dict | None = None, width: int = 100, height: int = 32,
            composing: bool = False, notice: str = "",
            cursor_index: int | None = None, source_scroll: int = 0,
            terms: tuple[str, ...] = (),
            blocks: dict[str, int] | None = None,
            block_focus: str = "matter",
            matter: str | None = None,
            advisor_undo: bool = False,
            term_builder: dict | None = None,
            term_focus: str = "kind",
            seal_data: dict | None = None,
            block_order=None,
            block_edits: dict[str, str] | None = None,
            bound: tuple[str, ...] = ()) -> Screen:
    """Lay source knowledge beside the wet outgoing tablet and its pieces."""
    recipient = str(item["sender"])
    picked = selected_blocks(recipient, blocks, block_edits)
    laid = normalise_order(block_order or OPENING_BLOCKS, recipient)
    bound = tuple(bound)
    terms = tuple(terms)
    term_builder = dict(term_builder or {"kind": TERM_KINDS[0]})
    seal_data = dict(seal_data or {})
    if matter is None:
        # Compatibility for direct callers: show the draft's likely matter.
        groups = [line.strip() for line in draft.text.splitlines() if line.strip()]
        matter = groups[-2] if len(groups) >= 2 else draft.text

    surface = Surface(width, height, fg=C["clay"], bg=C["ink"])
    who = render.actor_name(recipient, house)
    new_letter = bool(item.get("new_letter"))
    style.panel(
        surface, 0, 0, width, height,
        title=(
            f"SCRIBES' ROOM — "
            f"{'A LETTER' if new_letter else 'AN ANSWER'} TO {who.upper()}"),
        focus=dictating, drop=False)
    surface.text(2, 1, style.wedge_band(max(0, width - 4), phase=2),
                 C["shadow"], C["ink"])

    source_width = min(36, max(29, width // 3))
    divider = source_width + 1
    for row in range(2, height - 4):
        surface.put(divider, row, "│", C["faint"], C["ink"])

    # Pinned incoming clay.
    source_box_width = max(3, source_width - 2)
    source_bottom = height - 5
    source_title = (
        "COURT & ROUTE TABLET" if new_letter else "PINNED SOURCE TABLET")
    surface.box(2, 2, source_box_width, max(3, source_bottom - 1),
                style="single", fg=C["sand"], title=source_title)
    inner_x = 4
    source_room = max(1, source_box_width - 4)
    surface.fill(3, 3, max(0, source_box_width - 2),
                 max(0, source_bottom - 3),
                 " ", C["clay"], C["ink"])
    surface.text(inner_x, 3, style.wedge_band(source_room, phase=5),
                 C["shadow"], C["ink"])
    surface.text(inner_x, 4, _short(
        ("TO · " if new_letter else "FROM · ") + who, source_room),
                 C["bone"], C["ink"])
    summary = render.letter_summary(str(item.get("topic", "message")))
    y = 6
    surface.text(inner_x, y, "KNOWN MATTER" if new_letter else "MATTER",
                 C["dim"], C["ink"])
    y += 1
    for line in textwrap.wrap(summary, source_room)[:2]:
        surface.text(inner_x, y, line, C["clay"], C["ink"])
        y += 1
    facts = item.get("facts") or {}
    y += 1
    if facts:
        surface.text(inner_x, y, "CLAIMS ON THE TABLET", C["dim"], C["ink"])
        y += 1
        for key, value in list(facts.items())[:3]:
            shown = f"{value:,}" if isinstance(value, int) else str(value)
            surface.text(
                inner_x, y,
                _short(f"· {str(key).replace('_', ' ')}  {shown}", source_room),
                C["gold"], C["ink"])
            y += 1
    y += 1
    source_body = str(item.get("body") or "")
    empty_source = (
        "No incoming tablet is pinned. This begins a new exchange."
        if new_letter else "No voiced copy is ready.")
    source_lines = _wrapped(source_body or empty_source, source_room)
    room = max(1, source_bottom - y - 2)
    source_scroll = max(
        0, min(source_scroll, max(0, len(source_lines) - room)))
    for line in source_lines[source_scroll:source_scroll + room]:
        surface.text(inner_x, y, line, C["ash"], C["ink"])
        y += 1
    if len(source_lines) > room:
        surface.text(
            inner_x, source_bottom - 2,
            _short(f"{source_scroll + 1}–"
                   f"{min(len(source_lines), source_scroll + room)}"
                   f"/{len(source_lines)} lines", source_room),
            C["sky"], C["ink"])

    # Wet outgoing clay.
    right = divider + 3
    right_width = width - right - 3
    surface.box(right - 1, 2, right_width + 2, max(3, source_bottom - 1),
                style="single", fg=C["sand"],
                title=f"WET TABLET · {len(laid)} PIECES")
    surface.fill(right, 3, right_width, max(0, source_bottom - 3),
                 " ", C["clay"], C["ink"])
    surface.text(right, 3, style.wedge_band(right_width, phase=7),
                 C["shadow"], C["ink"])
    style.notice(surface, right, 3, right_width, notice)
    y = 4
    address_rows = 2 if height < 30 else 3
    # Pieces standing above the matter, in the order they lie on the clay.
    for name in laid:
        if name == "matter":
            break
        y = _draw_block(
            surface, right, y, right_width, BLOCK_LABELS.get(name, name),
            picked.get(name, BlockChoice("", "")),
            block_focus == name,
            address_rows if name == "address" else 1, f"block:{name}")

    below = [name for name in laid if name not in ("matter",)
             and laid.index(name) > laid.index("matter")]
    matter_rows = max(3, min(7, height - y - 11 - 2 * len(below)))
    surface.fill(right + 1, y, max(0, right_width - 2), matter_rows + 1,
                 " ", C["clay"], C["ink"])
    pointer = ">" if block_focus == "matter" else " "
    surface.text(right, y, pointer,
                 C["flame"] if block_focus == "matter" else C["faint"], C["ink"])
    surface.text(right + 2, y, BLOCK_LABELS["matter"], C["bone"], C["ink"])
    said = sentence_count(matter)
    chip = f" {said} SENTENCE{'' if said == 1 else 'S'} "
    surface.text(
        right + right_width - len(chip), y, chip,
        C["ink"] if block_focus == "matter" else C["clay"],
        C["sand"] if block_focus == "matter" else C["faint"])
    surface.link(right, y, right_width, matter_rows + 1, "block:matter")
    shown_matter = matter
    if dictating and cursor:
        position = len(shown_matter) if cursor_index is None else max(
            0, min(cursor_index, len(shown_matter)))
        shown_matter = (
            shown_matter[:position] + "█" + shown_matter[position:])
    matter_lines = _wrapped(shown_matter, max(8, right_width - 6))
    if not matter.strip() and not dictating:
        matter_lines = ["Write what you want said, in your own words."]
    for offset, line in enumerate(matter_lines[:matter_rows]):
        surface.text(
            right + 4, y + 1 + offset, _short(line, right_width - 6),
            C["clay"] if matter.strip() or dictating else C["ash"], C["ink"])
    if len(matter_lines) > matter_rows:
        surface.text(right + right_width - 2, y + matter_rows, "…",
                     C["ash"], C["ink"])
    y += matter_rows + 1

    # Pieces standing below the matter, then what the matter binds.
    for name in below:
        if name == "seal":
            continue
        if name == "terms":
            y = _draw_terms(surface, right, y, right_width, terms,
                            term_builder, block_focus == name, term_focus)
            continue
        y = _draw_block(
            surface, right, y, right_width, BLOCK_LABELS.get(name, name),
            picked.get(name, BlockChoice("", "")),
            block_focus == name, 1, f"block:{name}")
    y = _draw_bound(surface, right, y, right_width,
                    min(5, max(1, len(bound))), bound)

    seal_choice = picked["seal"]
    if seal_data:
        scribe = str(seal_data.get("scribe") or "unknown scribe")
        courier = str(seal_data.get("courier") or "no courier")
        route = str(seal_data.get("route") or "no known route")
        travel = seal_data.get("travel_time")
        formula_line = _short(
            " ".join(seal_choice.text.split()), max(8, right_width - 6))
        seal_choice = dataclasses.replace(
            seal_choice,
            text=(
                formula_line
                + ("\n" if formula_line else "")
                + f"{scribe} · {courier}"
                + (f" · about {travel}f" if type(travel) is int and travel
                   else "")
                + f" · {route}"
            ),
        )
    y = _draw_block(
        surface, right, y, right_width, "seal", seal_choice,
        block_focus == "seal", 2, "block:seal")

    failed_forms = tuple(
        name for name, ok in (
            ("address", draft.score.address_ok),
            ("prostration", draft.score.prostration_ok),
            ("self-designation", draft.score.self_designation_ok),
            ("one matter", draft.score.topic_count <= 1),
        ) if not ok)
    advice_top = min(y, height - 7)
    reading_y = advice_top
    if height >= 30:
        surface.fill(
            right + 1, advice_top, max(0, right_width - 2),
            max(0, height - advice_top - 5), " ", C["clay"], C["ink"])
        style.rule(surface, right, advice_top, right_width)
        reading_title = (
            "YABNINU'S READING · WORDS SMOOTHED"
            if advisor_undo else "YABNINU'S READING · HE EXPECTS")
        surface.text(right, advice_top + 1, _short(reading_title, right_width),
                     C["bone"], C["ink"])
        reading_y = advice_top + 2
        if matter.strip() and failed_forms and reading_y < height - 5:
            surface.text(
                right + 2, reading_y,
                _short(
                    "FORM BREAK · " + ", ".join(failed_forms),
                    right_width - 2),
                C["blood"], C["ink"])
            reading_y += 1
        if composing:
            advice = (
                "He is smoothing your words without changing their meaning…",)
        elif not matter.strip():
            advice = ("Write the matter; then ask him to correct it.",)
        else:
            advice = scribe_expects(draft, intent)
        for sentence in advice:
            wrapped = textwrap.wrap(sentence, max(8, right_width - 2))
            for line in wrapped:
                if reading_y >= height - 5:
                    break
                surface.text(right + 2, reading_y, line, C["clay"], C["ink"])
                reading_y += 1
            if reading_y >= height - 5:
                break

    if dictating:
        style.footer(surface, [
            style.FooterAction("arrows", "move stylus", command="Right"),
            style.FooterAction("ctrl-z", "undo"),
            style.FooterAction("ctrl-y", "redo"),
        ], y=height - 3, x=2, width=width - 4)
        style.footer(surface, [
            style.FooterAction("ctrl-d", "keep matter"),
            style.FooterAction("esc", "cancel changes"),
        ], y=height - 2, x=2, width=width - 4)
    else:
        compact = width < 90
        choice_label = "value" if block_focus == "terms" else "choice"
        style.footer(surface, [
            style.FooterAction("↑", "block", command="desk:block:previous"),
            style.FooterAction("↓", "block", command="desk:block:next"),
            style.FooterAction("←", choice_label,
                               command="desk:choice:previous"),
            style.FooterAction("→", choice_label,
                               command="desk:choice:next"),
            style.FooterAction("+", "add piece", command="desk:block:add"),
            style.FooterAction("-", "take off",
                               enabled=block_focus not in ("matter", "address"),
                               command="desk:block:remove"),
        ], y=height - 3, x=2, width=width - 4)
        advisor_action = (
            style.FooterAction(
                "u", "restore" if compact else "restore my words",
                command="desk:undo-correction")
            if advisor_undo else
            style.FooterAction(
                "y", "correct" if compact else "Yabninu correct",
                enabled=bool(matter.strip()) and not composing,
                command="desk:correct"))
        style.footer(surface, [
            style.FooterAction(
                "e", "write" if compact else "write this piece",
                command="desk:edit"),
            advisor_action,
            style.FooterAction(
                "Enter", "review · 2h" if compact else "review & seal · 2h",
                enabled=(
                    bool(matter.strip()) and not composing
                    and bool(seal_id(recipient, blocks))
                    and bool(seal_data.get("route"))),
                command="desk:dispatch"),
            style.FooterAction("esc", "keep"),
            style.FooterAction("x", "discard", command="desk:discard"),
        ], y=height - 2, x=2, width=width - 4)
    return surface.interactive()


def _short(text: str, width: int) -> str:
    """Truncate interface metadata, never the stored letter."""
    if width <= 0:
        return ""
    return text if len(text) <= width else text[:max(0, width - 1)] + "…"
