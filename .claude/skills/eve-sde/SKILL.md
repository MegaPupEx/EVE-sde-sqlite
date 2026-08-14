---
name: eve-sde
description: Query the EVE Online Static Data Export (SDE) - ships, modules, dogma attributes, blueprints and manufacturing, reprocessing yields, and the New Eden universe (regions, systems, planets, moons, stargates, stations). Use whenever a question involves EVE Online game data such as ship stats, fitting attributes, build materials, ore yields, system security, planet or moon data, jump routes, market groups, or type/group/category lookups. Covers building the local SQLite database and querying it with SQL.
---

# EVE Online SDE

The SDE is CCP's static game-data export: everything in EVE that isn't live
player state. This skill covers getting it into SQLite and querying it.

**Not in the SDE:** market prices, kills, sovereignty, character or corp data.
Those are live data — use ESI (`https://esi.evetech.net`) instead.

**Two failure modes.** The first is wrong answers rather than errors — see
below. The second is answering the query instead of the player; see "Answering a
player, not a query".

**The failure mode here is wrong answers, not errors.** The SDE is full of
columns that look like the thing you want and are not: resonance is inverted,
`security` alone does not mean nullsec, a millisecond column displays as "s".
Almost every trap returns a plausible number rather than raising. So read the
relevant `references/gotchas-*.md` **before** trusting a result, not after one
looks odd.

## Files

| File | Read it when |
| --- | --- |
| `references/gotchas-dogma.md` | what a ship or module **value means** — resistances, units, capacitor, speed, sensors, skill requirements |
| `references/gotchas-types.md` | **which rows belong** — `published`, tech level, volume vs `packagedVolume`, `basePrice`, planet type names, duplicate names |
| `references/gotchas-universe.md` | any system, planet, moon, star, security, region or routing question |
| `references/gotchas-industry.md` | any build cost, blueprint or invention question — and reprocessing yields, which live in `items.type_materials` |
| `references/schema.md` | you need column names, you are joining tables you have not used before, **or you need to find which table holds something** — it indexes the ~11 generic tables worth knowing (of 81), plus `factions` and `races` |
| `references/schema.md` (world section) | missions, agents, NPC corporations, dungeons, DED ratings, certificates, factions or races — the traps there are severe and live nowhere else |
| `references/examples.md` | **try this first for any straightforward stat, blueprint, reprocessing, planet, gate or security query** — its first example is the reusable shape for plain "what is X's Y" stat questions, though its attribute list is only nine scalars — anything outside them needs the ID block below |
| `references/acquisition.md` | no database is present and none was uploaded — how to fetch or build one |

The `gotchas-*` files follow the download parts, so fetching usually decides
reading too: fetch `universe`, read `gotchas-universe.md`. Two exceptions —
`items` has **two** files (`gotchas-dogma.md` for what a value means,
`gotchas-types.md` for which rows belong), and reprocessing is documented in
`gotchas-industry.md` although `type_materials` lives in the `items` part.

**Coverage is not uniform.** `items`, `universe` and `industry` are documented
in depth. The `world` part has traps but no gotcha file — they are in
`schema.md`'s world section. **`cosmetic` and `misc` are documented nowhere**:
skins, graphics, icons, `fighterAbilities` and roughly 60 other generically
ingested tables have no notes at all. (`misc.dbuffCollections` is the one
exception — its ID-collision trap is in `gotchas-universe.md`.) For those, list
`sqlite_master`, `PRAGMA table_info`, and say plainly that the shape is
unverified rather than inferring it.

**Tables you would not guess exist**, all indexed in `schema.md`: ship traits
(`typeBonus`), mutaplasmid roll ranges (`dynamicItemAttributes`), PI chains
(`planetSchematics`), wormhole system effects (`mapSecondarySuns`), star class
(`mapStars`), ore compression (`compressibleTypes`), NPC agents
(`npcCharacters`), missions, dungeons and certificates.

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

These seven prevent more wrong answers than anything else in the package. Full
treatment in the `gotchas-*` files.

- `unitID = 108` means the value is **inverted** — `0.4` is 60% resist, not 40%.
- Filter `space = 'kspace'` **before** any security comparison; wormhole, abyssal
  and void systems all store `security = -0.99`.
- High-sec is `security >= 0.45`, not `>= 0.5` — `security` is unrounded.
- Join gates on `stargates.destSystemID`, never `destStargateID` (the peer
  *gate*). Note `destStargateID` comes **first** in the table, so `SELECT *` with
  positional unpacking builds the graph on the wrong column.
- Hauling uses `packagedVolume`, not `volume` (assembled, ~11x larger).
- Manufacturing cost per unit is `bp_materials.quantity / bp_products.quantity` —
  a run can make 1 or 10,000, so reading materials alone is off by up to four
  orders of magnitude.
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
- **The other 81** were ingested generically, keep CCP's camelCase name, and are
  keyed on **`_key`**, not a named ID: `typeBonus._key`, `dogmaUnits._key`,
  `planetSchematics._key`, `mapStars._key`. By part: `cosmetic` 17 of 17, `world` 36 of 38,
  `industry` 8 of 13, `universe` 7 of 14, `items` 8 of 18 — so it is the rule in
  some parts and the exception in others. **Check, do not assume either way.** `JOIN typeBonus tb ON tb.typeID = t.typeID` fails
  with `no such column`; the join is `ON tb._key = t.typeID`.

  Two exceptions: **`factions` and `races` have no `_key`** — they use
  `factionID` and `raceID`.

  `_key` is not always a typeID. `planetSchematics._key` is a schematicID and
  `planetResources._key` is a mixed planetID/starID space (`gotchas-universe.md`,
  and `schema.md` for `planetSchematics`).

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

If you have ATTACHed several parts, **qualify this** — `universe.meta` — because
every part has its own `meta` and an unqualified read silently picks one.

If `sdeBuildNumber` differs from 3466501, **re-derive counts rather than quoting
them**. The *shapes* — which column lies, which join silently drops rows, which ID
space overlaps another — are stable across builds; the numbers are not.

`positions = '1'` means coordinates are present. Anything else — the value `'0'`,
or the key missing entirely because the build was not `--complete` — means
**verify before promising a distance**, since the key is only written on complete
builds and its absence proves nothing either way:

```sql
SELECT x FROM systems WHERE name = 'Jita';   -- NULL = no coordinates in this build
```

`complete = '1'` marks a full build; published parts always carry it.

`portable = '1'` marks a hand-built slimmed database — see `acquisition.md`.
Published releases never carry the key at all. On a portable build the `moons`
table still **exists but is empty**, so moon questions return zero rows rather
than raising `no such table`; check `meta` before reading absence as fact.

## Get a database

Work down this list and stop at the first that succeeds. Environments differ in
what they can reach, so do not assume any one of them works.

**1. Already present.** If a `.sqlite` is on disk, use it. Check `meta` as above.

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

The published parts are `universe`, `moons`, `items`, `world`, `industry`,
`cosmetic` and `misc` — each a complete database. Fetch only what the question
needs:

- Planets, routes, security — `universe` alone.
- Stations — `universe` for where they are, but **`npc_stations` has no name
  column**. Naming one, or listing its services or owner, needs `items.types`
  (structure type), `world.stationOperations` / `world.stationServices` and
  `world.npcCorporations`.
- A specific moon's **physical stats** — gravity, radius, orbit — `moons` alone;
  add `universe` only to name the system it is in. Moon *composition* is not in
  the SDE at all.
- Ship and module stats — `items` alone.
- Build costs — `items` + `industry`.
- Planet **types** (`Planet (Temperate)`) — `items` + `universe`; planets live in
  one and their type names in the other. **Do not add `published = 1` to that
  join**: every celestial type is `published = 0`, so it returns zero rows
  silently. Full note in `gotchas-types.md`.
- Reprocessing and ore yields — `items` for `type_materials`, plus `universe`
  if you want a realistic yield (station rates are on `npc_stations`).
  `type_materials` is **not** in `industry`.
- Planetary industry chains — `industry` (`planetSchematics`) + `items` for the
  input and output names.
- Wormhole system effects — `universe` (`mapSecondarySuns`) + `items` for the
  beacon's magnitudes.
- Faction or race names — `world`, not `universe`.
- Missions, agents, dungeons, certificates — `world`.

**`moons` is a separate part from `universe`.** Counting moons does not need it:
`planets.moons` and `planets.belts` are denormalised counts, verified exact
against the moon rows. Anything about a *specific* moon does, and without it the
query raises `no such table: moons` — it fails loudly rather than answering
wrongly.

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
so `SELECT * FROM types` works even when `types` lives in an attached part. The
examples in `references/` are written unqualified for that reason and need no
rewriting. Prefixing is still clearer in a cross-part join, and is *required* in
one case:

**`meta` exists in all seven parts.** An unqualified `SELECT ... FROM meta`
silently returns whichever part attached first — so a build check can report the
wrong `splitGroup`, or read `positions` from a part that has coordinates while
the one you are querying does not. Always qualify it: `SELECT key, value FROM
universe.meta`.

There is no `sqlite3` CLI on many systems; Python's built-in `sqlite3` module
needs no install.

## Coordinates

`x`, `y`, `z` on systems, planets, moons, belts and stargates are in **metres**;
divide by `9.4607304725808e15` for light years. Raw metres are meaningless to a
player. Confirm `meta.positions = '1'`, or just read one back
(`SELECT x FROM systems WHERE name='Jita'`), before promising a distance.
