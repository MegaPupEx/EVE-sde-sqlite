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

### 2026-08-17 — CI: one poll, both layers

The layer-1 release workflow grows two jobs instead of a sibling file, so
there is exactly one CCP poll and one "build changed" decision. On a new
build (schedule/dispatch, default branch only — GitHub's rule for
schedules): `fitting-engine` restores a cached pyfa checkout + venv,
runs `refresh.sh --build <N>` (the same build the release job just
published), reruns the reference battery with the diff posted to the job
summary — an empty diff is "no balance change touches the fits", a
non-empty one is the auto-generated re-pin worklist — then runs selftest
plus the full MCP smoke suite, whose pinned assertions are the
enforcement: a real balance change turns the job red until references,
keys and docs are re-pinned. On any push touching `fitting/` (any
branch): `fitting-tests` runs the same suite against the bundled data
build, deterministic. The engine job uploads its battery panels as a
workflow artifact and adds nothing to the release, keeping every layer
independently installable. Concurrency groups split so push-test runs
never queue behind release builds; the marker-commit push can't
retrigger the workflow (path-filtered, and GITHUB_TOKEN pushes don't
fire workflows anyway).

### 2026-08-17 — module_attrs + sweep: per-module truth and cheap enumeration

Two tools close the gap between "interpret a fit" and "author one". The
finding that motivated them: eos models overload bonuses fully headless
(Fed Navy web 14 → 18.2 km at +30%, Warp Disruptor II 24 → 28.8 km at
+20%, both verified) and `edit_fit` already accepted `state:
'overheated'` — but nothing exposed per-module *modified* attributes, so
"what's my heated web range" had no computed source; and any tradeoff
scan cost one conversation round-trip per variant.

`module_attrs(fit, item, attrs)` returns named dogma attributes off the
live calculated module (or drone) — skills, hull bonuses, heat and
mutations applied — ~30 tokens. `sweep(fit, item, candidates, metrics)`
swaps each candidate in server-side, reports dotted panel metrics plus
cpu/pg margins and problem count per row, and restores the fit
(smoke-tested: post-sweep panel identical); ~30 tokens a row, 20-candidate
cap. A ten-variant tradeoff question ("meta plate to free room for a
better rep?") drops from ~10 round-trips / ~3–4k tokens to one call at
~350. The division of labor is in the skill now: knowledge prunes the
candidate list, the engine adjudicates it; mutaplasmid roll feasibility
stays a layer-1 SQL enumeration with only the winner engine-verified.

18 tools, ~1,885 tokens standing (was ~1,550 at 16 — the two schemas pay
for themselves the first time a sweep replaces a hand loop).
`engine_info().unmodeled` now names heat burnout timers explicitly while
stating overload bonuses ARE modeled, since that split invited folklore.

### 2026-08-17 — run 4: complex composition questions, 6/6, no balloon

The question behind the run: does asking the stack to enumerate (roll
feasibility, candidate tradeoffs) balloon token and time cost? Answer in
`fitting/evals/results4-2026-08-17.md`: no — six hard questions
averaged 42.5k tokens (35.8–56.4k, inside run 3's ordinary turn-one
band) and 60–192 s. The roll-ceiling question — "which faction web +
mutaplasmid matches a heated faction point's range" — was answered
correctly as **impossible** (24.4 km ceiling vs 36 km, engine-verified
as a built mutated fit overheated), with the enumeration done in SQL
and the engine reserved for verifying the winner; the legality landmine
(a pasted fit quietly over powergrid) and the napkin-math trap
((base+flat)×skill vs base×skill+flat) were both caught. Remaining
C-axis residue: two answers restated table numbers in prose.

Key preparation earned its keep again: driving the live long-lived
server crashed it on a sqlite cross-thread error — eos SQLAlchemy
objects are thread-bound, the MCP SDK dispatches to arbitrary worker
threads, and the smoke test's client masks it by single-threading —
fixed by pinning tools to one re-entrant engine thread (naive submit
self-deadlocked: tools call tools). And the router's mutaplasmid recipe
pointed at engine-db table names that don't exist in layer 1
(`dynamicItemAttributes` JSON is the layer-1 home); fixed before
subjects launched.

### 2026-08-17 — EFT rack layout preserved (heat-conscious ordering)

Within an EFT section, line order is slot order — the game client fills
slots in sequence on import — and `[Empty ... slot]` placeholders hold
gaps, which is how players space overloaded modules apart (heat damage
spreads to *adjacent* slots, attenuated per hull). The parser used to
skip placeholders, so a heat-planned layout round-tripped scrambled.

Now: placeholders parse into positioned empty modules
(`Module.buildEmpty`), build uses `appendIgnoreEmpty` — eos's plain
`append()` fills the first empty position in the rack, which was
silently swallowing authored gaps (found when the first test's Low and
High placeholders vanished but Med survived: only gaps with no module
after them lived) — and render re-emits `[Empty X slot]` in position.
`edit_fit` add keeps the fill-the-gap behavior deliberately, matching
what fitting a module in-game does. Stats are order-independent (heat
over time unmodeled), so the smoke test pins: placeholders identical
through export, dps identical with and without them, add fills the gap.

### 2026-08-17 — keep_slot removal, layout-safe sweep, heat-aware authoring

Follow-ups to layout preservation. `edit_fit` remove gains
`keep_slot: true`: the module's position becomes an `[Empty ...]` gap
(eos's `HandledModuleList.free`) instead of the rack closing up —
in-game semantics, so remove-then-add round-trips a swap in place. One
eos landmine: `free()`'s dummy carries no owner, and calc paths read
`module.owner.factorReload` even on empties — the freed gap crashed the
next stat panel until the server gave the dummy an owner (imported
placeholders already got one, which is why import-built layouts never
hit it).

`sweep` now replaces candidates *in position* (`replace(idx, mod)`)
instead of remove+append — append semantics were quietly re-filling
authored gaps during trials, so a sweep on a layout fit would return
correct rows and a scrambled fit. Smoke test pins export-identical
before and after a sweep on a gapped fit.

The authoring half: tradeoffs.md now tells the model to lay racks out
for heat when building fits from scratch — infer the overload set from
the fit's job (brawler: prop/tackle/reps; kiter: prop/point; gun racks
heat as a block), space those with gaps where slots are free, and order
full racks so the heated module sits next to what the pilot would
sacrifice first. Engine stats are order-blind; the layout rides the EFT.

### 2026-08-17 — summaries show racks; v2 scope settled (owner's cut)

Fit summaries (`import_fit`/`edit_fit`/`create_fit`/`clone_fit`) now
carry `slots` ({rack: [used, total]}, subsystems included when the hull
has them) and `hardpoints` (turret/launcher) — the shape questions that
used to cost a `validate_fit` round trip are now free with every
mutation. Writing the assertion produced a tidy own-medicine moment:
"Rifter has 4 highs" is folklore — the data says 4 low / 3 high, and
the test now pins the data. The answer-economy rule against restating
table cells in prose got the explicit wording run 4 showed it needed.

v2 scope is now the owner's five: siege/bastion/triage (with a standing
requirement that bastion's odd stacking behavior be derived from dogma
effect data + engine verification, source cited — no wiki folklore),
spool-across-time, projection & application realism (falloff-aware
projection plus target sig/speed context for turrets *and* missiles),
Upwell structures (service interactions + fuel; POS setup math verified
already covered by layer 1 — `controlTowerResources` for towers, and
gotchas-industry now documents the Upwell per-service fuel dogma next to
it), and full fighter support. Dropped: custom skill sheets,
heat-over-time, ISK/ESI.

### 2026-08-17 — v2 item 1: siege/bastion/triage land; bastion stacking sourced

The headline finding: the three states were never unmodeled — they were
*unverified*. Bastion, siege and triage modules are ordinary active
modules to eos; their effects fire headless with `state: active` and the
panel simply becomes the in-state ship (Phoenix torps 126 → 1,890 dps
sieged at 3 launchers ≈ 15×, speed 0; Minokawa Capital RSB 1,437 hp /
20 s → 7,906 hp / 5 s in triage).

The owner-flagged bastion question — "where do you find the weird
stacking rule" — resolved from primary sources, not the wiki: pyfa's
`moduleBonusBastionModule` handler multiplies each resonance with
`stackingPenalties=True, penaltyGroup='preMul'` (hull layer:
`penalize=False`), ordinary hardeners boost resonance in the default
`postPercent` group, and eos's calculator penalizes **per group**
(`__penalizedMultipliers[attr][group]`). Separate groups = separate
chains, so bastion never dilutes hardeners and vice versa.
Engine-verified on a Golem: hardener ×0.675, bastion ×0.700, both
0.4725 — the product exactly, where same-chain math gives 0.4990; a
second hardener meanwhile penalizes normally (×0.7175). Now traps §T16,
source named.

Productized: battery grows bastion-Golem / siege-Phoenix /
minokawa-triage reference fits (13 fits, 572 pinned leaves, old 10
byte-identical); `validate_fit` gains the in-game hull restrictions
(`fit.canFit`: canFitShipType/Group + fitsToShipType + Standup split,
plus the capital-size rule) so a bastion Rifter finally fails loudly;
`get_stats` appends a note naming any active siege-class state and what
it costs; smoke suite pins the resist product, the restriction, sieged
dps/immobility and triage rep numbers. `engine_info` unmodeled now
carries 'industrial core state' (out of scope) instead of 'siege
states'.

### 2026-08-17 — v2 item 2: spool across time; DC joins the bastion chain

Weapon spool is modeled: `get_stats` takes `spool: 0..1` (default 1.0 —
full spool, pyfa's own `globalDefaultSpoolupPercentage` convention,
replacing the old zero-spool floors), `offense.spool` carries the level
+ zero-spool floor + time-to-full, the panel note names the level, and
`graph(fit, 'dps_vs_time')` returns the ramp via eos's own
`SpoolOptions(TIME, t)` — all pyfa math (`calculateSpoolup`), no new
formulas. Both eval key sets verified unchanged across the default
switch. T11 rewritten: quote the band ("full X after Y s, floor Z"),
never one number.

Owner follow-up on bastion answered from the handlers and pinned into
T16: the `preMul` chain's other common resident is the **Damage
Control** — `damageControl` multiplies shield/armor resonance with
`penaltyGroup='preMul'` exactly like bastion, so DC and bastion DO
penalize each other (Golem: DC ×0.875 + bastion ×0.700 → 0.6240
penalized, not the 0.6125 product) while both stay independent of
hardeners. And bastion has no passive resist component: its effect list
is online/hiPower/moduleBonusBastionModule — resists exist only while
the state runs; the passive preMul resident is the DC. Also verified
the new hull-restriction check covers the whole class the owner asked
about: covert ops cloaks (Buzzard yes / Rifter no), bomb launchers,
burst jammers (hull-restricted in the data), clone vats — one
`fit.canFit` check, covert cloak pinned in the smoke suite.

### 2026-08-17 — v2 item 3: projection ranges + applied damage in one call

`set_projected` now takes `{fit_id, range_km}` entries: the range flows
into eos's own projected calc (`ProjectedFit.projectionRange` →
`forcedProjRange` → each effect handler's `calculateRangeFactor`), so a
web at half its optimal webs at full strength, at 8× optimal it does
nothing, and everything between follows the module's real
optimal/falloffEffectiveness — smoke-tested at all three points. Bare
ids still mean zero range (calculateRangeFactor(None) = 1), so existing
behavior and its "worst case" framing are unchanged.
`graph(projector, 'ewar_vs_range', item=…)` returns the effectiveness
band (pyfa's calculateRangeFactor over the module's modified attrs, heat
included if overheated).

`applied_dps(fit, distance_km, target={sig_m, speed_ms})` is the
application half: pyfa's full `getApplicationPerKey` model — turret
tracking/sig, missile explosion radius+velocity, drone mobility — as a
single call returning raw vs applied totals and a per-source-class
split. Smoke-tested both directions: an AC Rifter collapses to ~14%
application against a 35 m / 700 m/s target and recovers to ~100%
against 400 m / 100 m/s; an RLML Caracal shows the same shape through
the missile formula. One honest wrinkle pinned in the test and docs:
perfect turret application reads ~101.5% of paper dps — the
wrecking-shot expectation, pyfa's own model, not a bug. Damage maps in
graphs now use full spool, matching the panel default. 19 tools,
~2,180 tokens standing; both key sets unchanged.

### 2026-08-17 — v2 item 4: Upwell structures land

The Citadel calc branch works headless: build_fit (and so create_fit)
constructs `Citadel` for category-Structure hulls, and an Astrahus with
standup modules computes everything — 1,023 dps of standup cruise
missiles, 30.15M EHP across layers, service fuel — pinned as battery
fit 14 (616 leaves). Service slots joined every rack surface (EFT
`[Empty Service slot]`, summaries, overflow validation), `fit.canFit`'s
Standup/ship split gives two-way legality (a Gyrostabilizer on an
Astrahus and a Standup service on a Rifter both fail loudly), and the
panel gains two structure sections: `services` (per-service fuel
blocks/hr + onlining cost) and `defense.incoming_dps_cap` — the
per-layer `*DamageLimit` attributes (Astrahus 5,000/layer), because
EHP ÷ cap is the floor on time-to-kill and quoting structure EHP
without it misleads. T17 written; reinforcement windows and low-power
state named unmodeled.

Also this session: the wrecking-shot number pinned precisely — pyfa's
`_calcTurretMult` (citing EVE Uni) has wrecking shots *replace* the top
1% of hit rolls rather than add: 0.99 × 0.995 + 0.01 × 3 = 1.01505, the
observed 101.5%, not the folk 102–103%.

### 2026-08-17 — versus: the duel question becomes one call

Owner question: is "how does this fit do vs ship X" one tool, both
directions? It wasn't — applied_dps covered outgoing application but
not the victim's resists, and the mirror direction took composed calls.
`versus(fit_a, fit_b, distance_km)` closes it: for each direction it
computes the attacker's applied damage *mix* (application vs the
victim's current post-ewar sig/speed), sets the victim's damage pattern
to that actual mix and reads EHP against it (resists finally in the
loop), subtracts sustained reps, applies structure incoming-damage caps,
and reports time-to-kill or `tanked`. Assumptions ship in the response:
victim at max transversal, reps as one pool (defender-favoring), ewar
only if projected. Smoke test pins both directions on a Rifter/Punisher
duel and that webbing the victim raises the attacker's applied dps.
20 tools, ~2,340 tokens standing.

### 2026-08-17 — v2 item 5: full fighters; v2 scope complete

The `ability` edit op toggles any fighter squadron ability (substring
match; a miss lists the squadron's real ability names), `module_attrs`
now surfaces fighters with per-ability active flags, and fighter tube
validation splits by class — light/support/heavy, ship-side and standup
— on top of the total count, which yields cross-legality for free (a
Standup Einherji on a Thanatos and an Einherji II on an Astrahus both
fail with the exact tube class named). One default worth knowing,
pinned in T9 and the smoke suite: eos's Fighter constructor activates
every implemented damage ability it iterates before reaching the
standard attack, so light fighters default to missiles ON — 521 dps for
a Thanatos Einherji II squad includes the limited-shot missile volley.
The panel quotes what's active; toggling missiles off drops it, MWD on
raises squadron speed in module_attrs. With this, the owner's five-item
v2 scope is complete: siege states, spool, projection/application,
structures, fighters — all engine-verified, all pinned.

### 2026-08-17 — post-v2 review: nine findings, two of them serious

A high-effort review of everything since eval run 4 (12 commits) found
nine real issues, all fixed and pinned the same session:

1. **Fighters were invisible to applied_dps and versus** — the damage
   map never included them while pyfa's application map keys fighters as
   `(fighter, effectID)` per ability. A carrier duel computed from ~0
   attacker dps. Fixed via `getDpsPerEffect` with matching tuple keys;
   a Thanatos now shows its fighters bucket (794 dps applied at 10 km).
2. **Fighters were dropped by export/clone** — render_eft never emitted
   them, so clone_fit produced fighterless copies (and versus's own
   advice is "clone_fit it first"). Fixed + quantity round-trip
   ('Einherji II x3' imports as 3, exports as 3; a bare fighter line no
   longer crashes the builder — and a partial squadron no longer
   silently quotes full-squadron dps).
3. **versus leaked the opponent's damage pattern** onto both fits,
   skewing later sweep/module_attrs reads; now saved and restored.
4. Offline disintegrators no longer trigger spool notes or graph a
   flat-zero ramp (spool detection now requires ACTIVE state).
5. versus names its full-spool assumption.  6. edit_fit's bad-op error
   lists all six ops.  7. The spool-ramp scan lives in ONE place
   (`panel.spool_ramp`, graphs import it).  8. The rack table is one
   module-level constant.  9. (verified non-issue: ewar_vs_range's
   attr choice matches the effect handlers.)

Battery 616 leaves and both key sets verified unchanged across all nine
fixes. Lesson recorded: the fighter gaps shipped inside the very item
called "full fighter support" — review-after-milestone stays in the
process.

## 2026-08-18 — eval gen 5: 20 live multi-turn sessions, full v2 surface

Ran the v2 acceptance eval: 20 subjects × 3 turns (10 full-stack, 10
layer-2-only), 30 brand-new questions, keys drive-script-pinned at build
3470007 before launch (`fitting/evals/questions5.md`, raw:
`keys5-3470007.json`, results: `results5-2026-08-18.md`).

**53/60 PASS (9 PASS+), 7 PARTIAL, 0 FAIL.** Subjects beat the pinned keys
twice — Standup Market Hub cannot fit an Astrahus (the key's derivation
had bypassed hull legality with a raw edit-add; validate knows better),
and the T1-frigate mids answer is a three-way tie at 5 (Griffin/Heron/
Vigil). Both corrections verified and folded back. One key typo fixed
(Astrahus armor 9.0M → 30 min).

Mid-run incident became the best test of the run: an account session
limit killed six subjects mid-turn AND silently restarted the shared MCP
server, wiping the fit registry. The two ch2 subjects lost the same
resident Vedmak: the one whose stale id failed loudly re-imported and
hit the key exactly; the one whose stale id had been recycled to another
subject's Thanatos got silently-aliased fighter numbers and built a
confident (wrong) engine-bug narrative on top of an honest refusal to
quote them. Loud staleness recovers; silent aliasing misleads.

Three product fixes implemented from findings: (1) fit-scoped responses
echo the ship name; (2) fit ids salted per server boot so stale handles
never silently resolve; (3) `incoming_dps_cap` reports a layer as 'none'
when its "cap" equals full layer HP. Root cause of the cap-flatten turned
out to be the skill itself: traps.md T17 asserted "5,000 dps on every
layer" — the doc taught the error and three of four subjects repeated it
over the panel's own 14.4M. T17 rewritten (non-uniform caps, read them
per layer). A wrong pinned fact grades worse than no fact — in the trap
catalogue most of all. Also recorded: both arms
mis-directed the Drake uniform-vs-Guristas comparison (traps.md
candidate), and the l2only arm can still answer enumeration questions
from the engine's own staticdata db (legit layer-2 capability; eval-arm
design note).
