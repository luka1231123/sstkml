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

**No specialists that matter.** Cohorts divide into `field_labour`, `craft` and
`palace`, and the last two eat the same ration while producing nothing the rest
of the system depends on. A palatial economy is one that feeds people who do
not farm, in return for administering the surplus. Here they are mouths with a
label.

**No demography.** Hunger kills and nothing recovers. A good decade should put
people back.

## What is wrong with it as the collapse

The palatial economies of the thirteenth century were not subsistence systems.
They were high surplus, centralised, and coupled hard to each other. Ugarit ate
Egyptian and Mycenaean grain. Hatti asked for it in the terms of RS 20.212 --
"it is a matter of life or death". Tin came two thousand kilometres overland
from beyond Mesopotamia and there was no western source.

That concentration and that coupling are what failed. Sea lanes were cut,
palaces burned, and the administrative capacity to redistribute burned with
them: the scribes, the records, the stores, the standing arrangements about who
owed what to whom. Fields went on producing in places where people starved,
because the mechanism that moved grain had stopped existing. The 3.2ka drought
is real, it is in the pollen cores, and it was the stressor that pushed a
tightly coupled system past its tolerance. It was not the executioner.

Flattening every region to subsistence -- which is what the extent division and
the arable ceilings do -- deletes the surplus concentration whose failure is the
whole story. A game whose spec is about information, delay, and interested
intermediaries should collapse through its network, not through a climate index.

## What a historical model would need

1. Fallow, so land is genuinely scarce and the ceilings are unnecessary.
2. Surplus concentration restored: palaces hold large stores and specialists
   depend on them completely.
3. Real specialisation -- Alashiya copper, Aegean oil and wine, Egyptian grain
   -- so that exchange is load-bearing rather than an optimisation.
4. Collapse as cascade: a route closing or a palace burning starves its
   dependents even with grain in a granary a week away.
5. Drought as trigger, not as cause.

Item 3 also settles a scale question left open elsewhere. `carry.LINE_CARGO` is
4,000 qa, negligible against a world that eats on the order of 95,000,000 qa a
fortnight, and that looked like a calibration error left over from the retired
560-person world. Historically these shipments were small *and* decisive,
because they went to places with no fallback. Under a model with real
specialisation the number can stay small and still decide who lives.

## The honest status of the current numbers

`EXTENT_PER_HEAD`, its division by regional yield, and `ARABLE_CEILING` were
put in to fix a real defect: a flat extent per head against yields spanning
0.65 to 1.60 sent Anatolia and the Aegean to a hundredth of their opening
stores in five years with no bad harvest anywhere, which was a generator
artefact and not a claim about the plateau. They fix that. They are tuning, in
the wrong direction, and they should be reverted rather than built on when
somebody takes the list above seriously.
