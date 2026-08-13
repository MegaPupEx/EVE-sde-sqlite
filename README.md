# eve-sde-sqlite

Builds the current EVE Online Static Data Export into a compact, indexed SQLite
database — small enough to upload anywhere — plus a Claude skill documenting the
schema and the traps in the data.

```bash
python3 build_sde_db.py                    # curated: 26 tables, 93 MB   (~20s)
python3 build_sde_db.py --complete         # everything: 107 tables, 148 MB
python3 build_sde_db.py --compress xz      # + .xz for upload  (14 MB / 27 MB)
python3 build_sde_db.py --complete --split # one file per domain (largest 18 MB)
python3 build_sde_db.py --portable         # smaller still, drops descriptions
```

`--complete` adds moon statistics as real columns plus 81 further tables —
missions, dungeons, NPC agents and corporations, ship trait bonuses,
certificates, planetary schematics, stars, skins. Those extra tables are
generic-ingested, so nested fields are JSON: query them with `json_extract()`.
The curated 26 tables are hand-shaped either way.

`--split` emits one database per domain — items, universe, industry, world,
cosmetic, misc. Each stands alone, and SQLite can `ATTACH` several and join
across them, so splitting costs nothing at query time. Since the 30 MB upload
cap is per *file*, this removes the ceiling: the largest part is 18 MB.

Standard library only. The script reads CCP's build manifest at runtime, so it
always fetches the current build. Needs `developers.eveonline.com`.

## Prebuilt downloads

[**Releases**](../../releases/latest) carries `eve-sde-full.sqlite.xz` — the
complete 107-table build, ~27 MB — rebuilt automatically within hours of each
CCP release. Skip the build entirely:

```bash
curl -sSLo sde.xz https://github.com/MegaPupEx/EVE-sde-sqlite/releases/latest/download/eve-sde-full.sqlite.xz
xz -d sde.xz
```

`.github/workflows/sde-release.yml` polls every 3 hours, rebuilds only when the
build number changes, and refuses to publish unless the archive round-trips and
passes an integrity check.

## Using it with Claude

`.claude/skills/eve-sde/` loads automatically in this repo. To use it elsewhere:

```bash
cp -r .claude/skills/eve-sde ~/.claude/skills/     # every project on this machine
```

For Claude apps, zip that folder and upload it under Settings → Capabilities →
Skills, then attach the `.xz` to a conversation. xz matters here: it fits the
30 MB per-file upload limit with room to spare, where gzip does not.

## Schema

26 tables, 40 indexes. Items (`types`, `groups_`, `categories`, `market_groups`),
attributes (`type_dogma`, `dogma_attributes`, `type_effects`), industry
(`blueprints`, `bp_materials`, `bp_products`, `bp_skills`, `type_materials`), and
the universe (`regions`, `systems`, `planets`, `moons`, `asteroid_belts`,
`stargates`, `npc_stations`). `meta` records which SDE build it came from.

Full column reference, query examples, and the data traps are in
[`.claude/skills/eve-sde/SKILL.md`](.claude/skills/eve-sde/SKILL.md). Four worth
knowing before writing any query:

- **Damage resonance is inverted** — `0.4` means 60% resist.
- **`security` alone does not identify nullsec** — wormhole, abyssal and void
  systems all read `-0.99`. Filter `space = 'kspace'`.
- **Ship skill requirements are dogma** (`requiredSkill1..6`), not `bp_skills`.
- **`basePrice` is not a market price** and is empty for most items.

Not in the SDE at all: market prices, kills, sovereignty, character data. Those
are live — use [ESI](https://esi.evetech.net).

## Compared to Fuzzwork

[Fuzzwork](https://www.fuzzwork.co.uk/dump/) has published SDE conversions for
years and is the established source. Same underlying data — row counts match
exactly on everything both contain.

|  | this | Fuzzwork |
| --- | --- | --- |
| Size | 93 MB / **14 MB** compressed | 497 MB / 162 MB |
| Tables | 26, purpose-built | 176, full classic schema |
| Formats | SQLite | SQLite, MySQL, PostgreSQL, MSSQL, CSV |
| Extras | `space` column, documented traps, Claude skill | historical builds |

With `--complete` this covers the same ground in 148 MB against Fuzzwork's
497 MB, because text is English-only rather than eight languages. Fuzzwork
still wins on non-SQLite formats and its archive of past builds.
