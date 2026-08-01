# The farming model is not how the collapse happened

Status: standing note, not a plan. Nothing here is scheduled and nothing here
is a requirement of `SPEC.md`. Written down so the next
person to open `tools/gen_detail.py` does not mistake the current numbers for a
considered position on Late Bronze Age agriculture. They are not; they are a
balance pass that stopped a generator bug from emptying half the map.

## What the model says now

Rain falls, a climate index drops, the standing crop withers in proportion
(`farm.tend`: `(100 - climate) * 0.0015` a fortnight, compounding across a nine
fortnight growing window), and the regions with the thinnest margin starve
first. Land per head divides by the region's yield and is capped on the island
and plateau, so every region sits near subsistence and the difference between
them is how far a bad year drops.

That is a Malthusian rainfall model. It is not Bronze Age agriculture and it is
not the Bronze Age collapse.

## Three things wrong with it as agriculture

**No fallow.** Near Eastern dry farming was biennial: half the land rests each
year, for weed control and for the soil moisture the next crop is grown on.
`gen_detail.py` sows the whole extent every year forever. Real land requirement
is roughly double what is authored, and fallow is exactly why working more
ground was not available to anybody as an answer to poor land -- which is the
assumption the `ARABLE_CEILING` table exists to patch after the fact.
Very important: fuck fallow, fallow isn't important because we're not simulating literally everything
**No specialists that matter.** Cohorts divide into `field_labour`, `craft` and
`palace`, and the last two eat the same ration while producing nothing the rest
of the system depends on. A palatial economy is one that feeds people who do
not farm, in return for administering the surplus. Here they are mouths with a
label.

**No demography.** Hunger kills and nothing recovers. A good decade should put
people back (there will be no good decade) demography should be modeled as cohorts are a whole really easily

## What is wrong with it as the collapse

The palatial economies of the thirteenth century were not subsistence systems.
They were surplus, centralised, and coupled hard to each other. Ugarit ate
Egyptian and Mycenaean grain. But over the last 50 years, droughts dry seasons, 
land over extraction resulted in lowering and lowering yields (potentially loss of bronze lowered yields as well)
overall this meant that the farms couldn't support the cities.

the famine is not however the only executioner. 

Flattening every region to subsistence -- which is what the extent division and
the arable ceilings do -- deletes the surplus concentration whose failure is the
whole story. A game whose spec is about information, delay, and interested
intermediaries should collapse through its network, not through a climate index.

## What a historical model would need

2. Surplus concentration restored: palaces hold large stores and specialists
   depend on them completely.

3. Real specialisation -- Alashiya copper, Aegean oil and wine, Egyptian grain
   -- so that exchange is load-bearing rather than an optimisation.

4. Collapse as cascade: a route closing or a palace burning starves its
   dependents even with grain in a granary a week away.

5. Drought as trigger, not only cause.

It is not necessary to simulate every fine detail to simulate the model.