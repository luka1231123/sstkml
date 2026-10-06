"""The ruler's campaign tablet, in the same palace desktop."""
from __future__ import annotations

import textwrap

from belief.facts import facts
from belief.chapters import chapter
from tui import art, render, style
from tui.grid import INDEX as C, Surface


def compose(b, width=76, height=32, *, hours=0, opening=False, can_resume=False,
            new_review=False, notice='', receipt=(), scroll=0, city='seat'):
    s = Surface(width, height)
    style.panel(s, 0, 0, width, height, title='SAY TO THE KING, MY LORD' if opening else 'THE REIGN', drop=False)
    def line(y, text, tone='clay'):
        s.text(3, y, text[:width - 6], C[tone], C['ink'])
    if opening or new_review:
        art.draw(s, width - 27, 3, art.THRONE, lit=C['gold'])
        rows = ['The cities at the end of the Bronze Age.',
                'Your officers report what they know.',
                'Letters take time. Orders spend your stores.', '',
                'Keep the city fed. Hear claims. Prepare',
                'for harvest. Keep other courts answering.', '',
                'There is no fixed date for the end.',
                'Your orders change the city.']
        for y, text in enumerate(rows, 3):
            line(y, text, 'bone' if y == 3 else 'clay')
        options = [('reign:begin', 'Begin a new reign')]
        if can_resume and not new_review:
            options.insert(0, ('reign:resume', 'Continue the saved reign'))
        if new_review:
            line(15, 'Your present reign will be kept in a separate save.', 'sand')
            line(16, 'A new seed creates a different history.', 'sand')
        for index, (command, text) in enumerate(options, 1):
            label = f'[{index}] {text}'
            line(19 + index * 2, label, 'gold')
            s.link(3, 19 + index * 2, len(label), 1, command)
        line(height - 6, 'Twenty-four fortnights make a year. Reading costs hours.', 'dim')
        line(height - 5, 'Every sealed order saves. Windows can be moved and tiled.', 'dim')
        footer = [style.FooterAction('?', 'how to play', command='reign:help')]
        footer.append(style.FooterAction('esc', 'cancel' if new_review else 'quit', command='reign:cancel'))
    else:
        line(2, f"{b['date']} · {hours} court hours remain", 'sand')
        if b.get('ended'):
            body = ['THE LAST TABLET', b.get('end_reason', 'The reign has ended.'), '',
                    f"The reign lasted {max(0, b['turn'] - 1) // 24} years and "
                    f"{max(0, b['turn'] - 1) % 24} fortnights.",
                    f"The court records {len(b.get('justice', {}).get('rulings', ()))} judgements.",
                    'The archive and final accounts can still be read.', '', *receipt]
            options = [('reign:report', 'Read the last report'), ('reign:orders', 'Read your orders'),
                       ('reign:begin', 'Choose a city or saved reign')]
        else:
            ruler = render.actor_name(b['house']['ruler'], b.get('house'))
            guide = chapter(b, city)
            body = [f"{ruler.upper()} · {b['scenario'].upper()}",
                    guide['title'], '', 'YOUR CITY’S THREE AIMS · F3 OPENS THE ROOMS']
            marks = {'ready': '✓', 'attention': '!', 'unknown': '?'}
            for goal in guide['goals']:
                body += [f"{marks[goal['status']]} {goal.get('short', goal['say'])}"]
            body += ['', 'NEEDS ATTENTION']
            for fact in facts(b)[:2]:
                body += [fact['say']]
            vow = b.get('royal_pledge')
            if vow:
                body += ['', f"Public pledge: {vow['kind']} · {vow['kept']}/{vow['checked']} closing accounts kept; due turn {vow['due_turn']}."]
            if receipt:
                body += ['', 'YOUR LAST ORDER', receipt[0]]
            body += ['', 'YOUR RECORD',
                     f"{len(b.get('justice', {}).get('rulings', ()))} judgements · {b['house'].get('reigns', 1)} rulers · {len(b.get('justice', {}).get('petitions', ()))} claims waiting.",
                     ('Heir: ' + render.actor_name(b['house']['named_heir'], b.get('house'))
                      if b['house'].get('named_heir') else 'No heir named. Read the household roll in Palace.')]
            options = [('reign:court', 'Hear the court'), ('reign:food', 'Rations and the granary'),
                       ('reign:trade', 'Buy grain at the market'), ('reign:relief', 'Ask a court for grain'),
                       ('reign:begin', 'Choose a city or saved reign')]
        room = max(1, height - 15)
        rows = [row for paragraph in body for row in (textwrap.wrap(paragraph, width - 6) or [''])]
        start = max(0, min(scroll, len(rows) - room))
        for y, row in enumerate(rows[start:start + room], 4):
            line(y, row, 'gold' if row.isupper() else 'bone')
        if len(rows) > room:
            line(4 + room, f'↑↓ read the tablet · lines {start + 1}-{min(len(rows), start + room)} of {len(rows)}', 'dim')
        for index, (command, text) in enumerate(options, 1):
            y = height - 9 + index
            label = f'[{index}] {text}'
            line(y, label, 'gold')
            s.link(3, y, len(label), 1, command)
        footer = [style.FooterAction('F3', 'city charter', command='reign:charter'),
                  style.FooterAction('n', 'new reign', command='reign:new'),
                  style.FooterAction('?', 'help', command='reign:help'),
                  style.FooterAction('esc', 'close', command='reign:cancel')]
    style.notice(s, 3, height - 3, width - 6, notice)
    style.footer(s, footer, y=height - 2)
    return s.interactive()


def letter_presets(width=68, height=22, notice=''):
    s = Surface(width, height)
    style.panel(s, 0, 0, width, height, title='THE BUSINESS OF THE TABLET', drop=False)
    body = ['Choose the business; then read and edit it in Scribes.',
            'Nothing is sent until you review and seal the tablet.']
    for y, text in enumerate(body, 3):
        s.text(3, y, text[:width - 6], C['bone'], C['ink'])
    options = [('aid', 'Ask for one fortnight of grain · a loan if accepted'),
               ('gift', 'Send a gift of copper · spends your stores'),
               ('reassure', 'Reassure the other court · no attached goods'),
               ('refuse', 'Refuse their request · no attached goods'),
               ('warn', 'Warn them to watch the roads · no attached goods')]
    for index, (kind, label) in enumerate(options, 1):
        y = 5 + index * 2
        s.text(3, y, f'[{index}] {label}'[:width - 6], C['gold'], C['ink'])
        s.link(3, y, width - 6, 1, 'preset:' + kind)
    style.notice(s, 3, height - 3, width - 6, notice)
    style.footer(s, [style.FooterAction('1-5', 'choose business'), style.FooterAction('esc', 'cancel')])
    return s.interactive()


def mandate_presets(b):
    # Island imports need a purse large enough to buy a real payroll.
    return ((2, 6000), (4, 12000), (8, 24000), (0, 0)) if b.get("scenario") == "Alashiya" else ((2, 1000), (4, 3000), (8, 6000), (0, 0))


def grain_mandate(b, width=72, height=24, notice=''):
    from tui import dialog
    mandate = b.get('grain_mandate', [])
    presets = mandate_presets(b)
    status = (f'Keeper maintains {mandate[0]} fortnights of grain; purse capped at {mandate[1]:,} copper each fortnight.'
              if mandate else 'No standing purchase mandate has been sealed.')
    return dialog.compose("THE KEEPER'S MANDATE",
        [status, '', 'The keeper buys local grain when stores fall below your reserve.',
         'Each purchase spends copper. No copper, no stock, or an empty office stops it.',
         *(['Alashiya depends on imports. Four payrolls / 12,000 copper is a useful opening limit.',
            'The factor has finite grain; review stock and copper after harvest.']
           if b.get('scenario') == 'Alashiya' else []),
         *b.get('mandate_report', ())],
        [(f'mandate:{reserve}:{purse}',
          f'Reserve: {reserve} fortnights; at most {purse:,} copper' if reserve
          else 'Cancel standing purchases') for reserve, purse in presets], width=width, height=height,
        notice=notice, footer=(style.FooterAction('1-4', 'review mandate'), style.FooterAction('esc', 'close')))


def cities(catalog, selected, width=76, height=32, notice='', saved=()):
    s = Surface(width, height)
    style.panel(s, 0, 0, width, height, title='CHOOSE YOUR SEAT', drop=False)
    s.text(3, 2, f'{len(catalog)} courts. Choose a seat, then read its account.', C['bone'], C['ink'])
    for index, city in enumerate(catalog, 1):
        y = 4 + (index - 1) * 2
        text = f"{'>' if city['id'] == selected else ' '} [{index}] {city['name']}"
        s.text(3, y, text, C['gold'] if city['id'] == selected else C['bone'], C['ink'])
        s.text(7, y + 1, city['tagline'][:width - 10], C['sand'], C['ink'])
        s.link(3, y, width - 6, 2, 'city:' + city['id'])
    city = next(c for c in catalog if c['id'] == selected)
    for y, row in enumerate(textwrap.wrap(city['description'], width - 6)[:4], 21):
        s.text(3, y, row, C['bone'], C['ink'])
    s.text(3, height - 5, '[enter] Begin a new reign', C['gold'], C['ink'])
    s.link(3, height - 5, 25, 1, 'city:begin')
    if selected in saved:
        s.text(3, height - 4, '[9/r] Continue this city’s saved reign', C['sand'], C['ink'])
        s.link(3, height - 4, width - 6, 1, 'city:resume')
    style.notice(s, 3, height - 3, width - 6, notice)
    style.footer(s, [style.FooterAction(f'1-{len(catalog)}', 'choose'), style.FooterAction('enter', 'begin'), style.FooterAction('esc', 'back')])
    return s.interactive()


PLEDGE_NAMES = {'bread': 'Bread in reserve', 'wages': 'No unpaid worker', 'justice': 'Claims heard on time'}


def charter(b, city='seat', width=76, height=30, detail=False, scroll=0, notice=''):
    guide = chapter(b, city)
    s = Surface(width, height)
    style.panel(s, 0, 0, width, height, title=f"THE CHARTER OF {b['scenario'].upper()}", drop=False)
    s.text(3, 2, guide['title'][:width - 6], C['gold'], C['ink'])
    marks = {'ready': '✓ covered', 'attention': '! needs attention', 'unknown': '? uncounted'}
    if detail:
        body = [guide.get('identity', ''), guide['summary'], '', 'VOLUNTARY AIMS · CONDITIONS CAN CHANGE']
        for index, goal in enumerate(guide['goals'], 1):
            body += [f"[{index}] {marks[goal['status']]} · {goal['where']}", goal['say'], '']
        rows = [row for paragraph in body for row in (textwrap.wrap(paragraph, width - 6) or [''])]
        room = height - 8
        start = max(0, min(scroll, max(0, len(rows) - room)))
        for y, row in enumerate(rows[start:start + room], 4):
            s.text(3, y, row, C['bone'], C['ink'])
    else:
        summary = textwrap.wrap(guide['summary'], width - 6, max_lines=3, placeholder=' …')
        for y, row in enumerate(summary, 4):
            s.text(3, y, row, C['bone'], C['ink'])
        for index, goal in enumerate(guide['goals'], 1):
            y = 8 + (index - 1) * 4
            s.text(3, y, f"[{index}] {marks[goal['status']]} · {goal['where']}"[:width - 6], C['sand'], C['ink'])
            for offset, row in enumerate(textwrap.wrap(goal.get('short', goal['say']), width - 6, max_lines=2, placeholder=' …'), 1):
                s.text(3, y + offset, row, C['bone'], C['ink'])
            s.link(3, y, width - 6, 3, f"charter:goal:{index - 1}")
        vow = b.get('royal_pledge')
        text = (f"King’s word: {PLEDGE_NAMES[vow['kind']]} · {vow['kept']}/{vow['checked']} accounts kept; due turn {vow['due_turn']}."
                if vow else 'Optional: make a public pledge for six fortnights.')
        for y, row in enumerate(textwrap.wrap(text, width - 6)[:2], height - 7):
            s.text(3, y, row, C['sand'], C['ink'])
    if b.get('governance'):
        s.text(3, height - 4, '[6/g] Governing orders', C['gold'], C['ink'])
        s.link(3, height - 4, 25, 1, 'charter:governance')
    style.notice(s, 3, height - 3, width - 6, notice)
    style.footer(s, [style.FooterAction('1-3', 'open room'), style.FooterAction('4/p', 'pledge', command='charter:pledge'),
                     style.FooterAction('5/v', 'brief' if detail else 'details', command='charter:detail'), style.FooterAction('esc', 'close')])
    return s.interactive()


def pledges(b, width=76, height=28, notice=''):
    from tui import dialog
    vow = b.get('royal_pledge')
    body = ['An optional public promise. Every closing account counts.',
            'Keep all six: court standing improves and anger falls.',
            'Miss any: the broken word costs standing and adds anger.',
            'One pledge at a time; twelve fortnights between declarations.', '']
    if vow:
        body += [f"Active: {PLEDGE_NAMES[vow['kind']]}; due turn {vow['due_turn']}.",
                 f"Kept {vow['kept']} of {vow['checked']} accounts checked. No new vow while this one lasts."]
    else:
        body += ['Bread: keep grain for two full payrolls, after every fortnight.',
                 'Wages: leave zero ration debt on every closing roll.',
                 'Justice: leave no claim waiting beyond its grace.']
    latest = b.get('pledge_history', [])
    if latest:
        last = latest[-1]
        body += ['', f"Last pledge: {PLEDGE_NAMES[last['kind']]} — {last['status']}."]
    remaining = max(0, max((p['start_turn'] for p in latest), default=-12) + 12 - b.get('turn', 0))
    if remaining and not vow:
        body += [f'Another public pledge may be made in {remaining} fortnights.']
    options = [] if vow or remaining else [(f'pledge:{kind}', name) for kind, name in PLEDGE_NAMES.items()]
    return dialog.compose('THE KING’S WORD', body, options, width=width, height=height, notice=notice,
        footer=[style.FooterAction('1-3', 'review promise'), style.FooterAction('esc', 'close')])
