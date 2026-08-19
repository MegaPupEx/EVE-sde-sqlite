---
name: eve-sde
description: Query the EVE Online Static Data Export (SDE) - ships, modules, dogma attributes, blueprints and manufacturing, planetary industry (PI) schematics, reprocessing yields, and the New Eden universe (regions, systems, planets, moons, stargates, stations). Use whenever a question involves EVE Online game data such as ship stats, fitting attributes, build materials, ore yields, PI chains, system security, planet or moon data, jump routes, market groups, or type/group/category lookups. Covers building the local SQLite database and querying it with SQL.
---

# EVE Online SDE

The SDE is CCP's static game-data export: everything in EVE that isn't live
player state. This skill covers getting it into SQLite and querying it.

**Not in the SDE:** market prices, kills, sovereignty, character or corp data.
Those are live data — use ESI (`https://esi.evetech.net`) instead.

**No database on disk?** That is step zero — jump to "Get a database" below.
Fetching one part takes seconds; `references/acquisition.md` has the full
ladder.

**Two failure modes.** First, **wrong answers rather than errors**: the SDE is
full of columns that look like the thing you want and are not — resonance is
inverted, `security` alone does not mean nullsec, a millisecond column displays
as "s". Almost every trap returns a plausible number rather than raising, so
read the relevant `references/gotchas-*.md` **before** trusting a result.
Second, answering the query instead of the player — see "Answering a player, not
a query".

## Files

| File | ~tokens | Read it when |
| --- | --- | --- |
| `references/gotchas-dogma.md` | 3.8k | what a ship or module **value means** — resistances, units, capacitor, speed, sensors, skill requirements |
| `references/gotchas-types.md` | 2.9k | **which rows belong** — `published`, tech level, volume vs `packagedVolume`, `basePrice`, planet type names, duplicate names |
| `references/gotchas-universe.md` | 4.4k | any system, planet, moon, star, security, region or routing question |
| `references/gotchas-industry.md` | 2.4k | any build cost, blueprint or invention question — and reprocessing yields, which live in `items.type_materials` |
| `references/gotchas-world.md` | 1.1k | missions, agents, dungeons, DED ratings, NPC corps, certificates, clone grades, masteries — severe traps, documented nowhere else |
| `references/schema.md` | 3.0k | you need column names, are joining a table you have not used, **or need to find which table holds something** — its second half indexes every generic table in every part |
| `references/examples.md` | 1.8k | **try first** for a straightforward stat, blueprint, invention, reprocessing, planet, gate or security query — 10 worked queries, each naming the parts it needs |
| `references/acquisition.md` | 1.5k | no database is present and none was uploaded — how to fetch or build one |

The token column is approximate (bytes/4), for budgeting context before
opening a file; this file itself is ~4.2k.

The `gotchas-*` files follow the download parts, so fetching usually decides
reading too: fetch `universe`, read `references/gotchas-universe.md`. Two
exceptions — `items` has **two** files (`references/gotchas-dogma.md` for what
a value means, `references/gotchas-types.md` for which rows belong), and
reprocessing is documented in `references/gotchas-industry.md` although
`type_materials` lives in the `items` part.

**Coverage is not uniform.** `items`, `universe`, `industry` and `world` are
documented in depth. In `cosmetic` and `misc`, six tables are covered —
`linkWithShip`, `fighterAbilities`, `fighterAbilitiesByType`,
`appliedProximityEffects`, `proximityTrap` and `dbuffCollections`, all indexed
in `references/schema.md` and routed from the parts table below — but **skins,
graphics and icons have no notes at all**. For anything uncovered in those two
parts, inspect with `sqlite_master` and `PRAGMA table_info` and say the shape
is unverified rather than inferring it.

**If you cannot find where something lives, `references/schema.md` indexes the
tables you would not guess** — ship traits, mutaplasmid ranges, PI chains,
wormhole effects, star class, ore compression, agents, missions, dungeons,
certificates.

## Answering a player, not a query

Most questions are not "run this SQL". They are questions where **the SDE gives
you a true fragment and the rest is judgement**, and a careful reader of this
skill can produce a flawless table that answers nothing the player asked. That
is a failure too.

What the SDE does **not** contain, so you will have to say so and then answer
anyway:

| Not in the SDE | Where it lives |
| --- | --- |
| Market prices (`basePrice` is a dead seed value) | ESI, or the in-game market |
| Population, traffic, kills, sovereignty | ESI |
| **What ore is in which asteroid belt or moon** | game knowledge — every belt row is `typeID = 15` and 344,456 of 344,457 moons are `typeID = 14` |
| NPC spawns, rat difficulty, site contents | game knowledge |
| Character skills, implants, boosters | the player's own character |
| Whether a thing is *good* | judgement |

Two standing habits:

- **Say which layer you are quoting.** Every ship number here is the untrained
  base hull; the player is looking at a trained, fitted ship. "A Rifter does
  365 m/s base" is honest, "a Rifter does 365 m/s" is not.
- **Answer the question under the question.** "Punisher or Rifter" is not a
  request for two stat blocks — it is "which should I fly", and the useful
  content is that three mid slots means tackle and five lows means brick. Quote
  the data, then say what it means.

## If you read nothing else

These eight prevent more wrong answers than anything else in the package. Full
treatment in the `gotchas-*` files.

- **Name matching is case-sensitive, and names contain apostrophes.**
  `WHERE name = 'rifter'` returns zero rows, silently — write
  `WHERE name = ? COLLATE NOCASE` and pass the name as a bound parameter
  (`db.execute(sql, (name,))`), which also survives `'Firewall' Signal
  Amplifier` and every `'Basic'` module.
- `unitID = 108` means the value is **inverted** — `0.4` is 60% resist, not 40%.
- Filter `space = 'kspace'` **before** any security comparison; wormhole, abyssal
  and void systems all store `security = -0.99`.
- High-sec is `security >= 0.45`, not `>= 0.5` — `security` is unrounded.
- Join gates on `stargates.destSystemID`, never `destStargateID` (the peer
  *gate*). Note `destStargateID` comes **first** in the table, so `SELECT *` with
  positional unpacking builds the graph on the wrong column.
- Hauling uses `packagedVolume`, not `volume`. They are **equal for 25,347
  published types** and differ for 685, by anything from 2x to 200x — never
  assume a ratio, read both columns.
- Manufacturing cost per unit is `bp_materials.quantity / bp_products.quantity` —
  a run can make 1 or 5,000 (10,000 for reactions), so reading materials alone is
  off by nearly four orders of magnitude.
- **Every ship value is pre-skill.** A Rifter's 365 m/s and 4.73 s align are the
  untrained hull; a player reading their own ship sees different numbers. Say
  "base hull". Resistances are the exception — they are skill-independent.

## Table names and keys

Two conventions, and guessing wrong costs a turn every time:

- **25 hand-shaped tables** use snake_case names and real ID columns:
  `types.typeID`, `type_dogma.attributeID`, `market_groups.marketGroupID`,
  `systems.solarSystemID`. Note `groups_` has a trailing underscore (`group` is
  reserved in SQL), and multi-word names are snake_case — it is `market_groups`,
  not `marketGroups`. **The name column is always bare `name`**, never CCP's
  classic `typeName` / `groupName` / `solarSystemName`: it is `types.name`,
  `groups_.name`, `systems.name`, `regions.name`.
- **The other 81** were ingested generically, keep CCP's own table name, and are
  keyed on **`_key`**, not a named ID: `typeBonus._key`, `dogmaUnits._key`,
  `planetSchematics._key`, `mapStars._key`. It is nearly every table in `world`
  and `cosmetic`, a minority in `items`, and mixed elsewhere — **check with
  `PRAGMA table_info`, do not assume**. `JOIN typeBonus tb ON tb.typeID =
  t.typeID` fails with `no such column`; the join is `ON tb._key = t.typeID`.

  **Do not use casing to tell the two groups apart.** It looks like camelCase
  means generic, but twelve generic tables are plain lowercase words —
  `missions`, `dungeons`, `certificates`, `masteries`, `skins`, `graphics`,
  `icons`, `landmarks`, `bloodlines`, `ancestries`, `schools`, `archetypes` —
  and they are indistinguishable by name from hand-shaped `types` or `systems`.
  The only reliable test is whether a `_key` column exists.

  Two exceptions: **`factions` and `races` have no `_key`** — they use
  `factionID` and `raceID`.

  `_key` is not always a typeID. `planetSchematics._key` is a schematicID and
  `planetResources._key` is a mixed planetID/starID space
  (`references/gotchas-universe.md`, and `references/schema.md` for
  `planetSchematics`).

When unsure, ask the database rather than guessing:

```python
db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
db.execute("PRAGMA table_info(typeBonus)").fetchall()
```

Full column reference is in `references/schema.md`.

## IDs you will need constantly

```
categoryID   6 Ship · 7 Module · 8 Charge · 9 Blueprint · 16 Skill
             17 Commodity · 18 Drone · 20 Implant · 25 Asteroid · 4 Material
attributeID  9 hp (structure) · 263 shieldCapacity · 265 armorHP · 37 maxVelocity
             482 capacitorCapacity · 55 rechargeRate · 479 shieldRechargeRate
             48 cpuOutput · 11 powerOutput · 14/13/12 hi/med/lowSlots · 1137 rigSlots
             102 turretSlotsLeft · 101 launcherSlotsLeft · 552 signatureRadius
             564 scanResolution · 76 maxTargetRange · 283 droneCapacity
             1271 droneBandwidth · 70 agility (inertia!) · 600 warpSpeedMultiplier
weapons      64 damageMultiplier · 114/116/117/118 em/exp/kin/thermDamage
             51 `speed` = rate of fire, in MILLISECONDS (not velocity — that is 37)
resistances  shield 271/274/273/272 · armor 267/270/269/268 · structure 113/110/109/111
             (EM/Thermal/Kinetic/Explosive — the client's order, not the ID order)
```

**Anchor on attributeIDs, not names**, for anything in a family — resistances,
sensor strength. Names in those families lie; see `references/gotchas-dogma.md`.
Tech level has three disagreeing sources and is a filtering question — see
`references/gotchas-types.md`.

## Check the build first

Every count in this skill was verified against build **3466501**. Before quoting
any figure from the reference files, check what you actually have:

```sql
SELECT key, value FROM meta;   -- sdeBuildNumber, sdeReleaseDate, builtAt, source, complete, splitGroup, positions
```

**Qualify it as `universe.meta` if you have ATTACHed several parts** — every
part has its own `meta` and an unqualified read silently picks one.

Note this check is against the **docs'** build, to know whether the documented
counts still hold. Whether your *database* is current is a different check —
CCP's `latest.jsonl` endpoint, in "Get a database" step 1. A long-lived
session can pass the first check and still be answering from a build CCP has
since replaced.

If `sdeBuildNumber` differs from 3466501, **run
`scripts/verify_claims.py --parts <dir>`** (or `--db <file>`): every hard number
in these docs is encoded there as a query, and it prints exactly which
documented figures moved on the newer build, so you re-derive three numbers
instead of all of them. Without it, re-derive anything you quote. The *shapes* —
which column lies, which join silently drops rows — are stable across builds;
the numbers are not.

Published parts carry `complete = '1'`, `positions = '1'` and no `portable` key.
Anything else is a hand-built database: `positions` other than `'1'` means verify
a coordinate before promising a distance (`SELECT x FROM systems WHERE
name='Jita'`), and `portable = '1'` means the `moons` table **exists but is
empty**, so moon questions return zero rows instead of raising — see
`references/acquisition.md`.

## Get a database

Work down this list and stop at the first that succeeds. Environments differ in
what they can reach, so do not assume any one of them works.

**1. Already present.** If a `.sqlite` is on disk, use it — after a staleness
check when the sandbox has network: CCP's current build is one GET away
(`https://developers.eveonline.com/static-data/tranquility/latest.jsonl`,
fields `buildNumber` / `releaseDate`). If it is newer than your
`meta.sdeBuildNumber`, re-fetch the parts you need (seconds — see
`references/acquisition.md`, including the two overwrite snags) and re-run
`scripts/verify_claims.py`. If you stay on the older file — no network, or the
user declines — **say which build and release date you are answering from**;
never silently quote stale data as current. Check once per session, not per
question.

**2. Uploaded to the conversation.** The only option in a sandbox with no
outbound access, and it costs nothing to check first. Decompress every
`.sqlite.xz` you were given and **keep its published name** —
`eve-sde-<group>.sqlite`, which is what everything downstream expects.
`references/acquisition.md` has the loop if you want it.

**3-5. Fetch or build one.** If neither of the above worked and the sandbox has
outbound network, read `references/acquisition.md`: it covers the prebuilt
release (fastest), building from CCP with `scripts/build_sde_db.py`
(authoritative), and Fuzzwork (last resort, different schema).

## Which parts a question needs

Parts are `universe`, `moons`, `items`, `world`, `industry`, `cosmetic`, `misc`
— each a complete database. Fetch only what the question needs:

| Question | Parts | Note |
| --- | --- | --- |
| Planets, routes, security | `universe` | |
| Ship and module stats | `items` | |
| Build costs | `items` + `industry` | |
| Reprocessing / ore yields | `items` (+ `universe`) | `type_materials` is **not** in `industry`; station rates are on `npc_stations` |
| Planet **types** (`Planet (Temperate)`) | `items` + `universe` | **never add `published = 1`** — every map typeID is `published = 0`, so it returns zero rows silently |
| A specific moon's physical stats | `moons` | add `universe` only to name the system; moon *composition* is not in the SDE |
| Stations | `universe` + `items` + `world` | `npc_stations` has **no name column**; names, services and owners come from `types`, `stationOperations`, `stationServices`, `npcCorporations` |
| Planetary industry chains | `industry` + `items` | `planetSchematics` |
| Wormhole system effects | `universe` + `items` | `mapSecondarySuns`, then the beacon's dogma |
| Abyssal / insurgency weather | `misc` + `items` | `appliedProximityEffects`, group `Cloud` — the SDE has only some strengths, see `references/gotchas-universe.md` |
| Fighter abilities, high-sec bans | `misc` + `items` | `fighterAbilitiesByType` → `fighterAbilities`; the restriction is on the ability, not the fighter |
| Factions, races, missions, agents, dungeons | `world` | not `universe` |

**`moons` is a separate part.** *Counting* moons does not need it —
`planets.moons` and `planets.belts` are denormalised and exact. Anything about a
specific moon does, and without it the query raises `no such table: moons`,
failing loudly rather than answering wrongly.

## Attaching several parts

Each part is a normal database; `meta.splitGroup` names it. ATTACH the ones you
need and join across them normally:

```python
import os, sqlite3
db = sqlite3.connect(":memory:")
for g in ("items", "universe"):
    path = f"eve-sde-{g}.sqlite"
    assert os.path.exists(path), path      # see the warning below
    db.execute(f"ATTACH DATABASE '{path}' AS {g}")
db.execute("SELECT t.name FROM universe.planets p JOIN items.types t ON t.typeID=p.typeID ...")
```

**`ATTACH` on a missing file does not error — it creates an empty database.** The
failure then surfaces as `no such table: items.types` on the next query, which
points at the schema when the real fault is the filename. Check the path exists
first, or a typo costs you a long detour.

**Unqualified table names resolve across attached databases**, in attach order,
so `SELECT * FROM types` works even when `types` lives in an attached part — the
examples in `references/` are written unqualified for that reason. The one table
you must always qualify is **`meta`**, which exists in all seven parts, so an
unqualified read silently returns whichever attached first.

**Never pull a big table into your context.** `moons` is 344k rows, `types` 52k,
`type_dogma` 645k — a bare `SELECT *` on any of them floods the conversation and
buries the answer. Aggregate in SQL, `LIMIT` what you print, and report counts,
not rows.

There is no `sqlite3` CLI on many systems; Python's built-in module needs none.

**Prefer the `eve-sde` MCP server when it is registered.** `query` runs many
statements in one call (every part pre-attached, `-- comment` labels, row caps,
one bad statement never kills the batch); `attrs` returns **unit-corrected**
values, which is the only way to read resonances and millisecond attributes
without the inversions below biting. Raw SQL stays available for anything they
do not cover.

## Coordinates

`x`, `y`, `z` on systems, planets, moons, belts and stargates are in **metres**;
divide by `9.4607304725808e15` for light years. Raw metres are meaningless to a
player. Confirm `meta.positions = '1'`, or just read one back
(`SELECT x FROM systems WHERE name='Jita'`), before promising a distance.
