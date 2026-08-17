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
