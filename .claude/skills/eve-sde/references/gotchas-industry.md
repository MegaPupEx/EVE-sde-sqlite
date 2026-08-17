# Gotchas: industry and reprocessing

For the `industry` part and `items.type_materials`. Read before answering
anything about build costs, blueprints, invention, ore yields, planetary
industry chains or ore compression.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs. **Every count here is population-sensitive** -- `published = 1` vs all
types, k-space vs all systems, ships vs all categories. Where the population is
not stated it is the whole table; if your query filters differently, re-derive
rather than quoting.

- **Manufacturing output per run is `bp_products.quantity`.** Antimatter Charge
  S consumes 204 Tritanium *per run of 100 charges* -- 2.04 each. 368
  manufacturing blueprints produce more than one per run and reactions reach
  10,000, so per-unit costs are off by up to four orders of magnitude if you
  read `bp_materials.quantity` directly.
- **Planetary industry has the same divisor trap as manufacturing.** In
  `planetSchematics`, the inputs and the output are both per *cycle*, and
  **60 of the 68 schematics produce more than one unit per cycle** — a P1 run
  makes 20 from 3,000 P0 in 1,800 s. Divide by the output entry's `quantity`
  (the single `types` row with `isInput = false`) before quoting a per-unit
  cost, exactly as with `bp_products.quantity`. The four tiers run
  3,000 P0 -> 20 P1 -> (40+40) -> 5 P2 -> (10+10+10) -> 3 P3 -> (6+6+6) -> 1 P4,
  so a single P4 unit is hundreds of thousands of P0.
- **`portionSize` governs reprocessing, and nothing else.** `type_materials`
  quantities are per `portionSize` units: Veldspar yields 400 Tritanium per
  **100** units. It is **not** the manufacturing batch size -- that is
  `bp_products.quantity`. The two coincide for most ammo, which is what makes
  the mistake easy, but 30 published types disagree -- and it is
  the **T2** ammo, not the family: `Mjolnir Javelin XL Torpedo` has
  `portionSize = 100` while a run makes 5,000 (a 50x error), whereas the plain
  `Mjolnir XL Torpedo` runs 100 and agrees. Of the 30, 24 are the 100 -> 5,000
  shape; the rest are smaller mismatches.

- **`bp_skills` mixes activities.** The Dominix blueprint has 1 manufacturing
  skill and 3 invention skills; without `AND activity = '...'` you get both and
  report the wrong set.
- **Structure and rig ME/TE bonuses *are* in the SDE, but not where the routing
  table points.** `industryModifierSources` (`_key` = typeID) names, per
  activity, which channel a structure or rig affects -- but the
  `dogmaAttributeID` it cites is an abstract channel, **not an attribute on that
  type**: it resolves in `type_dogma` for only **13 of 371** manufacturing
  references, which reads exactly like "the data is missing". The magnitudes are
  on the type itself under different attributes:

  | Source | material | time |
  | --- | --- | --- |
  | Engineering complexes | `strEngMatBonus` (Raitaru/Azbel/Sotiyo all 0.99) | `strEngTimeBonus` 0.85 / 0.80 / 0.70 |
  | Upwell engineering rigs | `attributeEngRigMatBonus` | `attributeEngRigTimeBonus` |
  | Reactor rigs | `RefRigMatBonus` | `RefRigTimeBonus` |
  | Tatara (reactions) | -- | `strReactionTimeMultiplier` 0.75 |

  Rig values are percentages scaled at runtime by `hiSecModifier` /
  `lowSecModifier` / `nullSecModifier` on the same rig (typically 1 / 1.9 / 2.1).
- **`industryTargetFilters` "Capital Ships" excludes Titans and Supercarriers.**
  That filter lists 6 groups and neither group 30 nor 659 is among them, so an
  L-Set capital rig does nothing for a supercapital; only the `Ships` filter
  (categories 6 and 32) covers them. 427 products also match more than one
  filter, so "which filter is this" has no single answer.
- **For invention, `bp_products.quantity` is BPC *runs*, not items.** The
  divide-by-quantity rule that gives per-unit manufacturing cost silently
  changes meaning here: an Intact relic's `quantity = 20` means the invented
  blueprint copy carries 20 runs, so dividing 6 datacores by it yields a
  confident, meaningless "0.3 datacores per subsystem". Cost per attempt is the
  material list as-is; expected cost per item also needs `probability` (0.26 for
  Intact, 0.21 Malfunctioning, 0.14 Wrecked -- for every **published** product.
  A naive `DISTINCT probability` over relic invention returns six values, because
  48 rows invent unpublished `OLD * Electronics` legacy blueprints at
  0.34/0.30/0.22; filter on the product's `published` before quoting the chance).
- **Tech III invention has no T1 blueprint.** Of 1,361 invention products, 978
  are Tech II and **216 rows are Tech III** (72 distinct blueprints, each invented from three relic grades) -- and the T3 rows are invented from
  **Ancient Relics** (`categoryID = 34`: Intact/Malfunctioning/Wrecked Hull
  Sections, Thruster Sections, Power Cores and so on), not from a blueprint at
  all. Starting a subsystem or strategic-cruiser question from a T1 blueprint
  finds nothing and reads as "T3 is not inventable".
- **Invention runs T1 -> T2 blueprint** (for Tech II). Materials, skills and time live on the
  **T1** blueprint, and the product is the **T2 blueprint**, not the T2 item.
  Starting from the T2 blueprint finds no invention rows at all.
  `bp_products.probability` is the *base* chance before decryptors and skills.
  It is NULL for all 4,848 manufacturing rows, all 120 reaction rows, **and 8
  invention rows** -- so `WHERE probability IS NOT NULL` silently drops eight
  inventable blueprints.

- **Every industry number in the SDE is the unmodified base.** `bp_materials`
  quantities are **ME 0** (research cuts up to 10%, and structure and rig bonuses
  cut more), and `bp_activity.time` is **TE 0** before rigs, structure and
  skills. Say "unresearched blueprint" when you quote either. Blueprint `time`
  values are seconds.
- **`industry.controlTowerResources` is two columns, and `quantity` is always
  per hour -- `purpose` picks the mode, not the meaning.** The table is `_key`
  (tower typeID) and a **`resources` JSON array** -- `quantity`, `purpose`,
  `resourceTypeID`, `factionID` and `minSecurityLevel` are fields inside it, not
  columns, so selecting them directly fails; use `json_each(resources)`.
  `purpose` is an undocumented two-value enum with no lookup table anywhere in
  the SDE: **`purpose = 1` is normal-operation fuel** (an Amarr Control Tower
  burns 40 Helium Fuel Blocks/hr; medium 20, small 10) and **`purpose = 4` is
  strontium burned per hour while reinforced** -- 400 / 200 / 100 by size, one
  entry per tower. The mode semantics are the known POS mechanic, not stated in
  the data; the numbers are. **Do not read the purpose-4 quantity as the
  strontium bay** -- that is the natural wrong guess, off by more than a unit
  mix-up: the bay is the tower's `capacitySecondary` dogma attribute,
  **50,000 / 25,000 / 12,500 m³** by size (Strontium Clathrates are 3 m³, so a
  large tower holds 16,666 units and reinforces for ~41 hours at 400/hr).
  Of the 295 `purpose = 1` entries, **252 are charters**: `quantity = 1`, gated
  on `factionID` with `minSecurityLevel` 0.45 on every one, so they apply only
  in that faction's high-sec. Filter them out with `factionID IS NULL` before
  quoting a fuel figure, or a tower reads as burning seven things an hour
  instead of one.
- **Upwell structure fuel is dogma, not `controlTowerResources`.** Service
  modules carry it as attributes in `type_dogma`:
  `serviceModuleFuelAmount` (fuel blocks per hour while running, e.g. a
  Standup Cloning Center burns 10/hr), `serviceModuleFuelOnlineAmount`
  (one-time cost to online, 720 for that same service) and
  `serviceModuleFuelConsumptionGroup`. Sum `serviceModuleFuelAmount`
  across the services a structure runs for its hourly burn; the structure
  hull itself burns nothing. Towers are the JSON table above; Upwell is
  per-service dogma — mixing the two models is the natural error.
- **Reprocessing yields are the theoretical 100% refine, which no player gets.**
  `type_materials` gives the perfect-refine output; what you actually receive is
  that multiplied by the facility rate, your skills and your implants. The
  facility half *is* in the SDE --
  `universe.npc_stations.reprocessingEfficiency` runs 0.25 to 0.50, and 4,649 of
  5,210 stations sit at **0.50**. It is uniform *in some systems* -- all 18 in Jita
  are 0.50 -- but **283 of the 1,143 multi-station systems do have a spread**,
  and it can be 2x: Oursulaert runs 0.25 to 0.50. So check the distribution for
  the system asked about rather than assuming either way. Note
  `world.stationServices` is not a useful fallback: **5,197 of 5,210 stations
  offer a Reprocessing Plant**, so it discriminates thirteen. So quote the 100% figure as a ceiling, halve it
  for a realistic NPC-station estimate, and say plainly that the SDE holds no
  skill or implant data. Reporting the raw number as "what you get" overstates a
  refine by roughly 2x.

- **84 products are made by more than one blueprint**: 4 manufacturing
  ('Firewall' Signal Amplifier has 5), **79 invention** (many T1 blueprints
  invent into one T2 blueprint) and **1 reaction** (Tungsten Carbide). Always
  filter by activity before assuming one blueprint per product. `bp_products -> blueprints` is not one-to-one.
- **Blueprint lookups start from the product**, not the blueprint name. Join
  `bp_products` to find which blueprint makes a thing.

- 18,915 published types have **no** `type_materials` row: not reprocessable,
  rather than reprocessing to nothing.

- **21 blueprint rows reference typeIDs that do not exist** (20 products, 1
  material) -- removed content whose blueprints remain. This is upstream data,
  not a build error; use inner joins so they drop out.

## Rare

Accurate, verified, and almost never load-bearing -- read only if the question
touches them directly.

- **The legacy `Batch Compressed *` line is stale and contradicts itself.** The
  `Compressed Arkonor Blueprint` consumes **1,000 Arkonor** to make **1 Batch
  Compressed Arkonor**, but that one unit reprocesses to exactly what **100**
  Arkonor gives -- a 10x loss of matter. It is dead pre-2021 content whose
  blueprints survive, and it is the only compression *ratio* anywhere in the
  SDE, so it is exactly what someone reaches for. Use `items.compressibleTypes`
  and the `types.volume` difference instead; modern compression is 1 unit to
  1 unit (documented under `compressibleTypes` in `schema.md`).
