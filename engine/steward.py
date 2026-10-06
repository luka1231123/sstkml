"""A sealed grain mandate, executed by the keeper against real local stocks."""
from __future__ import annotations

from engine import actions as A, seat
from engine.kernel import carry
from engine.state import replace_court


def set_mandate(world, action):
    if type(action.reserve_fortnights) is not int or type(action.max_copper) is not int:
        raise ValueError('the reserve and purse must be whole numbers')
    if not 0 <= action.reserve_fortnights <= 12 or not 0 <= action.max_copper <= 100000:
        raise ValueError('choose up to 12 fortnights of reserve and up to 100,000 copper per fortnight')
    enabled = bool(action.reserve_fortnights and action.max_copper)
    mandate = (action.reserve_fortnights, action.max_copper) if enabled else ()
    message = (f'Keeper instructed: maintain {action.reserve_fortnights} fortnights of grain, '
               f'spending at most {action.max_copper:,} copper each fortnight.' if enabled
               else 'The standing grain mandate is cancelled.')
    return replace_court(world, grain_mandate=mandate, mandate_report=(message,)), [A.GrainMandateSet(*mandate) if mandate else A.GrainMandateSet(0, 0)]


def step(world):
    if not world.court.grain_mandate:
        return replace_court(world, mandate_report=()), []
    reserve, ceiling = world.court.grain_mandate
    keeper = next((i.head for i in world.court.institutions.values()
                   if i.kind == 'granary' and i.place == world.court.seat), '')
    if not keeper:
        return replace_court(world, mandate_report=('No keeper holds the granary; the grain mandate waits for an appointment.',)), []
    groups = seat.groups(world)
    allowances = seat.allowances(world)
    demand = sum(min(allowances.get(gid, group.size * group.entitlement), group.size * group.entitlement)
                 for gid, group in groups.items())
    available = seat.available(world)
    deficit = max(0, demand * reserve - available.get('grain', 0))
    if not deficit:
        return replace_court(world, mandate_report=('Keeper: the ordered grain reserve is covered; no copper spent.',)), []
    location = world.kernel.seat_goods.seat
    price = max(1, carry.readings(world.kernel, location)['price_grain'])
    purse = min(ceiling, available.get('copper', 0), (deficit * price + 999) // 1000)
    if purse < 1:
        return replace_court(world, mandate_report=('Keeper: grain is below the ordered reserve, but no unreserved copper can buy it.',)), []
    from engine import trade_policy
    try:
        world, events = trade_policy.apply(world, A.FinanceTrade('copper', purse))
    except ValueError as error:
        report = f'Keeper could not restock: {error}.'
        return replace_court(world, mandate_report=(report,)), []
    bought = next(event for event in events if isinstance(event, A.TradeFinanced))
    report = (f'Keeper bought {bought.received_quantity:,} qa grain for {bought.quantity:,} copper under your standing mandate.',)
    return replace_court(world, mandate_report=report), events
