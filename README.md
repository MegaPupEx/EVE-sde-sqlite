# eve-sde-sqlite

CCP ships EVE Online's static data as ~100 JSONL files. This turns them into one
indexed SQLite database, and documents the traps in the data.

## Download

[**Releases**](../../releases/latest) carries the current build, republished
within hours of each CCP release:

```bash
curl -sSLo sde.xz https://github.com/MegaPupEx/eve-sde-sqlite/releases/latest/download/eve-sde.sqlite.xz
xz -d sde.xz
```

Also split by domain — `items`, `universe`, `industry`, `world`, `cosmetic`,
`misc` — for when one file is inconvenient. Each part is a complete database;
`ATTACH` several to join across them. Largest part is ~18 MB.

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

```sql
SELECT p.celestialIndex, t.name, p.radius, p.surfaceGravity
FROM planets p
JOIN systems s ON s.solarSystemID = p.solarSystemID
JOIN types   t ON t.typeID = p.typeID
WHERE s.name = 'TK-DLH';
```

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
