# Gotchas: industry and reprocessing

For the `industry` part and `items.type_materials`. Read before answering
anything about build costs, blueprints, invention or ore yields.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs.

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
  the mistake easy, but 30 published types disagree: XL torpedoes have
  `portionSize = 100` while a run makes 5,000, a 50x error.

- **`bp_skills` mixes activities.** The Dominix blueprint has 1 manufacturing
  skill and 3 invention skills; without `AND activity = '...'` you get both and
  report the wrong set.
- **Invention runs T1 -> T2 blueprint.** Materials, skills and time live on the
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
- **Reprocessing yields are the theoretical 100% refine, which no player gets.**
  `type_materials` gives the perfect-refine output; what you actually receive is
  that multiplied by the facility rate, your skills and your implants. The
  facility half *is* in the SDE --
  `universe.npc_stations.reprocessingEfficiency` runs 0.25 to 0.50, and 4,649 of
  5,210 stations sit at **0.50**. Because it is so nearly uniform, "which
  station refines best" usually has **no answer**: all 18 stations in Jita are
  0.50. Check the distribution before ranking, and if it is flat, say so and
  fall back to `world.stationServices` (only some stations offer a Reprocessing
  Plant at all). So quote the 100% figure as a ceiling, halve it
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

- **The legacy `Batch Compressed *` line is stale and contradicts itself.** The
  `Compressed Arkonor Blueprint` consumes **1,000 Arkonor** to make **1 Batch
  Compressed Arkonor**, but that one unit reprocesses to exactly what **100**
  Arkonor gives -- a 10x loss of matter. It is dead pre-2021 content whose
  blueprints survive, and it is the only compression *ratio* anywhere in the
  SDE, so it is exactly what someone reaches for. Use `items.compressibleTypes`
  and the `types.volume` difference instead; modern compression is 1 unit to
  1 unit.
- **21 blueprint rows reference typeIDs that do not exist** (20 products, 1
  material) -- removed content whose blueprints remain. This is upstream data,
  not a build error; use inner joins so they drop out.
