"""The stat panel: one compact dict per fit, shared by MCP server and harness.

Same figures as the pinned spike battery (superset: adds rep rates per the
GUI spot-check, and drops sections that are all-zero to save tokens). Keys
carry units so a consuming model never guesses: _s seconds, _ms metres/sec,
_km, _gj, _hps HP/sec effective.
"""
import math

DMG_TYPES = ('em', 'thermal', 'kinetic', 'explosive')
LAYERS = (('shield', 'shieldCapacity'), ('armor', 'armorHP'), ('hull', 'hp'))


def _recalc(fit, factor_reload):
    fit.factorReload = factor_reload
    fit.clear()
    fit.calculateModifiedAttributes()


def _resists(item, layer):
    prefix = '' if layer == 'hull' else layer
    out = {}
    for dmg in DMG_TYPES:
        attr = f'{prefix}{dmg.capitalize()}DamageResonance'
        attr = attr[0].lower() + attr[1:]
        out[dmg] = round(1 - item.getModifiedItemAttr(attr), 3)
    return out


def spool_ramp(fit):
    """(active spool-up modules, seconds to full spool) — the ONE place that
    decides what counts as a spool weapon; panel and graphs share it."""
    from eos.const import FittingModuleState, SpoolType
    from eos.utils.spoolSupport import calculateSpoolup
    mods = [m for m in fit.modules if not m.isEmpty
            and 'damageMultiplierBonusPerCycle' in m.item.attributes
            and m.state >= FittingModuleState.ACTIVE]
    ramp = max((calculateSpoolup(
        m.getModifiedItemAttr('damageMultiplierBonusMax'),
        m.getModifiedItemAttr('damageMultiplierBonusPerCycle'),
        (m.getModifiedItemAttr('speed') or m.getModifiedItemAttr('duration') or 0) / 1000,
        SpoolType.SPOOL_SCALE, 1.0)[2] for m in mods), default=0.0)
    return mods, ramp


def align_prop_off(fit):
    """(align seconds with the prop mod shut off, kg the prop adds), or None.

    `fit.alignTime` reflects the module states as they stand, so an ACTIVE
    microwarpdrive inflates it by the mass it adds — a 5MN MWD is +500,000 kg
    on a 1,400,000 kg destroyer, which is most of a second of align. Nobody
    aligns like that: you cut the prop and then warp, precisely because the
    mass penalty is what slows the align down. Reporting only the prop-on
    figure hands the reader the pessimistic number for the one manoeuvre the
    number exists to describe (measured 2026-08-20 on a graded Svipul answer,
    which quoted 4.98 s for an align that is really 3.67 s).

    Align time is linear in mass at fixed agility, and a prop mod changes only
    mass, so the correction is exact rather than a re-simulation.
    """
    from eos.const import FittingModuleState
    added = sum(m.getModifiedItemAttr('massAddition') or 0
                for m in fit.modules
                if not m.isEmpty and m.state >= FittingModuleState.ACTIVE
                and (m.getModifiedItemAttr('massAddition') or 0) > 0)
    mass = fit.ship.getModifiedItemAttr('mass') or 0
    if not added or not mass or added >= mass:
        return None
    return fit.alignTime * (mass - added) / mass, added


def stat_panel(fit, recalc=_recalc, spool=None):
    """Full stat panel. Caller sets fit.damagePattern first (default uniform).

    recalc(fit, factor_reload) is injectable because eos *consumes* command
    bonuses on application — a caller with command-burst boosters must rerun
    its booster pass before every calculation, not just the first.
    """
    ship = fit.ship
    attr = ship.getModifiedItemAttr

    _recalc = recalc
    _recalc(fit, factor_reload=False)

    # Spool-up weapons (Triglavian ramp): quote at a named spool level.
    # Default is FULL spool (pyfa's own globalDefaultSpoolupPercentage=1.0
    # convention); the zero-spool floor and ramp time ride along so the
    # answer can name the band instead of a single misleading number.
    from eos.const import SpoolType
    from eos.utils.spoolSupport import SpoolOptions
    spool_mods, ramp_s = spool_ramp(fit)
    spool_level = 1.0 if spool is None else max(0.0, min(1.0, float(spool)))
    spool_opts = SpoolOptions(SpoolType.SPOOL_SCALE, spool_level, True) if spool_mods else None

    dps_burst = fit.getTotalDps(spoolOptions=spool_opts).total
    volley = fit.getTotalVolley(spoolOptions=spool_opts).total
    dps_fighters = sum((f.getDps().total for f in fit.fighters), 0.0)
    dps_drones = fit.getDroneDps().total - dps_fighters  # getDroneDps folds fighters in
    spool_info = None
    if spool_mods:
        spool_info = {
            'level': spool_level,
            'dps_zero_spool': round(fit.getTotalDps(
                spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, 0.0, True)).total, 1),
            'time_to_full_s': round(ramp_s, 1),
        }
    ehp = fit.ehp
    cap_stable = fit.capStable
    cap_state = fit.capState
    reps = {k: round(v, 1) for k, v in fit.effectiveTank.items() if v}
    _align_off = align_prop_off(fit)

    _recalc(fit, factor_reload=True)
    dps_sustained = fit.getTotalDps(spoolOptions=spool_opts).total

    scan_res = attr('scanResolution')
    panel = {
        'fitting': {
            'cpu': [round(fit.cpuUsed, 2), round(attr('cpuOutput'), 2)],
            'powergrid': [round(fit.pgUsed, 2), round(attr('powerOutput'), 2)],
            'calibration': [round(fit.calibrationUsed), round(attr('upgradeCapacity') or 0)],
        },
        'defense': {
            'ehp': {k: round(v) for k, v in ehp.items()} | {'total': round(sum(ehp.values()))},
            'resists': {layer: _resists(ship, layer) for layer, _ in LAYERS},
            'hp': {layer: round(attr(a)) for layer, a in LAYERS},
        },
        'offense': {
            'dps': round(dps_burst, 1),
            'dps_sustained': round(dps_sustained, 1),
            'dps_drones': round(dps_drones, 1),
            'volley': round(volley, 1),
            **({'spool': spool_info} if spool_info else {}),
        },
        'capacitor': {
            'capacity_gj': round(attr('capacitorCapacity'), 1),
            'stable': bool(cap_stable),
            'stable_pct' if cap_stable else 'lasts_s': round(cap_state, 1),
        },
        'navigation': {
            'max_velocity_ms': round(fit.maxSpeed, 1),
            'align_time_s': round(fit.alignTime, 2),
            **({'align_time_prop_off_s': round(_align_off[0], 2)}
               if _align_off else {}),
            'signature_m': round(attr('signatureRadius'), 1),
            'warp_speed_aus': round(fit.warpSpeed, 2),
            'mass_kg': round(attr('mass')),
        },
        'targeting': {
            'scan_resolution_mm': round(scan_res),
            'lock_range_km': round(attr('maxTargetRange') / 1000, 1),
            'sensor_strength': round(fit.scanStrength, 1),
            'max_targets': fit.maxTargets,
            'lock_time_frigate_s': round(40000 / scan_res / math.asinh(35) ** 2, 2),
            'lock_time_battleship_s': round(40000 / scan_res / math.asinh(400) ** 2, 2),
        },
    }
    if _align_off:
        panel.setdefault('notes', []).append(
            f'align_time_s ({panel["navigation"]["align_time_s"]} s) is with the prop '
            f'mod RUNNING, which adds {_align_off[1]:,.0f} kg. You align with the prop '
            f'OFF: {panel["navigation"]["align_time_prop_off_s"]} s. Quote the prop-off '
            'figure for aligning, warping out and escaping; the prop-on figure only '
            'applies if you keep it burning through the align.')
    if reps:
        panel['defense']['reps_hps'] = reps
    # Upwell structures cap incoming dps per layer (data: *DamageLimit attrs);
    # EHP / cap is the floor on time-to-kill regardless of attacker count.
    # A "cap" as large as the layer's full HP is no cap at all (Astrahus
    # shield: limit 14.4M == shield HP) — three of four eval subjects read
    # the raw number as a per-layer 5k-style cap, so report it as 'none'.
    raw_hp = {'shield': attr('shieldCapacity'), 'armor': attr('armorHP'),
              'hull': attr('hp')}
    dmg_caps = {layer: 'none' if cap >= raw_hp[layer] else round(cap)
                for layer, a in (('shield', 'shieldDamageLimit'),
                                 ('armor', 'armorDamageLimit'),
                                 ('hull', 'structureDamageLimit'))
                for cap in [attr(a)] if cap}
    if dmg_caps:
        panel['defense']['incoming_dps_cap'] = dmg_caps
    if not dps_drones:
        del panel['offense']['dps_drones']
    if dps_fighters:
        panel['offense']['dps_fighters'] = round(dps_fighters, 1)
    if dps_burst == dps_sustained:
        del panel['offense']['dps_sustained']
    # Upwell service modules: fuel is per-service dogma, and the hourly burn
    # is the number every "what does it cost to run" question needs
    from eos.const import FittingModuleState
    services = [m for m in fit.modules if not m.isEmpty
                and 'serviceModuleFuelAmount' in m.item.attributes]
    if services:
        online = [m for m in services if m.state >= FittingModuleState.ONLINE]
        panel['services'] = {
            'fitted': [{'name': m.item.typeName,
                        'fuel_hr': round(m.getModifiedItemAttr('serviceModuleFuelAmount') or 0, 1),
                        'fuel_to_online': round(m.getModifiedItemAttr('serviceModuleFuelOnlineAmount') or 0),
                        'online': m.state >= FittingModuleState.ONLINE}
                       for m in services],
            'fuel_blocks_per_hour': round(sum(
                m.getModifiedItemAttr('serviceModuleFuelAmount') or 0 for m in online), 1),
        }
    return panel
