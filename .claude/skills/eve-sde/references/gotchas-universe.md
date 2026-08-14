# Gotchas: the universe

For the `universe` and `moons` parts. Read before answering anything of the
form "how many systems...", "which system is the most/least...", "how do I get
from A to B", or any question about planets, moons, stars, security or wormhole
system effects.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs.

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
  `signatureRadiusMultiplier = 0.5` is the same shape -- `highIsGood = 1` on a
  value where lower is the good direction. Whenever an effect writes onto a
  `unitID = 108` attribute, read the sign through the inversion, not off
  `highIsGood`.
- **`universe.systemWideEffects` is not the wormhole effect**, despite keying on
  the same beacon typeID. Its `dbuffs` are Sisters-of-EVE event bonuses scoped
  to a single ship, and those `_key`s are **`misc.dbuffCollections` IDs, not
  attributeIDs** -- 229 of 276 dbuff keys collide with a real attributeID (83%), so a join to
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

**Geography -- counting systems, and what "unreachable" means:**

- **`planets.moons` and `planets.belts` are denormalised counts, and they are
  exact** -- 0 mismatches against the moon rows across the 46,618 k-space
  planets. Counting moons therefore needs `universe` alone, not the `moons`
  part. Note 46,618 is the k-space figure; there are **68,407** planets in
  total, the other **21,789** all in wormhole space -- abyssal and void systems have no
  planets at all.
- **Zarzakh has no planets at all** -- the only k-space system without any. A
  count taken through `systems JOIN planets` therefore reports 3,551 nullsec
  systems instead of 3,552. Count from `systems` directly.
- **3,222 systems have no stargates**: 2,604 wormhole + 200 abyssal + 200 void
  + 217 k-space + GPMS-01. The gate graph is disconnected -- routing between
  components is impossible, so a BFS must handle "no path" rather than hang or
  error.
- **"Highest security" has no clean answer.** 53 real k-space systems in the
  region **Exordium** sit at security exactly `1.0`. It is real, flyable
  new-player content -- 53 NPC stations, 13 of them AIR-branded, a single
  gate to Yulai, 12 jumps from Jita -- so 1,246 is the correct current figure
  and 1,193 is the legacy one every older source quotes. `ORDER BY security DESC
  LIMIT 5` therefore returns an arbitrary five of a 53-way tie. Outside
  Exordium the top is Tew (0.949794) and Eystur (0.949232), and then a second
  tie: **53 systems across 13 regions** sit at exactly `0.949` -- not the
  handful in The Forge that the first page of results suggests. Say the tie
  exists rather than presenting five rows as a ranking.
- Region `19000001` (GPMR-01) is a dev region; its one system GPMS-01 also has
  `security = 1.0`. It carries `space = 'other'`, so a `space = 'kspace'` filter
  excludes it -- but that filter does **not** save you from the Exordium tie.
- **Three unused regions are `space = 'kspace'` with ordinary nullsec security**
  and inflate every nullsec count: `UUA-F4` (107 systems), `J7HZ-F` (77) and
  `A821-A` (46) -- 230 in all. Two have no stargates and the third forms an
  island unreachable from Jita. "How many nullsec systems does EVE have" is
  3,552 with them and **3,322** without.
- **"Unreachable" has three different meanings -- do not conflate them.**
  3,222 systems have no stargates; 3,262 are gate-unreachable from Jita; but
  only **231** are unreachable by any means at all. Wormhole (2,604), abyssal
  (200), void (200) and Pochven (27) are gate-unreachable yet entirely flyable
  by wormholes or filaments. The genuinely dead ones are the 230 systems in
  `UUA-F4`/`J7HZ-F`/`A821-A` plus GPMS-01. Answering a player's "can I fly
  there?" with 3,262 is badly wrong.
- **Every stargate appears as two rows**, one per direction -- verified 100%
  symmetric with no one-way edges. A directed adjacency list is therefore safe,
  but do not assume it for a hand-built graph.
- **`space` has five values**, not four: `kspace`, `wormhole`, `abyssal`, `void`
  and `other` (GPMS-01 alone). `WHERE space != 'kspace'` to mean "j-space and
  friends" quietly includes the dev system.
- **`security` has mixed storage classes.** 121 rows are INTEGER (the clamped
  `1` and `-1` values), 8,369 are REAL. Comparisons are unaffected, but
  `typeof()`, string formatting and JSON export will show `1` rather than `1.0`.
- **GPMS-01 sits at coordinates `(1, 1, 1)`** -- one metre from the origin. Any
  nearest-neighbour query that does not exclude `space = 'other'` finds it
  closest to everything near the centre of the map.
- **Pochven is sealed.** Its 27 systems have 60 internal stargates and **zero**
  to anywhere else -- filament access only. Niarja is now inside it, which is
  why the old short Jita-Amarr high-sec route no longer exists. Pochven systems
  are `space = 'kspace'` with security exactly -1.0, so they land in nullsec
  aggregates unless excluded.

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
