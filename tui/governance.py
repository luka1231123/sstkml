"""Institutional orders, read from the public account."""
from __future__ import annotations

import textwrap
from tui import style
from tui.grid import INDEX as C, Surface


def compose(b, width=80, height=34, notice='', scroll=0):
    s = Surface(width, height)
    account = b.get('governance', {})
    style.panel(s, 0, 0, width, height,
                title=account.get('title', 'GOVERNING ORDERS').upper(), drop=False)
    def line(y, text, tone='bone'):
        s.text(3, y, str(text)[:width - 6], C[tone], C['ink'])
    if not account:
        line(4, 'This court has no separate institutional account.')
        line(6, 'Use the ration roll, court, works and correspondence.')
    else:
        for y, row in enumerate(textwrap.wrap(account.get('summary', ''), width - 6)[:3], 3):
            line(y, row)
        line(8, account.get('progress', ''), 'sand')
        due = account.get('cycle_due', b.get('turn', 0))
        line(7, f"Account: {account.get('cycle_status', 'open')} · closes in {max(0, due - b.get('turn', 0))} fortnights (turn {due})", 'sand')
        for index, option in enumerate(account.get('options', ()), 1):
            y = 9 + (index - 1) * 5
            enabled = bool(option.get('available')) and b.get('attention', 0) >= 1
            cost = (f"{option['cost_amount']:,} {option['cost_good']} + 1h"
                    if option.get('cost_amount') else '1h')
            style.footer(s, [style.FooterAction(str(index), option['label'],
                         enabled=enabled, command='governance:' + option['id'])],
                         x=3, y=y, width=width - 6)
            for offset, row in enumerate(textwrap.wrap(option.get('description', option.get('detail', '')), width - 6,
                        max_lines=2, placeholder=' …'), 1):
                line(y + offset, row)
            reason = option.get('reason', '') if not option.get('available') else ''
            line(y + 3, reason or f"Cost: {cost}", 'sand')
        for y, row in enumerate(textwrap.wrap(account.get('stakes', ''), width - 6)[:2], height - 9):
            line(y, row, 'sand')
        result = account.get('last_result', '')
        if result:
            line(height - 6, 'LAST ENTRY', 'gold')
            for y, row in enumerate(textwrap.wrap(str(result), width - 6)[:2], height - 5):
                line(y, row)
    style.notice(s, 3, height - 3, width - 6, notice)
    style.footer(s, [style.FooterAction('1-3', 'review order'),
                    style.FooterAction('esc', 'close')])
    return s.interactive()


def describe(b, choice):
    option = next((o for o in b.get('governance', {}).get('options', ())
                   if o['id'] == choice), None)
    if not option:
        return 'Institutional order: ' + choice.replace('_', ' ')
    cost = (f" Spends {option['cost_amount']:,} {option['cost_good']}."
            if option.get('cost_amount') else '')
    stakes = b.get("governance", {}).get("stakes", "")
    return f"{option['label']}: {option.get('description', option.get('detail', ''))}{cost}\n{stakes}"
