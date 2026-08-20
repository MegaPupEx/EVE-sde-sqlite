---
name: eve-fitting
description: Interpret EVE Online ship fittings and fitting-engine output - DPS vs alpha vs sustained damage, EHP and damage profiles, capacitor stability, align and speed, stacking penalties, buffer vs active tank, shield vs armor, module and rig tradeoffs. Use whenever a question involves combining a ship with modules, skills or charges ("what does this fit do", "is this cap stable", "which tank", "why is my DPS lower than pyfa says"), generating or comparing fits, or reading a stat panel from the eve-fitting MCP server. ALSO load for quick mechanics questions that look like general knowledge - "do two of these stack", "can X be mutated", prop-mod/fighter/storm rules - measured runs show memory answers these wrong exactly when the skill isn't loaded. Pairs with the eve-sde skill (raw game data) and the eve-fitting MCP server (the calculator).
---

# EVE fitting knowledge

Layer 2 of the stack, and it depends on layer 1: the **eve-sde** skill plus its
MCP server answer what a thing *is* — every type, attribute, blueprint and
system — while this layer answers what a ship *does* once they combine. Reach
for eve-sde whenever you need an exact item name, a hull's raw attributes, or a
set question ("which cruiser has the most powergrid"); a module name recalled
rather than looked up is the single commonest way a fit answer goes wrong.

The **eve-fitting MCP server** (pyfa's engine, headless)
computes what a fit does; this skill teaches what the numbers mean and what
they cost. The eve-sde skill (layer 1) is the raw data underneath; every base
attribute question belongs there.

**Two failure modes.** First, quoting a correct number that answers nothing —
an EHP without a damage profile, a DPS that never applies, a cap-stable badge
on a fit that dies in 40 seconds. Second, computing fit math from memory:
stacking, hull bonuses and the cap simulation are exactly where memory is
confidently wrong. The engine computes; you interpret.

## Where numbers come from (the discipline)

- **Authority order: SDE > engine > wiki > memory.** Never quote a
  higher-layer number when a lower layer can produce it. Fit math (anything
  combining two or more effects) is engine territory; base attributes are SDE
  territory; doctrine and meta are wiki/memory and must be labeled as such.
- **Name the layer for every number you quote** — "engine, build 3470007,
  all-V skills" or "SDE base hull, pre-skill" or "player convention, not
  data". A number without its layer is not an answer.
- **Check builds once per session.** `engine_info()` returns the engine's
  data build; layer 1's `meta` table has `sdeBuildNumber`; CCP's latest is
  one GET away (see the eve-sde skill). If they disagree, say so whenever
  quoting affected numbers — skew produces silently-wrong figures, which is
  the failure class this whole stack exists to kill.
- **Name what the engine does not model.** `engine_info().unmodeled` lists
  it (currently: industrial core, structure reinforcement/low-power
  cycles, custom skill sheets). If the question touches one, answer with
  the engine number *plus* the named gap — never silently ignore it.
  Modeled: bursts (`set_booster`), environments (`set_env`), projected
  fits (`set_projected` — remote reps/ewar/neuts, zero range), T3D modes
  (`mode` op), fighters incl. ability toggles and class tubes (§T9),
  implants and drugs (`edit_fit` add), mutated
  (abyssal) modules — rolls travel in the EFT `[N]` dialect
  (`references/traps.md` §T15) — overload bonuses (`state: 'overheated'`;
  burnout timers are not modeled, so name the tradeoff), and
  bastion/siege/triage — fit the module, set it active; the panel is the
  in-state ship and a `notes` line names the costs (§T16, incl. why
  bastion never dilutes your hardeners) — and Upwell structures
  (Citadel hulls, standup modules, service rack, per-service fuel and
  the per-layer incoming damage cap in the panel — §T17).
- **Skills are part of every number.** Presets: `all-0`, `alpha`, `all-5`
  (import default: all-5). **Assume an omega pilot** and quote all-V,
  labeled. Reach for `alpha`/`all-0` only when the question signals it —
  "alpha friendly", "just started", a named low-SP situation — then the
  alpha preset plus `required_skills`' `alpha_blocked` are the answer
  ("can an alpha fly this" is data, not folklore).

**Layer-1 lookups go through the `eve-sde` MCP server when it is registered**
(`attrs` for unit-corrected attribute values — resonances come back as resist
%, millisecond attributes as seconds; `query` for many SQL statements in one
round). Hand-written SQL against the sqlite parts still works, but it returns
raw `type_dogma.value`, which inverts for 58 resistance attributes and lies
about units for 92 more — measured runs got exactly that wrong.

**No engine registered?** Setup is `fitting/mcp/README.md` (a local process +
`.mcp.json` entry). Without it you may quote layer-1 base-hull values marked
as pre-skill, pre-stacking — but do not hand-compute a stat panel, and do not
present remembered fit numbers as computed.

## Files

| File | ~tokens | Read it when |
| --- | --- | --- |
| `references/reading-stats.md` | 2.1k | interpreting any stat panel or graph — DPS/volley/sustained, EHP and damage profiles (incl. NPC profile table), cap stability, align, targeting, graph summaries, fitting headroom |
| `references/tradeoffs.md` | 1.9k | choosing between things — buffer vs active, shield vs armor, another damage mod vs a different slot, speed vs resists, and "what should I fit" questions (incl. the sweep-driven authoring loop) |
| `references/traps.md` | 4.2k | before asserting any mechanic: the numbered trap catalogue — stacking exemptions, wormhole/burst effects, hull resists, reload, tick rounding, drones, abyssal rolls, siege-class states |

Sizes are bytes/4, for budgeting; this router is ~3.6k.

## If you read nothing else

- **Never publish a fit you have not imported.** If you are naming modules,
  every one of them goes through `import_fit` before it reaches the player —
  no exceptions, not for a "quick suggestion", not for a shape you are sure
  of. Measured twice on 2026-08-19: a Machariel recommended from memory
  carried three module names that do not exist (`Adaptive Invulnerability
  Field II`, renamed years ago; `Faction Large Armor Plate`;
  `Republic Fleet Barrage L`, Barrage being T2-only), left a seventh turret
  hardpoint empty while explaining it as a launcher slot, and changed
  materially between two messages because half of it was invented. The engine
  catches every one of those in one call. If the eve-fitting tools are not
  available in this session, say the engine is missing and answer no further
  — do NOT hand-derive. Stacking, calibration, hardpoints and slot legality
  are precisely what memory gets wrong, and a fit that was never imported is
  a guess wearing a stat panel.

- **EHP is meaningless without a damage profile.** The panel default is
  uniform 25/25/25/25 — pyfa's convention, not a law. Name the profile;
  re-run `get_stats` with `profile` weights for the actual enemy
  (`references/reading-stats.md` has the NPC table).
- **"DPS" is three numbers**: volley (one shot), burst (reload-free),
  sustained (reload-in). Say which. A RLML Caracal is 298 burst / 179
  sustained — quoting either alone misleads.
- **Cap-stable % is an equilibrium, not a grade.** Recharge peaks at 25%
  fill and *falls* below it, so stable-at-30% sits on a cliff edge one neut
  cycle from cascade, while a non-stable fit that lasts 3 minutes outlives
  most fights. Distance from 25%, and time-to-empty vs engagement length,
  are the real readings.
- **The 4th damage mod gives ~28% of the 1st** (stacking: 100 / 87 / 57 /
  28 / 11%). Hulls, skills, implants, boosters and charges are exempt;
  modules and rigs share the chain.
- **Command bursts never stack-penalize** (warfare buffs sit outside dogma;
  strongest same buff wins). **Environmental beacons are ordinary penalized
  modifiers** (category 2 is not exempt): a black hole's velocity bonus
  joins your prop mod's penalty group. Both hit NPCs too. Details and the
  counterexamples: `references/traps.md` §T1.
- **Align time is tick-quantized**: the engine's 4.69 s is math; the server
  acts on whole seconds — quote `ceil()` for in-game behavior, and say
  which you're giving.
- **Slots are the currency.** Shield tank spends mids (vs tackle/prop/cap),
  armor spends lows (vs damage mods). Every tank comparison is a
  slot-economy comparison first and an HP comparison second.
- **Answer the pilot, not the spreadsheet.** A max-DPS fit that caps out in
  90 seconds, or a "stable" fit that traded its tackle for cap rechargers,
  answers the query and fails the player. Name what the fit is for, the
  range band it fights in, and what was traded away.
- **Never assert a mechanic from memory when one call can check it** — a
  labeled guess still grades wrong when the tool was available. The
  measured repeat offenders: prop mods (only ONE runs; a both-active
  panel is engine fiction — T18), mutaplasmid applicability and bands
  (just try the import; faction mods ARE mutable — T15), fighter tube
  classes and squadron sizes (read the fit — T9), beacon/storm effects
  (`set_env` diff on a fitted hull, never raw attrs — T1), and any
  "which hull has the most X" enumeration (the engine's own db answers
  it even without layer 1 — never enumerate from recall), and every
  "can hull X fit module Y" (import + validate answers by name;
  CPU/PG arithmetic is NOT legality — restrictions live in canFit, and
  a measured run said yes to an MJD on a cruiser off resource math
  alone). The audit is mechanical: a mechanics answer produced with zero engine/SDE calls
  this turn is unverified by definition — make the one call, or label
  every such claim as unchecked memory. "This is general mechanics, no
  tools needed" is the exact thought that precedes a measured wrong
  answer.

## Driving the engine

Fits are server-side objects addressed by short IDs — never re-send EFT
mid-conversation; it is the import/export currency only. Ids live only as
long as the server process: every fit-scoped response echoes the ship, and
an unknown-id error after a restart means re-import from your own context
and continue (never reason past a ship echo that doesn't match).

**Rounds are the cost, not calls.** Every reply you send re-reads the whole
conversation, so a turn costs roughly *rounds × context* (~45k a round) no
matter how many tool calls ride in each one. Two habits follow, and measured
runs show both are usually missed — 90% of recorded requests carried exactly
one call:

- **Put independent calls in one reply.** Importing two fits, reading three
  modules, pulling a panel and a graph — none of these wait on each other,
  so issue them together. Only a call that *needs the previous result*
  (a fit_id, a measured value) belongs in its own round.
- **`import_fit`, `create_fit`, `clone_fit` and `edit_fit` already return the
  full stat panel.** Do not follow them with `get_stats` — that was the most
  common wasted round in the corpus. Call `get_stats` only to re-read a
  resident fit with a different `profile`/`spool`, and pass `stats=False`
  when you genuinely want just the id.

A/B questions are one
`clone_fit` + edits + `compare_fits` (returns only what differs).
`validate_fit` names the violated constraint; run it after edits, not
before — CPU/PG needs are themselves dogma-modified. `set_skills` switches
all-V/alpha. On import failures, quote the parser's error — it names the
line.

`graph(fit_id, kind)` returns bounded curves (`dps_vs_range`,
`dps_vs_target_speed`, `cap_vs_time`, `dps_vs_time` — the spool ramp):
≤30 points, summary stats, named assumptions — reason from the summary,
chart the points only if asked. Spool-up fits quote full spool by
default with the floor and ramp time in `offense.spool`
(`references/traps.md` §T11); `get_stats(spool=…)` re-quotes any level.
`set_env` applies a system environment **to that fit only** — set the same
env on both sides of any comparison. `set_booster` attaches command-burst
fits; the booster fit's own hull/skills scale the burst. `set_projected`
applies enemy or friendly fits onto this one (webs, neuts, remote reps) —
bare ids project at zero range (full strength: quote it as the worst/best
case it is); `{fit_id, range_km}` entries apply falloff-aware strength,
zero past optimal + 3× falloff for most ewar. `graph(projector,
'ewar_vs_range', item=…)` is the band. `applied_dps(fit, distance_km,
target={sig_m, speed_ms})` answers "what does this fit actually do to
that hull there" in one call — turret tracking, missile explosion terms
and drone mobility, raw vs applied per source class; pull the target's
base sig/speed from layer 1, and note perfect turret application reads
~101.5% of paper (wrecking-shot expectation, pyfa's own model).
`versus(fit_a, fit_b, distance_km)` is the whole duel in one call —
both directions of applied dps into resist-weighted EHP (the victim's
EHP against the attacker's *actual* damage mix), reps subtracted,
structure damage caps applied, time-to-kill each way. Project ewar/links
first (`set_projected`/`set_booster`) and versus reads the post-ewar
sig/speed. Its assumptions ride in the response — quote them.
`required_skills` gives the fit-wide skill prerequisite closure ("can I
even sit in this").

`module_attrs(fit, item, attrs)` reads a module's *modified* attribute
values — ewar range and strength, rep amount, neut GJ — the only honest
source for per-module numbers (the panel is fit-level). Set `state:
'overheated'` first to quote heated figures. `sweep(fit, item,
candidates, metrics)` swaps each candidate in server-side and returns
one row each (~30 tokens): use it for every "which module here" and
"is the meta version worth the fitting room" question — prune the
candidate list with knowledge *first* (2–6 plausible options, not the
market group), then sweep once; never loop `edit_fit`+`get_stats` per
variant. Mutaplasmid roll feasibility ("can a web roll to X km") is
data-layer SQL — in layer 1 the bands live in `dynamicItemAttributes`
(`attributeIDs` JSON: `[{_key: attrID, min, max}]`, plus applicable
types and resulting type in `inputOutputMapping`); the engine's own db
has the same data relational as `mutaplasmids`/`mutaplasmidAttributes`.
Band × base attribute is the reachable window; build the winning roll
in the engine (EFT `[N]` dialect) to verify it in fit context. The same
engine db covers any type/attribute enumeration ("which T1 frigate has
the most mids") when layer 1 is absent — query it rather than
enumerating hulls from recall; recall-driven lists silently drop
members.

Panel keys carry units (`_s`, `_ms` = m/s, `_km`, `_gj`, `_hps`); resists
are fractions (0.598 = 59.8%), already converted from the SDE's inverted
resonance. Never guess a unit.

EFT rack order is slot order, and `[Empty ... slot]` gaps survive
import → export — heat-conscious layouts (modules spaced so overload
damage doesn't chain to neighbors) come back un-scrambled. The gaps
change no stats; `edit_fit` add fills the first gap, like fitting
in-game.

## Building a fit, as opposed to reading one

When you are the one choosing modules, a choice you cannot show a delta for is
a choice you have not made. Measured 2026-08-19: a generated Vindicator passed
`validate_fit` clean while carrying a cruiser-size prop mod (+36% speed for the
full battleship signature bloom), three empty slots, and a charge whose faction
variant holds the same capacitor in 25% less volume. Every one of those was
checkable in the engine and none of them was checked.

- **Read `advisories` on every panel.** Separate from `problems`: `problems`
  is legality, `advisories` is "legal but does nothing" — empty slots,
  undersized prop mods, a strictly better charge. Act on each one or say why
  you are not. `problems: []` does not mean the fit is good.
- **A/B anything you are unsure of** with `clone_fit` + `edit_fit` +
  `compare_fits`. One round gives you the real delta; guessing gives you the
  5MN. Size classes especially: prop mods, reps, cap boosters and guns all
  come in hull-size tiers, and the wrong tier is usually legal.
- **Never answer "which X is best" from a remembered shortlist — enumerate.**
  This is the failure that survives everything else: the tools get used
  correctly, but only on the two or three candidates that came to mind. Asked
  which T1 destroyer had the most powergrid, a measured run compared four and
  never queried the twenty-four. Asked for a solo hull, another compared four
  assault frigates on static attributes, built none, and shipped a fit doing
  113 dps where the same modules on a hull it never considered do 150 with
  more EHP. The set is a tool call, not a memory: `sweep_hulls(group=…)` ranks
  every hull in a class with the fit actually built on each, `sweep` does the
  same for module candidates, and layer 1's `query` returns the whole group in
  one statement. Reach for one of those before you type a candidate list.
  Build the fit on ONE hull first, then sweep it: `sweep_hulls` rebuilds the
  loadout you already have on every hull in the class, so the comparison is
  the real fit rather than static attributes. When a fit is over its grid,
  slots or hardpoints, or one resource is binding while the other has slack,
  the panel's `advisories` hand you that call ready to paste, sized for the
  class — a large class needs the `limit` the advisory already filled in.
  A class sweep enumerates hulls that cannot be bought: tournament prizes and
  event ships rank like any other, so read each row's `availability` note
  before recommending the winner.
- **Pick modules off the ladder, not out of memory.** `variants(item)` returns
  every published variant of a module — tech 1, the compact/enduring/restrained
  metas, tech 2, storyline, faction — with fitting cost and the attributes that
  decide between them. Naming a module and waiting for `import_fit` to reject
  it costs a round per guess and reveals exactly one name; the ladder shows in
  one call that a compact medium shield extender is **9 CPU cheaper than the
  tech 2 for 200 less shield**, which is the trade a CPU-bound fit is looking
  for and cannot see any other way.
- **Fix the constraint that is actually binding.** The panel's `advisories`
  name it. Measured 2026-08-19: a Confessor at 99% CPU with 24 MW of powergrid
  spare spent two rig slots on *powergrid* rigs — the exact slots that would
  have solved CPU — and shipped three guns on a four-turret hull as a result.
  Read which resource is tight before choosing a rig or a meta level.
- **Hull bonuses are already inside every number the engine returns**, so a
  ranking needs no adjustment for them — but read the `bonuses` line before
  concluding a hull is bad. A turret-bonused hull scored with a missile fit
  places low because the fit is wrong for it, not because the hull is.
- **Give the EFT block by default — never wait to be asked.** A fit is not
  delivered as prose; it is delivered as text the player can paste into the
  game or pyfa. Produce it with `export_fit` so it comes from the built fit
  rather than being retyped, and put it in the first answer alongside the
  numbers. Every measured run so far has made the player ask a second time.
- **Fill the slots or justify the gaps.** An empty high on a brawler is DPS or
  utility you declined to take; say which.
- **Take the free stats when the player offers them.** If they say "any
  module/rig/implant/whatever", that includes boosters and implants — most
  combat boosters are a straight buff with a side effect worth naming, and
  hardwirings cost only ISK. `set_booster` applies boosters; implants ride in
  the EFT text. Leaving them out of a "best fit I can train for" answer is
  leaving the question unanswered.
- **Say what the engine cannot see.** Its capacitor simulation assumes NO
  incoming neutralisation, so a triple-rep panel reads beautifully and tells
  you nothing about a fight with neut pressure — that is the case for resist
  modules over a third repper, and the panel will never make it for you.
  In-space rules (ESS field restrictions, gate/jump mechanics) are not modeled
  at all; name them rather than fitting around them silently.

## Answer economy

Answers are read on a phone between undocks. Measured runs show the cost
is in restating, so:

- **Verdict first, once.** One opening sentence answers the question; no
  closing "bottom line" that says it again — end when the support ends.
- **Each number appears once** — table or prose, never both. If a table
  carries the numbers, the prose around it carries only the verdict and
  what the table *doesn't* show — restating a cell in sentence form
  ("that's −4%", "2.1× the damage") is the residual failure measured
  runs keep finding.
- **Provenance is one trailing line** ("engine 3470007, all-V, uniform
  profile"), not clauses on every figure.
- **At most one unsolicited flag**, the most consequential one.
- Budgets: fit review ~200 words, follow-up ~100, data lookup ~50. Over
  budget almost always means something is being said twice.
- **Follow-ups answer the delta**: batch the turn's engine calls into one
  request, reuse resident fits and already-computed numbers, and never
  re-audit a settled answer — the swap question needs the changed figures
  and a verdict, not a second review.
