# Tradeoff mechanics

Every fitting question is a resource question: slots, CPU/PG, cap, mass,
sig, and the stacking curve. This file is how to reason about the exchanges;
`reading-stats.md` is how to read the resulting numbers.

## The stacking curve, in plain terms

Same attribute, same direction, penalized source → each additional modifier
is worth less. The i-th strongest multiplier keeps `e^(−(i−1)²/7.1289)` of
itself:

| module # | 1st | 2nd | 3rd | 4th | 5th | 6th |
| --- | --- | --- | --- | --- | --- | --- |
| kept | 100% | 86.9% | 57.1% | 28.3% | 10.6% | 3.0% |

So a mod worth +10% gives +10% fitted first, ~+8.7% as the second, ~+5.7%
as the third, **~+2.8% as the fourth** — by the fourth damage mod you are
paying a full low slot for about a quarter of a module. The engine applies
this exactly; your job is the judgement call: the 3rd damage mod usually
still beats nothing, but rarely beats a tracking enhancer, a tank module,
or fitting room for a bigger gun. Run the variant through `compare_fits`
instead of arguing from the table.

What the curve does **not** touch (exempt, always full strength): ship hull
bonuses, skills, implants, boosters, charges, T3 subsystems. What it does:
modules **and rigs, in one shared chain** — a Trimark rig is exempt only
because armor HP is a non-penalized attribute, not because it is a rig; a
Polycarbon and a Nanofiber *do* penalize each other. Separate attributes
are separate chains (a Gyrostabilizer and a Drone Damage Amplifier never
interact); bonuses and penalties are separate chains (two enemy webs
penalize each other, not your speed mods). Whether an attribute penalizes
at all is a data flag — HP and cap capacity don't (plates and extenders
always add in full); damage, RoF, velocity, sig, resists do. Full rules
and the wormhole/burst split: `traps.md` §T1, `docs/fitting-formulas.md` §1.

## Buffer vs active tank

**Buffer** (plates/extenders): all the EHP exists up front, works at zero
cap, immune to neuts, and is what logi wants under it (reps land on a ship
that is still alive). Cost: mass or sig, and it only ever shrinks — no
sustain. **Active** (boosters/repairers): trades burst survivability for
HP-over-time; wins any fight longer than the buffer would have lasted
*if* the cap holds and the incoming DPS stays under the rep rate. Cost:
cap dependence (a neut cycle can turn the tank off), and mids/lows that
buffer fits spend on damage or utility.

The decision is the expected engagement: fleet PvP is buffer (alpha kills
through active tanks; logi is the sustain), solo/small-gang is a judgement
call (ancillary reps give burst sustain — AAR triples its rep amount while
paste lasts, then reloads), PvE is active (infinite fights, predictable
incoming, no neuts in most sites). A passive-regen shield fit (battery
Drake: 197 hp/s peak, zero cap use) is the neut-immune middle road and
pays for it in mids and rig slots.

## Shield vs armor: the slot economy

The tank chooses which half of the ship you spend:

- **Shield tank spends mid slots** — the same slots as prop, tackle, cap
  modules and ewar. A shield cruiser with LSE + hardener + MWD has ~1 mid
  left for tackle; its lows are free for damage mods (why shield fits
  out-DPS their armor twins on paper).
- **Armor tank spends low slots** — the same slots as damage mods and
  nanos. An armor fit keeps its mids for scram/web/cap booster (why armor
  brawlers hold you down better) and pays in raw damage.

Second-order costs, all real and all in the panel: plates add **mass**
(slower align *and* weaker MWD boost — thrust divides by post-plate mass);
extenders add **sig** (easier to hit and to lock); armor reps cycle slower
than shield boosters but cost less cap per HP; shield regens passively,
armor doesn't. Rig slots follow the tank too: CDFEs/purgers vs trimarks/
pumps compete with damage and speed rigs.

Resists vs raw HP: resist modules multiply everything — EHP, your reps,
and incoming logi — while raw-HP modules add only EHP. Buffer fleet fits
still take plates/extenders because they're unpenalized flat HP; a DC or
hardener is usually the better first tank module, the plate the better
second.

## Speed and signature as a tank

Turret damage scales by tracking factor (angular × sig terms) and missile
damage by `sig/explosionRadius` and velocity — being fast and small
reduces *applied* damage before resists exist. This tank is binary in a
way resists aren't: a web or scram (or your own MWD's +450% sig bloom
while lit) switches it off. AB fits keep base sig and moderate speed —
the anti-missile, anti-turret-application choice; MWD fits are faster but
bloomed and cap-hungry. Kiters tank with range + speed and fold when
tackled: name that failure mode when recommending one.

## Fitting a player, not a spreadsheet

A fit is an answer to "what will you be doing", never to "which number is
biggest". A max-DPS fit that is cap-dry in 90 seconds, untackled, and
paper-thin answered the query and failed the pilot. Before presenting a
fit or a comparison:

- **Name the job and the range band.** Brawl (scram range, high dps),
  kite (point range, application and speed), fleet (buffer + doctrine
  role), PvE (sustain vs the site's known damage profile and neuts).
- **Cap for the fight, not forever.** Stable is a PvE luxury; `lasts_s`
  beyond the expected engagement is enough for PvP (`reading-stats.md`).
- **Check the fit does its own job**: a kiter that aligns slower than its
  point range saves it, a brawler with no web, a missile boat with no
  application mods vs frigates — legal fits, wrong answers.
- **Say what was traded away.** Every recommendation names its cost ("the
  third gyro over a tracking enhancer: +6% paper DPS, worse applied vs
  anything small") — the tradeoff is the content, the numbers are the
  evidence.
- **Skills and price are part of the answer**: quote the preset (all-V vs
  alpha changes double digits), and remember T2 guns need real skills a
  new player lacks — offer the meta variant when the asker sounds new.
