# Gotchas: the `types` table and filtering

For the `items` part. Read before answering **which rows belong in the answer**
— published flags, tech level, volumes, prices, planet type names, duplicate
names, hull-size group lists, ore variant names. For what a dogma *value means*, read `gotchas-dogma.md`.

**"Best/fastest X hull" questions need both files.** Picking the hulls is here;
what the stat means is there. The worked example below is one of them.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs.

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

- **There is no hull-size column.** "Frigate", "cruiser", "battleship" exist
  only as `groups_.name` values, so a size class is a list of group names you
  curate. Cruiser-sized T2, for instance, is Heavy Assault Cruiser + Heavy
  Interdiction Cruiser + Logistics + Combat Recon Ship + Force Recon Ship + Flag
  Cruiser (note **`Ship`** on both Recon names -- omitting it returns zero rows).
  **A group name is not a tech level**: `Logistics` also holds the faction
  Etana and Rabisu (`techLevel = 2`, `metaGroupID = 4`), which carry the two
  largest capacitors in the group, so "rank the T2 logistics ships" answers with
  a faction hull at the top unless you also filter `metaGroupID = 2`. Curate the
  groups *and* the meta group;
  frigate-sized T2 is Assault Frigate + Covert Ops + Electronic Attack Ship +
  Expedition Frigate + Interceptor + Logistics Frigate + Stealth Bomber. Say
  which groups you used -- two correct answers can differ on whether Marauders
  count as battleships.
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
  *Hydra* (4.148 s), a tournament prize almost nobody owns. The right answer is
  the **Nergal at 4.193 s** -- not the Ares, which is third at 4.544 s and is
  only the answer if the question is restricted to Interceptors. Their
  market group path runs through **`Special Edition Ships`** where a normal T2
  runs through `Frigates > Advanced Frigates`, so walk the tree to exclude them:

  ```sql
  WITH RECURSIVE up(typeID, mg) AS (
    SELECT typeID, marketGroupID FROM types
    WHERE categoryID = 6 AND published = 1 AND metaGroupID = 2   -- REQUIRED
    UNION ALL
    SELECT u.typeID, g.parentGroupID FROM up u
    JOIN market_groups g ON g.marketGroupID = u.mg
  )
  SELECT DISTINCT up.typeID FROM up
  JOIN market_groups g ON g.marketGroupID = up.mg
  WHERE g.name = 'Special Edition Ships';        -- the 7 to exclude
  -- Drop the metaGroupID filter and this returns 68 -- every published ship
  -- sold under Special Edition, at all tech levels. Used as a blanket exclusion
  -- list it removes ten times what you meant.
  ```

  For any "best X" question, say which set you used -- obtainable hulls or all
  of them.

  **The align times above come from `gotchas-dogma.md`, not from this file.**
  Align is `ln(4) * inertia * mass / 1e6` where `inertia` is attribute 70
  (named `agility`, which is not what it sounds like), and **SQLite's `LOG()` is
  base 10** -- using it makes every align time 2.3026x too fast while leaving the
  ranking intact, so the error is invisible. Do not recompute these numbers
  without reading that file.

- **Names are not unique.** 12 published type names, 6 group names and 2
  attribute names are shared by more than one ID. Joining on name can duplicate
  rows -- resolve to an ID first when a query must return exactly one thing.
- **Sparse columns give false negatives.** 960 published types have `volume`
  NULL, and `metaGroupID` and `techLevel` are populated for only ~26% and ~19%
  of types -- so `WHERE metaGroupID = 2` silently excludes three quarters of the
  catalogue before any filtering you intended.
- **Ore variant names changed.** "Concentrated Veldspar" and "Dense Veldspar" no
  longer exist as types; the grades are now `Veldspar II-Grade` and similar.
