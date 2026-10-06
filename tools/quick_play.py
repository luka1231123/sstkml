"""Fast, reproducible court playthroughs without Tk or a language model.

Uses public accounts and the same action costs as the interface. This simple
policy buys grain, pays affordable claims and meets affordable royal accounts;
it does not negotiate foreign supply or judge whether the game is enjoyable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import registry
from belief.project import project
from engine import actions as A
from engine.reduce import apply
from engine.tick import advance
from load import load_campaign

COURTS = ('seat', 'byblos', 'tyre', 'carchemish', 'alashiya', 'pylos', 'egypt', 'hattusa')


def run(court, turns, seed):
    world = load_campaign(court, seed)
    rows, refusals = [], []
    for _ in range(turns):
        world, _ = advance(world)
        b = project(world)
        hours = b['attention']

        def act(action):
            nonlocal world, hours, b
            cost = registry.cost_of(action)
            if cost > hours or world.ended:
                return
            try:
                world, _ = apply(world, action)
                hours -= cost
                b = project(world)
            except (ValueError, KeyError, TypeError) as error:
                refusals.append(f"t{b['turn']} {type(action).__name__}: {error}")

        if not world.ended:
            if b['turn'] == 1:
                act(A.SetGrainMandate(4, 12000 if court == 'alashiya' else 3000))
            for option in b.get('governance', {}).get('orders', ()):
                if option['available'] and option['cost_good']:
                    act(A.GovernanceOrder(option['id']))
                    break
            for case in list(b.get('justice', {}).get('petitions', ())):
                verdict = next((v for v in ('for', 'split')
                                if case['outcomes'][v]['affordable']), 'against')
                act(A.RulePetition(case['id'], verdict))
        rows.append({'turn': b['turn'], 'grain': b['stores'].get('grain', 0),
                     'copper': b['stores'].get('copper', 0),
                     'debt': sum(g['arrears_qa'] for g in b['groups']),
                     'anger': world.court.unrest})
        if world.ended:
            break
    return {'court': court, 'turns': len(rows), 'ended': world.ended,
            'cause': world.end_reason, 'first_empty': next((r['turn'] for r in rows if not r['grain']), None),
            'peak_debt': max(r['debt'] for r in rows), 'closing': rows[-1],
            'refusals': refusals, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--turns', type=int, default=72)
    parser.add_argument('--seed', type=int, default=20261006)
    parser.add_argument('--court', choices=COURTS, action='append')
    parser.add_argument('--output', type=Path, default=Path('output/quick-play.json'))
    args = parser.parse_args()
    if args.turns < 1:
        parser.error('--turns must be positive')
    start = time.monotonic()
    results = []
    courts = args.court or COURTS
    with ProcessPoolExecutor(max_workers=min(4, len(courts))) as pool:
        for row in pool.map(run, courts, [args.turns] * len(courts), [args.seed] * len(courts)):
            results.append(row)
            court = row['court']
            print(f"{court:10} turns={row['turns']:3} first_empty={str(row['first_empty']):>4} "
                  f"peak_debt={row['peak_debt']:10,} anger={row['closing']['anger']:4} "
                  f"ended={row['ended']} refusals={len(row['refusals'])}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    elapsed = round(time.monotonic() - start, 2)
    args.output.write_text(json.dumps({'seed': args.seed, 'seconds': elapsed, 'results': results}, indent=2) + '\n')
    print(f"Completed {sum(r['turns'] for r in results)} fortnights in {elapsed}s. {args.output}")
