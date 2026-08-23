# The farming year: what the player must be able to see

Scope: the grain year and the labour it costs. The general access rule and the
per-room sweep live in `PLAYER_INFORMATION_ACCESS_FIX.md`; this list is the
farm slice of it, because the farm is the one system the player cannot plan
against today.

Classification follows the same four kinds: court record, observation,
derivation, unobserved truth.

The field loop has three tasks: sow, tend, reap. Reaping turns standing crop
straight into grain; seed for the next year is held back from that harvest.

Done so far: the calendar (section 1), the labour figures (section 3), the
standing crop and harvest (section 4), the gauge in words with its provenance
(section 5), and the next season's ask (section 7). All five are drawn in the
Hall, the Land ledger and the Alu, and explained in four Help topics:
`grain_year`, `person_days`, `river_gauge`, `units`. What remains is the loss
record by cause, the exhaustion fortnight, and the per-cohort allocation rows.

## 1. The calendar

The player must be able to read the whole year, not only the fortnight he is
standing in.

- Every season, its first and last fortnight, and which task it permits.
- The current fortnight's position inside its season ("harvest, 2 of 4").
- Fortnights remaining until the next season opens.
- The harvest deadline, named as a deadline: crop still standing at the last
  harvest fortnight is destroyed.
- That grain comes in and seed is set aside during the harvest window.
- The dead fortnights, marked as dead, so idle hands are a visible choice and
  not an oversight.

Source: `engine/kernel/farm.py` SEASON_CODES, `content/kernel/world.toml`
[seasons]. Court record — the calendar is not secret.

## 2. The work rates

Every rate the engine uses to turn hands into grain, in its own unit, with the
arithmetic shown.

- Sow: qa of seed one person-day puts in the ground.
- Tend: qa of standing crop one person-day watches for a fortnight.
- Reap: qa of standing crop one person-day cuts.
- Harvest yield: grain returned per thousand of standing crop reaped.
- Sowing multiplier: standing crop per qa of seed, from the site's capacity.
- Neglect and drought loss per thousand, and the drought break past which each
  further step of dryness costs the multiple.

Derivation — show the inputs and the one-line formula, never a bare number.

## 3. Labour, per fortnight

Labour is already accounted for in the engine as one exclusive pool per
settlement. None of that accounting reaches the player.

- Person-days available this fortnight, and which cohorts supply them.
- Person-days asked by each task, by each actor.
- Person-days granted, and the order the allocator served them in.
- Person-days short, per intent, with the name of who was served first.
- Person-days idle, and what they could have been spent on.
- The year's shape: which fortnights are oversubscribed and which are empty.

Source: `engine/kernel/resolve.py` Allocation.grants and .remaining. The grants
already carry asked, granted, and authority. Court record for the player's own
settlement; observation elsewhere.

## 4. The crop, at every stage

The estate row shows sown, open, seed, and grain. The Land detail shows the
standing crop.

- Seed in store, seed in the ground.
- Standing crop, per estate.
- Grain brought in during each harvest fortnight, and seed held back from it.
- What was lost, and to what: neglect, weather, unreaped, spoiled.
- Each loss with its cause record and the fortnight it happened.

## 5. Weather

- The current climate index for the settlement's region, and what an ordinary
  year reads.
- The loss that index implies on the standing crop this fortnight.
- Whether the index is past the drought break.
- The gauge as the court observes it, with its error, kept distinct from the
  true index.

Observation, not court record. The true series is unobserved truth.

## 6. Land

- Extent, capacity, function, holder, settlement.
- Sown share and open share, in qa and as a share of extent.
- Seed required to close the open ground.
- Person-days required to sow that seed inside the sowing window.
- Whether the window is long enough at the hands available. This is the
  planning figure and it does not exist anywhere today.

## 7. The year ahead

One derivation the player needs before he spends grain on anything else.

- Seed the council intends to set aside, and the reserve it keeps back first.
- Ration need per fortnight, and fortnights of grain in hand.
- The fortnight the stores run out at the current rate.
- Whether stored seed is enough to sow the open ground.

Seed corn is protected from ordinary consumption.

## 8. Where each belongs

| Room | Additions |
|---|---|
| Land ledger | calendar strip, standing crop, deadlines, labour asked/granted/idle, weather loss |
| Storehouse | fortnights of grain in hand, seed reserve, exhaustion fortnight, loss by cause |
| Alu | per-cohort person-days available, allocated, performed, idle |
| Hall | end-of-fortnight preview names unused labour and the next deadline |
| Help | unit glossary: qa, person-day, per-thousand, capacity, climate index |
