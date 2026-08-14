# Worked examples

Queries that are correct against the traps documented in the `gotchas-*` files.
Prefer adapting one of these to writing from scratch.

## Examples

These are written **unqualified** (`types`, `type_dogma`), which works when a
part is opened directly as the main database. If you ATTACHed parts under names,
prefix every table -- `items.types`, `universe.systems`. Unprefixed queries
against attached parts fail with `no such table`, which looks identical to the
mistyped-filename failure and is easy to misdiagnose as a bad path.

```sql
-- ship fitting stats
SELECT a.name, d.value
FROM type_dogma d
JOIN dogma_attributes a ON a.attributeID = d.attributeID
JOIN types t ON t.typeID = d.typeID
WHERE t.name = 'Rifter'
  AND a.name IN ('hp','shieldCapacity','armorHP','maxVelocity',
                 'cpuOutput','powerOutput','hiSlots','medSlots','lowSlots');

-- what a blueprint consumes, found via its product
SELECT mt.name, m.quantity
FROM bp_materials m
JOIN types mt ON mt.typeID = m.typeID
JOIN bp_products p ON p.blueprintTypeID = m.blueprintTypeID
                  AND p.activity = m.activity
JOIN types t ON t.typeID = p.typeID
WHERE t.name = 'Rifter' AND m.activity = 'manufacturing'
ORDER BY m.quantity DESC;

-- reprocessing yield, normalised per unit
SELECT mt.name, m.quantity * 1.0 / t.portionSize AS per_unit
FROM type_materials m
JOIN types t  ON t.typeID = m.typeID
JOIN types mt ON mt.typeID = m.materialTypeID
WHERE t.name = 'Veldspar';

-- planets in a system with physical data
SELECT p.celestialIndex, ty.name, p.radius, p.surfaceGravity, p.temperature, p.moons
FROM planets p
JOIN systems s ON s.solarSystemID = p.solarSystemID
JOIN types  ty ON ty.typeID = p.typeID
WHERE s.name = 'TK-DLH'
ORDER BY p.celestialIndex;

-- gate neighbours
SELECT s2.name, s2.security, r.name AS region
FROM stargates g
JOIN systems s1 ON s1.solarSystemID = g.solarSystemID
JOIN systems s2 ON s2.solarSystemID = g.destSystemID
JOIN regions  r ON r.regionID = s2.regionID
WHERE s1.name = 'Jita';

-- all published ships in a hull class. There is no hull-size column: "cruiser",
-- "battleship" etc. exist only as group names, so a class is a list of groups
-- (Battleship + Marauder + Black Ops + Force Auxiliary...) you curate yourself.
SELECT t.name, t.mass, t.volume
FROM types t
JOIN groups_ g ON g.groupID = t.groupID
WHERE g.name = 'Battleship' AND t.published = 1
ORDER BY t.name;

-- security bands across known space (note the space filter)
SELECT CASE WHEN security >= 0.45 THEN 'high'
            WHEN security >  0.0  THEN 'low'
            ELSE 'null' END AS band, COUNT(*)
FROM systems WHERE space = 'kspace'
GROUP BY band;

-- Resistances as the client shows them: all three layers, client damage-type
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

-- what skills a ship requires (dogma, not bp_skills)
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
