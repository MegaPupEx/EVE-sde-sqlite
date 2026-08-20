# Gotchas: dogma and ship stats

For the `items` part. Read before answering **what a ship or module stat means**
— resistances, units, capacitor, speed, sensors, skills. For questions about
*which rows to select* (published, tech level, volumes, names) read
`gotchas-types.md` instead.

**"Best/fastest X hull" questions need both files** -- this one for the formula
and the unit trap, `gotchas-types.md` for which hulls are eligible.

Counts verified against build `3475087`; re-derive if `meta.sdeBuildNumber`
differs. **Every count here is population-sensitive** -- `published = 1` vs all
types, k-space vs all systems, ships vs all categories. Where the population is
not stated it is the whole table; if your query filters differently, re-derive
rather than quoting.

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
| **108** | Inverse absolute percent: `0.0` = 100%, `1.0` = 0% | **59 attributes, 69,050 rows.** Only 24 are named `*DamageResonance`; the rest -- `stasisWebifierResistance`, `ECMResistance`, `sensorDampenerResistance`, `energyWarfareResistance`, `remoteRepairImpedance` -- read as if higher were better |
| **101** | **Milliseconds**, but `displayName` says "s" | **92 attributes, 40,522 rows.** `rechargeRate` on a Rifter is `125000` = 125 s, not 125,000 |
| 3, 123 | Actual seconds | Sits beside unitID 101 with nothing in the schema to distinguish them |
| 109 | Modifier percent: `1.1` = +10%, `0.9` = -10% | `0.75` means **-25%**, not 75% |
| 9 / 128 | m3 and Mbit/sec | `droneCapacity` (9) is a volume, `droneBandwidth` (1271) is unitID **128** = Mbit/sec -- a Vexor's 125 m3 bay holds 12 Hammerhead IIs and its 75 Mbit/s allows 7 by bandwidth -- but the character's Drones skill caps you at **5 active**, which is in neither number (see the drone-cap bullet below) |
| 105 / 121 / 124 / 127 | Four more percent conventions | `-50` = -50%, `5` = 5%, `0.5` = 50% -- all display as `%` |

Worked example -- "which ship resists webs best?":

```sql
-- WRONG: names suggest higher is better
SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value DESC;              -- 409 of 423 ships tie at 1.0 (= 0% resist)

-- RIGHT: unitID 108 is inverted
SELECT t.name, ROUND((1 - d.value) * 100, 1) AS pct FROM type_dogma d
JOIN types t ON t.typeID = d.typeID
WHERE d.attributeID = 2115 AND t.published = 1 AND t.categoryID = 6
ORDER BY d.value ASC;               -- all eight titans tie at 80%
```

The naive answer names T1 frigates as the best web-resisters. They are the
**worst**, at 0%. `highIsGood` does not save you -- `remoteRepairImpedance` is
inverted and flagged `highIsGood = 1`.

**This attribute is also the tie trap in miniature**, so do not lift the top
rows of either query as an answer. There are exactly three distinct values
across the 423 published ships: 409 sit at 0%, six at 50% and the **eight
titans** (Avatar, Azariel, Erebus, Komodo, Leviathan, Molok, Ragnarok,
Vanquisher) at 80%. `LIMIT 3` on the correct query names three of eight and
reads as a podium; `LIMIT 3` on the wrong one names three of 409. Group by
`value` before you present a ranking -- see the tie rule in
`gotchas-universe.md`.

Two more name traps: **`agility` (70) is the Inertia Modifier**, so "most agile"
by either sort direction is wrong -- align time is
`ln(4) * inertia * mass / 1e6`. And **attribute 51 is named `speed` but means
rate of fire**, in milliseconds; ship velocity is `maxVelocity` (37).

**SQLite's `LOG()` is base 10, not natural.** `LOG(4)` returns 0.602, not
1.386, so `LOG(4) * inertia * mass / 1e6` gives align times exactly 2.3026x too
fast -- a Rifter reads **2.06 s instead of 4.73 s**. The ranking is unchanged,
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

  All **423 of 423** published ships carry the bare set at exactly `0.67` ->
  **33% structure resist to all four damage types, on every ship**. `hull*` is
  on 9 published ships, the Rifter among them, and reads 0% there. **Do not use
  974-977 for a ship**, and do not read a missing `hull*` row as 0% resistance.

  The three layers live in different ID blocks, and structure's is not
  contiguous:

  | Layer | EM | Thermal | Kinetic | Explosive |
  | --- | --- | --- | --- | --- |
  | Shield | 271 | 274 | 273 | 272 |
  | Armor | 267 | 270 | 269 | 268 |
  | Structure | 113 | 110 | 109 | **111** |

  112 is `energyDamageAbsorptionFactor`, not a resonance -- and it is attached to
  **zero types**, so `BETWEEN 109 AND 112` does not add a junk row: it silently
  returns **three** resistances instead of four, dropping EM (113) off the end.
  A missing layer is easier to overlook than an extra one.
- **The client's damage-type order is not the attributeID order.** Every EVE UI
  lists resists **EM, Thermal, Kinetic, Explosive**. The IDs run **EM,
  Explosive, Kinetic, Thermal** (267/268/269/270). Selecting
  `BETWEEN 267 AND 270` and labelling the results in the client's order swaps
  thermal and explosive -- a Rifter's armor becomes 60/10/25/35 instead of
  60/35/25/10. Label from `a.name`, or order explicitly.
- **Some hulls have an always-on role bonus that is not in the resonance
  value.** An Onyx's raw shield resonances give 0/80/70/50; the client shows
  20/84/76/60. The difference is `rookieShieldResistBonus` (1829) = `-20`,
  applied by four passive `ItemModifier` effects as `resonance * (1 + bonus/100)`. The complete list -- the name
  "rookie" is misleading, four of the six shield cases are HICs:

  | Attribute | -20 | -12 | -8 |
  | --- | --- | --- | --- |
  | 1829 shield | Onyx, Broadsword, Fiend, Laelaps | Taipan | Ibis |
  | 1825 armor | Devoter, Phobos, Gold Magnate, Silver Magnate | -- | Impairor (and the unpublished AIR Civilian Astero) |

  Both are `published = 0` with `displayName` and `unitID` NULL; search `name` or
  `description` (`rookieShieldResistBonus` / "Shield resistance bonus",
  `rookieArmorResistanceBonus` / "Bonus to armor resistances") to re-derive the
  list on a newer build.

  The general rule, wider than resistances: **`typeBonus.roleBonuses` is always
  on and already in what the client shows; the per-skill bonuses in
  `typeBonus.types` scale with skill level and are not** (a Damnation gets 4%
  armor resist per level of **Amarr Battlecruiser** -- the skill sits on the
  hull's own size band, not the cruiser one).

  **Do not screen on the prose alone**: 31 published ships mention "resist" in
  `roleBonuses` and only 11 carry 1825/1829. The 20 false positives are EWAR
  resistances -- every titan and supercarrier, the deep-space transports, the
  Monitor. Confirm against `type_dogma` 1825/1829. Two further cautions: casing
  is inconsistent (`LIKE` is case-insensitive, `GLOB` and Python are not), and
  **`roleBonuses` is NULL for 50 of the 423**, the Rifter included -- every ship
  has a `typeBonus` row, but a row is not a value.
- **A few hulls sit far outside the normal resist range**, so "which ship
  resists X best" does not land where a player expects. The **Monitor** (T2 Flag
  Cruiser) carries **90% on all four shield layers** and tops every one of them.
  It does not top them outright -- the faction **Cybele** ties it exactly on
  kinetic (both store `0.1`). Below those, the next-best hull **differs on every
  damage type** and is frequently a multi-way tie, so there is no stable
  runner-up to name. **Derive it per layer**, with the eligibility filter the
  question implies, rather than quoting one from another layer:

  ```sql
  SELECT t.name, mg.name AS meta,
         ROUND((1 - d.value * (1 + COALESCE(rb.value,0)/100.0)) * 100, 1) AS pct
  FROM type_dogma d
  JOIN types t USING(typeID)
  LEFT JOIN meta_groups mg ON mg.metaGroupID = t.metaGroupID
  LEFT JOIN type_dogma rb ON rb.typeID = t.typeID AND rb.attributeID = 1829
  WHERE d.attributeID = 271        -- 271/274/273/272 = EM/Th/Kin/Exp shield
    AND t.published = 1 AND t.categoryID = 6
  ORDER BY pct DESC LIMIT 10;
  ```

  Report the ties as ties. Two limits of that query: `meta_groups.name` separates
  `Faction`, but the **7 Alliance Tournament and CONCORD hulls are genuinely
  `Tech II`** and are indistinguishable here -- exclude them with the
  `Special Edition Ships` market-group walk in `gotchas-types.md` if the question
  implies obtainable hulls. And it hard-codes the **shield** role bonus
  (`1829`); for armor (267-270) swap it to **`1825`**.
- **Ship/module skill requirements are in dogma, not `bp_skills`.** They live in
  `requiredSkill1..6` (a typeID) paired with `requiredSkill1Level..6`.
  `bp_skills` is what a *blueprint activity* needs -- a different question.
  The Rifter needs `requiredSkill1 = 3329` (Minmatar Frigate) at level 1.
  **These do not recurse on their own.** Skills have their own
  `requiredSkill*` attributes, so "what do I need to fly this" means walking the
  tree: a Rifter also needs Spaceship Command I via Minmatar Frigate. One hop
  for a T1 frigate, several for T2 -- a single query under-reports.
- **Four families of resonance attribute exist.** Always anchor the layer --
  by attributeID, per the table above -- because a bare
  `LIKE '%DamageResonance'` returns **12** rows for a typical ship and **16** for
  the 9 that also carry `hull*` -- so the count itself varies by hull. There is also a
  `passive*DamageResonance` family (1418-1429). **`displayName` cannot identify
  a resonance attribute in any layer.** Only the EM pairs differ, and only in
  case (`Armor EM` vs `Armor Em`); thermal, kinetic and explosive are
  byte-identical between the active and passive families in armor and shield
  alike. Structure is worse still: **all four** of its display names are three-way
  collisions -- `Structure EM Damage Resistance` is shared by 113, 974 and 1426,
  and thermal, kinetic and explosive collide the same way (110/977/1429,
  109/976/1428, 111/975/1427). Match on attributeID, never on `displayName`.
  Note also that the four **`passiveHull*` members (1426-1429) are
  `unitID = 127`, not 108**, so the inversion rule does not apply to them. For resistances, select the attributeID family
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
  max, and which attribute is non-zero *is* the sensor type -- for 421 of 423
  published ships. The **Apotheosis (10/10/10/10)** and **Council Diplomatic
  Shuttle (8/8/8/8)** carry all four, so "the non-zero one is the sensor type"
  gives four contradictory answers there; use `MAX()`, which is right either way. An Onyx is
  gravimetric 19, a Rifter ladar 8. Averaging or summing the four gives a
  quarter of the right answer with no error to notice.
- **Weapon and drone damage has no ship-side attribute, and no DPS is stored.**
  Damage lives on the *weapon or drone item*: `damageMultiplier` (64) and the
  four damage types `emDamage` (114), `explosiveDamage` (116), `kineticDamage`
  (117), `thermalDamage` (118). Rate of fire is **attribute 51, named `speed`**
  and in milliseconds. So
  `dps = damageMultiplier * (em+exp+kin+therm) / (attr51 / 1000)`. The hull's
  contribution is prose in `typeBonus`, not a number in dogma.
- **Mining yield is `miningAmount / duration`, and `duration` is milliseconds.**
  `miningAmount` (77) is m3 per cycle (unitID 9); `duration` (73) is unitID 101,
  so a Miner I at 10 m3 / `15000` is **0.67 m3/s**, not 0.00067. Ship mining
  bonuses are per-skill-level prose in `typeBonus`, and the Venture's +100% is a
  role bonus -- always on.
- **A fighter's high-sec restriction is not on the fighter.** It lives on the
  *ability*: `misc.fighterAbilitiesByType` (`_key` = typeID, all 94 published
  fighters) gives three JSON `abilitySlot0..2` columns, and
  `misc.fighterAbilities.disallowInHighSec` carries the flag. Exactly one
  ability is restricted -- **`Launch bomb` (7), barred in high *and* low sec,
  on 16 of 94 fighters**. Read the fighter's own dogma and you find no
  restriction and report "usable anywhere" for all 16.
- **The 5-active-drone cap is not in the SDE.** `maxActiveDrones` (352) has
  `defaultValue = 0` and **zero rows on any ship** -- the limit comes from the
  character's Drones skill. Compute from `droneBandwidth` alone and an Ishtar
  "fields 25 light drones", five times the real figure, with nothing to flag it.
  Same shape as drone range below: a ship-looking number that is character data.
- **Drone range is not a ship attribute.** Both an Onyx and a Rifter show 20 km
  at zero skills and 60 km trained, because it comes from the character's
  Drone Avionics skills. Nothing in `type_dogma` will give it to you.
