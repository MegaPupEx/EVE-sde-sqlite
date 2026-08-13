# eve-sde-sqlite

Builds the current EVE Online Static Data Export into a compact, indexed SQLite
database — small enough to upload anywhere — plus a Claude skill documenting the
schema and the traps in the data.

```bash
python3 build_sde_db.py                    # -> sde.sqlite   (~20s, 93 MB)
python3 build_sde_db.py --compress xz      # -> +.xz          (~14 MB)
python3 build_sde_db.py --portable         # smaller, drops descriptions/moons
```

Standard library only. The script reads CCP's build manifest at runtime, so it
always fetches the current build. Needs `developers.eveonline.com`.

## Prebuilt downloads

[**Releases**](../../releases/latest) carries `eve-sde-full.sqlite.xz`, rebuilt
automatically within hours of each CCP release. Skip the build entirely:

```bash
curl -sSLo sde.xz https://github.com/MegaPupEx/Test/releases/latest/download/eve-sde-full.sqlite.xz
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
| Extras | `space` column, documented traps, Claude skill | agents, certificates, ship traits, historical builds |

Use Fuzzwork if you need agents, certificates, ship traits, planetary
schematics, or a non-SQLite format — this build omits them. Use this one if the
database has to be small enough to upload, or you want the traps written down.
