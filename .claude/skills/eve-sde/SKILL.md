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
| `references/gotchas-industry.md` | any build cost, blueprint, invention or reprocessing question |
| `references/schema.md` | you need column names, or are joining tables you have not used before |
| `references/examples.md` | before writing a query from scratch — adapt one of these instead |
| `scripts/build_sde_db.py` | no database is available and you can reach `developers.eveonline.com` |

These map onto the download parts below, so the routing is the same decision:
fetch `universe`, read `gotchas-universe.md`.

## Table names and keys

Two conventions, and guessing wrong costs a turn every time:

- **26 hand-shaped tables** use snake_case names and real ID columns:
  `types.typeID`, `type_dogma.attributeID`, `market_groups.marketGroupID`,
  `systems.solarSystemID`. Note `groups_` has a trailing underscore (`group` is
  reserved in SQL), and multi-word names are snake_case — it is `market_groups`,
  not `marketGroups`.
- **Everything else** was ingested generically, keeps CCP's camelCase name, and
  is keyed on **`_key`**, not a named ID: `typeBonus._key`, `dogmaUnits._key`,
  `planetSchematics._key`, `mapStars._key`. This is most tables —
  8 of 19 in `items`, 8 of 14 in `industry`, 7 of 15 in `universe`, 36 of 39 in
  `world`. `JOIN typeBonus tb ON tb.typeID = t.typeID` fails with
  `no such column`; the join is `ON tb._key = t.typeID`.

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
SELECT * FROM meta;   -- sdeBuildNumber, sdeReleaseDate, builtAt, source, splitGroup
```

If `sdeBuildNumber` differs from 3466501, **re-derive counts rather than quoting
them** — CCP adds ships, systems and blueprints every release. The *shapes* (which
column lies, which join silently drops rows, which ID space overlaps another) are
stable across builds and remain trustworthy; the numbers attached to them are not.

Two other `meta` keys change what is safe to say:

```sql
SELECT value FROM meta WHERE key = 'portable';    -- '1' = slimmed, see below
SELECT value FROM meta WHERE key = 'positions';   -- absent = x/y/z are NULL
```

A `--portable` database omits item descriptions, unpublished types and the
`moons` table. On one, do **not** filter on `published` (everything present is
published), do not promise moon data, and do not quote descriptions.

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
    if src.suffix in OPENERS:
        with OPENERS[src.suffix](src) as f, open("sde.sqlite", "wb") as o:
            shutil.copyfileobj(f, o)
        break
    if src.suffix == ".sqlite":
        shutil.copy(src, "sde.sqlite")
        break
db = sqlite3.connect("sde.sqlite")
```

**3. Prebuilt release** — fastest when reachable, already integrity checked, no
build step. Releases carry the SDE **split by domain**; fetch only the parts the
question needs:

```bash
BASE=https://github.com/MegaPupEx/eve-sde-sqlite/releases/latest/download
curl -sSLO $BASE/eve-sde-universe.sqlite.xz && xz -d eve-sde-universe.sqlite.xz
curl -sSLO $BASE/eve-sde-items.sqlite.xz    && xz -d eve-sde-items.sqlite.xz
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

Use `curl -O`, not `-o name.xz`: `xz -d` on a file called `universe.xz` yields
`universe`, and every example expects `eve-sde-universe.sqlite`.

`latest` always resolves to the newest release; a workflow republishes within
hours of each CCP build. The repository is public, so no authentication is
needed — but it is a single personal repo, so treat a failure here as "cannot
reach it, move on" and fall through. GitHub answers 404 rather than 403 for
anything it will not serve, so a failure never proves the release is gone.

**4. Build from CCP** — authoritative, ~20 s, downloads ~99 MB. Standard library
only. Needs `developers.eveonline.com`:

```bash
python3 scripts/build_sde_db.py --complete    # ~147 MB, all 107 tables
```

To produce upload-sized files for a sandbox with no network:

```bash
python3 scripts/build_sde_db.py --complete --positions --split --parts-only --compress xz
```

**Use xz, not gzip** — gzip does not get the parts under the 30 MB per-file
upload limit on claude.ai; xz does, with room to spare.

**5. Fuzzwork's prebuilt dump** — last resort. Same data, **different schema**
(classic `invTypes` / `mapSolarSystems` naming), so nothing in `references/`
applies:

```bash
curl -sO https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz && gunzip latest-sqlite.db.gz
```

## Which parts a question needs

- Planets, routes, security, stations — `universe` alone.
- A specific moon's gravity, radius or orbit — `universe` + `moons`.
- Ship and module stats — `items` alone.
- Build costs — `items` + `industry`.
- Planet **types** (`Planet (Temperate)`) — `items` + `universe`; planets live in
  one and their type names in the other.
- Faction or race names — `world`, not `universe`.

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

Examples in `references/` are written **unqualified** (`types`, `type_dogma`),
which works when a part is opened directly. If you attached parts under names,
prefix every table — `items.types`, `universe.systems`.

There is no `sqlite3` CLI on many systems; Python's built-in `sqlite3` module
needs no install.

## Coordinates

`x`, `y`, `z` on systems, planets, moons, belts and stargates are in **metres**;
divide by `9.4607304725808e15` for light years. Raw metres are meaningless to a
player. A build made without `--positions` has them NULL — check
`meta.positions` before promising a distance.
