# Gotchas: items, dogma and ships

For the `items` part. Read before answering anything about ship or module
stats, resistances, tech level, volumes or hauling.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs. The shapes stay true across builds, the numbers do not.

## Units: read `unitID`, not the name

`dogma_attributes.unitID` decides what a value means, and the `dogmaUnits` table
names each one -- but `dogmaUnits` has **no `unitID` column**; the unit number is
in `_key`, so the join is
`JOIN dogmaUnits u ON u._key = a.unitID`.

Attribute *names* are not a reliable guide -- this is the single richest source
of confidently wrong answers in the dataset. Note also that **`unitID` and
`attributeID` are separate ID spaces that overlap**: attributeID 101 is
`launcherSlotsLeft`, unitID 101 is "milliseconds", and the two have nothing to
do with each other. Read the table below as unit numbers, not attribute numbers.
(Shield recharge is attributeID **479**; capacitor recharge is 55.)

| unitID | Meaning | Trap |
| --- | --- | --- |
| **108** | Inverse absolute percent: `0.0` = 100%, `1.0` = 0% | **58 attributes defined (57 actually used), 69,032 rows.** Only 24 are named `*DamageResonance`; the rest -- `stasisWebifierResistance`, `ECMResistance`, `sensorDampenerResistance`, `energyWarfareResistance`, `remoteRepairImpedance` -- read as if higher were better |
| **101** | **Milliseconds**, but `displayName` says "s" | **92 attributes, 40,522 rows.** `rechargeRate` on a Rifter is `125000` = 125 s, not 125,000 |
| 3, 123 | Actual seconds | Sits beside unitID 101 with nothing in the schema to distinguish them |
| 109 | Modifier percent: `1.1` = +10%, `0.9` = -10% | `0.75` means **-25%**, not 75% |
| 105 / 121 / 124 / 127 | Four more percent conventions | `-50` = -50%, `5` = 5%, `0.5` = 50% -- all display as `%` |

Worked example -- "which ship resists webs best?":

```sql
-- WRONG: names suggest higher is better
SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value DESC;              -- Bantam, Condor, Griffin at 1.0

-- RIGHT: unitID 108 is inverted
SELECT t.name, ROUND((1 - d.value) * 100, 1) AS pct FROM type_dogma d
JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value ASC;               -- Erebus, Leviathan, Avatar at 80%
```

The naive answer names T1 frigates as the best web-resisters. They are the
**worst**, at 0%. `highIsGood` does not save you -- `remoteRepairImpedance` is
inverted and flagged `highIsGood = 1`.

Two more name traps: **`agility` (70) is the Inertia Modifier**, so "most agile"
by either sort direction is wrong -- align time is
`ln(4) * inertia * mass / 1e6`. And **attribute 51 is named `speed` but means
rate of fire**, in milliseconds; ship velocity is `maxVelocity` (37).

**SQLite's `LOG()` is base 10, not natural.** `LOG(4)` returns 0.602, not
1.386, so `LOG(4) * inertia * mass / 1e6` gives align times about 2.3x too
fast -- 1.7 s for a T2 frigate instead of 4.0 s. The ranking is unchanged,
which is exactly why the error survives a sanity check. Use `LN(4)`, or the
literal `1.386294`.

- **Resonance is not resistance; it is inverted.** `armorEmDamageResonance =
  0.4` means **60% resist**, not 40%. Resist % is `(1 - value) * 100`. The rule
  is **`unitID = 108`**, not the name -- see "Units" above; 19 inverted
  attributes have no "resonance" anywhere in the name (58 carry unitID 108, of
  which 24 end in `DamageResonance` and 39 contain "resonance" somewhere).
- **A ship's structure resistance is the bare set (109, 110, 111, 113), and it
  is 33% on every published ship.** The `hull*DamageResonance` family (974-977)
  is **not** the ship-side attribute, despite the name and the identical
  `displayName`. It is the *module* side of a modifier: a Damage Control's own
  `hull*` values are the bonus it grants, and the effect writes them onto the
  ship's bare attributes. `dogma_effects.modifierInfo` for effect 2302
  (`damageControl`) says so outright:

  ```
  113 (emDamageResonance)        <- 974 (hullEmDamageResonance)
  111 (explosiveDamageResonance) <- 975 (hullExplosiveDamageResonance)
  109 (kineticDamageResonance)   <- 976 (hullKineticDamageResonance)
  110 (thermalDamageResonance)   <- 977 (hullThermalDamageResonance)
  ```

  23 of the 24 effects that touch structure resonance target the bare set --
  Damage Control, Bastion, hull resistance bonuses, system-wide storms. Only
  `moduleBonusAssaultDamageControl` targets `hull*`, and it is modifying an
  Assault Damage Control module, not a hull.

  All **423 of 423** published ships carry the bare set at exactly `0.67`, none
  missing -> **33% structure resist to all four damage types, on every ship**,
  matching what fitting tools show. By category, `hull*` belongs to 44
  starbases, 42 modules, 22 celestials, 14 ships and 8 entities -- restricted to
  `published = 1`, 42 starbases, 34 modules, 9 ships and 1 celestial. Either
  way it is overwhelmingly module and structure furniture; those 9 published
  ships are the anomaly, and their `1.0` is not what the client displays. **Do
  not use 974-977 for a ship**, and do not read a missing `hull*` row as 0%
  structure resistance. The Rifter is one of the 9 that carries both, so it is
  the worst possible ship to test the rule on -- `hull*` gives 0% where the
  client shows 33%.

  The three layers therefore live in different ID blocks, and structure's is not
  contiguous:

  | Layer | EM | Thermal | Kinetic | Explosive |
  | --- | --- | --- | --- | --- |
  | Shield | 271 | 274 | 273 | 272 |
  | Armor | 267 | 270 | 269 | 268 |
  | Structure | 113 | 110 | 109 | **111** |

  112 is `energyDamageAbsorptionFactor` and is not a resonance, so
  `BETWEEN 109 AND 112` silently swaps one real value for a junk row.
- **The client's damage-type order is not the attributeID order.** Every EVE UI
  lists resists **EM, Thermal, Kinetic, Explosive**. The IDs run **EM,
  Explosive, Kinetic, Thermal** (267/268/269/270). Selecting
  `BETWEEN 267 AND 270` and labelling the results in the client's order swaps
  thermal and explosive -- a Rifter's armor becomes 60/10/25/35 instead of
  60/35/25/10. Label from `a.name`, or order explicitly.
- **Some hulls have an always-on role bonus that is not in the resonance
  value.** An Onyx's stored shield resonances are byte-identical to an Eagle's
  and a Cerberus's, but the client shows 20/84/76/60 where the raw values give
  0/80/70/50. The difference is `rookieShieldResistBonus` (1829) = `-20` plus
  four passive `ItemModifier` effects, applied as
  `resonance * (1 + bonus/100)`. The complete list -- the name "rookie" is
  misleading, four of the six shield cases are Heavy Interdiction Cruisers:

  | Attribute | -20 | -12 | -8 |
  | --- | --- | --- | --- |
  | 1829 shield | Onyx, Broadsword, Fiend, Laelaps | Taipan | Ibis |
  | 1825 armor | Devoter, Phobos, Gold Magnate, Silver Magnate | -- | Impairor (and the unpublished AIR Civilian Astero) |

  **Both attributes are near-invisible to the usual navigation.** They are
  `published = 0` with `displayName` and `unitID` NULL, and `highIsGood = 1` on
  an attribute where negative is the good direction -- so reading `unitID` or
  trusting `displayName` finds nothing. They *are* findable by name or
  description (`rookieArmorResistanceBonus` / "Bonus to armor resistances",
  `rookieShieldResistBonus` / "Shield resistance bonus"), which is how to
  re-derive the list from `type_dogma` if the build has moved on -- do that
  rather than trusting the names above.

  The general rule, which covers more than resistances: **`typeBonus.roleBonuses`
  is always on and is already reflected in what the client shows; the per-skill
  bonuses in `typeBonus.types` scale with skill level and are not.** 90 published
  ships carry an effect that modifies one of the twelve core resonance
  attributes; the other 79 are per-skill-level ship bonuses (a Damnation gets 4%
  armor resist per level of Amarr Cruiser) and correctly do not apply to a base
  hull. Widen the definition to all 58 `unitID = 108` attributes and the count
  is 121, so say which you mean.

  Reading `roleBonuses` in prose is the quickest check -- the Onyx's says "20.0
  bonus to all shield resistances", the Damnation's does not mention resists --
  but two cautions. **The prose is not consistently cased** -- both Magnates say
  "bonus to all Armor Resistances" in title case while the other nine are lower
  case. SQLite's `LIKE` is case-insensitive for ASCII, so it catches all 11; but
  `GLOB` is case-sensitive and returns only 9, as does any matching you do in
  Python. And **`roleBonuses` is NULL for
  50 of the 423 ships**, the Rifter among them -- every published ship has a
  `typeBonus` row, but a row is not a value, so handle NULL rather than assuming
  the column is populated.
- **Four families of resonance attribute exist.** Always anchor the layer --
  by attributeID, per the table above -- because a bare
  `LIKE '%DamageResonance'` returns 16 rows for one ship. There is also a
  `passive*DamageResonance` family (1418-1429) whose display names differ from
  the active ones only in capitalisation; note that its four **`passiveHull*`
  members (1426-1429) are `unitID = 127`, not 108**, so the inversion rule does
  not apply to them. For resistances, select the attributeID family
  deliberately rather than joining on name.
- **Every ship value in the SDE is pre-skill.** Confirmed exactly against a
  fitting tool with all skills at 0: a Rifter reads 250 GJ capacitor, 125 s
  recharge, 22.5 km targeting, 365 m/s, 4.73 s align; an Onyx 1,250 GJ, 335 s,
  80 km, 200 m/s, 11.74 s. Every one is the raw `type_dogma` value. The same
  panels at all-V show 312.5 GJ / 93.75 s / 456 m/s / 3.55 s -- nothing in the
  SDE produces those. So say "base hull" when you quote a number, and never
  compare an SDE figure against one a player read off their own fitted ship.
  Resistances are the exception worth knowing: they are skill-independent, so
  base and trained agree (bar the always-on role bonuses above).
- **Sensor strength is four attributes, only one of them non-zero.** 208 radar,
  209 ladar, 210 magnetometric, 211 gravimetric -- a ship carries all four and
  zeroes the three that do not apply, so the displayed "sensor strength" is the
  max, and which attribute is non-zero *is* the sensor type. An Onyx is
  gravimetric 19, a Rifter ladar 8. Averaging or summing the four gives a
  quarter of the right answer with no error to notice.
- **Drone range is not a ship attribute.** Both an Onyx and a Rifter show 20 km
  at zero skills and 60 km trained, because it comes from the character's
  Drone Avionics skills. Nothing in `type_dogma` will give it to you.
- **Hauling capacity: `capacity` vs `volume` vs `packagedVolume`.** Cargo space
  is `types.capacity`, and what a packaged item takes up is
  `types.packagedVolume` -- **not `volume`**, which is the assembled size. A
  Rifter is 27,289 m3 assembled and 2,500 m3 packaged, so using `volume` makes
  every ship-hauling answer ~10.9x too pessimistic (685 published types
  differ between the two). `capacity` is NULL for 25,265
  published types (anything with no hold), so `ORDER BY capacity DESC` is fine
  but `WHERE capacity > x` silently drops them.

  The related trap: a **ship maintenance bay holds *assembled* ships**. The
  Bowhead's 1,600,000 m3 `shipMaintenanceBayCapacity` sounds enormous but fits
  only 58 Rifters, while a Charon's 465,000 m3 of ordinary cargo fits 186
  packaged ones. Freighter cargo figures in the SDE are also **pre-skill** --
  no Racial Freighter bonus applied.

- **Ship/module skill requirements are in dogma, not `bp_skills`.** They live in
  `requiredSkill1..6` (a typeID) paired with `requiredSkill1Level..6`.
  `bp_skills` is what a *blueprint activity* needs -- a different question.
  The Rifter needs `requiredSkill1 = 3329` (Minmatar Frigate) at level 1.
  **These do not recurse on their own.** Skills have their own
  `requiredSkill*` attributes, so "what do I need to fly this" means walking the
  tree: a Rifter also needs Spaceship Command I via Minmatar Frigate. One hop
  for a T1 frigate, several for T2 -- a single query under-reports.
- **`basePrice` is not a market price** and is 0 or NULL for 17,652 of 26,992
  published types. It is an internal seed value. For real prices use ESI; the
  SDE has none.

- **`published = 1` applies to market items, not everything.** It is right for
  ships, modules, charges and ore -- 26,992 of 52,863 types are published, the
  rest being test and unreleased content. But **every celestial type is
  `published = 0`**: all ten planet types, plus whole categories (Station,
  Effects, Bonus, Placeables, Abstract). Joining `planets` to `types` with
  `published = 1` returns **zero rows**, silently. Scope the filter to the
  question.
- **Planet type names are `Planet (Temperate)`, not `Temperate`.** Filtering on
  the bare word returns zero rows with no error -- the same silent-zero shape as
  the `published` mistake, and planetary-industry questions hit it constantly.
  The ten values are `Planet (Barren)`, `(Gas)`, `(Ice)`, `(Lava)`, `(Oceanic)`,
  `(Plasma)`, `(Shattered)`, `(Storm)`, `(Temperate)` and `(Scorched Barren)`.
  Those ten names span **17 rows** in `types` -- seven are duplicated across
  typeIDs -- so joining planets to their type *by name* multiplies rows. `planets`
  references exactly 10 typeIDs; join on `typeID`.

- **Tech level has three sources that disagree.** "How many published Tech II
  items are there?" answers 2,537 from `types.techLevel`, 2,434 from dogma
  attribute 422, and 1,892 from `metaGroupID = 2` -- and 43 types have a
  `techLevel` column that flatly contradicts their dogma. 19 published hulls are
  `techLevel = 2` but `metaGroupID = 4` (Faction) -- Utu, Freki, Malice -- with
  no invention path at all. **`metaGroupID = 2` is the one to trust** for "is
  this T2".

  But `metaGroupID = 2` is not the same as "a ship a player can fly". **7 of the
  121 published T2 hulls are Alliance Tournament and CONCORD special editions** --
  Chameleon, Enforcer, Hydra, Marshal, Pacifier, Tiamat, Whiptail. They are
  genuinely `metaGroupID = 2`, so "the fastest-aligning T2 frigate" answers
  *Hydra*, a tournament prize almost nobody owns, instead of the Ares. Their
  market group path runs through **`Special Edition Ships`** where a normal T2
  runs through `Frigates > Advanced Frigates`, so walk the tree to exclude them:

  ```sql
  WITH RECURSIVE up(typeID, mg) AS (
    SELECT typeID, marketGroupID FROM types WHERE categoryID = 6 AND published = 1
    UNION ALL
    SELECT u.typeID, g.parentGroupID FROM up u
    JOIN market_groups g ON g.marketGroupID = u.mg
  )
  SELECT DISTINCT up.typeID FROM up
  JOIN market_groups g ON g.marketGroupID = up.mg
  WHERE g.name = 'Special Edition Ships';        -- the 7 to exclude
  ```

  For any "best X" question, say which set you used -- obtainable hulls or all
  of them.

- **Names are not unique.** 12 published type names, 6 group names and 2
  attribute names are shared by more than one ID. Joining on name can duplicate
  rows -- resolve to an ID first when a query must return exactly one thing.

- **`groups_` has a trailing underscore** (`group` is reserved in SQL).

- 960 published types have `volume` NULL; `metaGroupID` and `techLevel` are
  populated for only ~26% and ~19% of types.

- Ore variant names changed: "Concentrated Veldspar" and "Dense Veldspar" no
  longer exist as types. The grades are now `Veldspar II-Grade` and similar.
