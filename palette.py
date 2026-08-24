"""The deterministic command palette (UI/UX spec 10).

The text-adventure feeling comes from a capable text interface, not from
waiting for a large model. Everything here is a pure function of the registry
grammar and Belief: no model, no network, no cache, and no possibility of being
slow. With AI switched off the palette is not degraded -- it is the whole
feature.

The grammar is not written here. `registry.DESCRIPTORS` already states each
action's forms -- `assign <formation> to <task> at <place>` -- because Help and
the terminal game print them; this module compiles those same strings into a
matcher. An action added to the registry becomes typable, completable, and
documented in the same commit, and there is no second grammar to forget.

Four rules from the specification shape the design:

* never silently choose among matches -- an ambiguous word is an error that
  lists what it could have meant, not a guess;
* point at the part that is wrong -- the unknown verb, the unresolvable name,
  the value that is still missing;
* resolve only what Belief already shows, so typing cannot reveal anything
  looking could not;
* preview the structured meaning before anything mutates.
"""
from __future__ import annotations

import dataclasses
import re

import affordances
import registry

_SLOT = re.compile(r"<([a-z_]+)>")


@dataclasses.dataclass(frozen=True)
class Form:
    """One grammar line of one action, compiled into words and slots."""

    descriptor: registry.ActionDescriptor
    text: str
    tokens: tuple[str, ...]          # literal words, or "<field>" for a slot

    @property
    def verb(self) -> str:
        return self.tokens[0] if self.tokens else ""

    def field(self, name: str) -> registry.Field | None:
        for field in self.descriptor.fields:
            if field.name == name:
                return field
        return None


def _compile(descriptor: registry.ActionDescriptor) -> list[Form]:
    forms = []
    for line in descriptor.grammar:
        # Optional bracketed parts (`[for <subject>]`) are accepted without
        # their brackets; the field's own `optional` flag already says the
        # value may be absent, so the grammar text need not say it twice.
        tokens = tuple(line.replace("[", "").replace("]", "").split())
        if tokens:
            forms.append(Form(descriptor, line, tokens))
    return forms


FORMS: tuple[Form, ...] = tuple(
    form for descriptor in registry.DESCRIPTORS
    for form in _compile(descriptor))

VERBS: tuple[str, ...] = tuple(dict.fromkeys(form.verb for form in FORMS))


@dataclasses.dataclass(frozen=True)
class Parse:
    """What the palette understood, and what it wants next.

    `status` is `ok` when an action could be built, `incomplete` when the line
    is a legal prefix, and `error` when a word cannot be understood at all.
    Never `guess`: there is no state in which the palette proceeds on a word it
    could not resolve.
    """

    status: str = "empty"
    form: Form | None = None
    values: dict = dataclasses.field(default_factory=dict)
    missing: str = ""                # the field still wanted
    unknown: str = ""                # the word that could not be understood
    message: str = ""
    options: tuple[str, ...] = ()    # what the unknown or missing part allows
    completions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def descriptor(self) -> registry.ActionDescriptor | None:
        return None if self.form is None else self.form.descriptor

    @property
    def cost(self) -> int:
        return 0 if self.descriptor is None else self.descriptor.cost


def _candidate_forms(words: list[str]) -> list[Form]:
    """Forms whose verb the first word is, or could still become."""
    if not words:
        return list(FORMS)
    head = words[0].lower()
    exact = [form for form in FORMS if form.verb == head]
    if exact:
        return exact
    return [form for form in FORMS if form.verb.startswith(head)]


def _match(form: Form, words: list[str], belief: dict) -> Parse:
    """Walk one grammar form against the words, resolving as it goes."""
    values: dict = {}
    index = 0
    for position, token in enumerate(form.tokens):
        slot = _SLOT.fullmatch(token)
        if slot is None:
            # A literal word of the grammar: `to`, `at`, `archive`.
            if index >= len(words):
                return Parse("incomplete", form, values, missing=token,
                             message=f"expected “{token}”",
                             options=(token,))
            if words[index].lower() != token:
                return Parse("error", form, values, unknown=words[index],
                             message=f"expected “{token}”, not "
                                     f"“{words[index]}”",
                             options=(token,))
            index += 1
            continue

        name = slot.group(1)
        field = form.field(name)
        domain = field.domain if field else name
        # A trailing free-text field swallows the rest of the line; a name is
        # one word unless the following literal tells us where it ends.
        rest = form.tokens[position + 1:]
        if domain == "quantity":
            # Always one word. `gift <amount> <good> to <actor>` puts two slots
            # side by side, and a quantity that swallowed up to the next
            # literal would read “10 copper” as the number.
            taken = words[index:index + 1]
        elif domain == "text" or not rest:
            taken = words[index:]
        else:
            stop = next((t for t in rest if _SLOT.fullmatch(t) is None), None)
            if stop is None:
                taken = words[index:index + 1]
            else:
                lowered = [w.lower() for w in words[index:]]
                end = lowered.index(stop) if stop in lowered else len(lowered)
                taken = words[index:index + end]
        if not taken:
            if field is not None and field.optional:
                continue
            return Parse("incomplete", form, values, missing=name,
                         message=f"which {name}?",
                         options=tuple(
                             affordances.completions(domain, "", belief)[:12]))
        phrase = " ".join(taken)
        resolved = affordances.resolve(domain, phrase, belief)
        if resolved is None:
            offers = affordances.completions(domain, phrase, belief)
            if not offers:
                offers = affordances.completions(domain, "", belief)
            reason = (f"no {name} here is called “{phrase}”" if len(offers) != 1
                      else f"“{phrase}” could be more than one {name}")
            if len(affordances.completions(domain, phrase, belief)) > 1:
                reason = f"“{phrase}” could be more than one {name}"
            return Parse("error", form, values, unknown=phrase,
                         missing=name, message=reason,
                         options=tuple(offers[:12]))
        values[name] = resolved
        index += len(taken)

    if index < len(words):
        extra = " ".join(words[index:])
        return Parse("error", form, values, unknown=extra,
                     message=f"“{extra}” is not part of this order",
                     options=(form.text,))
    return Parse("ok", form, values, message=form.text)


def parse(line: str, belief: dict) -> Parse:
    """Understand a typed line, or say exactly which part failed.

    Every candidate form is tried and the most informative outcome wins: a
    complete order beats a partial one, and a partial one beats an error,
    because `assign chariotry` should ask for the task rather than complain
    that it is not `assign <formation> to <task>`.
    """
    words = line.split()
    if not words:
        return Parse("empty", completions=VERBS)
    forms = _candidate_forms(words)
    if not forms:
        near = tuple(verb for verb in VERBS if verb.startswith(words[0][:2]))
        return Parse("error", unknown=words[0],
                     message=f"“{words[0]}” is not something you can order",
                     options=near or VERBS)
    if len(words) == 1 and not any(form.verb == words[0].lower()
                                   for form in forms):
        # Still typing the verb itself.
        return Parse("incomplete", missing="order",
                     message="which order?",
                     options=tuple(dict.fromkeys(f.verb for f in forms)),
                     completions=tuple(dict.fromkeys(f.verb for f in forms)))
    attempts = [_match(form, words, belief) for form in forms]
    rank = {"ok": 0, "incomplete": 1, "error": 2}
    attempts.sort(key=lambda attempt: rank.get(attempt.status, 3))
    best = attempts[0]
    if best.status != "ok":
        return dataclasses.replace(
            best, completions=tuple(best.options))
    return best


# Some grammar lines say a value in a literal word rather than a slot: `file`
# and `restore` are one action with opposite flags, as are `quarantine` and
# `lift quarantine`. The keys are the registry's own grammar strings, and
# `tests/test_palette.py` asserts every one of them still exists -- so a
# reworded grammar line fails the suite rather than quietly ceasing to parse.
LITERAL_VALUES: dict[str, dict] = {
    "finance <amount>": {"good": "copper"},
    "inspect granary": {"ledger": "granary"},
    "inspect seed": {"ledger": "seed"},
    "file <tablet>": {"archived": True},
    "restore <tablet>": {"archived": False},
    "quarantine <place>": {"lift": False},
    "lift quarantine <place>": {"lift": True},
    "send <group> to harvest": {"to_fields": True},
    "recall <group>": {"to_fields": False},
}


# Orders that are a whole workflow rather than one action. `answer <tablet>`
# has to open the Desk: a reply is a letter the king writes, with an intent, a
# draft, and a protocol column, and no one line of typing can stand for it. The
# palette parses the form, resolves the tablet, and hands the rest over.
HANDOFF: dict[str, str] = {"answer <tablet>": "desk"}


def handoff(result: Parse) -> str:
    """The window this order opens instead of acting, if it is one of those."""
    if result.form is None:
        return ""
    return HANDOFF.get(result.form.text, "")


def build(result: Parse):
    """The engine action a complete parse means, or None.

    Values are already resolved ids, so this is assembly and never resolution:
    nothing here reads Belief, and a parse that was refused cannot be built by
    calling this anyway.
    """
    if not result.ok or result.form is None:
        return None
    descriptor = result.form.descriptor
    flags = LITERAL_VALUES.get(result.form.text, {})
    names = registry.argument_names(descriptor)
    # By name, not by position. `rule <verdict> on <petition>` says the verdict
    # first and the engine takes the petition first, so assembling positionally
    # built an order with its two arguments exchanged -- and an order that
    # names the wrong subject is worse than an order refused.
    arguments = dict(flags)
    for field in descriptor.fields:
        engine = names.get(field.name, field.name)
        value = result.values.get(field.name)
        if value is None:
            if engine in flags:
                continue        # the grammar said it in a literal word
            if not field.optional:
                return None
            continue
        arguments[engine] = (int(value) if field.domain == "quantity"
                             else value)
    try:
        return descriptor.action_type(**arguments)
    except (TypeError, ValueError):
        return None


def preview(result: Parse) -> str:
    """The exact structured meaning, in words, before anything happens."""
    if result.form is None:
        return ""
    descriptor = result.form.descriptor
    parts = [f"{name}: {value}" for name, value in result.values.items()]
    hours = "free" if not descriptor.cost else (
        f"{descriptor.cost} hour" + ("s" if descriptor.cost != 1 else ""))
    return f"{descriptor.label} — " + ("; ".join(parts) or "no arguments") \
        + f"  ·  {hours}"


def suggest(line: str, belief: dict) -> tuple[str, ...]:
    """What Tab would offer for the word being typed."""
    result = parse(line, belief)
    if result.completions:
        return result.completions
    return result.options


def complete(line: str, belief: dict) -> str:
    """Tab: extend the line by the one completion, if there is exactly one."""
    offers = suggest(line, belief)
    if len(offers) != 1:
        return line
    words = line.split()
    only = offers[0]
    if line and not line.endswith(" ") and words and \
            only.startswith(words[-1].lower()):
        return " ".join(words[:-1] + [only])
    return (line.rstrip() + " " + only).strip()
