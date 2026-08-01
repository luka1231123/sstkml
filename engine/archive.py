"""The archive (spec 6.17).

Every document ever received or sent, plus the authored predecessor archive
that exists before turn one, plus internal records.

Two constraints from the spec do all the work here:

**Sorting is by `received_turn` only.** The archive cannot sort by the sender's
date, because the senders' dates are in different calendars with different
epochs and there is no conversion. `dated_as` is a string, deliberately. The
player will act on a letter written before one he has already answered, and that
is not a bug to be smoothed over -- it is the historical situation.

**Search costs an hour per query.** So the query is a real decision, and a
player hunting the broken oath in an epidemic is spending the attention he
needed for the granary. That is the trade 6.12 is built on.

Matching is deterministic and dumb on purpose: case-folded substring over
title, body and tags. No stemming, no ranking by relevance, no fuzzy matching.
A clever search engine would do the player's reading for him, and the reading is
the game.
"""
from __future__ import annotations

import dataclasses

from engine.state import Document, World

SNIPPET = 200          # spec 8.8: the librarian sees a 200-character snippet


def _haystack(doc: Document) -> str:
    return " ".join((doc.title, doc.body, " ".join(doc.tags),
                     doc.sender or "", doc.kind)).lower()


def search(world: World, query: str, limit: int = 12) -> tuple[Document, ...]:
    """Keyword or tag. Multi-word queries are AND, because a player who types
    two words means both -- an OR would return the whole archive and teach him
    that searching is useless."""
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return ()
    hits = [doc for doc in world.documents
            if all(term in _haystack(doc) for term in terms)]
    # By received_turn, like everything else the court can order (6.17). The
    # predecessor archive is turn 0 or negative, so it sorts to the top, which
    # is right: the oldest thing in the room is the thing you have not read.
    hits.sort(key=lambda d: (d.received_turn, d.ref))
    # A tablet house nobody minds returns less of what is in it (6.18). The
    # documents do not move; the keeper simply cannot lay hands on them. Two is
    # the floor, because a search that returns nothing at all reads as a bug
    # rather than as neglect.
    from engine import institution
    keeping = institution.factor(world, "archive")
    limit = max(2, limit * keeping // 1000)
    return tuple(hits[:limit])


def snippet(doc: Document) -> str:
    body = " ".join(doc.body.split())
    return body if len(body) <= SNIPPET else body[:SNIPPET - 1] + "…"


def add(world: World, doc: Document) -> World:
    """Append a document. Refs are unique; re-adding one is a no-op, which keeps
    replay idempotent if a system ever files the same letter twice."""
    if any(existing.ref == doc.ref for existing in world.documents):
        return world
    return dataclasses.replace(world, documents=world.documents + (doc,))


def file_letter(world: World, letter, dated_as: str = "") -> World:
    """File an arrived or sent letter into the permanent record (6.17).

    Accepted outgoing text is immutable engine evidence and is stored exactly.
    Older/authored incoming letters still render their topic and asserted
    figures when no accepted text exists.
    """
    kind = "letter_out" if letter.outgoing else "letter_in"
    facts = ", ".join(f"{key} {value}" for key, value in letter.facts)
    rendered = (
        f"{letter.topic.replace('_', ' ')}. {facts}"
        if facts else letter.topic.replace("_", " ")
    )
    body = letter.text if letter.text else rendered
    return add(world, Document(
        ref=f"L-{letter.id}",
        kind=kind,
        received_turn=(letter.arrive_turn if letter.arrive_turn is not None
                       else letter.sent_turn),
        sender=letter.sender,
        recipient=letter.recipient,
        dated_as=dated_as,
        body=body,
        title=f"{letter.sender}: {letter.topic.replace('_', ' ')}",
        tags=(letter.topic, letter.sender, kind),
        terms=letter.terms,
        path=letter.path,
        reply_to=letter.reply_to,
        scribe_id=letter.scribe_id,
        seal=letter.seal,
        courier_id=letter.courier_id,
    ))


def file_letters(world: World, letters) -> World:
    """File a batch in one linear pass.

    The old turn pipeline offered the entire permanent inbox to
    :func:`file_letter` every fortnight.  ``add`` then scanned the whole
    archive for every old letter, making an idle campaign progressively slower
    even though almost every attempted filing was a duplicate.

    A set of refs is transient implementation detail, not simulation state, so
    using one here does not affect ordering, replay, or hashes.  New tablets
    retain inbox order and are appended exactly once.
    """
    existing = {document.ref for document in world.documents}
    documents = list(world.documents)
    for letter in letters:
        ref = f"L-{letter.id}"
        if ref in existing:
            continue
        kind = "letter_out" if letter.outgoing else "letter_in"
        facts = ", ".join(f"{key} {value}" for key, value in letter.facts)
        rendered = (
            f"{letter.topic.replace('_', ' ')}. {facts}"
            if facts else letter.topic.replace("_", " ")
        )
        body = letter.text if letter.text else rendered
        documents.append(Document(
            ref=ref,
            kind=kind,
            received_turn=(
                letter.arrive_turn
                if letter.arrive_turn is not None else letter.sent_turn
            ),
            sender=letter.sender,
            recipient=letter.recipient,
            dated_as="",
            body=body,
            title=f"{letter.sender}: {letter.topic.replace('_', ' ')}",
            tags=(letter.topic, letter.sender, kind),
            terms=letter.terms,
            path=letter.path,
            reply_to=letter.reply_to,
            scribe_id=letter.scribe_id,
            seal=letter.seal,
            courier_id=letter.courier_id,
        ))
        existing.add(ref)
    if len(documents) == len(world.documents):
        return world
    return dataclasses.replace(world, documents=tuple(documents))
