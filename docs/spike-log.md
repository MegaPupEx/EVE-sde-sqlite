# Engine spike log

Phase 1 of `docs/roadmap-fitting-mcp.md`. Timebox: one week per candidate,
A first. This log is the record the decision gets made from.

## 2026-08-16 — Candidate A (pyfa's embedded eos): extraction succeeded

**Result: pyfa's eos runs fully headless.** One session took it from "unknown
extraction depth" to the complete 10-fit reference battery computing every
v1 stat-panel figure — EHP by layer with resists, burst/sustained/drone DPS,
volley, cap stability from the event simulation, align/speed/sig, targeting,
fitting headroom. Runner and battery live in `fitting/spike/`.

### The entanglement map (the spike's central question, answered)

The wx dependency is shallower than the roadmap feared:

- **eos has zero top-level GUI imports.** The only `from gui` imports in the
  whole package are three *lazy* imports inside functions in
  `eos/effectHandlerHelpers.py` (fit-command helpers); none trigger on the
  headless calculation path.
- **One indirect wx reach**: `eos.db` → `eos/db/migration.py` →
  root `config.py` → `import wx` — and root config uses wx only for
  `wx.Colour` UI constants. A 3-line stub class satisfies it
  (`fitting/spike/wxstub/`). Root config also needs `cryptography`
  (ESI token storage) — a real pip dependency, installed not stubbed.
- **saveddata goes in-memory** via pyfa's own CI hook: eos/config.py checks
  `sys._called_from_test`.
- **Two API sharp edges** (documented in the runner, cost ~20 min total):
  `import eos.db` must precede any `eos.saveddata` import (circular
  otherwise), and `module.owner`/`drone.owner` are ORM backrefs that must be
  set manually when no saveddata session exists.
- **`eve.db` builds headless** from the JSON static data bundled in pyfa's
  repo (`python3 db_update.py`, ~1 min, 100 MB) — no GUI, no network beyond
  the clone.
- **Minimal dependency set**: sqlalchemy 1.4.50, logbook, python-dateutil,
  pyyaml, roman, cryptography, requests. No wxPython, no matplotlib, no
  numpy.

**What did not extract cleanly: EFT import/export.** `service/port/eft.py`
imports `service.fit`, `service.market` and `gui.fitCommands.helpers` —
the service layer imports wx at top level. Options for v1: stub deeper, or
write a thin EFT parser that builds `eos.saveddata` objects directly (the
battery runner already shows the construction pattern; a parser over it is
small). Leaning: own parser, revisit when the mutated-module EFT dialect
lands.

### The data-skew rule, vindicated immediately

pyfa's bundled static data is **client build 3424810, dumped 2026-07-07**.
CCP's current SDE (and our layer-1 database) is **build 3466501, released
2026-08-13**. The skew the roadmap's data-sync rule exists to name is not
hypothetical — it is present on day one of the spike. Every reference JSON
carries `engine_client_build` so no number can be quoted without its data
generation. Refreshing pyfa's staticdata (their Phobos dump pipeline) or
feeding eos from our SQLite is the open v2 investigation, now with evidence.

### The reference battery

10 fits, all-V, uniform damage profile, chosen for effect-matrix coverage
(`fitting/spike/battery.py` documents what each exercises; panels in
`fitting/spike/reference/`):

| fit | dps | sustained | volley | ehp | cap | align | m/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rifter-ac-brawler | 172.3 | 164.1 | 213.9 | 2,955 | 22.5s | 4.69 | 3,213 |
| punisher-pulse-armor | 91.6 | 91.6 | 206.6 | 6,682 | 87.7% | 5.10 | 1,071 |
| merlin-blaster-shield | 227.0 | 220.9 | 512.0 | 6,538 | 540s | 5.04 | 2,930 |
| caracal-rlml-shield | 298.0 | 178.7 | 780.9 | 16,943 | 80s | 6.27 | 2,078 |
| vexor-drone-armor | 431.6 | 428.9 | 1,744.9 | 31,102 | 69.9% | 10.25 | 575 |
| drake-ham-passive | 535.1 | 520.6 | 2,317.8 | 47,178 | 1,430s | 11.25 | 444 |
| hurricane-arty-alpha | 554.1 | 525.9 | 4,066.9 | 37,541 | 200s | 9.40 | 1,557 |
| abaddon-pulse-armor | 1,149.4 | 1,149.4 | 5,300.5 | 188,246 | 198.3s | 22.72 | 289 |
| raven-cruise-active | 838.2 | 793.2 | 5,473.9 | 52,360 | 120s | 16.77 | 381 |
| zealot-pulse-t2 | 442.4 | 442.4 | 1,360.2 | 44,572 | 77.7% | 10.93 | 593 |

Spot checks that pass: the RLML burst/sustained split (298 → 179) shows clip
+ 35 s reload modeling; the Drake panel shows the hull resist bonus
compounding with the hardener on shield only, DC II on hull, and 196.6 hp/s
peak passive regen; MWD sig bloom and mass math visible on the Rifter
(3,213 m/s, 210 m sig). Full battery computes in ~4 s.

### Verdict: candidate A wins — spike closed 2026-08-16

The human spot-check happened the same day: three battery fits (Rifter,
Punisher, Raven) imported into a desktop pyfa GUI with an All-5 character
and compared panel-by-panel against the reference JSONs. **Every figure
matched at display precision** — EHP per layer and resists, DPS and volley,
cap capacity plus stable-% / time-to-empty from the simulation (Raven
"lasts 2m0s" = the JSON's 120.0 s), speed/align/sig, scan res, lock range,
sensor strength, max targets, and CPU/PG including pyfa's two-decimal
rounding. Headless eos and the GUI are the same engine producing the same
numbers; the criterion ("reproduces pyfa's stat panels within rounding,
driven headless") is satisfied with confirmation, not by construction alone.

**The engine decision is made: wrap pyfa's eos.** The dogma-engine timebox
is not needed; B remains the named fallback if A develops a blocker, and
the battery JSONs are ready to grade it if that day comes.

Two small notes from the spot-check screenshots:
- The GUI's "Recharge rates" panel shows active rep rates (raw and
  effective HP/s) that our stat panel does not yet capture — add
  `fit.effectiveTank` rep rates to the `get_stats` schema at MCP v1.
- The battery's Punisher uses 3 guns on a 4-hardpoint hull (visible as 3/4
  in the GUI). Harmless for coverage; leave as-is since the references are
  now pinned, fill the 4th slot only if the battery is ever regenerated.

### Follow-ups carried out of the spike

- Battery additions: implants + booster fit, alpha-clone skill set
  (`cloneGrades` from layer 1), overheated states, a mutated-module fit,
  non-uniform damage profiles.
- ~~Thin EFT parser over eos.saveddata construction~~ **Done 2026-08-16**:
  `fitting/engine/eft.py` — parse/build/render; self-test proves the parsed
  battery produces panels identical to the pinned references and survives a
  render round-trip (10/10).
- License note: eos is GPL — fine while we run it as a local tool; if the
  MCP server ships bundled with pyfa code, the server is GPL too. Flag at
  MCP v1 packaging.
- ~~pyfa staticdata refresh cadence vs CCP builds~~ **Resolved 2026-08-16**,
  and better than the v2 investigation hoped: `fitting/adapter/` generates
  pyfa's staticdata inputs from CCP's current JSONL export, so pyfa's own
  unmodified `db_update.py` builds `eve.db` at the skill's SDE build.
  Verified: battery at build 3466501 vs pinned 3424810 references — 440
  leaves, zero diffs. The engine and the skill now share one data source,
  and the panel diff on future builds is the balance-change report.

### 2026-08-17 — MCP v1 server landed, token budget validated

`fitting/mcp/server.py`: 11 tools over headless eos — lifecycle, EFT
import/export, `edit_fit` ops, `set_skills` (all-5 and alpha, via eos's own
AlphaClone data from `cloneGrades`), `get_stats` with damage-profile
weights plus rep rates (closing the spot-check note), `compare_fits`
(diff-only), `validate_fit` (named constraints: cpu/pg/calibration, slots,
hardpoints, drone bandwidth/bay), `engine_info` with the explicit
unmodeled list. `test_server.py` drives the whole surface over real stdio,
asserting panel numbers against the pinned battery — passes on both the
bundled data build and the adapter-generated current build.

**Measured budget** (printed by every test run): ~880 tokens standing for
all schemas, ~260 per stats panel, ~290 per edit+stats iteration — an
order of magnitude inside the roadmap's envelope, sized for a Sonnet-class
consumer going answer to answer.

One engineering finding worth keeping: MCP tools execute on worker
threads, and sqlite `:memory:` saveddata is per-connection — the server
uses a temp-file saveddata DB plus `eos.db.saveddata_meta.create_all()`
(pyfa.py's own startup call). Symptom if regressed: `no such table:
overrides` on first import.

### 2026-08-16 — post-spike: EFT parser and data-sync adapter landed

Both first work items for MCP v1 are in:
- `fitting/engine/eft.py` — EFT parse (text-only, no eos) / build (eos
  objects, category-classified like pyfa's importer, comma-in-name safe) /
  render. Mutated modules fail loudly by design pending the dialect
  decision. `fitting/engine/selftest.py` is the proof harness.
- `fitting/adapter/make_staticdata.py` — see `fitting/adapter/README.md`
  for the format notes (two real CCP-vs-pyfa divergences found and
  handled: dynamicItemAttributes list-vs-dict, localized effect
  descriptions).

## 2026-08-17 — fitting-knowledge skill v1 + first graded eval run

Phase 3 of the roadmap. `.claude/skills/eve-fitting/` (named to match the
MCP server it pairs with, parallel to `eve-sde`): a ~1.6k-token router —
well inside the ~4k budget — plus three references (`reading-stats`,
`tradeoffs`, `traps`, ~1.5–1.9k each). The router carries the answer
discipline (authority order SDE > engine > wiki > memory, layer naming,
the engine/SDE/CCP build-skew check, unmodeled-means-named); the
references carry the teaching. NPC damage-profile weights come from
pyfa's own presets, so even the "game knowledge" table is engine-layer
sourced.

**Writing the traps file caught a formulas-doc error.** Verifying §1's
beacon claims against pyfa's actual handlers: category 2 decides
*eligibility*, the attribute's stackable flag decides each case — the
black-hole velocity multiplier and the resist maluses are penalized
(`stackingPenalties=True`), but a Pulsar's shield HP multiplier hits
`shieldCapacity` (stackable) and applies in full. The doc's example had
overshot; corrected 2026-08-17.

**Eval set 1** (`fitting/evals/`): 10 questions, roadmap classes 1+2,
keys engine-pinned per data build (`keys-3424810.json`, regenerable by
`make_keys.py`). Key generation itself caught an engine bug —
`set_skills('alpha')` mutated pyfa's shared All-5 character, silently
turning every fit in the session alpha (fixed; smoke test now asserts
restoration and fresh-import isolation) — and a docs error (the battery
Caracal *gains* EHP vs Guristas, 16,943 → 18,511; the doc claimed a
loss). Also pinned: the battery Hurricane (1,681/1,425) and Vexor
(985/875) are PG-over — coverage fits, never legality-checked; the evals
now use that as a discipline probe.

**Graded run** (`results-2026-08-17.md`): control 27.5/40 (69%) vs
with-skill 39/40 (98%), fresh Sonnet sessions, identical engine access.
Both control outright misses (guessed NPC profile weights; "env effects
are stacking-exempt" plus inverted Wolf-Rayet effects) are exactly the
docs-owned content the skill carries. Every miss root-caused: one docs
gap fixed and pinned mid-run (validate_fit doesn't check skill
prerequisites — traps §T12), one harness key fixed (the battery Vexor has
a free mid; a shield tank needn't drop the web), one model-owned nit
logged. Notable negative result: the control's 69% shows the MCP surface
itself (problems lists, unit-suffixed keys) carries real discipline —
every control run that imported a fit caught the PG-illegal battery fits.

## 2026-08-17 — phase 4: graphs + the external-effects pipeline (first slice)

Same day, phase 4 of the roadmap. The MCP grows from 11 to 14 tools
(~1,281 tokens standing, still an order of magnitude inside the envelope);
eval keys verified unchanged after the refactor.

**`graph()`** — `dps_vs_range`, `dps_vs_target_speed`, `cap_vs_time`; ≤30
points + summary stats + named assumptions, ~110–190 tokens a payload.
Wrap-don't-reimplement held: the application factors are pyfa's own
`fitDamageStats/calc/application.py` — reached by registering synthetic
`graphs.*` package entries so the wx GUI `__init__`s never run, with
`GraphSettings` shimmed to pyfa's pinned defaults — and the cap series is
eos's event-sim trace (`fit.getCapSimData`, times in seconds). One
teaching note fell out: applied DPS at perfect hit reads ~1.015× the
panel figure (the wrecking-shot expectation; the GUI graph shows the
same) — pinned in `reading-stats.md`.

**`set_env`** — projects a system beacon onto the fit
(`projectedModules`, one per fit, groups: Effect Beacon,
MassiveEnvironments, Abyssal Hazards, Destructible Effect Beacon).
Verified: C5 Wolf-Rayet takes the battery Rifter ×2.69 DPS — the ×2.72
beacon modifier stack-penalized in the multiply group, exactly the traps
§T1 story, now engine-computable instead of doc-only. `set_env` affects
only the fit it is set on; the skill's T2 now says so.

**`set_booster`** — command bursts, pyfa's recursive model without the
saveddata ORM: each booster fit's own `calculateModifiedAttributes(subject,
CalcType.COMMAND)` runs before the subject's calc. Measured: Drake burst
+15.0% shield, Vulture +17.25% (hull scaling), both-projected = Vulture
alone (strongest-wins). Engineering finding worth keeping: **eos consumes
`commandBonuses` as it applies them** (`__runCommandBoosts` deletes each
entry), so the booster pass must rerun before *every* calculation —
`panel.stat_panel` gained an injectable `recalc` for this; the smoke test
asserts the second read still carries the burst.

**T3D modes** — `edit_fit` op `mode` sets `fit.mode` (group Ship
Modifiers); Confessor Defense vs Sharpshooter sig 43.3 vs 65 verified.

**Deferred from v1.5, with reasons:** projected fits (remote reps/ewar —
same CalcType pattern but needs per-module projection wiring and a
target-fit surface), fighters (ability-level model plus battery
additions), mutated modules (blocked on the EFT dialect decision).
`engine_info().unmodeled` names all three, and now also names
implants/boosters — true since v1, previously unstated.

Docs updated in step: router + traps §T1/T2 no longer call bursts/env
unmodeled, reading-stats gained a graphs section, MCP README re-measured.
Eval generation 2 candidates (results-2026-08-17.md) now include
engine-truth keys for T4/T5's mechanics, which this slice made computable.

## 2026-08-17 — v1.5 closed (minus mutated), all-0 preset, v2 scoped

`set_projected` finishes the external-effects pipeline: other fits'
modules/drones apply onto the subject (webs ×0.500 exact, a Curse neut
takes a stable Punisher to dead-in-12-seconds, Scythe remote reps land in
`reps_hps`). The ordering finding is the mirror of the burst one and both
now live in `_recalc`: **bursts before the subject's local calc, projected
fits after it** — the local calc's `clear()` wipes anything projected
earlier, which cost an hour of "projection silently does nothing" before
pyfa's own LOCAL path revealed the order. Fighters (squadron-sized,
standard attack, `dps_fighters` panel key, tube/bay validation), implants
and drugs (category-routed through `edit_fit` add; +3% hardwiring and
Quafe Zero verified to the percent) closed the rest. `set_skills` gained
`all-0` — per product decision, the *default answer* for a pilot of
unknown skills is now the all-0 floor bracketed with the all-V ceiling.

Mutated modules are the one v1.5 item deferred: the dialect decision is
made (pyfa's `[N]`-reference EFT format), the remaining work is parser +
eos construction, spec'd in the roadmap's new "What v2 needs" list along
with siege states, spool-up, structures, custom sheets, projection-range
realism, fighter toggles, heat, and ISK cost.

15 tools, ~1,422 tokens standing; smoke test covers every new mechanism;
eval keys verified unchanged throughout.

### 2026-08-17 — graded run 2: layered 100% vs fit-sim-only 81%

Full write-up in `fitting/evals/results2-2026-08-17.md`. The headline:
sim-only jumped 69% → 81% between generations *because v1.5 moved the
mechanics into the engine* — the skill's edge now concentrates in
discipline, the unmodeled, and the engine/game-knowledge boundary
(spool: 1.5 vs 4; T2 prerequisites: 3 vs 4). Two engine fixes fell out
of grading and are pinned in the smoke test: `get_stats` names zero-spool
floors on spool weapons, and charge ops reject wrong-size charges (the
sim arm's Vedmak number had been computed on an L charge in an M gun,
silently). One docs pin (§T1: bonuses and penalties are separate chains)
and one harness fix (G4's phantom armor repairer). Token accounting and
the no-effort-control caveat are in the results file.

### 2026-08-17 — run 3: multi-turn session costs

Twelve persistent sessions × three turns (fitting-layered, fitting-bare,
SDE-only, and layered-with-unrelated-questions arms), measuring marginal
cost per follow-up. Full data in `fitting/evals/results3-2026-08-17.md`.
Headlines: turn one is the whole cliff (38–82k transcript tokens) and
follow-ups run ~6k (SDE) to ~8–18k (fitting) — even *unrelated* questions
in a warm session cost a fifth of a cold start; latency is dominated by
per-invocation engine boots the production MCP registration doesn't pay;
and the two cheapest turns in the run were the two *wrong* ones (sim-only
answering environment and neut questions from memory). One engine bug
found and fixed mid-run: rack overflow had never actually been validated
(eos compares slot enums by identity; EFT-built modules carry ints) —
caught by a layered subject reading layer 1, of all things, after it
flagged an illegal test fit of mine the broken check had passed. Router
gained the conversation-economy rules the outlier turns paid for.

### 2026-08-17 — mutated (abyssal) modules land; v1.5 is complete

Pyfa's EFT mutation dialect adopted exactly (`service/port/eft.py` +
`muta.py` are the de-facto spec): fitted lines carry the *base* item name
plus an ` [N]` reference; a trailing section maps each N to base item,
mutaplasmid item, and comma-separated `attr value` pairs — **absolute**
rolled values. `fitting/engine/eft.py` now parses the section (strict:
malformed pairs and unknown attrs raise, naming the block), builds via
eos's own path (`getDynamicItem(mutaplasmid.ID)` →
`Module/Drone(dyn.resultingItem, baseItem, dyn)` → set
`mutators[attrID].value`, where the Mutator validator clamps to the
mutaplasmid band), and renders the section back (attrs sorted by name,
`floatUnerr`, refs renumbered from 1 — byte-compatible with pyfa's
export).

Verified: a max-roll Decayed Gyrostabilizer moves a Rifter's panel DPS,
export→reimport is stat-identical, an out-of-band roll (2.0 on a
0.995–1.008 mutaplasmid) clamps to the max-roll number, and the drone
path round-trips too (Exigent-mutated Hobgoblin). Two traps worth the
log: a bare abyssal type name ('Abyssal Gyrostabilizer') used to die
inside eos with "Passed item is not a Module" — it now raises a named
EftError explaining the mutation block *is* the data; and unrolled
attributes still carry the mutated item's own baseline values, so the
render emits the full mutator set, exactly like pyfa. One test-authoring
lesson: Hobgoblin II's base damageMultiplier is already 1.92 on this
build — the first "mutated" drone test rolled the base value and proved
nothing until the roll moved.

`engine_info().unmodeled` drops 'mutated modules'; skill router updated;
traps gains §T15 (roll-is-the-data, killboard pastes without the section,
clamping); eval keys 1 and 2 verified unchanged; smoke test grows the
module + drone round-trip, clamp, and bare-abyssal-rejection assertions.

### 2026-08-17 — build refresh operationalized; engine moves to 3470007

`fitting/adapter/refresh.sh` turns the adapter's three manual steps into
one idempotent command: read CCP's manifest (or `--build N`), download
that build's JSONL zip into a gitignored cache, generate pyfa's
staticdata, swap it into the checkout, rebuild with pyfa's own
`db_update.py`, and verify `client_build` — a no-op when the db is
already current. CCP shipped build 3470007 the same day (the manifest
moved past even layer 1's 3466501), so the working engine refreshed to
it as the first real run.

The re-pin that follows a refresh, executed in full: battery rerun at
3470007 vs the pinned 3424810 references — **440 leaves, zero
differences** (two CCP builds without a balance change these fits
touch); reference panels re-stamped at the working build (meta-only
diff); eval keys regenerated — numerically identical, so
`keys-3470007.json` / `keys2-3470007.json` replace the 3424810 files
with only the embedded build string moved; selftest 10/10 and the full
smoke suite green on the new db. Skill docs now quote 3470007 and traps
notes the claims held across the refresh.

The remaining skew window is operational, not architectural: layer 1's
release workflow polls CCP every 3 h and self-publishes; the engine
refreshes when `refresh.sh` is run. Between the two, `engine_info()` vs
`meta.sdeBuildNumber` names the gap — which is the designed behavior,
not a bug. CI running `refresh.sh` + battery-diff per CCP build (the
auto-generated balance report) stays on the backlog.
