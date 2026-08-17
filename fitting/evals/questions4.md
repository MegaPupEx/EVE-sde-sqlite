# Eval generation 4 — complex tool-composition questions (2026-08-17)

Probes the v1.5-complete surface: mutaplasmid roll feasibility, heat,
`module_attrs`, `sweep`-shaped tradeoffs, environments, and cross-layer
questions that need layer 1's SQL next to the engine. Keys in
`keys4-3470007.json`, engine build 3470007 (local layer-1 parts at
3466501 — subjects naming that skew is a discipline point, not a
requirement). Key derivations: the SQL and drive-script calls are
documented per question below; grading axes K/M/D/P/C as in
`README.md`.

Arm A needs only the fitting stack; arm B needs layer 1 too.

## A1 — the roll-ceiling question (correct answer: impossible)

> what combination of faction web and abyss mutaplasmid is best to roll
> a web that has the same range as the max range faction warp disruptor,
> if they are both heated?

Key: **no combination reaches it.** Longest faction points (Dark Blood /
Domination / True Sansha / Republic Fleet) are 30,000 m base, ×1.2
overheated = **36,000 m**. Longest faction webs are 15,000 m base
(same four factions' tier); best web mutaplasmid maxRange roll is
Unstable ×1.2 → 23,400 m heated (Glorified Unstable ×1.25 → 24,375 m,
engine-verified via a mutated import + `module_attrs` overheated).
Best falls ~11.6 km short. Full credit requires saying it cannot be
done and quoting the ceiling; naming that a web-range-bonused hull
(Huginn/Rapier) changes the picture is bonus, not required. Inventing
a combination that "works" is the K-fail this question exists to catch.
Derivation: metaGroup-4 webs/points × `mutaplasmidAttributes` attr 54
bands × overloadRangeBonus (+30% web, +20% point).

## A2 — plate/rep tradeoff (with a legality landmine)

> Here's my Punisher:
> [Punisher, brawl] 400mm Steel Plates II / Small Armor Repairer I /
> Damage Control II / Multispectrum Coating II // 5MN Y-T8 Compact
> Microwarpdrive / Warp Scrambler II // 3× Small Focused Pulse Laser II
> (Imperial Navy Multifrequency S)
> Is it worth downgrading the plate to the 400mm Rolled Tungsten
> Compact so I can upgrade the repairer to a Small Armor Repairer II?

Key: the current fit is **powergrid-illegal** (86.7 used / 83.8, all-V)
— catching that is the M-axis point. The swap makes it legal, costs
337 EHP (7,819 → 7,482 uniform), gains +13.8 hps armor rep (41.3 →
55.1, +33%). Verdict: yes — and not optional, since the "current" fit
can't undock as pasted.

## A3 — environment choice

> My blaster Enyo: [Enyo] 2× Magnetic Field Stabilizer II / Micro
> Auxiliary Power Core II // 5MN MWD / Warp Scrambler II // 4× Light
> Neutron Blaster II (Void S). I can day-trip into a C3 Wolf-Rayet or a
> C3 Pulsar — which favors this fit more, and by how much?

Key: Wolf-Rayet, overwhelmingly. C3 WR: dps 434.4 → **901.8** (×2.08),
EHP 5,467 → 6,700. C3 Pulsar: dps unchanged 434.4, EHP 5,598 (+2.4%).
(`set_env` per side; same env on both sides of any NPC comparison is
the T2 discipline point but not probed here.)

## B1 — cross-layer enumeration

> Which tech-1 combat battlecruiser has the most drone bandwidth, and
> what's its drone-only DPS if I fill that bandwidth with Ogre IIs, max
> skills, no drone damage mods?

Key: **Myrmidon**, 100 Mbit/s (layer-1: Combat Battlecruiser group,
metaGroup 1, attr 1271; Prophecy 75 is second). 100/25 = 4× Ogre II →
**380.2 dps** (engine, all-V, bare hull).

## B2 — cross-layer + hull bonus + heat

> What's the longest-range faction web, and how far does it actually
> reach on my Huginn with max skills if I overheat it?

Key: 15,000 m base — a four-way faction tie (Dark Blood, Domination,
True Sansha, Republic Fleet; any named is fine). On a Huginn at all-V
the hull bonus takes it to 60,000 m, **78,000 m overheated** (engine
`module_attrs`; +30% overload on top of the hull's +300%). Quoting
15 km × 1.3 = 19.5 km without the hull bonus is the K-fail here.

## B3 — the napkin-math trap

> How much powergrid does a max-skills Merlin have with a Micro
> Auxiliary Power Core II fitted? My napkin math says 62 but I want the
> real number.

Key: **65.0 MW** — (40 base + 12 from the MAPC) × 1.25 skill; the
skill multiplies the module's added grid too. The napkin's 62 is
40 × 1.25 + 12 — the plausible-but-wrong ordering. Base 40 is layer-1
(`type_dogma` attr 11); 65 is the engine's fitting panel.

## Protocol

One subject per question, fresh session, no hints beyond the question
text; subjects asked to append `--- calls: N mcp, M sql` for cost
accounting. Measured: total tokens (harness counters), wall time,
answer length, tool calls, K/M/D/P/C grading vs this file.
