# Schema reference

Column-level reference for the hand-shaped tables, plus how the generically
ingested tables are keyed. `PRAGMA table_info(<table>)` lists every column; the
tables here name the ones you will reach for.

Names are English-only; the builder discards other locales.

## Hand-shaped tables

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
| `dogma_attributes` | `attributeID`, `name`, `displayName`, `description`, `defaultValue` (**use it -- a missing `type_dogma` row means "default", not "no value"**), `highIsGood` (unreliable), `stackable`, `published`, `unitID` (**decides what the number means -- see "Units" in `gotchas-items.md`, and note it is a different ID space from `attributeID`**), `attributeCategoryID`, `dataType`, `minAttributeID`, `maxAttributeID`, `tooltipTitle`, `tooltipDescription` |
| `dogmaUnits` | `_key` (**this is the unitID**), `name`, `displayName`, `description` |
| `type_effects` | `typeID`, `effectID`, `isDefault` |
| `dogma_effects` | `effectID`, `name`, `displayName`, `effectCategoryID`, `isOffensive`, `isAssistance`, `durationAttributeID`, `rangeAttributeID`, `falloffAttributeID`, `modifierInfo` (JSON) |

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
| `systems` | `solarSystemID`, `name`, `regionID`, `constellationID`, `security`, `securityClass`, `factionID`, `wormholeClassID` (usually NULL -- see `gotchas-universe.md`), `x`, `y`, `z` (metres), `space` (`kspace`/`wormhole`/`abyssal`/`void`/`other` -- five values, see `gotchas-universe.md`) |
| `planets` | `planetID`, `solarSystemID`, `celestialIndex`, `typeID`, `radius`, `surfaceGravity`, `temperature`, `pressure`, `density`, `orbitRadius`, `orbitPeriod`, `eccentricity`, `moons`, `belts` |
| `moons` | `moonID`, `solarSystemID`, `planetID`, `celestialIndex`, `orbitIndex`, `typeID`, `radius`, `density`, `surfaceGravity`, `escapeVelocity`, `orbitRadius`, `orbitPeriod`, `rotationRate`, `eccentricity`, `massDust`, `massGas`, `temperature`, `pressure`, `fragmented`, `locked`, `x`, `y`, `z` — same physical statistics as `planets` |
| `asteroid_belts` | `beltID`, `solarSystemID`, `planetID` |
| `stargates` | `stargateID`, `solarSystemID`, `destSystemID`, `destStargateID` |
| `npc_stations` | `stationID`, `solarSystemID`, `ownerID`, `typeID`, `operationID`, `reprocessingEfficiency`, `reprocessingStationsTake`, `useOperationName`, `orbitID`, `celestialIndex`, `x`, `y`, `z` — **no name column**: the station's name is built from `items.types.name` (the structure type) plus `world.stationOperations.operationName` |

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

**Do not reach for these by name.** Attribute names are the single richest
source of confidently wrong answers in this dataset — see `gotchas-items.md`.
Anchor on the attributeID for anything in a family: resistances, resonances,
the four sensor-strength attributes, the three tech-level sources. Name joins
are safe only for isolated scalars like `maxVelocity`, and even then two
attribute names (`902`, `cynoJammerActivationDelay`) are shared by two IDs each,
so add `AND published = 1` or resolve to an ID when a query must return exactly
one row.

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
| NPC agents | `npcCharacters` | **no `agents` table.** Agents are rows where the `agent` column is non-null: `{agentTypeID, divisionID, isLocator, level}`. 10,966 of them. `locationID` joins `universe.npc_stations.stationID`. **Filter `agentTypeID = 2`** (`BasicAgent`) for the mission agents a player means -- of 180 level-5 agents, 143 are `agentTypeID = 8` EventMissionAgent and only **37** are real. `agentTypes` (`_key`, `name`) names all 13 kinds |
| NPC corporations | `npcCorporations` | not `corporations` |
| Missions | `missions` | `messages` is an array of `{_key: slot, text}`; the briefing slot is `messages.mission.briefing`. `killMission` / `courierMission` are `{dungeonID, objectiveQuantity}` and mutually exclusive |
| Combat sites | `dungeons` | `description` holds the DED rating as prose |
| Certificates | `certificates` | `skillTypes` is an array of `{_key: skillTypeID, basic, standard, improved, advanced, elite}`; `recommendedFor` is a bare int array -- inconsistent shapes in one table |
| Factions, races | `factions`, `races` | here, not in `universe` |
| Ship traits / role bonuses | `items.typeBonus` | the in-game Traits panel, not derivable from dogma. Keyed on **`_key` = typeID**. `types` is `[{_key: skillTypeID, _value: [{bonus, bonusText, unitID}]}]` (per level of that skill); `roleBonuses` is the flat role bonus; `miscBonuses` is prose only. All 423 published ships have a row. `bonusText` carries raw `&lt;a href=showinfo:N&gt;` HTML |
| Wormhole system effects | `universe.mapSecondarySuns` | 1,038 of 2,604 J-space systems have one. `typeID` names it (the exact star names are `Wolf-Rayet Star`, `Magnetar`, `Pulsar`, `Black Hole`, `Red Giant`, `Cataclysmic Variable`). **The beacon is spelled differently from the star**: `Class 6 Wolf Rayet Effects` is unhyphenated, so `LIKE '%Wolf-Rayet%'` matches the star and returns *zero* beacons; `effectBeaconTypeID` -> `items.type_dogma` gives the magnitudes |
| Star class, temperature, luminosity | `universe.mapStars` | one row per real system (8,089); `statistics` is JSON with `spectralClass`, `temperature`, `luminosity`, `age` |
| PI production chains | `industry.planetSchematics` | 68 rows, P1-P4 only -- there are no P0 rows, so P1 inputs dangle by design. **`_key` is a schematicID, not a typeID**; the product is the single `types` entry with `isInput = false` |
| Mutaplasmid roll ranges | `items.dynamicItemAttributes` | `_key` = mutaplasmid typeID; `attributeIDs` is `[{_key: attributeID, min, max}]` as multipliers on the base module |
| Ore/ice compression | `items.compressibleTypes` | `_key` -> `compressedTypeID`, strictly 1:1. **The 100x (ore) and 10x (ice/gas) figures are volume ratios, not unit ratios** -- 1 unit compresses to 1 unit, and Arkonor goes 16 m3 -> 0.16 m3. Compressed and uncompressed reprocess identically, same `portionSize`, so compressing loses nothing. The table holds no ratio; derive it from `types.volume` |

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
