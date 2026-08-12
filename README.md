# Test

testing claude n making a project

## EVE Online SDE → SQLite

`build_sde_db.py` downloads the current EVE Online Static Data Export from CCP
and flattens it into a queryable SQLite database.

```bash
python3 build_sde_db.py            # -> sde.sqlite  (~16s, ~93 MB)
python3 build_sde_db.py --db eve.sqlite --keep-raw
```

Standard library only — no dependencies. The database is *not* committed: it is
derived data that rebuilds in seconds, and binary blobs bloat git history
permanently. The script always fetches the latest build, so re-running it is how
you update.

### Claude skill

`.claude/skills/eve-sde/SKILL.md` documents the schema, the query gotchas, and
worked examples. Claude loads it on demand when a question involves EVE data,
in this repo or anywhere the skill folder is copied (e.g. `~/.claude/skills/`).

### Requires network access to

| Host | Purpose |
| --- | --- |
| `developers.eveonline.com` | current SDE (build manifest + JSONL zip) |

The older `eve-static-data-export.s3-eu-west-1.amazonaws.com` mirror still
responds but has not been updated since 2025-07-07 — do not use it.

### Tables

| Area | Tables |
| --- | --- |
| Items | `types`, `groups_`, `categories`, `market_groups`, `meta_groups` |
| Attributes | `dogma_attributes`, `dogma_effects`, `type_dogma`, `type_effects` |
| Industry | `blueprints`, `bp_activity`, `bp_materials`, `bp_products`, `bp_skills`, `type_materials` |
| Universe | `regions`, `constellations`, `systems`, `planets`, `moons`, `asteroid_belts`, `stargates`, `npc_stations` |
| Misc | `factions`, `races`, `meta` (SDE build number + release date) |

Localised strings are reduced to English. `meta` records which SDE build the
database was made from.

### Examples

```sql
-- planet radii in a system
SELECT p.celestialIndex, t.name, p.radius, p.surfaceGravity, p.moons
FROM planets p
JOIN systems s ON s.solarSystemID = p.solarSystemID
JOIN types   t ON t.typeID = p.typeID
WHERE s.name = 'TK-DLH'
ORDER BY p.celestialIndex;

-- what a blueprint consumes
SELECT mt.name, m.quantity
FROM bp_materials m
JOIN types mt ON mt.typeID = m.typeID
JOIN bp_products p ON p.blueprintTypeID = m.blueprintTypeID AND p.activity = m.activity
JOIN types t ON t.typeID = p.typeID
WHERE t.name = 'Rifter' AND m.activity = 'manufacturing';

-- gate neighbours of a system
SELECT s2.name, s2.security
FROM stargates g
JOIN systems s1 ON s1.solarSystemID = g.solarSystemID
JOIN systems s2 ON s2.solarSystemID = g.destSystemID
WHERE s1.name = 'Jita';

-- a ship's fitting attributes
SELECT a.name, d.value
FROM type_dogma d
JOIN dogma_attributes a ON a.attributeID = d.attributeID
JOIN types t ON t.typeID = d.typeID
WHERE t.name = 'Rifter';
```

### Notes

- `stargates.destSystemID` is the destination *system*; `destStargateID` is the
  peer gate. The pre-2025 YAML SDE only gave the peer gate ID, which silently
  broke naive joins.
- `systems.security` is the unrounded security status (Jita is 0.9459, shown
  in-game as 0.9).
