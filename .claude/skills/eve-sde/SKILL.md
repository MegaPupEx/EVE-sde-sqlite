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
curl -sSLo universe.xz $BASE/eve-sde-universe.sqlite.xz && xz -d universe.xz  # ~8 MB
curl -sSLo items.xz    $BASE/eve-sde-items.sqlite.xz    && xz -d items.xz     # ~7 MB
```

| Part | Size | Covers |
| --- | --- | --- |
| `universe` | ~8 MB | systems, planets, belts, stargates, stations, 3D coordinates |
| `moons` | ~20 MB | all 344k moons with physical statistics |
| `items` | ~7 MB | types, dogma attributes and effects, reprocessing, market groups |
| `world` | ~1.4 MB | missions, dungeons, NPC agents and corporations, certificates, **factions**, **races** |
| `industry` | ~0.5 MB | blueprints, schematics, assembly lines |
| `cosmetic` | ~0.4 MB | skins, graphics, icons |
| `misc` | ~0.01 MB | the remainder |

**`moons` is a separate part from `universe`.** Which parts you need depends on
the question:

- **Counting moons** -- `universe` alone is enough. `planets.moons` and
  `planets.belts` are denormalised counts, verified exact against the moon rows
  (0 mismatches across the 46,618 k-space planets; 68,407 planets in total,
  the rest being wormhole/abyssal/void). "Which system has the most moons?"
  answers correctly from `universe` by itself.
- **Anything about a specific moon** -- gravity, radius, coordinates, orbit --
  needs `moons` too. Without it the query raises `no such table: moons`, so it
  fails loudly rather than answering wrongly.

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

A build may arrive split by domain: `-universe`, `-moons`, `-items`,
`-industry`, `-world`, `-cosmetic`, `-misc`. Each is a normal database; `meta.splitGroup`
names the part. ATTACH the ones you need and join across them normally:

```python
import os, sqlite3
db = sqlite3.connect(":memory:")
for g in ("items", "universe"):
    path = f"eve-sde-{g}.sqlite"
    assert os.path.exists(path), path      # see the warning below
    db.execute(f"ATTACH DATABASE '{path}' AS {g}")
db.execute("SELECT t.name FROM universe.planets p JOIN items.types t ON t.typeID=p.typeID ...")
```

**`ATTACH` on a missing file does not error -- it creates an empty database.**
The failure then surfaces as `no such table: items.types` on the next query,
which points at the schema when the real fault is the filename. Check the path
exists first, or a typo costs you a long detour.

Download with `curl -O` rather than `-o name.xz`: `xz -d` on a file called
`universe.xz` yields `universe`, and every example here expects
`eve-sde-universe.sqlite`.

Only fetch the parts a question needs. Common pairings: planet or route
questions want `universe` alone; moon questions want `universe` + `moons`; ship
and module questions want `items`; build costs want `items` + `industry`.

**Use xz, not gzip** -- gzip does not get the data under the 30 MB per-file
limit on claude.ai; xz does, with room to spare per part.

Coordinates (`x`, `y`, `z` on systems, planets, moons, belts, stargates) are
present in the published parts, so distance questions are answerable. They are
in **metres**; divide by `9.4607304725808e15` for light years. Raw metres are
meaningless to a player. A build
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
| `types` | `typeID`, `name`, `groupID`, `categoryID`, `mass`, `volume` (assembled), `packagedVolume` (what it takes up in a hold), `capacity` (its own cargo space), `basePrice`, `portionSize`, `published`, `metaLevel`, `techLevel`, `metaGroupID`, `raceID`, `factionID` |
| `groups_` | `groupID`, `name`, `categoryID` (note the trailing underscore) |
| `categories` | `categoryID`, `name` |
| `market_groups` | `marketGroupID`, `parentGroupID`, `name` |
| `meta_groups` | `metaGroupID`, `name` (Tech I/II, Faction, Officer …) |

Attributes (all ship/module stats live here):

| Table | Key columns |
| --- | --- |
| `type_dogma` | `typeID`, `attributeID`, `value` |
| `dogma_attributes` | `attributeID`, `name`, `displayName`, `description`, `defaultValue` (**use it -- a missing `type_dogma` row means "default", not "no value"**), `highIsGood` (unreliable), `stackable`, `published`, `unitID` (**decides what the number means -- see "Units" below, and note it is a different ID space from `attributeID`**), `attributeCategoryID`, `dataType`, `minAttributeID`, `maxAttributeID`, `tooltipTitle`, `tooltipDescription` |
| `dogmaUnits` | `_key` (**this is the unitID**), `name`, `displayName`, `description` |
| `type_effects` | `typeID`, `effectID`, `isDefault` |
| `dogma_effects` | `effectID`, `name`, `displayName`, `effectCategoryID`, `isOffensive`, `isAssistance`, `durationAttributeID`, `rangeAttributeID`, `falloffAttributeID`, `modifierInfo` (JSON) |

`PRAGMA table_info(<table>)` lists every column; the tables here name the ones
you will reach for, not the full set.

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
| `systems` | `solarSystemID`, `name`, `regionID`, `constellationID`, `security`, `securityClass`, `factionID`, `wormholeClassID` (usually NULL -- see Gotchas), `x`, `y`, `z` (metres), `space` (`kspace`/`wormhole`/`abyssal`/`void`/`other` -- five values, see Gotchas) |
| `planets` | `planetID`, `solarSystemID`, `celestialIndex`, `typeID`, `radius`, `surfaceGravity`, `temperature`, `pressure`, `density`, `orbitRadius`, `orbitPeriod`, `eccentricity`, `moons`, `belts` |
| `moons` | `moonID`, `solarSystemID`, `planetID`, `celestialIndex`, `orbitIndex`, `typeID`, `radius`, `density`, `surfaceGravity`, `escapeVelocity`, `orbitRadius`, `orbitPeriod`, `rotationRate`, `eccentricity`, `massDust`, `massGas`, `temperature`, `pressure`, `fragmented`, `locked`, `x`, `y`, `z` — same physical statistics as `planets` |
| `asteroid_belts` | `beltID`, `solarSystemID`, `planetID` |
| `stargates` | `stargateID`, `solarSystemID`, `destSystemID`, `destStargateID` |
| `npc_stations` | `stationID`, `solarSystemID`, `ownerID`, `reprocessingEfficiency` |

`factions` and `races` are in the **`world`** part, not `universe` -- resolving
`systems.factionID` or `types.raceID` to a name needs `world` attached. They are
also the only two `world` tables keyed on something other than `_key`: join on
`factions.factionID` and `races.raceID`.

**`systems.factionID` is 99.2% NULL** -- only 70 of 8,490 systems carry it.
Faction ownership inherits upward exactly like wormhole class does: 386 of 1,184
constellations and 33 of 114 regions have it. Querying the system column alone
answers "which faction holds the most systems?" with *CONCORD Assembly, 26*.
The real answer is **Amarr Empire, 706**:

```sql
SELECT f.name, COUNT(*) FROM systems s
JOIN constellations c ON c.constellationID = s.constellationID
JOIN regions        r ON r.regionID = s.regionID
JOIN world.factions f ON f.factionID = COALESCE(s.factionID, c.factionID, r.factionID)
WHERE s.space = 'kspace' GROUP BY 1 ORDER BY 2 DESC;
```

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

## The `world` part and other generic tables

Everything outside the 26 hand-shaped tables was ingested generically. Two
consequences: the primary key is **`_key`** rather than a domain-specific name
(not `missionID`, `dungeonID`, etc.), and nested fields are JSON -- use
`json_extract()` and `json_each()`.

Two exceptions: **`factions` and `races` have no `_key`** -- they use
`factionID` and `raceID`. They are the only two of 38 `world` tables that do.

Table names do not match the casual descriptions:

| You want | Table | Notes |
| --- | --- | --- |
| NPC agents | `npcCharacters` | **no `agents` table.** Agents are rows where the `agent` column is non-null: `{agentTypeID, divisionID, isLocator, level}`. 10,966 of them. `locationID` joins `universe.npc_stations.stationID` |
| NPC corporations | `npcCorporations` | not `corporations` |
| Missions | `missions` | `messages` is an array of `{_key: slot, text}`; the briefing slot is `messages.mission.briefing`. `killMission` / `courierMission` are `{dungeonID, objectiveQuantity}` and mutually exclusive |
| Combat sites | `dungeons` | `description` holds the DED rating as prose |
| Certificates | `certificates` | `skillTypes` is an array of `{_key: skillTypeID, basic, standard, improved, advanced, elite}`; `recommendedFor` is a bare int array -- inconsistent shapes in one table |
| Factions, races | `factions`, `races` | here, not in `universe` |
| Ship traits / role bonuses | `items.typeBonus` | the in-game Traits panel, not derivable from dogma. Keyed on **`_key` = typeID**. `types` is `[{_key: skillTypeID, _value: [{bonus, bonusText, unitID}]}]` (per level of that skill); `roleBonuses` is the flat role bonus; `miscBonuses` is prose only. All 423 published ships have a row. `bonusText` carries raw `&lt;a href=showinfo:N&gt;` HTML |
| Wormhole system effects | `universe.mapSecondarySuns` | 1,038 of 2,604 J-space systems have one. `typeID` names it (Wolf-Rayet, Magnetar, Pulsar, Black Hole, Red Giant, Cataclysmic Variable); `effectBeaconTypeID` -> `items.type_dogma` gives the magnitudes |
| Star class, temperature, luminosity | `universe.mapStars` | one row per real system (8,089); `statistics` is JSON with `spectralClass`, `temperature`, `luminosity`, `age` |
| PI production chains | `industry.planetSchematics` | 68 rows, P1-P4 only -- there are no P0 rows, so P1 inputs dangle by design. **`_key` is a schematicID, not a typeID**; the product is the single `types` entry with `isInput = false` |
| Mutaplasmid roll ranges | `items.dynamicItemAttributes` | `_key` = mutaplasmid typeID; `attributeIDs` is `[{_key: attributeID, min, max}]` as multipliers on the base module |
| Ore/ice compression | `items.compressibleTypes` | `_key` -> `compressedTypeID`, strictly 1:1. Ore compresses **100x**, ice and gas only **10x**. Compressed and uncompressed reprocess identically |

**Mission dungeon references are almost all dangling.** Only **3 of 1,662**
kill missions have a `dungeonID` that exists in `dungeons`; `agentsInSpace`
resolves **0 of 360**. The ID ranges overlap, so this is not an ID-space
mismatch -- the dungeon definitions those missions point at are simply not in
the SDE. An inner join silently returns 3 rows where you expected 1,662, and a
left join reports "no dungeon" for 99.8% of combat missions. Say the reference
is unresolvable rather than reporting an absence.

**`dungeons.description` is 84% NULL** (226 of 1,409 populated), so a missing
DED rating means "no description shipped", not "unrated". Ratings appear in
three incompatible formats -- `DED Threat Assessment: Deadly (10 of 10)`,
`DED Threat Assessment Level: 10 of 10`, and `Threat Assessment Level: 8 of 10`
-- so `LIKE '%DED Threat Assessment:%'` finds 38 and misses 6, including a
10/10. Match on `Threat Assessment` alone (44 rows). The severity word is not
reliable either: level 10 appears as both "Critical" and "Deadly". Dungeon names
also repeat -- 1,409 rows, 1,014 distinct names -- so counting by name and by
key give different answers.

## Units: read `unitID`, not the name

`dogma_attributes.unitID` decides what a value means, and the `dogmaUnits` table
names each one -- but `dogmaUnits` has **no `unitID` column**; the unit number is
in `_key`, so the join is
`JOIN dogmaUnits u ON u._key = a.unitID`.

Attribute *names* are not a reliable guide -- this is the single richest source
of confidently wrong answers in the dataset. Note also that **`unitID` and
`attributeID` are separate ID spaces that overlap**: attributeID 101 is
`shieldRechargeRate`, unitID 101 is "milliseconds", and the two have nothing to
do with each other. Read the table below as unit numbers, not attribute numbers.

| unitID | Meaning | Trap |
| --- | --- | --- |
| **108** | Inverse absolute percent: `0.0` = 100%, `1.0` = 0% | **58 attributes, 69,032 rows.** Only 24 are named `*DamageResonance`; the rest -- `stasisWebifierResistance`, `ECMResistance`, `sensorDampenerResistance`, `energyWarfareResistance`, `remoteRepairImpedance` -- read as if higher were better |
| **101** | **Milliseconds**, but `displayName` says "s" | **92 attributes, 40,522 rows.** `rechargeRate` on a Rifter is `125000` = 125 s, not 125,000 |
| 3, 123 | Actual seconds | Sits beside unitID 101 with nothing in the schema to distinguish them |
| 109 | Modifier percent: `1.1` = +10%, `0.9` = -10% | `0.75` means **-25%**, not 75% |
| 105 / 121 / 124 / 127 | Four more percent conventions | `-50` = -50%, `5` = 5%, `0.5` = 50% -- all display as `%` |

Worked example -- "which ship resists webs best?":

```sql
-- WRONG: names suggest higher is better
SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value DESC;              -- Bantam, Condor, Griffin at 1.0

-- RIGHT: unitID 108 is inverted
SELECT t.name, ROUND((1 - d.value) * 100, 1) AS pct FROM type_dogma d
JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value ASC;               -- Erebus, Leviathan, Avatar at 80%
```

The naive answer names T1 frigates as the best web-resisters. They are the
**worst**, at 0%. `highIsGood` does not save you -- `remoteRepairImpedance` is
inverted and flagged `highIsGood = 1`.

Two more name traps: **`agility` (70) is the Inertia Modifier**, so "most agile"
by either sort direction is wrong -- align time is
`ln(4) * inertia * mass / 1e6`. And **attribute 51 is named `speed` but means
rate of fire**, in milliseconds; ship velocity is `maxVelocity` (37).

**SQLite's `LOG()` is base 10, not natural.** `LOG(4)` returns 0.602, not
1.386, so `LOG(4) * inertia * mass / 1e6` gives align times about 2.3x too
fast -- 1.7 s for a T2 frigate instead of 4.0 s. The ranking is unchanged,
which is exactly why the error survives a sanity check. Use `LN(4)`, or the
literal `1.386294`.

## Gotchas

These cause silently wrong answers -- plausible numbers, not errors -- so check
them before trusting a result. Verified against build 3466501.

**Wrong-answer traps (highest priority):**

- **Resonance is not resistance; it is inverted.** `armorEmDamageResonance =
  0.4` means **60% resist**, not 40%. Resist % is `(1 - value) * 100`. The rule
  is **`unitID = 108`**, not the name -- see "Units" above; 19 inverted
  attributes have no "resonance" anywhere in the name (58 carry unitID 108, of
  which 24 end in `DamageResonance` and 39 contain "resonance" somewhere).
- **A ship's structure resistance is the bare set (109, 110, 111, 113), and it
  is 33% on every published ship.** The `hull*DamageResonance` family (974-977)
  is **not** the ship-side attribute, despite the name and the identical
  `displayName`. It is the *module* side of a modifier: a Damage Control's own
  `hull*` values are the bonus it grants, and the effect writes them onto the
  ship's bare attributes. `dogma_effects.modifierInfo` for effect 2302
  (`damageControl`) says so outright:

  ```
  113 (emDamageResonance)        <- 974 (hullEmDamageResonance)
  111 (explosiveDamageResonance) <- 975 (hullExplosiveDamageResonance)
  109 (kineticDamageResonance)   <- 976 (hullKineticDamageResonance)
  110 (thermalDamageResonance)   <- 977 (hullThermalDamageResonance)
  ```

  23 of the 24 effects that touch structure resonance target the bare set --
  Damage Control, Bastion, hull resistance bonuses, system-wide storms. Only
  `moduleBonusAssaultDamageControl` targets `hull*`, and it is modifying an
  Assault Damage Control module, not a hull.

  All **423 of 423** published ships carry the bare set at exactly `0.67`, none
  missing -> **33% structure resist to all four damage types, on every ship**,
  which is what the client and every fitting tool show. By category, `hull*` is
  carried by 42 starbases, 34 modules, 9 ships and 1 celestial -- those 9 ships
  are the anomaly, not the rule, and their `1.0` is not what the client
  displays. **Do not use 974-977 for a ship**, and do not read a missing `hull*`
  row as 0% structure resistance.

  The three layers therefore live in different ID blocks, and structure's is not
  contiguous:

  | Layer | EM | Thermal | Kinetic | Explosive |
  | --- | --- | --- | --- | --- |
  | Shield | 271 | 274 | 273 | 272 |
  | Armor | 267 | 270 | 269 | 268 |
  | Structure | 113 | 110 | 109 | **111** |

  112 is `energyDamageAbsorptionFactor` and is not a resonance, so
  `BETWEEN 109 AND 112` silently swaps one real value for a junk row.
- **The client's damage-type order is not the attributeID order.** Every EVE UI
  lists resists **EM, Thermal, Kinetic, Explosive**. The IDs run **EM,
  Explosive, Kinetic, Thermal** (267/268/269/270). Selecting
  `BETWEEN 267 AND 270` and labelling the results in the client's order swaps
  thermal and explosive -- a Rifter's armor becomes 60/10/25/35 instead of
  60/35/25/10. Label from `a.name`, or order explicitly.
- **Some hulls have an always-on role bonus that is not in the resonance
  value.** An Onyx's stored shield resonances are byte-identical to an Eagle's
  and a Cerberus's, but the client shows 20/84/76/60 where the raw values give
  0/80/70/50. The difference is `rookieShieldResistBonus` (1829) = `-20` plus
  four passive `ItemModifier` effects, applied as
  `resonance * (1 + bonus/100)`. Affected hulls -- the name "rookie" is
  misleading, four of the six are Heavy Interdiction Cruisers:

  | Attribute | Hulls |
  | --- | --- |
  | 1829 shield | Onyx, Broadsword, Fiend, Laelaps, Taipan (-20/-12), Ibis (-8) |
  | 1825 armor | Devoter, Phobos, Gold Magnate, Silver Magnate (-20), Impairor (-8) |

  The general rule, which covers more than resistances: **`typeBonus.roleBonuses`
  is always on and is already reflected in what the client shows; the per-skill
  bonuses in `typeBonus.types` scale with skill level and are not.** 89 published
  ships carry an effect that modifies a resonance attribute, but the other 78 are
  per-skill-level ship bonuses (a Damnation gets 4% armor resist per level of
  Amarr Cruiser) and correctly do not apply to a base hull. Reading
  `roleBonuses` in prose is the fastest check: the Onyx's says "20.0 bonus to
  all shield resistances", the Damnation's does not mention resists at all.
- **Four families of resonance attribute exist.** Always anchor the layer --
  by attributeID, per the table above -- because a bare
  `LIKE '%DamageResonance'` returns 16 rows for one ship. There is also a
  `passive*DamageResonance` family (1418-1429) whose display names differ from
  the active ones only in capitalisation; note that its four **`passiveHull*`
  members (1426-1429) are `unitID = 127`, not 108**, so the inversion rule does
  not apply to them. For resistances, select the attributeID family
  deliberately rather than joining on name.
- **Hauling capacity: `capacity` vs `volume` vs `packagedVolume`.** Cargo space
  is `types.capacity`, and what a packaged item takes up is
  `types.packagedVolume` -- **not `volume`**, which is the assembled size. A
  Rifter is 27,289 m3 assembled and 2,500 m3 packaged, so using `volume` makes
  every ship-hauling answer ~11x too pessimistic. `capacity` is NULL for 25,265
  published types (anything with no hold), so `ORDER BY capacity DESC` is fine
  but `WHERE capacity > x` silently drops them.

  The related trap: a **ship maintenance bay holds *assembled* ships**. The
  Bowhead's 1,600,000 m3 `shipMaintenanceBayCapacity` sounds enormous but fits
  only 58 Rifters, while a Charon's 465,000 m3 of ordinary cargo fits 186
  packaged ones. Freighter cargo figures in the SDE are also **pre-skill** --
  no Racial Freighter bonus applied.
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
- **`universe.systemWideEffects` is not the wormhole effect**, despite keying on
  the same beacon typeID. Its `dbuffs` are Sisters-of-EVE event bonuses scoped
  to a single ship, and those `_key`s are **`misc.dbuffCollections` IDs, not
  attributeIDs** -- the two ID spaces overlap completely, so a join to
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
  7 and 9 (high/low/null designations), so without it the same query answers
  "Jita is class 7" and "1DQ1-A is class 9". Class 8 never appears on a
  constellation at all -- it is system-level only, on 687 k-space systems.
  Classes 1-6 are the familiar
  wormhole classes, 12 is Thera, 13 shattered/frigate holes, 14-18 Drifter,
  19-25 abyssal/void/Pochven.
- **`security` alone cannot identify nullsec.** Wormhole, abyssal and void
  systems all carry `security = -0.99`, so `WHERE security <= 0` sweeps in 3,004
  systems that are not nullsec. Filter `space = 'kspace'` first. Counts in known
  space (5,485 total): 1,246 high, 687 low, 3,552 null -- but that "high" figure
  includes Exordium's 53 systems at security 1.0. Conventional New Eden high-sec
  is **1,193**. Say which you mean.
- **`>= 0.5` instead of `>= 0.45` fails silently on routing.** A high-sec-only
  Jita-to-Amarr route is 34 jumps at the correct threshold and 39 at the wrong
  one -- a plausible answer either way, with no error to notice.
- **Ship/module skill requirements are in dogma, not `bp_skills`.** They live in
  `requiredSkill1..6` (a typeID) paired with `requiredSkill1Level..6`.
  `bp_skills` is what a *blueprint activity* needs -- a different question.
  The Rifter needs `requiredSkill1 = 3329` (Minmatar Frigate) at level 1.
  **These do not recurse on their own.** Skills have their own
  `requiredSkill*` attributes, so "what do I need to fly this" means walking the
  tree: a Rifter also needs Spaceship Command I via Minmatar Frigate. One hop
  for a T1 frigate, several for T2 -- a single query under-reports.
- **`basePrice` is not a market price** and is 0 or NULL for 17,652 of 26,992
  published types. It is an internal seed value. For real prices use ESI; the
  SDE has none.

**Filtering and units:**

- **`published = 1` applies to market items, not everything.** It is right for
  ships, modules, charges and ore -- 26,992 of 52,863 types are published, the
  rest being test and unreleased content. But **every celestial type is
  `published = 0`**: all ten planet types, plus whole categories (Station,
  Effects, Bonus, Placeables, Abstract). Joining `planets` to `types` with
  `published = 1` returns **zero rows**, silently. Scope the filter to the
  question.
- **Planet type names are `Planet (Temperate)`, not `Temperate`.** Filtering on
  the bare word returns zero rows with no error -- the same silent-zero shape as
  the `published` mistake, and planetary-industry questions hit it constantly.
  The ten values are `Planet (Barren)`, `(Gas)`, `(Ice)`, `(Lava)`, `(Oceanic)`,
  `(Plasma)`, `(Shattered)`, `(Storm)`, `(Temperate)` and `(Scorched Barren)`.
- **`volume` is the assembled volume; `packagedVolume` is what you haul.** A
  Rifter is 27,289 m3 assembled and **2,500 m3 packaged** -- 685 published types
  differ. Every "how many X fit in a Y" answer is ~10x wrong on the assembled
  figure.
- **Manufacturing output per run is `bp_products.quantity`.** Antimatter Charge
  S consumes 204 Tritanium *per run of 100 charges* -- 2.04 each. 368
  manufacturing blueprints produce more than one per run and reactions reach
  10,000, so per-unit costs are off by up to four orders of magnitude if you
  read `bp_materials.quantity` directly.
- **`portionSize` governs reprocessing, and nothing else.** `type_materials`
  quantities are per `portionSize` units: Veldspar yields 400 Tritanium per
  **100** units. It is **not** the manufacturing batch size -- that is
  `bp_products.quantity`. The two coincide for most ammo, which is what makes
  the mistake easy, but 30 published types disagree: XL torpedoes have
  `portionSize = 100` while a run makes 5,000, a 50x error.
- **Tech level has three sources that disagree.** "How many published Tech II
  items are there?" answers 2,537 from `types.techLevel`, 2,434 from dogma
  attribute 422, and 1,892 from `metaGroupID = 2` -- and 43 types have a
  `techLevel` column that flatly contradicts their dogma. 19 published hulls are
  `techLevel = 2` but `metaGroupID = 4` (Faction) -- Utu, Freki, Malice -- with
  no invention path at all. **`metaGroupID = 2` is the one to trust** for "is
  this T2".
- **`bp_skills` mixes activities.** The Dominix blueprint has 1 manufacturing
  skill and 3 invention skills; without `AND activity = '...'` you get both and
  report the wrong set.
- **Invention runs T1 -> T2 blueprint.** Materials, skills and time live on the
  **T1** blueprint, and the product is the **T2 blueprint**, not the T2 item.
  Starting from the T2 blueprint finds no invention rows at all.
  `bp_products.probability` is the *base* chance before decryptors and skills.
  It is NULL for all 4,848 manufacturing rows, all 120 reaction rows, **and 8
  invention rows** -- so `WHERE probability IS NOT NULL` silently drops eight
  inventable blueprints.
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
- **1,364 moons have NULL `surfaceGravity`** (and NULL `density`), all
  `typeID = 14`. `ORDER BY surfaceGravity DESC` is safe -- SQLite sorts NULL
  smallest -- but `ASC` puts 1,364 NULLs at the top of a "lowest gravity"
  query, and `AVG()` silently skips them.
- 960 published types have `volume` NULL; `metaGroupID` and `techLevel` are
  populated for only ~26% and ~19% of types.
- **21 blueprint rows reference typeIDs that do not exist** (20 products, 1
  material) -- removed content whose blueprints remain. This is upstream data,
  not a build error; use inner joins so they drop out.
- Ore variant names changed: "Concentrated Veldspar" and "Dense Veldspar" no
  longer exist as types. The grades are now `Veldspar II-Grade` and similar.
- Names are English-only; the builder discards other locales.

**Geography -- counting systems, and what "unreachable" means:**

Read this before answering anything of the form "how many systems...", "which
system is the most/least...", or "how do I get from A to B". Every trap here
produces a plausible number rather than an error.

- **Zarzakh has no planets at all** -- the only k-space system without any. A
  count taken through `systems JOIN planets` therefore reports 3,551 nullsec
  systems instead of 3,552. Count from `systems` directly.
- **3,222 systems have no stargates**: 2,604 wormhole + 200 abyssal + 200 void
  + 217 k-space + GPMS-01. The gate graph is disconnected -- routing between
  components is impossible, so a BFS must handle "no path" rather than hang or
  error.
- **"Highest security" has no clean answer.** 53 real k-space systems in the
  region **Exordium** sit at security exactly `1.0`. It is real, flyable
  new-player content -- 40 NPC stations including 13 AIR Laboratories, a single
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

-- all published ships in a hull class. There is no hull-size column: "cruiser",
-- "battleship" etc. exist only as group names, so a class is a list of groups
-- (Battleship + Marauder + Black Ops + Force Auxiliary...) you curate yourself.
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

-- Resistances as the client shows them: all three layers, client damage-type
-- order, and the always-on role bonus applied. Verified against the in-game
-- fitting window for the Rifter (0/20/40/50, 60/35/25/10, 33/33/33/33) and the
-- Onyx (20/84/76/60, 50/86/63/10, 33/33/33/33).
WITH layer(attributeID, layer, dmg, ord) AS (
  VALUES (271,'Shield','EM',1),   (274,'Shield','Thermal',2),
         (273,'Shield','Kinetic',3), (272,'Shield','Explosive',4),
         (267,'Armor','EM',1),    (270,'Armor','Thermal',2),
         (269,'Armor','Kinetic',3),  (268,'Armor','Explosive',4),
         (113,'Structure','EM',1),(110,'Structure','Thermal',2),
         (109,'Structure','Kinetic',3), (111,'Structure','Explosive',4)
)
SELECT l.layer, l.dmg,
       ROUND((1 - d.value * (1 + COALESCE(rb.value, 0) / 100.0)) * 100, 2) AS resist_pct
FROM types t
CROSS JOIN layer l
JOIN type_dogma d ON d.typeID = t.typeID AND d.attributeID = l.attributeID
LEFT JOIN type_dogma rb ON rb.typeID = t.typeID       -- always-on role bonus
     AND rb.attributeID = CASE l.layer WHEN 'Armor'  THEN 1825
                                       WHEN 'Shield' THEN 1829 END
WHERE t.name = 'Onyx'
ORDER BY CASE l.layer WHEN 'Shield' THEN 1 WHEN 'Armor' THEN 2 ELSE 3 END, l.ord;

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
