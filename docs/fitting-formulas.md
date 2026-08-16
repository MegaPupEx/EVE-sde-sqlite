# Fitting formulas: the v1 reference

Every formula the v1 fitting engine's numbers rest on, pinned to sources.

**This document does not license reimplementation.** The roadmap's rule stands:
we wrap an existing engine. These formulas exist so that (a) the spike's
reference-fit battery can be checked by hand when engines disagree, (b) the
fitting-knowledge skill can teach what the numbers mean, and (c) graded eval
misses can be root-caused to model vs docs vs engine.

**Sources, in authority order:**

- `pyfa` @ `8b04f3b271e614b3e103853b44a7851a63d79d0e`
  (github.com/pyfa-org/Pyfa) — ground truth for v1 by roadmap decision. File
  and line references below are against this commit.
- `dogma-engine` @ `e8e536be341959a8abdc6f02600fe449bc6f4764`
  (github.com/eveshipfit/dogma-engine) — the candidate-B engine, used here as
  an independent cross-check. Where both engines encode the same constant, it
  is noted.
- EVE University wiki — cited where pyfa's own source cites it.
- SDE build **3466501** — attribute IDs, `stackable` flags and category IDs
  below were read from our own layer-1 database, not copied from memory.

Both engine repos clone directly in remote sessions (verified 2026-08-16); no
local copy needs uploading.

## 1. The dogma calculation model

### Operation order

Modifiers to an attribute apply in this fixed order (dogma-engine
`src/calculate/item.rs:18`):

```
preAssign → preMul → preDiv → modAdd → modSub → postMul → postDiv → postPercent → postAssign
```

pyfa collapses the same pipeline into
`preIncrease → multiplier → stacking-penalized multipliers → postIncrease`
(`eos/modifiedAttributeDict.py:408`), with min/max clamps applied last.
`postPercent` (the most common operator — nearly every "+X%" bonus) is
`value × (1 + bonus/100)`.

**pyfa fidelity detail:** `cpu`, `power`, `cpuOutput` and `powerOutput` are
rounded to 2 decimals at every calculation step
(`eos/modifiedAttributeDict.py:373`, `:451`). An engine that skips this
rounding can disagree with pyfa's fitting-headroom panel by 0.01.

### Stacking penalty

The formula both engines agree on, byte-for-byte in the constant. Within one
penalty group, sort the multipliers by significance (largest deviation from
1 first); the i-th multiplier (0-indexed) applies as:

```
effective = 1 + (multiplier − 1) × e^(−i² / 7.1289)
```

(pyfa `eos/calc.py:49`, `eos/modifiedAttributeDict.py:441`). 7.1289 = 2.67².
dogma-engine stores the same curve as
`PENALTY_FACTOR = 1/e^((1/2.67)²) = 0.8691199808003974`, applied as
`factor^(i²)` (`src/calculate/pass_3.rs:7-8`) — algebraically identical.

| module # | 1st | 2nd | 3rd | 4th | 5th | 6th |
| --- | --- | --- | --- | --- | --- | --- |
| effectiveness | 100% | 86.91% | 57.06% | 28.30% | 10.60% | 3.00% |

Rules around the formula, all load-bearing:

- **Bonuses and penalties are penalized separately** — two damage bonuses and
  a damage penalty form two chains, not one (pyfa `eos/calc.py:36-37`). A
  web's −60% and another web's −55% penalize each other; they do not penalize
  a speed *bonus*.
- **A modifier is penalized only if** the attribute has `stackable = 0` in
  `dogma_attributes` **and** the source item's category is not exempt.
  The exempt categories (dogma-engine `src/calculate/pass_2.rs:10`):
  **6 Ship, 8 Charge, 16 Skill, 20 Implant, 32 Subsystem** — verified as
  those exact names in SDE build 3466501. Boosters are group 303 inside
  category 20, so drugs are exempt too.
- Only multiplicative operators penalize: `preMul`, `preDiv`, `postMul`,
  `postDiv`, `postPercent` (dogma-engine `src/calculate/pass_3.rs:10`).
  `modAdd`/`modSub` never do — which is why armor plates and shield extenders
  always add in full (their HP attributes are also `stackable = 1`).
- Penalty groups are per attribute *and* per operator — things in different
  groups never penalize each other (pyfa `eos/modifiedAttributeDict.py:415`).

**Consequences worth pinning as gotchas:**

- `shieldCapacity` (263) and `armorHP` (265) are `stackable = 1`;
  `damageMultiplier` (64), `maxVelocity` (37), `signatureRadius` (552) and
  rate-of-fire `speed` (51) are `stackable = 0`. Read the flag, don't guess.
- **Environmental effects are stack-penalized; command bursts are not — for
  different reasons.** Wormhole/weather Effect Beacons are category 2
  (Celestial), which is *not* exempt: a Pulsar's shield bonus joins the same
  penalty chain as your shield modules. Command bursts apply through the
  warfare-buff system (`dbuffCollections` in the SDE), which sits outside
  dogma modifiers entirely — buffs don't stack with each other at all
  (strongest of each buff ID wins) and don't join penalty chains. The
  roadmap's earlier "env/burst effects are stacking-exempt" lumped these
  together wrongly; this split is the corrected claim, and the eval harness
  should test both directions.

### Skill and hull bonuses

Per-level bonuses apply as `bonus × trained level`, almost always
`postPercent`, and are exempt from stacking (category 16; the hull is
category 6). pyfa registers ship bonuses with the skill as the affector
(`eos/effects.py`, e.g. `speedFBonus × level` at line 3671).

## 2. Defense

Resonance, not resist, is the stored quantity: `resonance = 1 − resist`, and
the SDE stores resonance (the layer-1 inversion gotcha). All EHP math runs on
resonances directly.

**EHP against a damage profile** (pyfa `eos/saveddata/damagePattern.py:242`):

```
weighted_resonance(layer) = Σ_dmgtype ( profile_fraction × resonance_layer,dmgtype )
EHP(layer)  = raw_HP(layer) / weighted_resonance(layer)
EHP(total)  = EHP(shield) + EHP(armor) + EHP(hull)
```

Each layer uses its own resonances; "EHP" without a named profile is
meaningless (uniform 25/25/25/25 is pyfa's default, not a law of nature).

**Passive shield recharge** (pyfa `eos/saveddata/fit.py:1423-1433`): the
recharge *rate* at fill fraction `f` of capacity `C` with recharge time `R`
seconds is

```
rate(f) = (10 × C / R) × (√f − f)        hp/s (or GJ/s — same curve as capacitor)
peak    = rate(0.25) = 2.5 × C / R
```

Peak passive tank is `2.5 × shieldCapacity / shieldRechargeRate`, then
divided by weighted resonance for effective HP/s.

**Repairers**: effective rep/s = (rep amount per cycle / cycle time) /
weighted resonance, same `effectivify` call. Ancillary armor repairers
multiply rep amount by `chargedArmorDamageMultiplier` (×3) while paste is
loaded — data-driven, but the reload changes sustained rep (see §3 reload).

## 3. Offense: volley and DPS

**Volley** (pyfa `eos/saveddata/module.py:477`): per damage type,

```
volley = charge_damage × damageMultiplier(module)
```

Turrets take damage from the loaded charge; drones and some weapons from the
item itself. Drones multiply by `amountActive` as well
(`eos/saveddata/drone.py:163`). Missile launchers usually have no
`damageMultiplier` of their own; missile damage bonuses land on the charge's
damage attributes via skills/hull (per-type — a Gila boosts kinetic/thermal
only).

**Cycle time** (`eos/saveddata/module.py:1026`): milliseconds, read as
`max(speed, duration, durationHighisGood, …)` — the layer-1 gotcha that
attribute 51 `speed` is a duration lives here.

```
DPS = volley / (cycle_time_ms / 1000)
```

**Reload — burst vs sustained** (`eos/saveddata/module.py:967`): burst DPS
ignores reload; sustained DPS models a clip of `N = numShots` cycles followed
by `reloadTime`:

```
sustained_DPS = burst_DPS × (N × cycle) / (N × cycle + reload)
```

(pyfa generalizes to cycle sequences — reactivation delays, AAR paste clips,
crystal-less lasers with `reload = None` never reload. If a module's forced
inactivity ≥ reload time, reload is free.)

**Spool-up** (v2, pinned now because the constant is here): Triglavian
damage multiplier bonus = `min(damageMultiplierBonusMax,
damageMultiplierBonusPerCycle × cycles)` (`eos/utils/spoolSupport.py:31`).
"DPS" is ambiguous for these weapons without a spool parameter.

## 4. Turret application

All from `graphs/data/fitApplicationProfile/calc/turret.py`, which pyfa's own
comments source to the EVE Uni turret-mechanics page.

**Angular velocity** (rad/s), center-to-center:

```
angular = |v_attacker×sin(θ_a) − v_target×sin(θ_t)| / (r_attacker + distance + r_target)
```

**Tracking factor** (line 50):

```
T = 0.5 ^ ( (angular × optimalSigRadius / (trackingSpeed × target_sig))² )
```

`optimalSigRadius` is the turret's signature resolution attribute;
`trackingSpeed` is the turret's tracking attribute (post-2016 units — no
40000 constant in the modern formula).

**Range factor** (`eos/calc.py:53`):

```
R = 0.5 ^ ( (max(0, distance − optimal) / falloff)² )
```

(1.0 inside optimal; for non-gun modules — ewar, remote reps — the same
formula applies but activation is blocked beyond optimal + 3×falloff.)

**Chance to hit**: `CTH = T × R`.

**Damage per shot** (line 68): a uniform roll `q ∈ [0,1]` hits if `q < CTH`;
rolls ≤ 0.01 are wrecking shots at 3× damage; a normal hit deals
`(q + 0.49)×` base. The expected damage multiplier pyfa uses:

```
wrecking = min(CTH, 0.01) × 3
normal   = (CTH − min(CTH, 0.01)) × ( (0.01 + CTH)/2 + 0.49 )
E[mult]  = wrecking + normal
```

So a 100%-CTH turret averages ~0.995× volley plus the wrecking tail, and hit
quality ranges 0.5×–1.49×.

## 5. Missile application

From `graphs/data/fitApplicationProfile/calc/launcher.py`.

**Application factor** (line 30):

```
A = min( 1,
         target_sig / explosionRadius,
         ( (explosionVelocity × target_sig) / (explosionRadius × target_speed) ) ^ DRF )
```

`explosionRadius` = `aoeCloudSize`, `explosionVelocity` = `aoeVelocity`,
`DRF` = `aoeDamageReductionFactor` — all on the charge, all modified by
skills (Guided Missile Precision, Target Navigation Prediction, …).
Applied volley = raw volley × A. A stationary target takes the sig term only.

**Flight range** (line 193, CCP's own posted formula): missiles accelerate,
then cruise:

```
t_accel = min(flight_time, mass × agility / 10⁶)      (missile's own mass/agility)
range   = v_max/2 × t_accel + v_max × (flight_time − t_accel)
```

**Flight time is server-tick discrete** (line 261): `flight_time =
explosionDelay/1000 + ship_radius/v_max`, then a 3.4 s flight time means 40%
chance of flying 4 s and 60% of 3 s — pyfa models range as
`lowerRange`/`higherRange` with `higherChance` probability between them, and
subtracts the launching ship's radius (missiles spawn at center).

## 6. Capacitor

**Recharge between events** (pyfa `eos/capSim.py:155,180`): with
`τ = rechargeRate / 5` (same units as `rechargeRate`, ms in the SDE):

```
C(t) = Cmax × ( 1 + (√(C₀/Cmax) − 1) × e^(−Δt/τ) )²
```

**Recharge rate** at fill fraction `f` — same curve as shield
(`eos/saveddata/fit.py:1423`):

```
rate(f) = (10 × Cmax / R_s) × (√f − f),   R_s = rechargeRate in seconds
peak    = 2.5 × Cmax / R_s   at f = 0.25
```

**Analytic stability**: for a smooth average drain `D` (GJ/s), setting
`rate(f) = D` with `b = D×R_s/(10×Cmax)` gives

```
stable iff b ≤ 1/4   (i.e. D ≤ peak);   f_stable = ( (1 + √(1 − 4b)) / 2 )²
```

Note the stable point is always **above 25%** — a fit whose drain equals peak
recharge is stable *at* 25%, and anything below 25% is past the peak and
cascades to empty.

**What pyfa actually does**: a discrete event simulation (`eos/capSim.py`) —
every module activation is an event with its own cycle, cap need, clip and
reload; cap boosters inject discretely and are postponed rather than wasted
on overshoot; stability is detected when a full activation pattern repeats
with no less cap than the previous repeat. Time-to-empty comes from the same
sim. The analytic formula above is the sanity check, not the implementation —
matching pyfa's "cap stable %" in the harness means matching the sim.

## 7. Navigation

**Align time** (pyfa `eos/saveddata/fit.py:455`):

```
t_align = −ln(0.25) × agility × mass / 10⁶      (agility = attr 70, mass in kg)
```

Verified against layer 1: Rifter (mass 1,067,000, agility 3.19) → 4.733 s,
matching the SDE skill's documented 4.73 s. A ship enters warp at 75% of max
velocity — that is where the ln(0.25) comes from (ln(1−0.75)). The server
processes movement in 1 s ticks, so in-game align is effectively
`ceil(t_align)`; quote both, and say which.

**Acceleration** generally: `v(t) = v_max × (1 − e^(−t × 10⁶ / (agility × mass)))`.

**Propulsion modules** (pyfa `eos/effects.py:6730-6731`, MWD and AB
identical in form):

```
1. mass += massAddition                      (modAdd — before the boost reads mass)
2. maxVelocity boost % = speedFactor × speedBoostFactor / mass
   (stack-penalized, in the postMul penalty group)
3. MWD only: signatureRadius boost % = signatureRadiusBonus  (penalized)
```

`speedFactor` is the module's boost %, `speedBoostFactor` its thrust; the
division by post-addition mass is why plates and MWDs interact. pyfa's
comment pins the operator: it is a postMul in CCP's implementation, which is
observable in black-hole wormholes (both land in one penalty group).

**Warp** (pyfa `graphs/data/fitWarpTime/getter.py`, taken from the EVE Uni
warp-time implementation):

```
k_accel = warp_speed (AU/s)          k_decel = min(warp_speed/3, 2)
warp_dropout = min(subwarp_speed/2, 100) m/s
accel_dist = 1 AU                    decel_dist = v_warp_m/s / k_decel
if accel_dist + decel_dist > total:  v_peak = total × k_accel×k_decel/(k_accel+k_decel)
else:                                cruise_time = (total − accel − decel) / v_warp
t = cruise + ln(v_peak/k_accel)/k_accel + ln(v_peak/dropout)/k_decel
```

with 1 AU = 149,597,870,700 m (`AU_METERS`, matching the layer-1 coordinate
conventions).

## 8. Targeting

**Lock time** (pyfa `eos/calc.py:68`):

```
t_lock = 40000 / ( scanResolution × asinh(target_sig)² )      capped at 1800 s
```

Max locked targets = min(ship's `maxLockedTargets`, character's from skills).
Sensor strength is a plain attribute (highest-type rule matters only for
ECM, out of v1 scope).

## 9. Fitting limits

Validation is comparison, not math: Σ module `cpu` ≤ `cpuOutput`, Σ `power`
≤ `powerOutput`, Σ rig `upgradeCost` ≤ `upgradeCapacity`, hardpoints
(`turretSlotsLeft`/`launcherSlotsLeft`), slot counts, drone bay volume, and
Σ active-drone `droneBandwidthUsed` ≤ `droneBandwidth`. Remember the pyfa
2-decimal rounding on cpu/power (§1) when reproducing its headroom numbers,
and that CPU/PG needs are themselves dogma-modified attributes (weapon
upgrades, ship bonuses) — validate after calculation, not from base values.

## 10. Overheat

Overheating applies the module's own `overload*` attributes as ordinary
modifiers while state = overheated: `overloadRofBonus` on cycle time
(`eos/effects.py:9354`), `overloadDamageModifier` on damage multiplier
(`:9427`), plus hardening/duration/speed-factor variants — all data, no new
math. Heat *buildup and burnout* (how long before the rack cooks) is a
simulation pyfa does not run for the stats panel and v1 does not need.

## Constants, in one place

| Constant | Value | Where |
| --- | --- | --- |
| Stacking penalty denominator | 7.1289 = 2.67² | both engines, identical |
| Stacking factor per index | e^(−i²/7.1289) → 1, .8691, .5706, .2830, .1060, .0300 | §1 |
| Wrecking shot | roll ≤ 0.01, ×3 damage | §4 |
| Hit quality | (roll + 0.49)×, range 0.5–1.49 | §4 |
| Peak regen | 2.5 × capacity / recharge time, at 25% fill | §2, §6 |
| Capacitor τ | rechargeRate / 5 | §6 |
| Align constant | −ln(0.25) ≈ 1.3863; warp entry at 75% v_max | §7 |
| Lock-time constant | 40000; asinh() of sig radius | §8 |
| Warp decel cap | min(warp/3, 2); dropout min(subwarp/2, 100) | §7 |
| 1 AU | 149,597,870,700 m | §7 |
| Server tick | 1 s (align, missile flight) | §5, §7 |
| pyfa cpu/pg rounding | 2 decimals, every step | §1 |

## What was verified vs transcribed

**Verified this session** (2026-08-16, against SDE build 3466501 and both
engine checkouts): the stacking constant matches between pyfa and
dogma-engine; the exempt-category IDs resolve to Ship/Charge/Skill/Implant/
Subsystem; Effect Beacons are category 2 (not exempt); Booster is group 303
in category 20; the `stackable` flags quoted in §1; the align formula
reproduces the layer-1 Rifter number. **Transcribed from source but not yet
executed**: everything else. The spike's reference-fit battery is what
promotes the rest from "read" to "verified" — until then, treat line
references as the authority and this prose as the index into them.
