# Worked examples

Queries that are correct against the traps documented in the `gotchas-*` files.
Prefer adapting one of these to writing from scratch.

These are written **unqualified** (`types`, `type_dogma`). SQLite resolves an
unqualified name across `main` and every ATTACHed database, so they run as-is
whether you opened one part directly or attached several -- no rewriting needed.
The one table you must always qualify is `meta`, which exists in every part.

**Each example names the parts it needs.** A `no such table` here means a part
is not open, not that the query is wrong.

```sql
-- ship fitting stats                              [needs: items]
-- Safe to match on name here ONLY because these nine are isolated scalars.
-- Do not extend this template to resistances, resonances, sensor strength or
-- tech level -- those are families where the name lies. Use attributeIDs.
SELECT a.name, d.value
FROM type_dogma d
JOIN dogma_attributes a ON a.attributeID = d.attributeID
JOIN types t ON t.typeID = d.typeID
WHERE t.name = 'Rifter'
  AND a.name IN ('hp','shieldCapacity','armorHP','maxVelocity',
                 'cpuOutput','powerOutput','hiSlots','medSlots','lowSlots');

-- what a blueprint consumes, via its product      [needs: industry + items]
SELECT mt.name, m.quantity
FROM bp_materials m
JOIN types mt ON mt.typeID = m.typeID
JOIN bp_products p ON p.blueprintTypeID = m.blueprintTypeID
                  AND p.activity = m.activity
JOIN types t ON t.typeID = p.typeID
WHERE t.name = 'Rifter' AND m.activity = 'manufacturing'
ORDER BY m.quantity DESC;

-- reprocessing yield, normalised per unit         [needs: items]
SELECT mt.name, m.quantity * 1.0 / t.portionSize AS per_unit
FROM type_materials m
JOIN types t  ON t.typeID = m.typeID
JOIN types mt ON mt.typeID = m.materialTypeID
WHERE t.name = 'Veldspar';

-- planets in a system with physical data          [needs: universe + items]
-- planets live in universe, their type names in items -- this fails on
-- universe alone with "no such table: types".
SELECT p.celestialIndex, ty.name, p.radius, p.surfaceGravity, p.temperature, p.moons
FROM planets p
JOIN systems s ON s.solarSystemID = p.solarSystemID
JOIN types  ty ON ty.typeID = p.typeID
WHERE s.name = 'TK-DLH'
ORDER BY p.celestialIndex;

-- gate neighbours                                 [needs: universe]
SELECT s2.name, s2.security, r.name AS region
FROM stargates g
JOIN systems s1 ON s1.solarSystemID = g.solarSystemID
JOIN systems s2 ON s2.solarSystemID = g.destSystemID
JOIN regions  r ON r.regionID = s2.regionID
WHERE s1.name = 'Jita';

-- all published ships in a hull class             [needs: items]
-- There is no hull-size column -- "cruiser", "battleship" etc. exist only as
-- group names, so a class is a list of groups you curate. Battleship-sized is
-- Battleship + Marauder + Black Ops. Curated lists for the T2 cruiser and
-- frigate classes are in gotchas-types.md; do not invent your own.
SELECT t.name, t.mass, t.volume
FROM types t
JOIN groups_ g ON g.groupID = t.groupID
WHERE g.name = 'Battleship' AND t.published = 1
ORDER BY t.name;

-- security bands across known space               [needs: universe]
SELECT CASE WHEN security >= 0.45 THEN 'high'
            WHEN security >  0.0  THEN 'low'
            ELSE 'null' END AS band, COUNT(*)
FROM systems WHERE space = 'kspace'
GROUP BY band;

-- Resistances as the client shows them            [needs: items]
-- All three layers, client damage-type
-- order, and the always-on role bonus applied. Checked against EVE Workbench's
-- base-hull panel for the Rifter (0/20/40/50, 60/35/25/10, 33/33/33/33) and the
-- Onyx (20/84/76/60, 50/86/63/10, 33/33/33/33) -- a fitting tool, not the
-- client itself, so treat it as strong corroboration rather than proof.
-- Fitting tools round to integers; the exact values here are 86.25 and 62.5.
WITH layer(attributeID, layer, dmg, ord) AS (
  VALUES (271,'Shield','EM',1),   (274,'Shield','Thermal',2),
         (273,'Shield','Kinetic',3), (272,'Shield','Explosive',4),
         (267,'Armor','EM',1),    (270,'Armor','Thermal',2),
         (269,'Armor','Kinetic',3),  (268,'Armor','Explosive',4),
         (113,'Structure','EM',1),(110,'Structure','Thermal',2),
         (109,'Structure','Kinetic',3), (111,'Structure','Explosive',4)
)
SELECT l.layer, l.dmg,
       ROUND((1 - d.value * (1 + COALESCE(rb.value, 0) / 100.0)) * 100, 2) AS resist_pct
FROM types t
CROSS JOIN layer l
JOIN type_dogma d ON d.typeID = t.typeID AND d.attributeID = l.attributeID
LEFT JOIN type_dogma rb ON rb.typeID = t.typeID       -- always-on role bonus
     AND rb.attributeID = CASE l.layer WHEN 'Armor'  THEN 1825
                                       WHEN 'Shield' THEN 1829 END
WHERE t.name = 'Onyx'
ORDER BY CASE l.layer WHEN 'Shield' THEN 1 WHEN 'Armor' THEN 2 ELSE 3 END, l.ord;

-- what skills a ship requires (dogma, not bp_skills)  [needs: items]
-- ONE HOP ONLY. Skills have their own requiredSkill* attributes, so this
-- under-reports: on a Drake it returns "Caldari Battlecruiser I" and misses
-- Caldari Cruiser III, Destroyer III, Frigate III and Spaceship Command III.
-- Recurse over the result for "what do I need to fly this".
SELECT sk.name, lvl.value AS level
FROM type_dogma req
JOIN dogma_attributes ra ON ra.attributeID = req.attributeID AND ra.name LIKE 'requiredSkill_'
JOIN types t   ON t.typeID = req.typeID
JOIN types sk  ON sk.typeID = CAST(req.value AS INT)
JOIN type_dogma lvl ON lvl.typeID = t.typeID
JOIN dogma_attributes la ON la.attributeID = lvl.attributeID
     AND la.name = ra.name || 'Level'
WHERE t.name = 'Rifter';
```

## Elsewhere

Two query shapes deliberately live next to the trap they depend on rather than
here, to avoid a copy drifting out of sync:

- **Shortest-route BFS over the stargate graph** — `gotchas-universe.md`, beside
  the warning that the graph is disconnected and a route may not exist.
- **Resolving `systems.factionID` / `types.raceID` to a name** — `schema.md`.

