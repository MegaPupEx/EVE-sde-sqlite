# Reading a stat panel

What each `get_stats` section means, what it hides, and what to quote.
Formula sources are pinned in `docs/fitting-formulas.md`; this file is the
interpretation. Every figure below marked "battery" is from the pinned
reference fits (`fitting/spike/reference/`), engine build 3470007, all-V.

## offense — dps, dps_sustained, dps_drones, volley

Three different numbers answer "how much damage":

- **`volley`** (alpha): one simultaneous shot from everything. Governs
  whether a target dies *before its logi reacts* — fleet arty doctrines buy
  volley at heavy DPS cost. Battery Hurricane: 4,067 volley but 554 DPS;
  its RLML counterpart inverts the tradeoff.
- **`dps`** (burst): reload-free cycling. The right number for short fights
  and for "can I break their reps *right now*".
- **`dps_sustained`**: models the clip — `burst × N·cycle / (N·cycle +
  reload)`. The right number for long grinds. When the two are equal the
  panel omits `dps_sustained` (crystal lasers never reload; projectiles
  reload in 1 s). When they diverge, say both: a RLML Caracal is **298
  burst / 179 sustained** — it fights in ~24 s bursts separated by 35 s
  reloads, and quoting either number alone misleads.
- **`dps_drones`** is *included* in `dps`, broken out because drones can be
  shot off, left behind, or out of control range.

**Paper DPS applies only if you hit.** Turrets: chance-to-hit = tracking
factor × range factor — angular velocity vs `trackingSpeed·target_sig`, and
`0.5^((dist−optimal)/falloff)²` beyond optimal (half damage at optimal +
1×falloff, ~6% at +2×falloff). Missiles always hit but scale by
`min(1, sig/explosionRadius, (explosionVelocity·sig / (explosionRadius·speed))^DRF)`
— a cruise Raven's paper 838 lands in full on a battleship and in small
fraction on an orbiting frigate. When the question involves a target, run
`graph` (`dps_vs_range` / `dps_vs_target_speed`, below) — the panel itself
is a zero-range, full-application number.

Spool-up (Triglavian) is **unmodeled in v1** — for those hulls "DPS"
needs a spool parameter; say so rather than quoting a single figure.

## defense — ehp, resists, hp, reps_hps

**EHP = raw HP ÷ profile-weighted resonance, per layer, summed.** It moves
with the attacker's damage split, so it means nothing until you name the
profile. The panel default is uniform 25/25/25/25 — pyfa's convention, not
a law of nature. Re-run with `profile` weights for the real enemy.
Weights below are pyfa's own presets (engine layer,
`eos/saveddata/damagePattern.py` BUILTINS), normalized, belt/"Asteroid"
variants — deadspace rows differ a few points:

| Enemy | em/th/kin/exp | Enemy | em/th/kin/exp |
| --- | --- | --- | --- |
| Guristas | 0/20/80/0 | Angel | 22/7/26/45 |
| Serpentis | 0/53/47/0 | Blood Raiders | 55/45/0/0 |
| Sansha | 58/42/0/0 | Sleepers (W-space) | 26/26/24/24 |
| Trig subcaps | 0/61/0/39 | Sansha incursion | 16/13/35/35 |

The swing is large and the *direction* is fit-dependent, so compute, don't
reason from the bare hull: shield's bare hole is EM and armor's is
explosive, but hardeners move the holes. The battery Caracal (multispectrum
hardener) is 16.9k uniform, **18.5k vs Guristas** (kin/therm — its best
resists) and **15.0k vs Sansha** (EM — its worst): same fit, ±10% either
way. Tanking *for the enemy* is often worth more than another extender.
When you state which way the profile moved the number, read it off both
panels (uniform and profiled) — never narrate it from the hardener list:
a hardener-heavy fit can still read *lower* vs its enemy than uniform if
the profile leans on an uncovered hole (measured miss: both eval arms
called a kin-holed Drake "up vs Guristas" when it was down 1.8k).

- `resists` are fractions per layer/type, already converted (0.598 =
  59.8%) — not the SDE's inverted resonance. Every hull has **33% base
  hull resists** (all four types, all ships); a Damage Control multiplies
  that (DC II → 59.8%) — see `traps.md` §T3 before touching raw hull
  attributes.
- `reps_hps` is **effective** HP/s (through resists, vs the current
  profile). Passive shield regen peaks at `2.5 × capacity / recharge_time`
  at 25% fill — battery Drake: 196.6 raw hp/s — and *falls off below 25%*,
  the same cliff as capacitor. Resists multiply your reps and your logi's:
  a resist-tanked buffer receives remote reps better than a raw-HP one.

Quote EHP as "X vs \<profile\>", and for active tanks quote both buffer EHP
and effective rep/s — which one matters is an engagement-length question
(`tradeoffs.md`).

## capacitor — stable_pct or lasts_s

The engine runs pyfa's discrete event simulation (every module cycle, clip
and reload), not the smooth formula — quote it as simulated equilibrium.

- **`stable_pct` is an equilibrium point, not a grade.** Recharge peaks at
  25% fill and *decreases below it* — the stable point is always above
  25%, and its distance above 25% is your margin. Stable-at-70% shrugs off
  a neut cycle; stable-at-30% is one neut cycle from sliding under the
  peak, where recharge falls as drain continues and the cap cascades to
  empty. "Cap stable" alone says nothing about how robust.
- **`lasts_s` (non-stable) is often the better design point.** Battery
  Abaddon: lasts 198 s with everything running — most engagements are
  shorter, and stability would cost slots that are currently guns and
  tank. Compare `lasts_s` to the fight you expect, not to infinity.
- The simulation runs *everything always-on*, the worst case: real pilots
  pulse reps and prop. A fit "unstable" with the MWD on may be stable with
  it pulsed — say which assumption the number carries.
- Neuts, and cap boosters, are not in the panel number unless fitted; a
  "stable" reading says nothing about surviving energy warfare.

## navigation — max_velocity_ms, align_time_s, signature_m, mass_kg

- **`align_time_s` is the analytic figure** (`−ln(0.25)·agility·mass/1e6`,
  warp entry at 75% of max velocity). The server processes movement in 1 s
  ticks: in-game you warp on the tick after crossing 75%, effectively
  `ceil(align_time)`. A 4.69 s battery Rifter aligns in 5 server ticks;
  3.9 s vs 4.1 s is a real gap (4 vs 5), 4.2 vs 4.9 is not. Quote both
  forms, and say which is which.
- `max_velocity_ms` includes active prop. MWD sig bloom (~+450%) is in
  `signature_m` while active — a MWD frigate has cruiser-class sig, which
  is why MWD + big sig = catchable and AB brawlers are hard to hit. Speed
  and low sig *are* defense: they shrink turret tracking factor and
  missile application before resists ever apply.
- Mass matters twice: in align time and in MWD boost (thrust is divided by
  post-plate mass) — a 1600mm plate slows both. See `tradeoffs.md`.

## targeting — scan_resolution_mm, lock_time_*, sensor_strength, max_targets

Lock time is `40000 / (scanRes × asinh(sig)²)` — the panel pre-computes it
vs a 35 m frigate and a 400 m battleship; interpolate mentally for the
rest. Sensor strength is jam resistance (ECM is out of v1 scope);
`max_targets` is already min(ship, skills). Battleships locking frigates
in 10+ s is a design fact to mention when someone asks "why fit a signal
amp".

## graphs — bounded curves from the same engine

`graph(fit_id, kind)` returns ≤30 points, summary stats, and its
assumptions — read the summary first; the points are for when the user
wants a chart.

- **`dps_vs_range`**: applied DPS with tracking/falloff/missile terms.
  Default target is *ideal* (stationary, infinite sig) — the curve is then
  pure range decay; pass `target {speed_ms, sig_m}` for the questions that
  matter ("can this hit an orbiting frigate"). `summary.half_dps_km` is
  the falloff crossover; `zero_beyond_km` is the hard edge (missiles).
- **`dps_vs_target_speed`**: the tracking/application cliff at a fixed
  distance. A plateau at high speed is the drones keeping up.
- **`cap_vs_time`**: the event simulation's own trace, everything running —
  same worst-case assumption as the panel.
- **Graph DPS at perfect application reads ~1.5% above panel DPS.** That
  is the wrecking-shot expectation (rolls ≤ 0.01 hit at 3×) which the
  application model includes and the plain panel does not; pyfa's GUI
  graph shows the same offset. Name which figure you are quoting.

## fitting — cpu, powergrid, calibration

Each is `[used, output]`. CPU/PG needs and outputs are themselves
dogma-modified (weapon upgrades, ship bonuses) — validate **after**
calculation, which `validate_fit` does; and pyfa rounds cpu/pg to 2
decimals at every step, so an independent calculation can disagree by
0.01. "Does it fit" answers come from `validate_fit`'s named problems, not
from eyeballing sums.
