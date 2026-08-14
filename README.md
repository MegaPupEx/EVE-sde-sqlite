# eve-sde-sqlite

CCP ships EVE Online's static data as ~100 JSONL files. This turns them into one
indexed SQLite database, and documents the traps in the data.

## Download

[**Releases**](../../releases/latest) carries the SDE split by domain,
republished within hours of each CCP release. Fetch only what a question needs:

| Part | Size | Covers |
| --- | --- | --- |
| `eve-sde-moons.sqlite.xz` | ~20 MB | all 344k moons with physical statistics |
| `eve-sde-universe.sqlite.xz` | ~8 MB | systems, planets, belts, gates, stations, 3D coordinates |
| `eve-sde-items.sqlite.xz` | ~7 MB | types, dogma attributes and effects, reprocessing |
| `eve-sde-world.sqlite.xz` | ~1.4 MB | missions, dungeons, agents, corps, certificates |
| `eve-sde-industry.sqlite.xz` | ~0.5 MB | blueprints, schematics, assembly lines |
| `eve-sde-cosmetic.sqlite.xz` | ~0.4 MB | skins, graphics, icons |
| `eve-sde-misc.sqlite.xz` | ~0.01 MB | the remainder |

Moons are their own part because they are 344,457 rows — over half the universe
data — and are asked about far less often than systems and planets.

```bash
BASE=https://github.com/MegaPupEx/eve-sde-sqlite/releases/latest/download
curl -sSLO $BASE/eve-sde-universe.sqlite.xz
curl -sSLO $BASE/eve-sde-items.sqlite.xz
xz -d eve-sde-*.sqlite.xz
```

Use `-O`, not `-o name.xz` — the examples below expect the files to keep their
published names.

Each part is a complete SQLite database. `ATTACH` several to join across them —
splitting costs nothing at query time. Together they reassemble to the whole
export exactly: same tables, same row counts.

Split rather than one file because the 30 MB upload limit on claude.ai is **per
file**. One combined archive fits only by dropping the 3D coordinates; as parts,
everything fits with room to spare. Build one locally with
`--complete --compress xz` if you would rather have a single file.

## Build

```bash
python3 build_sde_db.py --complete                        # 107 tables, 147 MB
python3 build_sde_db.py --complete --compress xz          # + 27 MB archive
python3 build_sde_db.py --complete --split --compress xz  # one file per domain
```

Standard library only. Reads CCP's build manifest at runtime, so it always
fetches the current build. Needs `developers.eveonline.com`.

| Flag | Effect |
| --- | --- |
| *(none)* | 26 hand-shaped tables: items, dogma, industry, universe |
| `--complete` | +81 tables and moon statistics — missions, dungeons, agents, ship traits, certificates, schematics |
| `--split` | one database per domain |
| `--compress {xz,gz,bz2}` | compressed copy; xz reaches 27 MB |
| `--portable` | drops descriptions, unpublished types, moons |

`--complete`'s extra tables are generic-ingested, so nested fields are JSON —
query with `json_extract()`. The 26 core tables are hand-shaped either way.

## Query

Planet types live in `items` and planets live in `universe`, so this needs both
parts attached — most real questions cross a part boundary:

```python
import sqlite3
db = sqlite3.connect(":memory:")
db.execute("ATTACH DATABASE 'eve-sde-universe.sqlite' AS universe")
db.execute("ATTACH DATABASE 'eve-sde-items.sqlite'    AS items")

db.execute('''
  SELECT p.celestialIndex, t.name, p.radius, p.surfaceGravity
  FROM universe.planets p
  JOIN universe.systems s ON s.solarSystemID = p.solarSystemID
  JOIN items.types      t ON t.typeID = p.typeID
  WHERE s.name = 'TK-DLH'
  ORDER BY p.celestialIndex''').fetchall()
```

There is no `sqlite3` CLI on many systems; Python's built-in `sqlite3` module
needs no install. **`ATTACH` on a path that does not exist silently creates an
empty database** — so a mistyped filename surfaces later as `no such table`,
pointing at your SQL instead of at the typo.

Four things produce wrong answers rather than errors:

- **Damage resonance is inverted** — `0.4` means 60% resist.
- **`security` alone does not identify nullsec** — wormhole, abyssal and void
  systems all read `-0.99`. Filter `space = 'kspace'`.
- **Ship skill requirements are dogma** (`requiredSkill1..6`), not `bp_skills`.
- **`basePrice` is not a market price** and is empty for most items.

Full column reference and the rest of the traps:
[`.claude/skills/eve-sde/SKILL.md`](.claude/skills/eve-sde/SKILL.md).

Not in the SDE: market prices, kills, sovereignty, character data. Those are
live — use [ESI](https://esi.evetech.net).

## With Claude

The skill loads automatically in this repo. Elsewhere:

```bash
cp -r .claude/skills/eve-sde ~/.claude/skills/     # every project on this machine
```

For Claude apps, zip that folder and upload it under Settings → Capabilities →
Skills, then attach a `.xz` to the conversation. xz matters: it fits the 30 MB
per-file upload limit where gzip does not.

## Automation

`.github/workflows/sde-release.yml` polls CCP every 3 hours and rebuilds only
when the build number changes, so a typical run costs seconds and downloads
nothing. It refuses to publish unless every archive round-trips, passes an
integrity check, and fits the upload limit.
