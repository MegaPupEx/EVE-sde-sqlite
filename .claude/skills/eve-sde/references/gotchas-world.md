# Gotchas: the `world` part

For the `world` part -- missions, agents, dungeons, NPC corporations,
certificates, clone grades, masteries. Read before answering anything about
mission agents, combat sites and DED ratings, what an Alpha clone can train, or
ship mastery levels. Column names and the cross-part table finder stay in
`schema.md`; this file is the traps.

Counts verified against build `3466501`; re-derive if `meta.sdeBuildNumber`
differs. **Every count here is population-sensitive** -- `published = 1` vs all
types, k-space vs all systems, ships vs all categories. Where the population is
not stated it is the whole table; if your query filters differently, re-derive
rather than quoting.

| You want | Table | Notes |
| --- | --- | --- |
| NPC agents | `npcCharacters` | **no `agents` table.** Agents are rows where the `agent` column is non-null: `{agentTypeID, divisionID, isLocator, level}`. 10,966 of them. `locationID` joins `universe.npc_stations.stationID`. **Filter `agentTypeID = 2`** (`BasicAgent`) for the mission agents a player means -- of 180 level-5 agents, 143 are `agentTypeID = 8` EventMissionAgent and only **37** are real. `agentTypes` (`_key`, `name`) names all 13 kinds |
| NPC corporations | `npcCorporations` | not `corporations` |
| Missions | `missions` | `messages` is an array of `{_key: slot, text}`; the briefing slot is `messages.mission.briefing`. `killMission` / `courierMission` are `{dungeonID, objectiveQuantity}` and mutually exclusive |
| Combat sites | `dungeons` | `description` holds the DED rating as prose -- see below |
| Certificates | `certificates` | `skillTypes` is an array of `{_key: skillTypeID, basic, standard, improved, advanced, elite}`; `recommendedFor` is a bare int array -- inconsistent shapes in one table |
| Alpha-clone skill list | `cloneGrades` | `_key` is a **raceID** (1/2/4/8), and although the four rows are named per race their `skills` JSON is **byte-identical** -- 175 skills, 23 of them to level V. "What can an Alpha Minmatar train that a Caldari can't" returns a confident empty answer |
| Ship masteries | `masteries` | `_key` = typeID (476/476). `_value` is `[{_key: 0..4, _value:[certificateID]}]`, and the 0-4 index selects which **tier column** of `certificates.skillTypes` to read (`basic`..`elite`) -- the SDE never says so. **72 of 476 rows carry an identical cert list at every level**, so reading it wrong looks self-consistent |
| NPC agents sitting in space | `agentsInSpace` | 360 rows, columns `_key`, `dungeonID`, `solarSystemID`, `spawnPointID`, `typeID`. `_key` is the agent's `npcCharacters._key`; **`dungeonID` resolves 0 of 360** (see below) |
| Epic arcs | `epicArcs` | 21 rows but only **9 are epic arcs** -- the other 12 `Pilot Certification Course` rows are AIR career-program tutorials sharing the table. All 9 arcs tie at `arcRestartInterval = 129,600`, and **the unit is not stated in the data**: read as minutes it matches the known 90-day reset (as seconds it would be 36 hours, which is wrong) -- flag the unit as corroborated by game knowledge, not by the SDE. `missions` is a JSON chain of `{_key, agentID, nextMissions}` |

**Mission dungeon references are almost all dangling.** 1,662 missions carry a
`killMission` object; **1,661 of those name a `dungeonID` and only 3 of them
resolve** against `dungeons` (the odd one out is `_key` 16414, whose
`killMission` is `{objectiveQuantity: 0}` with no `dungeonID` at all).
`agentsInSpace` resolves **0 of 360**. The ID ranges overlap, so this is not an
ID-space mismatch -- the dungeon definitions those missions point at are simply
not in the SDE. An inner join silently returns 3 rows where you expected 1,661,
and a left join reports "no dungeon" for 99.8% of combat missions. Say the
reference is unresolvable rather than reporting an absence.

**`dungeons.description` is 84% NULL** (226 of 1,409 populated), so a missing
DED rating means "no description shipped", not "unrated". Ratings appear in
three incompatible formats -- `DED Threat Assessment: Deadly (10 of 10)`,
`DED Threat Assessment Level: 10 of 10`, and `Threat Assessment Level: 8 of 10`
-- so `LIKE '%DED Threat Assessment:%'` finds 38 and misses 6, including a
10/10. Match on `Threat Assessment` alone (44 rows). The severity word is not
reliable either: level 10 appears as both "Critical" and "Deadly". Dungeon names
also repeat -- 1,409 rows, 1,014 distinct names -- so counting by name and by
key give different answers.

Two location notes that live elsewhere but bite here: `factions` and `races`
are in this part (not `universe`) and are its only two tables keyed on
`factionID` / `raceID` rather than `_key`; and `world.shipTreeGroups._key` is
**not** a `groupID` -- that trap is in `gotchas-types.md` because the wrong
join is against `items.groups_`.
