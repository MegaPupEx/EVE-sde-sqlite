---
name: eve-sde
description: Query the EVE Online Static Data Export (SDE) - ships, modules, dogma attributes, blueprints and manufacturing, reprocessing yields, and the New Eden universe (regions, systems, planets, moons, stargates, stations). Use whenever a question involves EVE Online game data such as ship stats, fitting attributes, build materials, ore yields, system security, planet or moon data, jump routes, market groups, or type/group/category lookups. Covers building the local SQLite database and querying it with SQL.
---

# EVE Online SDE

The SDE is CCP's static game-data export: everything in EVE that isn't live
player state. This skill covers getting it into SQLite and querying it.

**Not in the SDE:** market prices, kills, sovereignty, character or corp data.
Those are live data — use ESI (`https://esi.evetech.net`) instead.

## Get a database

Work down this list and stop at the first that succeeds. Environments differ in
what they can reach, so do not assume any one of them works.

**1. Already present.** If `sde.sqlite` exists, use it. Check it is current:

```sql
SELECT * FROM meta;   -- sdeBuildNumber, sdeReleaseDate, builtAt, source
```

**2. Uploaded to the conversation.** See "When the sandbox has no network"
below. This is the only option in a sandbox with no outbound access, and it
costs nothing to check first.

**3. Prebuilt release** — fastest when reachable, already integrity checked, no
build step. Releases carry the SDE **split by domain**. Fetch only the parts the question
needs -- most questions need one or two:

```bash
BASE=https://github.com/MegaPupEx/eve-sde-sqlite/releases/latest/download
curl -sSLo universe.xz $BASE/eve-sde-universe.sqlite.xz && xz -d universe.xz  # ~28 MB
curl -sSLo items.xz    $BASE/eve-sde-items.sqlite.xz    && xz -d items.xz     # ~7 MB
```

| Part | Size | Covers |
| --- | --- | --- |
| `universe` | ~8 MB | systems, planets, belts, stargates, stations, 3D coordinates |
| `moons` | ~20 MB | all 344k moons with physical statistics |
| `items` | ~7 MB | types, dogma attributes and effects, reprocessing, market groups |
| `world` | ~1.4 MB | missions, dungeons, agents, corporations, certificates |
| `industry` | ~0.5 MB | blueprints, schematics, assembly lines |
| `cosmetic` | ~0.4 MB | skins, graphics, icons |
| `misc` | ~0.01 MB | the remainder |

**`moons` is a separate part from `universe`.** A moon question needs both --
`moons` for the moon rows, `universe` to resolve which system or planet they
orbit. Fetching only `universe` gives no `moons` table at all, which reads as
"this system has no moons" if you do not notice.

There is no single combined download: one file only fits the 30 MB upload limit
by dropping 3D coordinates, so the parts are the published form. ATTACH whatever
you fetched (see "Split databases" below) and query across them normally.

The `latest` in that URL always resolves to the newest release; a workflow
republishes within hours of each CCP build. The repository is public, so no
authentication is needed. If a fetch still fails, treat it as "cannot reach it,
move on" and fall through to building -- GitHub answers 404 rather than 403 for
anything it will not serve, so a failure here never proves the release is gone.

**4. Build from CCP** — authoritative, ~20 s, downloads ~99 MB. Needs
`developers.eveonline.com`:

```bash
python3 build_sde_db.py --complete   # stdlib only, ~147 MB, all 107 tables
```

**5. Fuzzwork's prebuilt dump** — last resort. Same data, but a **different
schema** (classic `invTypes` / `mapSolarSystems` naming), so none of the table
and column names below apply:

```bash
curl -sO https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz && gunzip latest-sqlite.db.gz
```

### When the sandbox has no network

Some environments (notably the Claude apps code sandbox) cannot reach CCP to
download anything. In that case the database must be **uploaded to the
conversation** rather than built. Look for an attached `.sqlite` or
`.sqlite.gz` before assuming a build is possible:

```python
import gzip, lzma, bz2, shutil, sqlite3, pathlib

OPENERS = {".xz": lzma.open, ".gz": gzip.open, ".bz2": bz2.open}
for src in pathlib.Path(".").glob("*.sqlite*"):        # adjust to the upload path
    if src.suffix in OPENERS:
        with OPENERS[src.suffix](src) as f, open("sde.sqlite", "wb") as o:
            shutil.copyfileobj(f, o)
        break
    if src.suffix == ".sqlite":
        shutil.copy(src, "sde.sqlite")
        break
db = sqlite3.connect("sde.sqlite")
```

Produce upload files with:

```bash
python3 build_sde_db.py --complete --positions --split --parts-only --compress xz
```

Attach whichever parts the question needs. A single combined file is possible
with `--complete --compress xz` (~27 MB) but cannot carry coordinates.

### Split databases

A build may arrive split by domain: `-items`, `-universe`, `-industry`,
`-world`, `-cosmetic`, `-misc`. Each is a normal database; `meta.splitGroup`
names the part. ATTACH the ones you need and join across them normally:

```python
db = sqlite3.connect(":memory:")
for g in ("items", "universe"):
    db.execute(f"ATTACH DATABASE 'eve-sde-{g}.sqlite' AS {g}")
db.execute("SELECT t.name FROM universe.planets p JOIN items.types t ON t.typeID=p.typeID ...")
```

Only fetch the parts a question needs. Common pairings: planet or route
questions want `universe` alone; moon questions want `universe` + `moons`; ship
and module questions want `items`; build costs want `items` + `industry`.

**Use xz, not gzip** -- gzip does not get the data under the 30 MB per-file
limit on claude.ai; xz does, with room to spare per part.

Coordinates (`x`, `y`, `z` on systems, planets, moons, belts, stargates) are
present in the published parts, so distance questions are answerable. A build
made without `--positions` has them NULL -- check `meta.positions` before
promising a distance.

If a database *was* built with `--portable` it sets `meta.portable = '1'` and
omits item descriptions, unpublished types, and the `moons` table. On such a
database do **not** filter on `published` (everything present is published),
do not promise moon data, and do not quote descriptions. Check first, so
reduced coverage is never reported as fact:

```sql
SELECT value FROM meta WHERE key = 'portable';   -- '1' means slimmed
```

## Schema

Items and classification:

| Table | Key columns |
| --- | --- |
| `types` | `typeID`, `name`, `groupID`, `categoryID`, `mass`, `volume`, `capacity`, `basePrice`, `portionSize`, `published`, `metaLevel`, `techLevel` |
| `groups_` | `groupID`, `name`, `categoryID` (note the trailing underscore) |
| `categories` | `categoryID`, `name` |
| `market_groups` | `marketGroupID`, `parentGroupID`, `name` |
| `meta_groups` | `metaGroupID`, `name` (Tech I/II, Faction, Officer …) |

Attributes (all ship/module stats live here):

| Table | Key columns |
| --- | --- |
| `type_dogma` | `typeID`, `attributeID`, `value` |
| `dogma_attributes` | `attributeID`, `name`, `description`, `defaultValue`, `highIsGood` |
| `type_effects`, `dogma_effects` | `typeID`/`effectID`, `name` |

Industry:

| Table | Key columns |
| --- | --- |
| `blueprints` | `blueprintTypeID`, `maxProductionLimit` |
| `bp_activity` | `blueprintTypeID`, `activity`, `time` (seconds) |
| `bp_materials` | `blueprintTypeID`, `activity`, `typeID`, `quantity` |
| `bp_products` | `blueprintTypeID`, `activity`, `typeID`, `quantity`, `probability` |
| `bp_skills` | `blueprintTypeID`, `activity`, `typeID`, `level` |
| `type_materials` | `typeID`, `materialTypeID`, `quantity` (reprocessing yield) |

Universe:

| Table | Key columns |
| --- | --- |
| `regions` | `regionID`, `name` |
| `constellations` | `constellationID`, `name`, `regionID` |
| `systems` | `solarSystemID`, `name`, `regionID`, `constellationID`, `security`, `securityClass`, `space` (`kspace`/`wormhole`/`abyssal`/`void`) |
| `planets` | `planetID`, `solarSystemID`, `celestialIndex`, `typeID`, `radius`, `surfaceGravity`, `temperature`, `pressure`, `density`, `orbitRadius`, `orbitPeriod`, `eccentricity`, `moons`, `belts` |
| `moons` | `moonID`, `solarSystemID`, `planetID`, `orbitIndex`, `radius` |
| `asteroid_belts` | `beltID`, `solarSystemID`, `planetID` |
| `stargates` | `stargateID`, `solarSystemID`, `destSystemID`, `destStargateID` |
| `npc_stations` | `stationID`, `solarSystemID`, `ownerID`, `reprocessingEfficiency` |
| `factions`, `races` | `factionID`/`raceID`, `name` |

`activity` values: `manufacturing`, `copying`, `invention`,
`research_material`, `research_time`, `reaction`.

Useful category IDs: 6 Ship, 7 Module, 8 Charge, 9 Blueprint, 16 Skill,
17 Commodity, 18 Drone, 20 Implant, 25 Asteroid, 4 Material.

Common `attributeID`s: 9 hp (structure), 263 shieldCapacity, 265 armorHP,
37 maxVelocity, 48 cpuOutput, 11 powerOutput, 482 capacitorCapacity,
55 rechargeRate, 14 hiSlots, 13 medSlots, 12 lowSlots, 1137 rigSlots,
102 turretSlotsLeft, 101 launcherSlotsLeft, 552 signatureRadius,
564 scanResolution, 76 maxTargetRange, 283 droneCapacity, 1271 droneBandwidth,
70 agility, 600 warpSpeedMultiplier.

Prefer joining on `dogma_attributes.name` over hardcoding IDs — it is clearer
and survives schema drift. Two attribute names (`902`, `cynoJammerActivationDelay`)
are shared by two IDs each, so add `AND published = 1` or resolve to an ID when a
query must return exactly one row.

## Gotchas

These cause silently wrong answers -- plausible numbers, not errors -- so check
them before trusting a result. Verified against build 3466501.

**Wrong-answer traps (highest priority):**

- **Resonance is not resistance; it is inverted.** `armorEmDamageResonance =
  0.4` means **60% resist**, not 40%. Resist % is `(1 - value) * 100`. Every
  `*DamageResonance` attribute works this way.
- **Wormhole class is on the constellation and region, not the system.**
  `systems.wormholeClassID` is NULL for most of J-space -- only 692 of 2,604
  wormhole systems carry it, while 1,127 constellations and 108 regions do.
  Join upward or a C2 hole reads as "unknown":

  ```sql
  SELECT s.name, COALESCE(s.wormholeClassID, c.wormholeClassID, r.wormholeClassID) AS class
  FROM systems s
  JOIN constellations c ON c.constellationID = s.constellationID
  JOIN regions r       ON r.regionID = s.regionID
  WHERE s.name = 'J124611';        -- class 2
  ```

  Classes 1-6 are the familiar wormhole classes; 13 is shattered/frigate holes
  and 12 is Thera.
- **`security` alone cannot identify nullsec.** Wormhole, abyssal and void
  systems all carry `security = -0.99`, so `WHERE security <= 0` sweeps in 3,004
  systems that are not nullsec. Filter `space = 'kspace'` first. Counts in known
  space (5,485 total): 1,246 high, 687 low, 3,552 null.
- **Ship/module skill requirements are in dogma, not `bp_skills`.** They live in
  `requiredSkill1..6` (a typeID) paired with `requiredSkill1Level..6`.
  `bp_skills` is what a *blueprint activity* needs -- a different question.
  The Rifter needs `requiredSkill1 = 3329` (Minmatar Frigate) at level 1.
- **`basePrice` is not a market price** and is 0 or NULL for 17,652 of 26,992
  published types. It is an internal seed value. For real prices use ESI; the
  SDE has none.

**Filtering and units:**

- **Filter `published = 1`.** Only 26,992 of 52,863 types are published; the
  rest are test items, unreleased content and dev leftovers that pollute
  aggregates and name searches.
- **`portionSize` governs reprocessing.** `type_materials` quantities are per
  `portionSize` units, not per unit. Veldspar yields 400 Tritanium per **100**
  units. Divide by `portionSize` for per-unit figures.
- **`systems.security` is unrounded.** Jita is 0.9459, shown in-game as 0.9.
  High-sec is `security >= 0.45` (which rounds to 0.5), not `>= 0.5`.
- Blueprint `time` values are seconds.

**Joins that silently multiply or drop rows:**

- **Use `stargates.destSystemID`**, not `destStargateID`. The latter is the peer
  *gate*; joining it against `solarSystemID` returns zero rows.
- **Names are not unique.** 12 published type names, 6 group names and 2
  attribute names are shared by more than one ID. Joining on name can duplicate
  rows -- resolve to an ID first when a query must return exactly one thing.
- **4 products are made by more than one blueprint** ('Firewall' Signal
  Amplifier has 5). `bp_products -> blueprints` is not one-to-one.
- **Blueprint lookups start from the product**, not the blueprint name. Join
  `bp_products` to find which blueprint makes a thing.
- **`groups_` has a trailing underscore** (`group` is reserved in SQL).

**Coverage gaps -- absence is not evidence:**

- 18,915 published types have **no** `type_materials` row: not reprocessable,
  rather than reprocessing to nothing.
- 960 published types have `volume` NULL; `metaGroupID` and `techLevel` are
  populated for only ~26% and ~19% of types.
- **3,222 systems have no stargates** (all wormhole/abyssal/void, plus 217 in
  known space). The gate graph is disconnected -- routing between components is
  impossible, so a BFS must handle "no path" rather than hang or error.
- **21 blueprint rows reference typeIDs that do not exist** (20 products, 1
  material) -- removed content whose blueprints remain. This is upstream data,
  not a build error; use inner joins so they drop out.
- Region `19000001` (GPMR-01) is a dev region whose single system GPMS-01 has
  `security = 1.0`, above any real system. Exclude it from "highest security"
  style queries -- `space = 'kspace'` already does.
- Names are English-only; the builder discards other locales.

## Examples

```sql
-- ship fitting stats
SELECT a.name, d.value
FROM type_dogma d
JOIN dogma_attributes a ON a.attributeID = d.attributeID
JOIN types t ON t.typeID = d.typeID
WHERE t.name = 'Rifter'
  AND a.name IN ('hp','shieldCapacity','armorHP','maxVelocity',
                 'cpuOutput','powerOutput','hiSlots','medSlots','lowSlots');

-- what a blueprint consumes, found via its product
SELECT mt.name, m.quantity
FROM bp_materials m
JOIN types mt ON mt.typeID = m.typeID
JOIN bp_products p ON p.blueprintTypeID = m.blueprintTypeID
                  AND p.activity = m.activity
JOIN types t ON t.typeID = p.typeID
WHERE t.name = 'Rifter' AND m.activity = 'manufacturing'
ORDER BY m.quantity DESC;

-- reprocessing yield, normalised per unit
SELECT mt.name, m.quantity * 1.0 / t.portionSize AS per_unit
FROM type_materials m
JOIN types t  ON t.typeID = m.typeID
JOIN types mt ON mt.typeID = m.materialTypeID
WHERE t.name = 'Veldspar';

-- planets in a system with physical data
SELECT p.celestialIndex, ty.name, p.radius, p.surfaceGravity, p.temperature, p.moons
FROM planets p
JOIN systems s ON s.solarSystemID = p.solarSystemID
JOIN types  ty ON ty.typeID = p.typeID
WHERE s.name = 'TK-DLH'
ORDER BY p.celestialIndex;

-- gate neighbours
SELECT s2.name, s2.security, r.name AS region
FROM stargates g
JOIN systems s1 ON s1.solarSystemID = g.solarSystemID
JOIN systems s2 ON s2.solarSystemID = g.destSystemID
JOIN regions  r ON r.regionID = s2.regionID
WHERE s1.name = 'Jita';

-- all published ships in a group, with hull size
SELECT t.name, t.mass, t.volume
FROM types t
JOIN groups_ g ON g.groupID = t.groupID
WHERE g.name = 'Battleship' AND t.published = 1
ORDER BY t.name;

-- security bands across known space (note the space filter)
SELECT CASE WHEN security >= 0.45 THEN 'high'
            WHEN security >  0.0  THEN 'low'
            ELSE 'null' END AS band, COUNT(*)
FROM systems WHERE space = 'kspace'
GROUP BY band;

-- resistances, converting resonance to the percentage shown in game
SELECT a.name, ROUND((1 - d.value) * 100, 1) AS resist_pct
FROM type_dogma d
JOIN dogma_attributes a ON a.attributeID = d.attributeID
JOIN types t ON t.typeID = d.typeID
WHERE t.name = 'Rifter' AND a.name LIKE '%DamageResonance';

-- what skills a ship requires (dogma, not bp_skills)
SELECT sk.name, lvl.value AS level
FROM type_dogma req
JOIN dogma_attributes ra ON ra.attributeID = req.attributeID AND ra.name LIKE 'requiredSkill_'
JOIN types t   ON t.typeID = req.typeID
JOIN types sk  ON sk.typeID = CAST(req.value AS INT)
JOIN type_dogma lvl ON lvl.typeID = t.typeID
JOIN dogma_attributes la ON la.attributeID = lvl.attributeID
     AND la.name = ra.name || 'Level'
WHERE t.name = 'Rifter';
```

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
