"""The action registry and the inventory that guards it (UI/UX spec 19, 21).

Phase 0's exit gate is that the suite fails on an orphan action, an unreachable
room, a duplicate mnemonic, or a cost that disagrees with itself. These tests
are that gate.
"""
from __future__ import annotations

import registry
from ai import parser as ai_parser
from engine import actions as A
from tools import inventory


# The normative Required-attention column of UI/UX specification section 19,
# copied here on purpose. If someone changes a cost in the registry, this test
# should make them come and change the specification's number too, rather than
# letting the two drift the way the GUI and the parser already did once.
REQUIRED_ATTENTION = {
    "end_fortnight": 0, "allocate": 0, "set_priority": 0, "eat_seed": 0,
    "read_letter": 2, "file_letter": 0, "delegate_letter": 1,
    "dictate_reply": 2, "inspect_ledger": 1, "send_gift": 1,
    "send_to_harvest": 1, "assign_troops": 1, "raise_corvee": 1,
    "dredge_canal": 1, "marry_abroad": 2, "consult_diviner": 2,
    "suppress_omen": 2, "defy_omen": 0, "swear_oath": 2, "quarantine": 1,
    "expiate": 2, "search_archive": 1, "hear_petition": 1, "rule_petition": 0,
    "set_land_due": 0, "set_harbour_due": 0, "place_person": 0,
    "dismiss_person": 0, "name_heir": 0, "begin_build": 1, "begin_repair": 1,
    "abandon_work": 1,
}


def test_the_inventory_reports_no_faults():
    assert inventory.faults() == []


def test_every_action_costs_what_the_specification_says():
    got = {d.id: d.cost for d in registry.DESCRIPTORS}
    assert got == REQUIRED_ATTENTION


def test_delegating_costs_the_same_hour_whichever_way_it_is_said():
    """The divergence the audit caught: 1h in the Inbox, 0h through Counsel."""
    action = A.DelegateLetter("tablet_1", "ehli_nikkalu")
    assert registry.cost_of(action) == 1
    assert ai_parser.action_cost(action) == 1


def test_the_typed_path_never_invents_a_second_cost():
    for descriptor in registry.DESCRIPTORS:
        sample = inventory._sample(descriptor.action_type)
        if sample is None:
            continue
        assert ai_parser.action_cost(sample) == descriptor.cost, descriptor.id


def test_an_engine_event_is_not_charged_to_the_player():
    """Events are what happened, not what was asked for, so they are free."""
    assert registry.cost_of(A.LetterArrived("tablet_1", "carchemish", 1)) == 0


def test_no_two_actions_in_one_window_want_the_same_key():
    for context in registry.contexts():
        keys = [d.mnemonic for d in registry.in_context(context) if d.mnemonic]
        assert len(keys) == len(set(keys)), context


def test_every_descriptor_names_a_real_action_and_a_grammar():
    for descriptor in registry.DESCRIPTORS:
        assert hasattr(A, descriptor.action_type.__name__), descriptor.id
        assert descriptor.grammar, descriptor.id
        assert descriptor.label, descriptor.id
        assert descriptor.contexts, descriptor.id


def test_a_result_says_why_when_it_refuses():
    refusal = registry.ActionResult(
        status=registry.REFUSAL, action_id="delegate_letter",
        message="No courtier is at the seat.", missing="person")
    assert not refusal.ok
    assert refusal.missing == "person"
    assert registry.ActionResult(status=registry.SUCCESS).ok
