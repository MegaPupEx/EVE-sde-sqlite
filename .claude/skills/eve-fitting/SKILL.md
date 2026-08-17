---
name: eve-fitting
description: Interpret EVE Online ship fittings and fitting-engine output - DPS vs alpha vs sustained damage, EHP and damage profiles, capacitor stability, align and speed, stacking penalties, buffer vs active tank, shield vs armor, module and rig tradeoffs. Use whenever a question involves combining a ship with modules, skills or charges ("what does this fit do", "is this cap stable", "which tank", "why is my DPS lower than pyfa says"), generating or comparing fits, or reading a stat panel from the eve-fitting MCP server. Pairs with the eve-sde skill (raw game data) and the eve-fitting MCP server (the calculator).
---

# EVE fitting knowledge

Layer 2 of the stack. The **eve-fitting MCP server** (pyfa's engine, headless)
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
  it (currently: industrial core, structures, custom skill sheets,
  fighter ability toggles). If the question touches one, answer
  with the engine number *plus* the named gap — never silently ignore it.
  Modeled: bursts (`set_booster`), environments (`set_env`), projected
  fits (`set_projected` — remote reps/ewar/neuts, zero range), T3D modes
  (`mode` op), fighters, implants and drugs (`edit_fit` add), mutated
  (abyssal) modules — rolls travel in the EFT `[N]` dialect
  (`references/traps.md` §T15) — overload bonuses (`state: 'overheated'`;
  burnout timers are not modeled, so name the tradeoff), and
  bastion/siege/triage — fit the module, set it active; the panel is the
  in-state ship and a `notes` line names the costs (§T16, incl. why
  bastion never dilutes your hardeners).
- **Skills are part of every number.** Presets: `all-0`, `alpha`, `all-5`
  (import default: all-5). **Assume an omega pilot** and quote all-V,
  labeled. Reach for `alpha`/`all-0` only when the question signals it —
  "alpha friendly", "just started", a named low-SP situation — then the
  alpha preset plus `required_skills`' `alpha_blocked` are the answer
  ("can an alpha fly this" is data, not folklore).

**No engine registered?** Setup is `fitting/mcp/README.md` (a local process +
`.mcp.json` entry). Without it you may quote layer-1 base-hull values marked
as pre-skill, pre-stacking — but do not hand-compute a stat panel, and do not
present remembered fit numbers as computed.

## Files

| File | ~tokens | Read it when |
| --- | --- | --- |
| `references/reading-stats.md` | 2.1k | interpreting any stat panel or graph — DPS/volley/sustained, EHP and damage profiles (incl. NPC profile table), cap stability, align, targeting, graph summaries, fitting headroom |
| `references/tradeoffs.md` | 1.7k | choosing between things — buffer vs active, shield vs armor, another damage mod vs a different slot, speed vs resists, and "what should I fit" questions (incl. the sweep-driven authoring loop) |
| `references/traps.md` | 3.1k | before asserting any mechanic: the numbered trap catalogue — stacking exemptions, wormhole/burst effects, hull resists, reload, tick rounding, drones, abyssal rolls, siege-class states |

Sizes are bytes/4, for budgeting; this router is ~2.4k.

## If you read nothing else

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

## Driving the engine

Fits are server-side objects addressed by short IDs — never re-send EFT
mid-conversation; it is the import/export currency only. The iteration loop
is `edit_fit` → `get_stats` (~290 tokens a step); A/B questions are one
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
in the engine (EFT `[N]` dialect) to verify it in fit context.

Panel keys carry units (`_s`, `_ms` = m/s, `_km`, `_gj`, `_hps`); resists
are fractions (0.598 = 59.8%), already converted from the SDE's inverted
resonance. Never guess a unit.

EFT rack order is slot order, and `[Empty ... slot]` gaps survive
import → export — heat-conscious layouts (modules spaced so overload
damage doesn't chain to neighbors) come back un-scrambled. The gaps
change no stats; `edit_fit` add fills the first gap, like fitting
in-game.

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
