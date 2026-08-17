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


def stat_panel(fit):
    """Full stat panel. Caller sets fit.damagePattern first (default uniform)."""
    ship = fit.ship
    attr = ship.getModifiedItemAttr

    _recalc(fit, factor_reload=False)
    dps_burst = fit.getTotalDps().total
    volley = fit.getTotalVolley().total
    dps_drones = fit.getDroneDps().total
    ehp = fit.ehp
    cap_stable = fit.capStable
    cap_state = fit.capState
    reps = {k: round(v, 1) for k, v in fit.effectiveTank.items() if v}

    _recalc(fit, factor_reload=True)
    dps_sustained = fit.getTotalDps().total

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
        },
        'capacitor': {
            'capacity_gj': round(attr('capacitorCapacity'), 1),
            'stable': bool(cap_stable),
            'stable_pct' if cap_stable else 'lasts_s': round(cap_state, 1),
        },
        'navigation': {
            'max_velocity_ms': round(fit.maxSpeed, 1),
            'align_time_s': round(fit.alignTime, 2),
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
    if reps:
        panel['defense']['reps_hps'] = reps
    if not dps_drones:
        del panel['offense']['dps_drones']
    if dps_burst == dps_sustained:
        del panel['offense']['dps_sustained']
    return panel
