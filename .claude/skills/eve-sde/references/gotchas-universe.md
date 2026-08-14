# Gotchas: the universe

For the `universe` and `moons` parts. Read before answering anything of the
form "how many systems...", "which system is the most/least...", "how do I get
from A to B", or any question about planets, moons, stars, security or wormhole
system effects.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs. **Every count here is population-sensitive** -- `published = 1` vs all
types, k-space vs all systems, ships vs all categories. Where the population is
not stated it is the whole table; if your query filters differently, re-derive
rather than quoting.

- **`universe.sovereigntyUpgrades` has two power columns pointing opposite
  ways.** `power_allocation` is consumption, `power_production` is output, and
  **no row sets both** -- 44 of the 49 rows allocate, 4 produce and 1 does
  neither (`workforce_*` splits identically). So a budget is
  `SUM(power_production) - SUM(power_allocation)`; summing one column alone, or
  reading `power_allocation` as "power" generally, silently drops the producers.
  14 of 49 rows carry `fuel` (`{hourly_upkeep, startup_cost, type_id}`, Magmatic
  Gas or Superionic Ice); the other 35 are NULL meaning *free*, not unknown.
  Five rows are unpublished placeholder/QA junk, and one of them -- QA Colony
  Resources Management Enhancer, at 9,000 power and 90,000 workforce -- is a
  *producer*, so it is one of only four and will wreck any max or mean taken
  over that side. Filter on `types.published = 1` -- but note the reverse trap
  too: **`Deprecated Cynosural Navigation` (typeID 2008) and `Deprecated
  Cynosural Suppression` (2001) are `published = 1` types with no
  `sovereigntyUpgrades` row**, so a *name*-based lookup ("the cyno nav
  upgrade") can land on a dead legacy type. Start from
  `sovereigntyUpgrades._key` and join to `types`, never the other way. `mutually_exclusive_group` is
  free text (`Mining_A`, `PvE_C`, `Infrastructure_3`) with no lookup table.
- **`universe.planetResources` is Equinox sovereignty, not planetary industry.**
  It holds `power` / `workforce` / `reagent` for the 2,712 sov-claimable nullsec
  systems. **`_key` is a mixed ID space**: 23,086 rows are `planets.planetID`
  and 2,712 are `mapStars._key` (the star is the power source, 500-1,000 each),
  with no column distinguishing them -- joining only to `planets` silently drops
  every star. NPC nullsec, Pochven and the three unused regions have no rows.
- **Star spectral class is in `mapStars.statistics`, not the type name.** The
  944 stars named `Sun O1 (Bright Blue)`, `Sun B0 (Blue)`, `Sun B5 (White
  Dwarf)` and `Sun A0 (Blue Small)` are all **F-class** in the statistics JSON.
  EVE has no O or B stars at all -- only A, F, G, K and M. The type name is an
  art asset label, so "how many blue giants" answered from `types.name` is
  confidently wrong.
- **A wormhole effect's "resistance bonus" reduces your resists.** The beacon
  behind `mapSecondarySuns.effectBeaconTypeID` carries
  `shieldEmDamageResistanceBonus = 50` with `highIsGood = 1` and `unitID = 105`
  (a plain percent) -- every signal says "+50% resist". But effects 4135-4138
  apply it with `operation 6` (postPercent) onto attributes 271-274, which are
  **inverted resonances**: resonance x 1.5, so a 50% shield resist becomes 25%.
  A Class 6 Wolf-Rayet is the well-known **-50% shield resists**, not +50%.

  **That 50 is one beacon's value, not the attribute's.** Among the 36 beacons
  `mapSecondarySuns` actually references, the shield bonus is carried only by
  the six Wolf-Rayet beacons and scales by class --
  **15 / 22 / 29 / 36 / 43 / 50** for C1-C6 -- so a C3 hole is -29%, not -50%.
  The armor equivalent is on the six Pulsars, scaling identically -- **and it is
  the same penalty, not a buff**: a C3 Pulsar is **-29% to all four armor
  resists**, despite the attribute reading `armor*DamageResistanceBonus = 29`.
  Do not let "armor equivalent" read as "armor bonus" -- Pulsars help your
  shield pool and hurt your armor resists. **24 of the 36 beacons carry no
  resistance bonus at all** (other effect beacons outside those 36 -- incursions, Metaliminal storms
  -- carry their own). Read the magnitude off the beacon you actually have.
  `signatureRadiusMultiplier` scales by class too, in both directions:
  **0.85 / 0.78 / 0.71 / 0.64 / 0.57 / 0.50** for C1-C6 Wolf-Rayet and
  **1.30 / 1.44 / 1.58 / 1.72 / 1.86 / 2.00** for the Pulsars. So a C6
  Wolf-Rayet halves your signature and a C1 only trims 15%, while a C6 Pulsar
  doubles it -- `highIsGood = 1` on an attribute where the good direction
  depends on which effect you are in. Note this one is `unitID 109` writing onto
  `signatureRadius`, so it is *not* an instance of the inversion rule above --
  it is a plain multiplier whose flag lies about direction. Whenever an effect writes onto a
  `unitID = 108` attribute, read the sign through the inversion, not off
  `highIsGood`.

  **Two beacon attributes whose names invite over-broad glosses** -- three
  graded sessions made both mistakes: `rechargeRateMultiplier` writes
  `rechargeRate` (attribute 55), which is **capacitor** recharge time only --
  shield recharge is attribute 479 and the wormhole beacons do not touch it, so
  do not say "shield/cap recharge". And `energyWarfareStrengthMultiplier` is
  **NOS and neutralizer drain amount only** -- not damps, ECM, webs or scrams,
  so do not gloss it as "e-war strength".
- **`universe.systemWideEffects` is not the wormhole effect**, despite keying on
  the same beacon typeID. Its `dbuffs` are Sisters-of-EVE event bonuses scoped
  to a single ship, and those `_key`s are **`misc.dbuffCollections` IDs, not
  attributeIDs** -- 229 of the 276 keys in `dbuffCollections` collide with a real attributeID (83%)
  -- and of the 55 keys `systemWideEffects` actually references, **55 of 55
  collide**, so not one join fails loudly to expose the bug. A join to
  `dogma_attributes` succeeds and returns nonsense. Use `mapSecondarySuns` ->
  `items.type_dogma` on the beacon type instead.
- **Wormhole class is on the constellation and region, not the system.**
  Only **5 of 2,604** wormhole systems carry a system-level `wormholeClassID`,
  and those five are Drifter hives whose system class (14-18) *contradicts*
  their constellation's class of 1. A further 687 k-space systems carry class 8,
  which is unrelated to J-space -- so filtering `wormholeClassID IS NOT NULL`
  gets you mostly k-space. Join upward or a C2 hole reads as "unknown":

  ```sql
  SELECT s.name, COALESCE(s.wormholeClassID, c.wormholeClassID, r.wormholeClassID) AS class
  FROM systems s
  JOIN constellations c ON c.constellationID = s.constellationID
  JOIN regions r       ON r.regionID = s.regionID
  WHERE s.space = 'wormhole'       -- REQUIRED
    AND s.name = 'J124611';        -- class 2
  ```

  **The `space` filter is not optional.** k-space constellations carry classes
  7 (1,880 systems), 9 (3,188), 10 (6), 11 (7) and 25 (Pochven's 27), so without it the same query answers
  "Jita is class 7" and "1DQ1-A is class 9". Class 8 never appears on a
  constellation at all -- it is system-level only, on 687 k-space systems.
  Classes 1-6 are the familiar
  wormhole classes, 12 is Thera, 13 shattered/frigate holes, 14-18 Drifter,
  19-25 abyssal/void/Pochven.
- **`security` alone cannot identify nullsec.** Wormhole, abyssal and void
  systems all carry `security = -0.99`, so `WHERE security <= 0` sweeps in 3,004
  systems that are not nullsec. Filter `space = 'kspace'` first. Counts in known
  space (5,485 total): 1,246 high, 687 low, 3,552 null -- but that "high" figure
  includes Exordium's 53 systems at security 1.0; the legacy figure older
  sources quote is **1,193**. Give **1,246** and name the Exordium caveat --
  see "Highest security" below for why it is real content, not an artefact.
- **`>= 0.5` instead of `>= 0.45` fails silently on routing.** A high-sec-only
  Jita-to-Amarr route is 34 jumps at the correct threshold and 39 at the wrong
  one -- a plausible answer either way, with no error to notice.

- **`systems.security` is unrounded.** Jita is 0.9459, shown in-game as 0.9.
  High-sec is `security >= 0.45` (which rounds to 0.5), not `>= 0.5`.

- **Use `stargates.destSystemID`**, not `destStargateID`. The latter is the peer
  *gate*; joining it against `solarSystemID` returns zero rows.

- **1,364 moons have NULL `surfaceGravity`** (and NULL `density`), all
  `typeID = 14`. `ORDER BY surfaceGravity DESC` is safe -- SQLite sorts NULL
  smallest -- but `ASC` puts 1,364 NULLs at the top of a "lowest gravity"
  query, and `AVG()` silently skips them.

- **Faction ownership: `systems.factionID` is 99.2% NULL** -- only 70 of 8,490
  systems carry it, because ownership inherits upward exactly like wormhole
  class does: 386 of 1,184 constellations and 33 of 114 regions have it.
  Querying the system column alone answers "which faction holds the most
  systems?" with *CONCORD Assembly, 26*. The real answer is **Amarr Empire,
  706** (then Caldari 422, Gallente 390, Minmatar 285). This is static NPC
  empire ownership -- live nullsec sovereignty and faction-warfare front lines
  are ESI, not the SDE -- but the NPC map itself is right here; do not refuse
  the question as "live data". Needs `world` attached for the faction names:

  ```sql
  SELECT f.name, COUNT(*) FROM systems s
  JOIN constellations c ON c.constellationID = s.constellationID
  JOIN regions        r ON r.regionID = s.regionID
  JOIN world.factions f ON f.factionID = COALESCE(s.factionID, c.factionID, r.factionID)
  WHERE s.space = 'kspace' GROUP BY 1 ORDER BY 2 DESC;
  ```

**Geography -- counting systems, and what "unreachable" means:**

- **`planets.moons` and `planets.belts` are denormalised counts, and they are
  exact** -- 0 mismatches against the moon rows across the 46,618 k-space
  planets. Counting moons therefore needs `universe` alone, not the `moons`
  part. Note 46,618 is the k-space figure; there are **68,407** planets in
  total, the other **21,789** all in wormhole space -- abyssal and void systems have no
  planets at all.
- **`moons` says nothing about what is in a moon either.** 344,456 of the
  344,457 rows carry `typeID = 14` (the lone exception is Jita IV - Moon 4), and
  no table anywhere links a moon to its ore. The 23 columns are physical stats
  only. Ranking moons by `surfaceGravity` or `radius` produces a fluent,
  well-sourced and completely useless answer to "which moon should we mine" --
  moon composition comes from an in-game survey, not the SDE.
- **Abyssal and insurgency weather live in `misc.appliedProximityEffects`, and
  the SDE has only some of it.** The rows are group **`Cloud`** -- the group
  actually named `Abyssal Hazards` holds Proving Ground beacons, not weather.
  Each abyssal weather is one **penalty that rolls** with a **fixed bonus that
  does not**: the penalty is -30/-50/-70%, rolled by tier (**30 or 50 through
  tier 3, 50 or 70 at tier 4+** -- the roll is not in the SDE, so these numbers
  are the only source), while the paired bonus stays the same at every
  strength. Per weather, read off the present rows' `dbuffs` ->
  `dbuffCollections.itemModifiers`:

  | Weather | Penalty (all three layers) | Fixed bonus | rows present |
  | --- | --- | --- | --- |
  | Electric | EM resist | capacitor recharge | 3 -- all strengths, but the suffixes are not in order: base = **50**, `2` = **30**, `3` = **70** |
  | Exotic | Kinetic resist | +50% scan resolution | 1 (30 only) |
  | Firestorm | Thermal resist | +50% armor HP | 1 (70 only) |
  | Gamma | Explosive resist | +50% shield HP | 1 (50 only) |
  | Dark | turret optimal + falloff | velocity | **0 abyssal rows** -- but the pair *is* derivable: the `[HF]` Dark rows use the same dbuffs (97: `maxRange`+`falloff` penalty, 98: `maxVelocity` bonus). Only the abyssal -30/-50/-70 strengths are missing |

  **Answer any tier question with the roll, not the row** -- "a Tier 4
  <weather> rolls **-50% or -70%** <its resist>; the SDE carries only the <n>
  row". Leading with a lone row's value as "the" penalty is the most-repeated
  mistake sessions make with this table, and it reads as authoritative
  precisely because the row is real. Two sign traps in the modifiers: a
  resistance *penalty* is stored **positive** (postPercent onto an inverted
  resonance), and Electric's capacitor bonus is stored as **-50 on
  `rechargeRate`**, because a shorter recharge time is better -- read the
  attribute, not the sign, in both directions. The penalty writes all three
  layers (hull, armor, shield resonances). Separately, the 15
  **`[HF] Weather Effect - *`** rows are a different, non-abyssal system at
  -10/-20/-30% with a +20% bonus -- do not mix them in.
- **`asteroid_belts` says nothing about what is in a belt either.** All 40,928
  rows carry `typeID = 15`. Same shape as moons: the column exists and never
  varies, so composition is game knowledge, not data.
- **Not every high-sec system has belts, and Exordium has none.** 1,179 of the
  1,246 high-sec systems have at least one, but the 53-system Exordium region
  contains **zero** -- so the highest-security region in the game is the wrong
  answer to "where should I mine".
- **Zarzakh has no planets at all** -- the only k-space system without any. A
  count taken through `systems JOIN planets` therefore reports 3,551 nullsec
  systems instead of 3,552. Count from `systems` directly.
- **3,222 systems have no stargates**: 2,604 wormhole + 200 abyssal + 200 void
  + 217 k-space + GPMS-01. The gate graph is disconnected -- routing between
  components is impossible, so a BFS must handle "no path" rather than hang or
  error.
- **"Highest security" has no clean answer -- it is ties all the way down.**
  53 k-space systems in **Exordium** sit at exactly `1.0` (real, flyable
  new-player content, one gate to Yulai), so `ORDER BY security DESC LIMIT 5`
  returns an arbitrary five of a 53-way tie. Outside Exordium the top is Tew
  (0.949794) then Eystur (0.949232), and then **another 53 systems across 13
  regions** at exactly `0.949`. Report ties as ties. More generally: this
  dataset is full of exact ties -- resists, moon radii, security -- so check for
  them before presenting any `LIMIT n` as a ranking.
- **Three counting traps compound, and all inflate nullsec.** The three unused
  regions `UUA-F4` (107), `J7HZ-F` (77) and `A821-A` (46) are `kspace` with
  ordinary nullsec security -- 230 systems nobody can reach, so nullsec is 3,552
  with them and **3,322** without. **Pochven**'s 27 systems are also `kspace`, at
  security exactly -1.0, and land in nullsec aggregates unless excluded; they
  have 60 internal gates and **zero** external ones (Niarja is inside, which is
  why the old Jita-Amarr high-sec route is gone). And `space` has **five**
  values, not four -- `kspace`, `wormhole`, `abyssal`, `void` and `other`
  (GPMS-01 alone), so `space != 'kspace'` quietly includes the dev system.
- **"Unreachable" has three meanings -- do not conflate them.** 3,222 systems
  have no stargates; 3,262 are gate-unreachable from Jita; only **231** are
  unreachable by any means. Wormhole, abyssal, void and Pochven are
  gate-unreachable yet entirely flyable. Answering "can I fly there?" with 3,262
  is badly wrong.
- **Every stargate appears as two rows**, one per direction -- 100% symmetric,
  no one-way edges -- so a directed adjacency list is safe here, though not
  something to assume in general.
- **`security` has mixed storage classes**: 121 INTEGER rows (the clamped ±1),
  8,369 REAL. Comparisons are unaffected; `typeof()` and JSON export are not.

## Routing

`stargates` is a graph: `solarSystemID -> destSystemID`. For shortest jump
routes, load the edges and run a breadth-first search in Python rather than
attempting it in SQL.

```python
import sqlite3, collections
db = sqlite3.connect("sde.sqlite")
adj = collections.defaultdict(list)
for a, b in db.execute("SELECT solarSystemID, destSystemID FROM stargates"):
    adj[a].append(b)
```

Filter the edge list by `systems.security` for high-sec-only routing. The graph
is **disconnected** -- 3,222 systems have no gates at all -- so always handle the
"no path exists" case rather than assuming a route can be found.

## Rare

Accurate, verified, and almost never load-bearing -- read only if the question
touches them directly.

- Region `19000001` (GPMR-01) is a dev region; its one system **GPMS-01** has
  `security = 1.0` and `space = 'other'`, so a `space = 'kspace'` filter
  excludes it -- but that filter does **not** save you from the Exordium tie.
- **GPMS-01 sits at `(1, 1, 1)`**, one metre from the origin, so any
  nearest-neighbour query that does not exclude `space = 'other'` finds it
  closest to everything near the map's centre.
