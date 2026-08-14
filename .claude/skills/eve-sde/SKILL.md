---
name: eve-sde
description: Query the EVE Online Static Data Export (SDE) - ships, modules, dogma attributes, blueprints and manufacturing, reprocessing yields, and the New Eden universe (regions, systems, planets, moons, stargates, stations). Use whenever a question involves EVE Online game data such as ship stats, fitting attributes, build materials, ore yields, system security, planet or moon data, jump routes, market groups, or type/group/category lookups. Covers building the local SQLite database and querying it with SQL.
---

# EVE Online SDE

The SDE is CCP's static game-data export: everything in EVE that isn't live
player state. This skill covers getting it into SQLite and querying it.

**Not in the SDE:** market prices, kills, sovereignty, character or corp data.
Those are live data — use ESI (`https://esi.evetech.net`) instead.

**The failure mode here is wrong answers, not errors.** The SDE is full of
columns that look like the thing you want and are not: resonance is inverted,
`security` alone does not mean nullsec, a millisecond column displays as "s".
Almost every trap returns a plausible number rather than raising. So read the
relevant `references/gotchas-*.md` **before** trusting a result, not after one
looks odd.

## Files

| File | Read it when |
| --- | --- |
| `references/gotchas-items.md` | any ship or module stat, resistance, dogma attribute, tech level, volume or hauling question |
| `references/gotchas-universe.md` | any system, planet, moon, star, security, region or routing question |
| `references/gotchas-industry.md` | any build cost, blueprint or invention question — and reprocessing yields, which live in `items.type_materials` |
| `references/schema.md` | you need column names, you are joining tables you have not used before, **or you need to find which table holds something** — it indexes the 13 generic tables worth knowing, out of 81 |
| `references/schema.md` (world section) | missions, agents, NPC corporations, dungeons, DED ratings, certificates, factions or races — the traps there are severe and live nowhere else |
| `references/examples.md` | a resistance, blueprint-material, reprocessing, ship-skill, planet, gate or security-band query — adapt one rather than composing from scratch |
| `references/acquisition.md` | no database is present and none was uploaded — how to fetch or build one |

The three `gotchas-*` files map onto the download parts, so it is one decision:
fetch `universe`, read `gotchas-universe.md`.

**Coverage is not uniform.** `items`, `universe` and `industry` are documented
in depth. The `world` part has traps but no gotcha file — they are in
`schema.md`'s world section. **`cosmetic` and `misc` are documented nowhere**:
skins, graphics, icons, `fighterAbilities`, `dbuffCollections` and roughly 60
other generically ingested tables have no notes at all. For those, list
`sqlite_master`, `PRAGMA table_info`, and say plainly that the shape is
unverified rather than inferring it.

**Tables you would not guess exist**, all indexed in `schema.md`: ship traits
(`typeBonus`), mutaplasmid roll ranges (`dynamicItemAttributes`), PI chains
(`planetSchematics`), wormhole system effects (`mapSecondarySuns`), star class
(`mapStars`), ore compression (`compressibleTypes`), NPC agents
(`npcCharacters`), missions, dungeons and certificates.

## If you read nothing else

These six prevent more wrong answers than anything else in the package. Full
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
- **The other 81** were ingested generically, keep CCP's camelCase name, and
  is keyed on **`_key`**, not a named ID: `typeBonus._key`, `dogmaUnits._key`,
  `planetSchematics._key`, `mapStars._key`. Counting domain tables (excluding
  `meta`, which every part has): 8 of 18 in `items`, 8 of 13 in `industry`,
  7 of 14 in `universe`, 36 of 38 in `world`, 17 of 17 in `cosmetic`. So it is
  nearly everything in `world` and `cosmetic` but a minority in the three parts
  most questions touch — **check, do not assume either way**.
  `JOIN typeBonus tb ON tb.typeID = t.typeID` fails with `no such column`; the
  join is `ON tb._key = t.typeID`.

  Two exceptions: **`factions` and `races` have no `_key`** — they use
  `factionID` and `raceID`.

  `_key` is not always a typeID. `planetSchematics._key` is a schematicID and
  `planetResources._key` is a mixed planetID/starID space — see the gotchas.

When unsure, ask the database rather than guessing:

```python
db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
db.execute("PRAGMA table_info(typeBonus)").fetchall()
```

Full column reference is in `references/schema.md`.

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

`portable = '1'` marks a slimmed build (see below). Published parts carry
`complete = '1'` and no `portable` key at all.

A `--portable` database omits item descriptions, unpublished types and the
`moons` table. On one, do **not** filter on `published` (everything present is
published), do not promise moon data, and do not quote descriptions. Note that
dropping unpublished types removes **every planet type** — all ten are
`published = 0` — so planet-type questions cannot be answered from a portable
build at all. Published releases are never portable.

## Get a database

Work down this list and stop at the first that succeeds. Environments differ in
what they can reach, so do not assume any one of them works.

**1. Already present.** If a `.sqlite` is on disk, use it. Check `meta` as above.

**2. Uploaded to the conversation.** The only option in a sandbox with no
outbound access, and it costs nothing to check first:

```python
import gzip, lzma, bz2, shutil, sqlite3, pathlib

OPENERS = {".xz": lzma.open, ".gz": gzip.open, ".bz2": bz2.open}
for src in pathlib.Path(".").glob("*.sqlite*"):        # adjust to the upload path
    if src.suffix in OPENERS:                          # eve-sde-items.sqlite.xz
        with OPENERS[src.suffix](src) as f, open(src.stem, "wb") as o:
            shutil.copyfileobj(f, o)                   # -> eve-sde-items.sqlite
```

**Decompress every part and keep its published name.** Several are usually
uploaded together, and everything downstream expects `eve-sde-<group>.sqlite`.
Renaming one to `sde.sqlite` is the same failure as a mistyped path, described
under "Attaching several parts" below.

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
- A specific moon's gravity, radius or orbit — `universe` + `moons`.
- Ship and module stats — `items` alone.
- Build costs — `items` + `industry`.
- Planet **types** (`Planet (Temperate)`) — `items` + `universe`; planets live in
  one and their type names in the other. **Do not add `published = 1` to that
  join**: every celestial type is `published = 0`, so it returns zero rows
  silently. Full note in `gotchas-items.md`.
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

There is no single combined download: one file only fits the upload limit by
dropping 3D coordinates, so the parts are the published form.

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
