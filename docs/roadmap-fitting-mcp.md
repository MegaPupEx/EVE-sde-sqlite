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
- Command bursts — modeled as a *separate boost fit* whose own skills,
  mindlinks and hull scale the burst (recursive, like pyfa does it)
- Projected fits: remote assistance/impedance, where the projecting ship's
  own rigs/skills scale the projected module (same recursion)
- Environmental: wormhole phenomena, k-space metaliminal storms, abyssal
  system-wide weather, local AoE (abyssal clouds, ESS bubble), incursion and
  insurgency system effects. Note: internally these are the same effect class
  as command bursts, which is why they share the tier.
- Mutated (abyssal) modules — rolled stats within mutaplasmid ranges;
  import/export must carry exact rolled values or real PvP fits cannot
  round-trip
- Fighters (ability-level effects; the SDE work already mapped
  `fighterAbilities`) — promoted from v2, 2026-08-16
- Tactical destroyer modes (Confessor/Svipul/Hecate/Jackdaw) — promoted from
  v2, 2026-08-16; modes are items applying ordinary dogma modifiers, no new
  math

**v2:**
- Siege-class states (siege, bastion, triage, industrial core)
- Spool-up weapons (Triglavian ramp — makes DPS time-dependent; needs a
  spool parameter or time series)
- Structures (fittable citadels)

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

### Data-sync rule (non-negotiable)

Pyfa bundles its own SDE snapshot on its own cadence; the SDE skill tracks
CCP's current build. Version skew produces exactly the silent-wrong-number
class this project exists to kill. Therefore:
- `engine_info()` exposes the engine's data build, mirroring the SDE `meta`
  table.
- The fitting-knowledge skill's build-check compares engine build vs SDE
  build vs CCP latest, and **names any skew** whenever layers disagree.
- v2 investigation (not assumed): feed the engine from our SQLite so there is
  one data source.

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
   *Started 2026-08-16; candidate A extracted successfully on day one — see
   `docs/spike-log.md` and `fitting/spike/`.*
2. MCP v1: lifecycle + `get_stats` + `validate_fit`; harness of ~10 reference
   fits
3. Fitting-knowledge skill v1 + first eval generation
4. `compare_fits` + `graph` + v1.5 external-effects pipeline
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

## Open questions (for the build sessions)

- How deep does pyfa's GUI entanglement go? (Answered by the spike.)
- EFT dialect for mutated modules: adopt pyfa's exactly, or document our own?
  (Lean: pyfa's exactly — interop is the point.)
- Graph rendering: does the consuming session chart the series (artifacts)
  or reason over summaries only? Both should work; neither should be assumed.
