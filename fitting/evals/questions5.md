# Eval generation 5 — multi-turn, both stacks, full v2 surface (2026-08-17)

20 subjects × 3 turns. Two arms share the same 30 questions:
- **full** (10 subjects): layers 1+2 (eve-sde skill + sqlite parts + fitting MCP).
- **l2only** (10 subjects): fitting MCP + eve-fitting skill only — subjects are
  told layer 1 is unavailable; layer-1-shaped questions probe degradation
  honesty (label the gap, don't fake the data).

Within each arm: subjects ch1–ch5 get a **chain** (turns 2–3 follow from
turn 1); subjects fr1–fr5 get three **unrelated** questions. All keys below
were derived by drive script against a fresh server, engine build 3470007
(raw results: keys5-3470007.json). Several draft keys moved when the engine
answered — kept notes inline where the miss would be tempting. Grading
K/M/D/P/C as in README.md.

## Chains

### ch1 — bastion stacking (T16)
- T1: Golem `[Multispectrum Shield Hardener II // Bastion Module I]`, bastion
  running: shield resists + "does bastion stack-penalize my hardener?"
  KEY: EM **52.8%** (th 71.6 / kin 75.2 / exp 76.4); **no cross-penalty** —
  hardener postPercent, bastion preMul, separate chains.
- T2: add a Damage Control II — how much more EM resist, anything fighting it?
  KEY: 52.8 → **57.9%** (+5.1 pts): DC shares bastion's preMul chain and IS
  penalized against it (naive full-DC gives ~59.4 — the miss).
- T3: "what am I giving up while sieged, keep it short."
  KEY: immobile, remote assistance blocked, full-cycle commitment; the panel
  note names it; ≤~100 words (C axis).

### ch2 — spool honesty (T11)
- T1: Vedmak `[Entropic Radiation Sink II ×2 // Heavy Entropic
  Disintegrator II (Occult M)]`: "what's my dps?"
  KEY: the band: **909 full spool / floor 291 / ramp 109 s** (offense.spool
  + note). One number alone = C/K fail.
- T2: "my fights last ~30 s — what do I actually get?"
  KEY: ~**435–455** (dps_vs_time: 433 at 26 s, 454 at 31 s) — half the
  headline; must be ramp-sourced.
- T3: "how much lands on a 40 m frigate doing 700 m/s at 5 km?"
  KEY: essentially nothing — **1.0 dps applied (0.1%)** (applied_dps; Occult
  tracking vs small+fast). Quoting hundreds = K-fail; the honest zero is
  the point.

### ch3 — the duel (versus; both fits given in T1, resident after)
- T1: battery-style Rifter (3×150mm AC II RF EMP, MWD/scram/web, SAAR+paste,
  Gyro II, DC II, aerator rig) vs Punisher (400mm Tungsten, SAR II, DC II,
  Multispectrum Coating, 1MN AB II, 3×Small Focused Pulse II IN Multi) at
  2 km: "who wins?"
  KEY: **neither breaks the other's tank**: Rifter applies 45.6 into
  8,342 EHP w/ 198.6 hps reps (tanked); Punisher applies 38.4 into 3,102 /
  246.4 hps (tanked). Verdict: a rep-off — decided by paste/cap/heat, which
  the tool names as out of scope. Declaring a clean winner = K-fail.
- T2: "he webs me the whole fight — does that change it?"
  KEY: web on the Rifter nearly doubles the Punisher's applied: 38.4 →
  **74.8** (still under 246 hps reps → still tanked, but the margin story
  changes; must be computed via set_projected + versus).
- T3: "I load Barrage and hold 7 km instead?"
  KEY: Rifter applied rises to **94.2** (falloff ammo), Punisher collapses
  to **35.7**; both still out-repped. Scram/AB range caveat welcome.

### ch4 — structure math (T17)
- T1: Astrahus `[Standup BCS I // Standup Multirole Missile Launcher I
  (Standup Cruise) // Standup Cloning Center I]`: dps, tank, fuel bill.
  KEY: **1,023.5 dps**; EHP ~**29.25M** uniform with per-layer incoming caps
  named — **shield 14.4M / armor 5,000 / hull 5,000 dps** (the caps are NOT
  uniform — assuming 5k everywhere is the trap the derivation caught);
  fuel **10 blocks/hr** (+720 to online).
- T2: add Standup Reprocessing Facility I + Standup Market Hub I: fuel now?
  KEY: 10 + 10 + 40 = **60 blocks/hr** (reproc is 10, not guessed 5;
  onlining 720/2880 one-time optional mention).
- T3: "30-man gang, 40k combined dps — how long per layer?"
  KEY: shield is NOT meaningfully capped (14.4M cap ≫ 40k): 18M/40k ≈
  **7.5 min**; armor caps at 5k: 9.9M/5k = **33 min**; hull 2.25M/5k =
  **7.5 min**. Reinforcement windows named as unmodeled game rules.

### ch5 — abyssal roll → hull → alpha (T15/T12)
- T1: "can any mutaplasmid get a Republic Fleet web to 20 km base? best case?"
  KEY: **no** — Glorified Unstable ×1.25 max → **18,750 m** (standard
  Unstable 18,000). Inventing a 20 km roll = K-fail.
- T2: "best case anyway, on a Huginn, overheated — range?"
  KEY: **97,500 m** (18,750 × hull ×4 at V × 1.3 heat; engine-verified via
  mutated import + module_attrs overheated).
- T3: "could a fresh alpha sit in that Huginn at all?"
  KEY: **no** — required_skills alpha_blocked: Recon Ships (+ Cloaking,
  Minmatar Cruiser 5, Signature Analysis 5, Spaceship Command 5);
  tool-sourced, not folklore.

## Fresh triplets

### fr1
- A (layer-1): "large Amarr control tower — fuel blocks/hr, and strontium
  units in the bay?" KEY: **40/hr** Helium; bay 50,000 m³ / 3 m³ =
  **16,666 units** (purpose-4 400/hr is reinforced burn, NOT the bay).
  l2only: must label layer 1 unavailable.
- B: "turn off my Einherji IIs' missiles on the Thanatos — dps lost?"
  KEY: 521.1 → 315.6 per squad: **−205.5 dps (−39%)** (ability op;
  missiles are the bigger half than folklore expects).
- C: "is cap-stable at 28% good enough for a C3 site?" KEY: T5 discipline —
  the 25% cliff, one neut from cascade, C3 sleepers neut; verdict: thin.

### fr2
- A: Incursus fit-check `[MFS II ×2, DC II // 5MN Quad LiF MWD, scram,
  X5 web // Light Neutron Blaster II ×3 (Void S)]`.
  KEY: **CPU over: 216.5 / 168.75** at all-V — catching it is the point.
- B: "where does my Cormorant's rail dps halve?
  `[125mm Railgun II ×7 (CN Antimatter S), MFS II ×2]`"
  KEY: **~20.9 km** (graph half_dps_km; 18–23 accepted, graph-sourced).
- C: heat-spaced Rifter `[Gyro II // 5MN MWD // 150mm AC II, [Empty High
  slot], 150mm AC II]` — "swap one AC for a 200mm AutoCannon II without
  wrecking my layout." KEY: returned EFT keeps the gap in position
  (keep_slot remove + add, or sweep; layout intact).

### fr3
- A: "Hobgoblin II rolled 2.2 damageMultiplier — 5 on my Tristan with two
  DDA IIs: drone dps?" KEY: **161.0** (mutated-drone EFT dialect; base-roll
  1.92 gives 142.9 — the roll is +18).
- B (layer-1): "which T1 frigate has the most mid slots?" KEY: **Griffin, 5**
  (enumeration; l2only must label the gap, not assert from memory).
- C: "do two 10MN Afterburner IIs stack on a cruiser?" KEY: honest mechanics
  — only one prop mod runs per ship in practice; if both ran, same-attribute
  stacking penalty applies; second AB is a wasted mid. No pinned number.

### fr4
- A: passive Drake `[SPR II ×4 // LSE II ×2, Multispectrum Shield Hardener
  II, EM Shield Amplifier II // HML II ×6 (Scourge Fury)]` vs Guristas:
  real EHP? KEY: **51,419** with Guristas (kin80/th20) vs 53,212 uniform —
  the profile must be applied and named (it goes DOWN despite the hardeners;
  presenting uniform as the answer = miss).
- B: "does a second Drake running the same shield burst help?" KEY: **no** —
  strongest same buff wins, bursts never add (T1; engine demo optional).
- C: "Confessor sig: Defense vs Sharpshooter mode?" KEY: **43.3 m vs 65 m**
  (mode op, both numbers).

### fr5
- A: RLML Caracal `[RLML II ×5 (CN Scourge Light), BCS II ×2]` vs blaster
  Enyo `[LNB II ×4 (Void S), MFS II ×2, MAPC II, MWD, scram]` at 15 km:
  "who applies?" KEY: one-sided — Caracal applies **172.8** (ttk ~77 s);
  Enyo applies **0.0** (Void at 15 km). Range control is the verdict.
- B: "strong exotic metaliminal storm — what does it do to my armor Vexor?"
  KEY: env-tool-sourced direction with build named (set_env; exact beacon
  name discoverable via the tool's fuzzy error). No pinned number; folklore
  without the tool = M-fail.
- C: "how many Gyro IIs is too many on an arty Hurricane?" KEY: sweep/edit
  measured: 2→3 gyros **+58.9 dps (+12.4%)**, 3→4 **+31.8 (+6.0%)** —
  verdict: 3 on this hull unless a low has nothing better; the stacking
  curve (100/87/57/28) named.

## Protocol

Turn-1 prompt = environment preamble + question; turns 2–3 continue the
same subject session, follow-up style (chains never re-paste fits).
Footer per turn: `--- calls: N mcp, M sql`. Measured: harness tokens,
wall time, calls, words; graded K/M/D/P/C. l2only preamble adds: "Layer 1
(eve-sde databases/skill) is NOT available; do not run SQL — if a
question needs it, say so and answer with what layer 2 provides."
