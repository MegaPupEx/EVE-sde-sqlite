# Roadmap: EVE Fitting Engine MCP + Knowledge Layers

Status: design approved, build not started. This document is the starting
brief for the sessions that build it. The SDE skill (`.claude/skills/eve-sde`)
is the finished layer this builds on; its eval methodology is the process
model for everything below.

## What we're building

The SDE skill answers *what the data says*. It cannot answer *what happens
when you combine things* (fits, buffs, stacking) or *what players know*
(doctrine, strategy, mechanics not in any data). This adds both, as two new
layers on the same philosophy that made the SDE skill work: **local verifiable
data + a query surface + docs that teach the traps + an eval harness that pins
every claim.**

- **Layer 1 — SDE skill** (done): what the data says.
- **Layer 2 — Fitting engine MCP + fitting-knowledge skill**: what happens
  when you combine things.
- **Layer 3 — EVE knowledge base + strategy skill**: what players know.

**Product target (stated 2026-08-17):** the end product is a skill stack a
**Sonnet 5 medium-effort** chat runs well (high only if truly needed) —
answering EVE questions quickly, generating fits, compiling accurate SDE
data *with interpretation of what the numbers mean*, and going answer to
answer with token counts low enough to never brush rate or context limits.
Every design decision below serves that consumer; anything that costs
standing tokens must earn them.

Each layer is verified against the layer below it. Each has its own harness.
Answer authority is strictly ordered: SDE data > engine output > wiki >
model memory, and answers name the layer they came from.

## Non-goals (v1)

- No live data (market prices, kills, sov) beyond the ESI pointers the SDE
  skill already carries. Fit ISK cost is a later ESI bolt-on.
- No killboard/meta analysis ("what are people flying").
- No GUI. The session is the interface; graphs are structured data the
  session renders or reasons over.
- Not a pyfa replacement for humans — it is pyfa *for the model*.
- Structures (fittable citadels) are explicitly out of v1 (see effect matrix).

## Layer 2: the fitting engine

### The rule that dominates the design

**Do not reimplement dogma math.** The SDE carries every input (attributes,
effects, 509/511 skills' machine-readable `modifierInfo` wiring — verified
during the SDE work) but not the engine: the stacking-penalty constant,
operation ordering, and per-category application rules are game constants
that exist only in implementations. Pyfa has spent 15+ years getting the edge
cases right. We wrap, not rebuild.

### Engine candidates and the decision criterion

| Option | For | Against |
| --- | --- | --- |
| **A. Pyfa's embedded engine** (the `eos` package inside the pyfa repo) | Python (matches stack), the reference implementation players trust, GPL | Entangled with the wx GUI; extraction depth unknown |
| **B. Standalone `dogma-engine`** (Rust, powers EVEShip.fit) | Built headless, clean API | Second language, own data format, younger project |
| **C. Reimplement from SDE** | Perfect build-sync | Months of edge cases; the wrong use of time |

**Decision criterion (timeboxed, one week each, A first):** the winner is the
first engine that, driven headless, reproduces a battery of ~10 known fits'
pyfa stat panels (EHP, DPS, cap stability, align) within rounding. If A's
extraction is shallow, A wins on language and trust. If it is a tarpit, B.
C only if both fail.

Both candidates clone directly in remote sessions (verified 2026-08-16):
`github.com/pyfa-org/Pyfa` and `github.com/eveshipfit/dogma-engine` (note the
lowercase org — `EVEShip-fit` 404s). The formulas the harness checks by hand
are pinned in `docs/fitting-formulas.md`, with pyfa/dogma-engine file and
line references.

**Ground truth = pyfa** for v1: it is what players compare against.
Divergences from the live server get documented as gotchas when found, not
silently corrected either way.

### Effect-source matrix (tiered)

The complete list of things that change a fit's numbers, and when each lands.
Anything not modeled in the current tier must be *named as unmodeled* in
output, never silently ignored.

**v1 — the fit itself:**
- Character skills (all-V, the byte-exact Alpha set from `cloneGrades`, or a
  custom sheet)
- Ship hull bonuses (per-skill-level and role bonuses)
- Charges loaded, including damage/tracking tradeoffs, **and scripts** (which
  flip *what* a module boosts rather than scaling it)
- Other fitted modules, rigs, T3 subsystems
- Drones (damage and effect receivers both)
- Implants (including set bonuses) and boosters/drugs
- Overheat
- Ancillary states (AAR paste, ASB charges) and the reload-DPS toggle

**v1.5 — external effects (one shared pipeline):**
- ~~Command bursts~~ *landed 2026-08-17* — modeled as a *separate boost
  fit* whose own skills, mindlinks and hull scale the burst (recursive,
  like pyfa does it)
- ~~Projected fits~~ *landed 2026-08-17 (`set_projected`, zero-range)*:
  remote assistance/impedance, where the projecting ship's own rigs/skills
  scale the projected module (same recursion)
- ~~Environmental~~ *landed 2026-08-17 (`set_env`)*: wormhole phenomena,
  k-space metaliminal storms, abyssal system-wide weather, local AoE
  (abyssal clouds, ESS bubble), incursion and insurgency system effects.
  Note: internally these are dogma projections while bursts are warfare
  buffs — different systems (see `docs/fitting-formulas.md` §1), though
  they share the tier.
- ~~Mutated (abyssal) modules~~ *landed 2026-08-17 (pyfa's `[N]` EFT
  dialect: parse/build/render in `fitting/engine/eft.py`; rolls are
  absolute values, eos-clamped to the mutaplasmid band; identical
  export→reimport verified for modules and drones)*
- ~~Fighters~~ *landed 2026-08-17 (standard attack; ability toggles are
  v2)* (ability-level effects; the SDE work already mapped
  `fighterAbilities`) — promoted from v2, 2026-08-16
- ~~Tactical destroyer modes~~ *landed 2026-08-17 (`edit_fit` op `mode`)*
  (Confessor/Svipul/Hecate/Jackdaw) — promoted from v2, 2026-08-16; modes
  are items applying ordinary dogma modifiers, no new math

**v2:**
- Siege-class states (siege, bastion, triage, industrial core)
- Spool-up weapons (Triglavian ramp — makes DPS time-dependent; needs a
  spool parameter or time series)
- Structures (fittable citadels)

### What v2 needs (assessed 2026-08-17, at v1.5 close)

Everything left, with what building each requires:

1. ~~**Mutated (abyssal) modules**~~ *landed 2026-08-17* — pyfa's EFT
   format adopted exactly (`[N]` references + mutation section);
   parse/build/render in `fitting/engine/eft.py`, eos Mutators clamp
   rolls to the mutaplasmid band, round-trip tests in
   `fitting/mcp/test_server.py` (module + drone, clamp, bare-abyssal
   rejection).
**v2 scope settled 2026-08-17 (owner's cut): the five items below, and
the rest is dropped.**

2. ~~**Siege-class states**~~ *landed 2026-08-17* (siege, bastion,
   triage; industrial core stays out of scope). The effects turned out
   to run headless as ordinary active modules — the work was
   verification and productizing: three battery fits (bastion Golem,
   siege Phoenix, triage Minokawa; battery now 13 fits / 572 pinned
   leaves), hull-restriction legality in `validate_fit` (`fit.canFit` +
   capital-size — a bastion Rifter now fails), and a `notes` line naming
   the state's unshowable costs. **Bastion sourcing requirement:
   fulfilled** — the answer came from the `moduleBonusBastionModule`
   effect handler + eos's per-group penalized calculator: bastion
   multiplies resonance in the `preMul` penalty group, hardeners boost
   in `postPercent`, groups penalize independently, so the chains never
   meet (engine: 0.675 × 0.700 = 0.4725 exactly; same-chain would be
   0.4990); hull resists exempt outright. Documented as traps §T16 with
   the source named.
3. **Spool across time** — DPS quotable at named spool levels/times.
   eos already carries `SpoolOptions`; needs a `spool` parameter on
   `get_stats`/`graph` (or dps_at_0/50/100 keys), a `dps_vs_time` graph
   kind, and skill docs for quoting spool honestly (pyfa's own NPC
   profiles ship at three spool levels).
4. **Projection & application realism** — two halves of one feature.
   Projection: `set_projected` at actual ranges with falloff-aware
   ewar/rep strength (`ProjectedFit.projectionRange` is already plumbed
   in eos), plus an `ewar_vs_range` graph kind. Application: target
   signature and speed as first-class context for **both** weapon
   systems — turrets (tracking vs transversal, sig vs resolution) and
   missiles (explosion radius/velocity vs target sig/speed) — so
   "what does this fit do to a frigate under it" is one computed
   answer, not a graph the model must interpolate by hand.
5. **Structures (Upwell)** — eos has the `isStructure` calc branch.
   Needs: structure hulls in `create_fit`, service-slot fitting rules
   and separate validation, service-module *interactions* checked, fuel
   accounting surfaced (per-service `serviceModuleFuelAmount` /
   `serviceModuleFuelOnlineAmount` dogma — verified present in the SDE
   2026-08-17), and structure-specific panel semantics. Note: POS
   (starbase) setup math needs **no engine work** — layer 1 already
   carries tower fuel (`controlTowerResources`, gotchas-industry
   documents the `purpose` trap) and the Upwell fuel attributes;
   gotchas-industry now points at both models.
6. **Full fighter support** — abilities beyond the auto-activated
   standard attack (missiles, bombs, utility), light/support/heavy tube
   split validation, across every fighter-capable hull and, once item 5
   lands, structures.

Dropped from scope (2026-08-17, owner's call): custom skill sheets;
heat-over-time (assessed the same day: every input is in the SDE —
per-rack capacity 100 / dissipation 0.01, per-hull
`heatGenerationMultiplier` 1.0→0.25 and `heatAttenuation` 0.5→0.82,
per-module `heatDamage` vs 40 heat HP, Thermodynamics −5%/lvl; buildup
is deterministic, the damage rolls are the random part — but pyfa has
no heat-over-time sim, so there is no wrap target and no ground truth
to pin keys against; revisit only if demand appears once layer 3 makes
the mechanism citable); and fit ISK cost (ESI stays out entirely).

### MCP tool surface (v1)

Consolidated to ~8–10 tools (see token budget). Fits are **stateful**
server-side objects addressed by ID; EFT text is the import/export escape
hatch, not the per-call payload.

Lifecycle:
- `create_fit(ship)` / `clone_fit(fit)` / `delete_fit(fit)`
- `import_fit(eft_text)` / `export_fit(fit) -> EFT` — EFT is the interop
  currency (game clipboard, zkill, community tools); the dialect must carry
  mutated-module stats
- `edit_fit(fit, op, ...)` — one mutator tool: add/remove/swap module, rig,
  drone, charge, implant, booster; set state (offline/online/active/
  overheated); errors name the violated constraint (CPU/PG/slot/calibration)
- `set_skills(fit, "all-5" | "alpha" | sheet)`
- `set_env(fit, ...)` — v1.5: wormhole effect, weather, bursts via boost-fit

Read side:
- `get_stats(fit)` — full panel: EHP by damage profile, raw HP, per-layer
  resists, DPS (turret/missile/drone split), alpha, cap stability or
  time-to-empty, speed/align/sig/agility, targeting, fitting headroom
- `compare_fits(a, b)` — same panel, diffed
- `graph(fit, x, y, vs?)` — structured series: DPS-vs-range,
  DPS-vs-target-speed/sig, EHP-vs-profile, cap-vs-time. Bounded output (see
  token budget).
- `validate_fit(fit)` — in-game legality: fitting resources, slots,
  one-per-type limits, capital restrictions
- `engine_info()` — engine version + its data build number (see data sync)

### Token budget as a design constraint

CPU is irrelevant — a dogma engine computes a fit in milliseconds. The entire
cost of this system is context tokens in the (likely Sonnet) chat that uses
it. Three rules, fixed at design time:

1. **Schemas are standing overhead**, paid on every request in the chat.
   Target ≤ ~10 tools with terse descriptions; the *teaching* lives in the
   fitting-knowledge skill (loaded once), never in schemas (paid always).
2. **Fits travel as IDs, not payloads.** Stateless designs re-send 300–800
   tokens of fit per call; over a thirty-call iteration session that is ~25k
   vs ~2k. This is why fits are stateful.
3. **Graphs are bounded.** ≤ ~30 downsampled points plus the summary stats
   the session actually reasons with (peak DPS, falloff crossover,
   cap-stable %, time-to-empty). A `detail` flag exists for more. Raw
   1,000-point series are forbidden — the `SELECT *` rule of this layer.

Expected budget in a dedicated chat: ~8–10k standing (schemas + skill),
~1–2k per fit-iteration loop, 40–80k for a long fitting conversation —
comfortably inside rate limits. Without these rules the same conversation is
300k+.

**Measured (MCP v1, 2026-08-17):** the budget held with room to spare —
~880 tokens standing for all 11 tool schemas, ~260 per full `get_stats`
panel, ~290 per edit+stats iteration step. A thirty-step fitting session is
~9k tokens of tool traffic. `fitting/mcp/test_server.py` prints these on
every run, so schema bloat shows up as a diff.

### Data-sync rule (non-negotiable)

Pyfa bundles its own SDE snapshot on its own cadence; the SDE skill tracks
CCP's current build. Version skew produces exactly the silent-wrong-number
class this project exists to kill. Therefore:
- `engine_info()` exposes the engine's data build, mirroring the SDE `meta`
  table.
- The fitting-knowledge skill's build-check compares engine build vs SDE
  build vs CCP latest, and **names any skew** whenever layers disagree.
- ~~v2 investigation (not assumed): feed the engine from our SQLite so there
  is one data source.~~ Resolved early, 2026-08-16: `fitting/adapter/`
  generates pyfa's staticdata inputs from CCP's current JSONL export, so
  pyfa's own db builder produces `eve.db` at the skill's SDE build —
  verified zero panel drift on the reference battery. Operationalized
  2026-08-17: `fitting/adapter/refresh.sh` does the whole rebuild in one
  command (no-op when already current), and the working engine moved to
  build 3470007 with eval keys re-pinned (`keys-3470007.json`,
  numerically identical to the 3424810 keys). Layer 1's release workflow
  polls CCP every 3 h, so "both layers current" is: let the workflow
  publish, run `refresh.sh` — the runtime build check guards the gap
  between the two. Same-day follow-up: the release workflow itself now
  carries a `fitting-engine` job off the same poll (refresh at the new
  build + battery diff in the job summary + full test suite; goes live
  when the workflow reaches the default branch) and a `fitting-tests`
  job on every push touching `fitting/`. Release assets untouched —
  layers remain independently installable.

### The fitting-knowledge skill (the docs half)

The engine produces numbers; the skill teaches what they mean — the same
division of labor as SDE + gotchas. Target size ≤ ~4k tokens for the router,
following the SDE skill's structure. Content plan:

- **Stat interpretation**: what cap-stable implies (and why 30%-stable is not
  automatically good), why EHP without a damage profile is meaningless, alpha
  vs DPS, server-tick quantization of align time
- **Tradeoff mechanics**: buffer vs active, shield vs armor slot economy and
  speed/sig implications, speed/sig tanking vs resist tanking, the
  stacking-penalty curve in plain terms (why the 4th damage mod gives ~28% of
  the 1st), env/burst effects being stacking-exempt
- **Trap catalogue, built the proven way**: seed with known traps (stacking
  exemptions — note command bursts are exempt via the warfare-buff system but
  environmental beacons are category 2 and therefore penalized, see
  `docs/fitting-formulas.md` §1; hull vs fitted resonance; env effects
  applying to NPCs too; spool-up making "DPS" ambiguous), then let graded
  eval runs find the rest
- **"Fitting a player, not a spreadsheet"**: a max-DPS fit that caps out in
  90 seconds answers the query, not the pilot

## Layer 3: general EVE knowledge

**Architecture: the SDE-skill pattern, different corpus.** EVE Uni wiki →
SQLite FTS5 → a `search_wiki` tool + a knowledge-skill doc. Deliberately not
a RAG pipeline: FTS is debuggable, offline, versionable.

**Measured facts (probed 2026-08):** the wiki's MediaWiki API is open;
**4,587 articles** (18.5k pages across namespaces); license
**CC BY-SA 4.0** — attribution satisfied by per-page source URLs, which we
want anyway so sessions can cite; per-page **last-edit timestamps** available
via the same API. Corpus is small (~50–80 MB raw) — the FTS database ships as
just another "part" alongside the SDE parts.

Build notes:
- Dump via `allpages` + revisions (or Special:Export); handle redirects as
  search aliases; strip templates to text but **keep the category graph** —
  categories enable scoped search (Combat/Missions/Industry per question
  type), which generic wiki-bots skip.
- Ignore infobox ship stats entirely: layers 1–2 own numbers; the wiki's
  numbers are its least trustworthy content.

Trust rules (the gotchas of this layer):
- Every quoted page carries its last-edit date — the wiki's build check. An
  old page about a reworked mechanic is the stale-data trap in prose form.
- Authority order: SDE > engine > wiki > memory; answers name their layer.
- Wiki numbers that matter get cross-checked against layers 1–2.

## Eval plan

The loop that produced the SDE skill's 16 pinned fixes, with three new
question classes:

1. **Engine-truth**: "EHP of this exact EFT fit vs Guristas profile" — key
   computed via the engine; grades MCP plumbing.
2. **Tradeoff**: "same Vexor, armor vs shield — what do I gain and lose?" —
   grades the skill docs' reasoning; key = engine numbers + documented
   mechanics.
3. **Knowledge**: "why did my cyno die instantly in Pochven" — grades layer-3
   retrieval and staleness discipline.

Plus a no-stack control run to measure what it all buys, and the standing
rule: **every graded miss is root-caused to model vs docs vs engine, and
doc-owned misses get fixed and pinned in the harness.**

## Phasing

1. **Engine spike** — the timeboxed A-vs-B bake-off; everything waits on this.
   *Done 2026-08-16, in one day instead of two weeks: candidate A (pyfa's
   eos) extracted headless, produced the 10-fit reference battery, and was
   confirmed against a desktop pyfa GUI panel-for-panel. See
   `docs/spike-log.md` and `fitting/spike/`.*
2. MCP v1: lifecycle + `get_stats` + `validate_fit`; harness of ~10 reference
   fits. *Landed 2026-08-17 (`fitting/mcp/`): all lifecycle tools, EFT
   import/export, `edit_fit`, `set_skills` (all-5/alpha), `get_stats` with
   damage profiles, `compare_fits`, `validate_fit`, `engine_info` — smoke
   test drives the full surface over real stdio against the reference
   battery, on both bundled and adapter-current data builds.*
3. Fitting-knowledge skill v1 + first eval generation. *Landed
   2026-08-17: `.claude/skills/eve-fitting/` (router ~1.6k tokens of the
   ~4k budget + three references) and `fitting/evals/` (10 questions,
   classes 1+2, engine-pinned keys). First graded run: control 69% vs
   with-skill 98%; misses root-caused, fixes pinned — including one
   engine bug (alpha-preset character mutation) and one formulas-doc
   error (Pulsar shield HP is not stack-penalized) caught before the run.
   See `docs/spike-log.md`.*
4. `compare_fits` + `graph` + v1.5 external-effects pipeline. *First
   slice landed 2026-08-17 (`compare_fits` had landed with MCP v1):
   `graph()` (dps_vs_range / dps_vs_target_speed / cap_vs_time, bounded
   per the token rules, pyfa's own application math), `set_env`
   (wormhole/storm/abyssal beacons via projection — C5 Wolf-Rayet ×2.69
   on the battery Rifter, verified), `set_booster` (recursive
   command-burst fits, strongest-wins measured), and T3D modes via the
   `mode` edit op. The rest of v1.5 landed later the same day: projected
   fits (`set_projected`), fighters, and mutated modules (pyfa's `[N]`
   EFT dialect) — details in `docs/spike-log.md`.*
5. Layer 3: corpus build + search + knowledge skill
6. Cross-layer eval (questions requiring all three layers)

## Decisions made

- Wrap, don't reimplement (pyfa's engine first, `dogma-engine` fallback)
- Pyfa is ground truth for v1; server divergences become gotchas
- Fits are **stateful** with EFT as escape hatch (token budget forces this)
- Token budget is a named design constraint with the three rules above
- Layer 3 is FTS over EVE Uni, built ourselves; category-scoped search;
  infobox numbers ignored
- Monorepo with the SDE skill until layer 2 stabilizes (revisit at v1.5)
- Fighters and tactical-destroyer modes are v1.5, not v2 (2026-08-16)
- **Engine: pyfa's eos, wrapped headless** (2026-08-16) — spike verdict,
  GUI-confirmed panel-for-panel; dogma-engine stays the named fallback

## Open questions (for the build sessions)

- ~~How deep does pyfa's GUI entanglement go?~~ Answered: shallow — one
  wx.Colour stub suffices; see the entanglement map in `docs/spike-log.md`.
- ~~EFT dialect for mutated modules: adopt pyfa's exactly, or document our
  own?~~ Answered 2026-08-17: pyfa's exactly — interop is the point.
- Graph rendering: does the consuming session chart the series (artifacts)
  or reason over summaries only? Both should work; neither should be assumed.
