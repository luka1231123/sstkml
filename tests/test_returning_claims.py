"""Returning claims remember actual awards and transfer only real goods."""

import pytest

from belief.project import project
from engine import actions as A, seat
from engine.core import state_hash
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign
from session import save, replay
from tui import briefing, palace, reckoning
from tui.grid import plain_text


@pytest.mark.parametrize('verdict,case_id,amount,good', [
    ('for', 'shipwright_bread', 18000, 'grain'),
    ('split', 'shipwright_balance', 3000, 'copper'),
    ('against', 'shipwright_balance', 6000, 'copper'),
])
def test_return_depends_on_the_award_and_can_be_refused(verdict, case_id, amount, good, tmp_path):
    seed = 8814402919
    world = advance(load_campaign('seat', seed))[0]
    action = A.RulePetition('debt_shipwright', verdict)
    world, _ = apply(world, action)
    log = [{'turn': 1, 'action': A.to_dict(action)}]
    award = world.court.rulings['debt_shipwright'].amount
    for _ in range(2):
        world = advance(world)[0]
        assert case_id not in world.court.petitions
    world = advance(world)[0]
    b = project(world)
    case = next(p for p in b['justice']['petitions'] if p['id'] == case_id)
    assert case['claim']['amount'] == amount and case['good'] == good
    assert f'{award:,}' in case['claim_text']
    assert case['outcomes']['against']['amount'] == 0
    for width, height in ((92, 30), (68, 24)):
        screen = palace.compose(b, view='audience', selected=case_id, hours=7,
                                width=width, height=height)
        controls = [hit for hit in screen.hits if hit.command.startswith('verdict:')]
        assert len(controls) == 3 and all(hit.enabled for hit in controls)
    path = tmp_path / 'return.json'
    save(path, seed, 'seat', 4, log, world)
    assert state_hash(replay(path)) == state_hash(world)
    held = seat.held(world)
    refused, _ = apply(world, A.RulePetition(case_id, 'against'))
    assert seat.held(refused) == held
    paid, _ = apply(world, A.RulePetition(case_id, 'for'))
    assert seat.held(paid)[good] == held[good] - amount
    for _ in range(5):
        paid = advance(paid)[0]
    assert case_id not in paid.court.petitions
    assert len(paid.court.rulings) == 2


def test_waiting_has_a_grace_period_and_ruling_stops_its_cost():
    import dataclasses
    from engine import justice
    world = advance(load_campaign('seat', 8814402919))[0]
    def court_turn(w):
        return justice.step(dataclasses.replace(
            w, kernel=dataclasses.replace(w.kernel, date=w.date.advance())))[0]
    initial = world.court.unrest
    for _ in range(2):
        world = court_turn(world)
    assert world.court.unrest == initial
    world = court_turn(world)
    assert world.court.unrest == initial + 2
    b = project(world)
    assert 'adds 2 city unrest' in next(m for m in briefing.agenda(b) if m.id == 'justice').stake
    world, _ = apply(world, A.RulePetition('debt_shipwright', 'for'))
    unrest = world.court.unrest
    world = court_turn(world)
    assert world.court.unrest == unrest


def test_year_reckoning_uses_recorded_awards_and_keeps_unread_answers_sealed():
    world = advance(load_campaign('seat', 8814402919))[0]
    world, _ = apply(world, A.RulePetition('debt_shipwright', 'split'))
    for _ in range(23):
        world = advance(world)[0]
    b = project(world)
    b['outbox'] = [{'id': 'L1', 'status': 'answer come — seal unbroken', 'decision': ''}]
    text = ' '.join(reckoning.lines(b))
    assert '6,000 copper' in text and 'Abdi-Anu' in text
    assert 'returned debt claim' in text and 'seal unbroken' in text
    assert 'accepted' not in text
    assert briefing.agenda(b)[0].id == 'year'
    assert len(briefing.arguments(b, 'food')) == 2
