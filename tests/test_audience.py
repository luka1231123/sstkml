"""Court receives decisions; planning is a deliberate departure."""
from engine import actions as A
from engine.tick import advance
from tests.test_ledgers import _game, _Key
from tui import audience, document
from tui.grid import plain_text
import registry


def test_campaign_opens_with_the_petition_and_reviewable_actions():
    game = _game(turns=1)
    item = audience.current(game.belief)
    assert item['id'] == 'case:debt_shipwright'
    screen = audience.compose(game.belief, hours=game.hours)
    text = plain_text(screen)
    assert 'Abdi-Anu' in text and '9,000 copper' in text
    assert 'lower unrest' not in text.lower() and 'YABNINU' not in text
    assert 'split' in text and len([h for h in screen.hits if 'verdict:' in h.command]) == 3
    before = game.world
    game.on_key(_Key('f'))
    assert game.world is before and game.pending_action
    game.cancel_pending()
    assert game.world is before and not game.log
    game.on_key(_Key('f'))
    game.confirm_pending()
    assert game.log[-1]['action']['_t'] == 'RulePetition'
    assert not any(i['kind'] == 'case' for i in audience.queue(game.belief))


def test_defer_and_planning_do_not_spend_hours_or_resolve_claims():
    game = _game(turns=1)
    before, hours = game.world, game.hours
    game.on_key(_Key('d'))
    assert audience.current(game.belief, game.audience_deferred) is None
    game.on_key(_Key('r'))
    assert audience.current(game.belief, game.audience_deferred)
    game.on_key(_Key(keysym='Tab'))
    assert game.home_view == 'planning'
    game.on_key(_Key(keysym='Tab'))
    assert game.home_view == 'court'
    game.on_key(_Key(keysym='space'))
    assert game.home_view == 'planning'
    assert game.world is before and game.hours == hours


def test_reading_a_letter_happens_in_court_and_keeps_the_opened_letter_selected():
    game = _game(turns=3)
    letter = next(l for l in game.belief['stack'] if not l['read'])
    game.audience_pick = 'letter:' + letter['id']
    before = game.hours
    game.on_key(_Key(keysym='Return'))
    item = audience.current(game.belief, selected=game.audience_pick)
    assert item['letter']['read'] and game.hours == before - registry.BY_ID['read_letter'].cost
    text = plain_text(audience.compose(game.belief, hours=game.hours, selected=game.audience_pick))
    assert 'reply' in text and 'A sealed letter awaits' not in text
    assert 'unbroken' not in ' '.join(t for t, _ in document.answer_lines({'read': True, 'facts': {}}, 70))


def test_new_fortnight_returns_to_court_without_opening_report_window():
    game = _game(turns=1)
    class Window:
        def focus(self): pass
    class App:
        windows = {}
        def close(self, key): pass
        def window(self, *args, **kwargs): raise AssertionError('No automatic report window')
    game.app, game.hall_window = App(), Window()
    game.counsel_pending = None
    game.open_letters, game.stack_order = set(), []
    game.save_current = lambda automatic=False: True
    game.home_view, game.audience_deferred = 'planning', {'case:debt_shipwright'}
    game.end_fortnight()
    assert game.home_view == 'court' and not game.audience_deferred
    assert game.events and game.world.date.absolute == 2


def test_large_letter_scroll_and_empty_court_keep_planning_available():
    b = _game(turns=1).belief
    b['justice']['petitions'] = []
    b['stack'] = [{'id': 'L', 'sender': 'ammurapi', 'read': True,
                   'body': ' '.join(['a long letter'] * 500), 'received_turn': b['turn']}]
    text = plain_text(audience.compose(b, selected='letter:L', scroll=100000, hours=7))
    assert 'reply' in text and 'planning' in text
    empty = plain_text(audience.compose(b, deferred={'letter:L'}))
    assert 'Recall' in empty and 'Planning' in empty
