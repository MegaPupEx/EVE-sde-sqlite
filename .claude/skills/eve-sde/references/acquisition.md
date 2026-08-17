# Getting a database when none is present

Three things live here: the decompression loop for parts **uploaded to the
conversation**, how to **fetch or build** a database when none is present, and
what a `--portable` build leaves out. Work down and stop at the first that
succeeds — the numbering starts at 3 because steps **1** (already on disk) and
**2** (uploaded) live in SKILL.md's "Get a database".

**3. Prebuilt release** — fastest when reachable, already integrity checked, no
build step. Releases carry the SDE **split by domain**; fetch only the parts the
question needs:

```bash
BASE=https://github.com/MegaPupEx/EVE-sde-sqlite-Claude-skill/releases/latest/download
curl -sSLO $BASE/eve-sde-universe.sqlite.xz && xz -d eve-sde-universe.sqlite.xz
curl -sSLO $BASE/eve-sde-items.sqlite.xz    && xz -d eve-sde-items.sqlite.xz
```

| Part | Size | Covers |
| --- | --- | --- |
| `universe` | ~8 MB | systems, planets, belts, stargates, stations, 3D coordinates |
| `moons` | ~20.5 MB | all 344k moons with physical statistics |
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

Because `latest` tracks CCP, a fresh download is usually a **newer build than
the one this skill's counts were verified against**. That is fine — run
`scripts/verify_claims.py --parts .` and it prints which documented figures
moved, if any (see "Check the build first" in SKILL.md).

## Refreshing mid-session

CCP's current build is always one GET away:
`https://developers.eveonline.com/static-data/tranquility/latest.jsonl`
(`buildNumber`, `releaseDate`). When it is newer than your
`meta.sdeBuildNumber` — or the user asks for the newest SDE — re-fetching
works at any point in a session; `latest` always serves the current release
and the builder always builds it. Two snags make a naive refresh fail:

1. **`xz -d` refuses to overwrite** an existing `.sqlite` — use `xz -df`, or
   delete the old parts first.
2. **Open connections keep the old file.** An ATTACHed database is the file as
   it was opened; close and reopen every connection after replacing the parts,
   or half your queries silently answer from the old build.

After a refresh, re-run `scripts/verify_claims.py --parts .` so you know which
documented counts moved on the new build.

**Sizes are the compressed `.xz` download at the preset the builder uses**
(`preset=9|PRESET_EXTREME`). This matters for `moons`, the only part near the
30 MB cap: 20.5 MB at 9e but **24.0 MB at xz's default preset 6**, so
recompressing a part yourself gives the larger figure. Uncompressed, the three
large parts are roughly universe 22 MB, moons 68 MB, items 53 MB — plan disk
against those.

**4. Build from CCP** — authoritative. Downloads ~99 MB and takes **well under
a minute** on a fast link (measured 29 s and 41 s); needs ~1.5 GB of temporary
disk. Do not treat this as the slow fallback — download speed dominates, and
the output is byte-for-byte the size of the release. Standard library only. Needs
`developers.eveonline.com`:

```bash
python3 scripts/build_sde_db.py --complete --positions   # ~162 MB, 107 tables (106 domain + meta)
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

## Decompressing uploaded parts

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
under "Attaching several parts" in SKILL.md.

## `--portable` builds

A `--portable` database drops item descriptions and unpublished types, empties
the `moons` table, and sets `meta.portable = '1'`. Note *empties*, not drops:
`moons` still exists and returns zero rows, so moon questions fail silently
rather than raising `no such table`. On one, do **not** filter on
`published` (everything present is published), do not promise moon data, and do
not quote descriptions from `types`, `dogma_attributes` or `factions` -- those
are the three the builder nulls; `market_groups`, `regions`, `races`,
`dogma_effects` and `dungeons` descriptions survive. Dropping unpublished types
removes **every planet
type** — all ten are `published = 0` — so planet-type questions cannot be
answered from a portable build at all. Published releases are never portable.
