# Schema reference

Column-level reference for the hand-shaped tables, plus how the generically
ingested tables are keyed. `PRAGMA table_info(<table>)` lists every column; the
tables here name the ones you will reach for.

Names are English-only; the builder discards other locales.

## Hand-shaped tables

Items and classification:

| Table | Key columns |
| --- | --- |
| `types` | `typeID`, `name`, `groupID`, `categoryID`, `mass`, `volume` (assembled), `packagedVolume` (what it takes up in a hold), `capacity` (its own cargo space), `basePrice`, `portionSize`, `published`, `metaLevel`, `techLevel`, `metaGroupID`, `marketGroupID`, `raceID`, `factionID` |
| `groups_` | `groupID`, `name`, `categoryID` |
| `categories` | `categoryID`, `name` |
| `market_groups` | `marketGroupID`, `parentGroupID`, `name` |
| `meta_groups` | `metaGroupID`, `name` (Tech I/II, Faction, Officer …) |

Attributes (all ship/module stats live here):

| Table | Key columns |
| --- | --- |
| `type_dogma` | `typeID`, `attributeID`, `value` |
| `dogma_attributes` | `attributeID`, `name`, `displayName`, `description`, `defaultValue` (**use it -- a missing `type_dogma` row means "default", not "no value"**), `highIsGood` (unreliable), `stackable`, `published`, `unitID` (**decides what the number means -- see "Units" in `gotchas-dogma.md`, and note it is a different ID space from `attributeID`**), `attributeCategoryID`, `dataType`, `minAttributeID`, `maxAttributeID`, `tooltipTitle`, `tooltipDescription` |
| `dogmaUnits` | `_key` (**this is the unitID**), `name`, `displayName`, `description` — listed here because dogma queries need it, but it is a *generic* table: camelCase, `_key`-keyed |
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
| `moons` | **its own download — not in the `universe` part.** `moonID`, `solarSystemID`, `planetID`, `celestialIndex`, `orbitIndex`, `typeID`, `radius`, `density`, `surfaceGravity`, `escapeVelocity`, `orbitRadius`, `orbitPeriod`, `rotationRate`, `eccentricity`, `massDust`, `massGas`, `temperature`, `pressure`, `fragmented`, `locked`, `x`, `y`, `z` — same physical statistics as `planets`. It is universe-domain data in a separate 20.5 MB part because it is 344,457 rows; attaching `universe` alone gives `no such table: moons` |
| `asteroid_belts` | `beltID`, `solarSystemID`, `planetID` |
| `stargates` | `stargateID`, `solarSystemID`, `destStargateID`, `destSystemID`, `typeID`, `x`, `y`, `z` — **note the order**: `destStargateID` comes first, so `SELECT *` with positional unpacking silently builds the graph on gate IDs |
| `npc_stations` | `stationID`, `solarSystemID`, `ownerID`, `typeID`, `operationID`, `reprocessingEfficiency`, `reprocessingStationsTake`, `useOperationName`, `orbitID`, `celestialIndex`, `orbitIndex`, `x`, `y`, `z` — **no name column**, see below |

**Stations and moons have no names in the SDE; the client assembles them.** For
a station:
`<system> <celestialIndex in Roman>[ - Moon <orbitIndex>] - <world.npcCorporations.name> <world.stationOperations.operationName>`
— which reproduces strings like `Jita IV - Moon 6 - Hyasyoda Corporation
Refinery` (verified). Moons take the same shape (`Arifsdald VII - Moon 1`) from
`moons.celestialIndex` and `orbitIndex`. Both need `world` attached. The
assembly is not in CCP's export, so if you quote a station or moon name, say it
was derived.

`factions` and `races` are in the **`world`** part, not `universe` -- resolving
`systems.factionID` or `types.raceID` to a name needs `world` attached. They are
also the only two `world` tables keyed on something other than `_key`: join on
`factions.factionID` and `races.raceID`.

**`systems.factionID` is 99.2% NULL** -- faction ownership inherits upward from
constellation and region. The trap, the counts and the COALESCE query are in
`gotchas-universe.md` ("Faction ownership").

`activity` values: `manufacturing`, `copying`, `invention`,
`research_material`, `research_time`, `reaction`.

Category IDs and the commonly used attributeIDs are in SKILL.md's
"IDs you will need constantly" block.

**Do not reach for attributes by name.**

Attribute names are the single richest
source of confidently wrong answers in this dataset — see `gotchas-dogma.md`.
Anchor on the attributeID for anything in a family: resistances, resonances and
the four sensor-strength attributes. (Tech level also has three disagreeing
sources, but that is a filtering question — see `gotchas-types.md`.) Name joins
are safe only for isolated scalars like `maxVelocity`, and even then two
attribute names are shared by two IDs each — and **`published = 1` does not
separate them**, since all four rows are published:

| attributeID | name | unitID |
| --- | --- | --- |
| 1847, 1848 | `902` | NULL |
| 2794 | `cynoJammerActivationDelay` | 3 (seconds) |
| 2795 | `cynoJammerActivationDelay` | 101 (**milliseconds**) |

The cyno pair differs in unit, so picking the wrong ID is a 1000x error with no
symptom. Resolve to an attributeID; nothing else works.

## Finding a generic table, in any part

Everything outside the 25 hand-shaped tables was ingested generically -- 81 of
the 106 domain tables. Two
consequences: the primary key is **`_key`** rather than a domain-specific name
(not `missionID`, `dungeonID`, etc.), and nested fields are JSON -- use
`json_extract()` and `json_each()`.

**This index spans every part.** Rows are qualified with the part that holds
them (`items.typeBonus`, `misc.fighterAbilities`). It is the section to search
whenever you cannot guess a table name -- the answer to "where does X live" for
the whole database. The `world` tables' traps have their own file,
`gotchas-world.md`; this index only points at them.

Table names do not match the casual descriptions:

| You want | Table | Notes |
| --- | --- | --- |
| Missions, agents, dungeons, certificates, clone grades, masteries | `world` part | **traps and details in `gotchas-world.md`** -- there is no `agents` or `corporations` table (it is `npcCharacters` / `npcCorporations`), and the dungeon references are almost all dangling |
| Factions, races | `factions`, `races` | in `world`, not `universe` |
| Ship traits / role bonuses | `items.typeBonus` | the in-game Traits panel, not derivable from dogma. Keyed on **`_key` = typeID**. `types` is `[{_key: skillTypeID, _value: [{bonus, bonusText, unitID}]}]` (per level of that skill); `roleBonuses` is the flat role bonus; `miscBonuses` is prose only. All 423 published ships have a row. `bonusText` carries raw **unescaped** HTML -- `<a href=showinfo:23594>Sentry Drone</a>` -- so strip tags before matching, and do not search for an escaped form |
| Wormhole system effects | `universe.mapSecondarySuns` | 1,038 of 2,604 J-space systems have one. `typeID` names it (the exact star names are `Wolf-Rayet Star`, `Magnetar`, `Pulsar`, `Black Hole`, `Red Giant`, `Cataclysmic Variable`). **The beacon is spelled differently from the star**: `Class 6 Wolf Rayet Effects` is unhyphenated, so `LIKE '%Wolf-Rayet%'` matches the star and returns *zero* beacons; `effectBeaconTypeID` -> `items.type_dogma` gives the magnitudes |
| Star class, temperature, luminosity | `universe.mapStars` | one row per real system (8,089); `statistics` is JSON with `spectralClass`, `temperature`, `luminosity`, `age` |
| PI production chains | `industry.planetSchematics` | 68 rows, P1-P4 only -- there are no P0 rows, so P1 inputs dangle by design. **`_key` is a schematicID, not a typeID**; the product is the single `types` entry with `isInput = false` |
| Mutaplasmid roll ranges | `items.dynamicItemAttributes` | `_key` = mutaplasmid typeID; `attributeIDs` is `[{_key: attributeID, min, max}]` as multipliers on the base module |
| Which hulls can link to a beacon | `cosmetic.linkWithShip` | 3 rows -- **in `cosmetic`, not `items`**, despite having nothing to do with skins. `linkableShipTypeListID` -> `items.typeLists` gives the eligible hulls; also carries `linkDuration`, `maxLinkRange`, `omegaOnly`, `applyPvpFlag` and a `dbuffs` array. C-CRAB = Carriers and Command Carriers only; CRAB adds Titan/Dread/Supercarrier/Lancer; Skyhook Reagent Silo takes 22 groups and blocks cloak, jump, dock and MJD while capping you at 1,000 m/s |
| Eligibility sets (who may dock/link/trigger) | `items.typeLists` | 10 columns, of which **six define the set and all six matter**: `included`/`excluded` x `TypeIDs`/`GroupIDs`/`CategoryIDs` (non-NULL on 218/268/45 and 26/27/2 of 462 rows). Reading only the typeID column returns **empty** for rows defined by group -- the C-CRAB list has 0 typeIDs and 2 groups. `displayName` is a pre-written human answer but is NULL on 425 rows and **can under-state the data**: list 300 says "Titans, Supercarriers, Carriers, and Dreadnoughts" while its groups also include Lancer Dreadnought and Command Carrier. Two lists include typeID 11019 (Cockroach, `published = 0`) -- drop unpublished hulls before answering. 229 of 462 `_key`s are also valid typeIDs, so never join `_key` to `types` |
| Fighter abilities | `misc.fighterAbilities` | 36 rows. Columns are `_key`, `displayName`, `tooltipText`, `targetMode`, `disallowInHighSec`, `disallowInLowSec`, `iconID`, `turretGraphicID` — **the name column is `displayName`, there is no `name`**, so the usual `t.name` pattern fails here. Which fighter has which ability is `misc.fighterAbilitiesByType` (`_key` = typeID, 94 rows, three columns `abilitySlot0/1/2` each holding `{abilityID, cooldownSeconds}` — a slot is NULL when unused, so unpivot all three) |
| Proximity effects (abyssal weather, insurgencies) | `misc.appliedProximityEffects` | 118 rows, columns `_key` (the cloud/beacon typeID), `dbuffs`, `radius`, `delaySeconds`. `dbuffs` is `[{_key: dbuffID, _value: magnitude}]` -> `misc.dbuffCollections`, whose `displayName` names the effect and whose `itemModifiers` name the attributes it touches. `misc.proximityTrap` (24 rows) is the same shape for traps and adds `triggerFilterTypeListID` -> `items.typeLists` |
| Ore/ice compression | `items.compressibleTypes` | `_key` -> `compressedTypeID`, strictly 1:1. **The 100x (ore) and 10x (ice/gas) figures are volume ratios, not unit ratios** -- 1 unit compresses to 1 unit, and Arkonor goes 16 m3 -> 0.16 m3. Compressed and uncompressed reprocess identically, same `portionSize`, so compressing loses nothing. The table holds no ratio; derive it from `types.volume` |

The `world`-specific traps -- dangling mission dungeons, DED rating formats,
byte-identical clone grades, the masteries tier index -- are in
`gotchas-world.md`.
