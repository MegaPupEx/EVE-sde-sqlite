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

If `sde.sqlite` is not already present, build it:

```bash
python3 build_sde_db.py          # ~16s, stdlib only, writes ./sde.sqlite (~89 MB)
```

The script reads CCP's `latest.jsonl` at runtime, so it always fetches the
current build. Needs network access to `developers.eveonline.com`.

If that host is blocked, use Fuzzwork's prebuilt dump instead — same data,
different schema (classic `invTypes` / `mapSolarSystems` naming, not the schema
below):

```bash
curl -sO https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz && gunzip latest-sqlite.db.gz
```

Check which build a database came from:

```sql
SELECT * FROM meta;   -- sdeBuildNumber, sdeReleaseDate, builtAt, source
```

### When the sandbox has no network

Some environments (notably the Claude apps code sandbox) cannot reach CCP to
download anything. In that case the database must be **uploaded to the
conversation** rather than built. Look for an attached `.sqlite` or
`.sqlite.gz` before assuming a build is possible:

```python
import gzip, shutil, sqlite3, pathlib
src = pathlib.Path("eve-sde-portable.sqlite.gz")      # adjust to the upload path
if src.exists():
    with gzip.open(src) as f, open("sde.sqlite", "wb") as o:
        shutil.copyfileobj(f, o)
db = sqlite3.connect("sde.sqlite")
```

Produce that upload file with:

```bash
python3 build_sde_db.py --db eve-sde-portable.sqlite --portable --gzip   # 13 MB
```

A portable database has `meta.portable = '1'` and omits three things: item
description text, unpublished types, and the `moons` table. So on a portable
database, do **not** filter on `published` (everything present is published),
do not promise moon data, and do not quote item descriptions. Everything else
-- dogma attributes, blueprints, reprocessing, systems, planets, stargates,
stations -- is complete.

Check before answering:

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
| `systems` | `solarSystemID`, `name`, `regionID`, `constellationID`, `security`, `securityClass` |
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
and survives schema drift.

## Gotchas

These cause silently wrong answers, so check them before trusting a result:

- **Filter `published = 1`.** Only 26,992 of 52,848 types are published; the
  rest are test items, unreleased content, and dev leftovers that will pollute
  aggregates and name searches.
- **`portionSize` governs reprocessing.** `type_materials` quantities are per
  `portionSize` units, not per unit. Veldspar yields 400 Tritanium per **100**
  units. Divide by `portionSize` for per-unit figures.
- **`systems.security` is unrounded.** Jita is 0.9459, displayed in-game as 0.9.
  High-sec is `security >= 0.45` (which rounds to 0.5), not `>= 0.5`.
- **Use `stargates.destSystemID`**, not `destStargateID`. The latter is the peer
  *gate*; joining it against `solarSystemID` silently returns zero rows.
- **`planets.celestialIndex`** is the in-game roman numeral — planet II is
  `celestialIndex = 2`. `planetID` is unrelated to ordering.
- **Blueprint lookups start from the product**, not the blueprint name. Join
  `bp_products` to find which blueprint makes a thing.
- **`groups_` has a trailing underscore** (`group` is reserved in SQL).
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

-- every system in a region, by security band
SELECT s.name, s.security,
       CASE WHEN s.security >= 0.45 THEN 'high'
            WHEN s.security >  0.0  THEN 'low'
            ELSE 'null' END AS band
FROM systems s
JOIN regions r ON r.regionID = s.regionID
WHERE r.name = 'Insmother'
ORDER BY s.security DESC;
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

Filter the edge list by `systems.security` first for high-sec-only routing.
