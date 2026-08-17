"""Bounded graph series over pyfa's own application math and cap simulation.

The roadmap's rules: <= ~30 downsampled points, plus the summary stats a
session actually reasons with; assumptions named in the output. No dogma or
application math is reimplemented here — the per-key application factors
come from pyfa's `graphs/data/fitDamageStats/calc/application.py` and the
cap series from eos's own event simulation (`fit.getCapSimData`).

pyfa's `graphs` package __init__ imports the wx GUI, so the pure calc
modules are reached through synthetic package entries that shadow the GUI
__init__ files; `service.settings` (a wx-backed prefs store) is shimmed
with pyfa's own graph defaults, pinned from `service/settings.py`.
"""
import math
import os
import sys
import types

_ready = False


def _install_shims(pyfa_path):
    """Register synthetic packages so the pure calc modules import headless."""
    global _ready
    if _ready:
        return
    import service.const as service_const  # real module, import-clean

    if 'service.settings' not in sys.modules:
        shim = types.ModuleType('service.settings')

        class GraphSettings:
            # pyfa's own defaults (service/settings.py, GraphSettings.__init__)
            _defaults = {
                'mobileDroneMode': service_const.GraphDpsDroneMode.auto,
                'ignoreDCR': False,
                'ignoreResists': True,
                'ammoOptimalIgnoreResists': True,
                'ammoOptimalApplyProjected': True,
                'ignoreLockRange': True,
                'applyProjected': True,
            }
            _instance = None

            @classmethod
            def getInstance(cls):
                if cls._instance is None:
                    cls._instance = cls()
                return cls._instance

            def get(self, key):
                return self._defaults[key]

        shim.GraphSettings = GraphSettings
        sys.modules['service.settings'] = shim

    for name, rel in (('graphs', ('graphs',)),
                      ('graphs.data', ('graphs', 'data')),
                      ('graphs.data.fitDamageStats', ('graphs', 'data', 'fitDamageStats'))):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [os.path.join(pyfa_path, *rel)]
            sys.modules[name] = mod
    _ready = True


def _dmg_map(fit):
    """{key: DmgTypes dps} for everything active that deals damage."""
    dmg = {}
    for mod in fit.activeModulesIter():
        if mod.isDealingDamage():
            dmg[mod] = mod.getDps()
    for drone in fit.activeDronesIter():
        if drone.isDealingDamage():
            dmg[drone] = drone.getDps()
    return dmg


def _applied_dps(fit, distance, tgt_speed, tgt_sig, atk_speed, dmg):
    from graphs.data.fitDamageStats.calc.application import getApplicationPerKey
    from graphs.wrapper import SourceWrapper, TargetWrapper
    from eos.saveddata.targetProfile import TargetProfile
    src = SourceWrapper(fit, 0)
    tgt = TargetWrapper(TargetProfile(maxVelocity=tgt_speed, signatureRadius=tgt_sig), 0, 0)
    amap = getApplicationPerKey(
        src=src, tgt=tgt, atkSpeed=atk_speed, atkAngle=0, distance=distance,
        tgtSpeed=tgt_speed, tgtAngle=90, tgtSigRadius=tgt.getSigRadius())
    total = 0.0
    for key, d in dmg.items():
        total += (d * amap.get(key, 0)).total
    return total


def _max_relevant_range(fit):
    r = 10000.0
    for mod in fit.activeModulesIter():
        if not mod.isDealingDamage():
            continue
        optimal = mod.getModifiedItemAttr('maxRange') or 0
        falloff = mod.getModifiedItemAttr('falloff') or 0
        r = max(r, (mod.maxRange or optimal + 3 * falloff or 0))
        r = max(r, optimal + 3 * falloff)
    if any(True for _ in fit.activeDronesIter()):
        r = max(r, fit.extraAttributes['droneControlRange'] or 0)
    return min(r * 1.05, 300000.0)


def dps_vs_range(fit, tgt_speed=0.0, tgt_sig=None, atk_speed=0.0, points=30):
    dmg = _dmg_map(fit)
    max_r = _max_relevant_range(fit)
    xs = [max_r * i / (points - 1) for i in range(points)]
    series = [[round(x / 1000, 1), round(_applied_dps(fit, x, tgt_speed, tgt_sig, atk_speed, dmg), 1)]
              for x in xs]
    peak = max(y for _, y in series)
    peak_km = next(x for x, y in series if y == peak)
    half_km = next((x for x, y in series if x > peak_km and y < peak / 2), None)
    summary = {'peak_dps': peak, 'peak_at_km': peak_km}
    if half_km is not None:
        summary['half_dps_km'] = half_km
    if series[-1][1] == 0:
        summary['zero_beyond_km'] = next(x for x, y in reversed(series) if y > 0)
    return {
        'x': 'range_km', 'y': 'dps', 'points': series, 'summary': summary,
        'assumptions': _assumptions(fit, tgt_speed, tgt_sig),
    }


def dps_vs_target_speed(fit, distance_km=5.0, tgt_sig=None, max_speed=3600.0, points=25):
    dmg = _dmg_map(fit)
    dist = distance_km * 1000
    xs = [max_speed * i / (points - 1) for i in range(points)]
    series = [[round(x), round(_applied_dps(fit, dist, x, tgt_sig, 0.0, dmg), 1)] for x in xs]
    peak = max(y for _, y in series)
    half = next((x for x, y in series if y < peak / 2), None)
    return {
        'x': 'target_speed_ms', 'y': 'dps', 'points': series,
        'summary': {'peak_dps': peak, 'at_km': distance_km,
                    **({'half_dps_target_ms': half} if half is not None else {})},
        'assumptions': _assumptions(fit, None, tgt_sig),
    }


def dps_vs_time(fit, points=24):
    """Spool ramp: total dps as a function of continuous fire time."""
    from eos.const import SpoolType
    from eos.utils.spoolSupport import SpoolOptions, calculateSpoolup
    ramp = 0.0
    for m in fit.modules:
        if m.isEmpty:
            continue
        mx = m.getModifiedItemAttr('damageMultiplierBonusMax')
        step = m.getModifiedItemAttr('damageMultiplierBonusPerCycle')
        if mx and step:
            cyc = (m.getModifiedItemAttr('speed') or m.getModifiedItemAttr('duration') or 0) / 1000
            ramp = max(ramp, calculateSpoolup(mx, step, cyc, SpoolType.SPOOL_SCALE, 1.0)[2])
    if not ramp:
        raise ValueError('no spool-up weapons on this fit; dps_vs_time is the Triglavian ramp')
    tmax = ramp * 1.15
    series = []
    for i in range(points + 1):
        t = tmax * i / points
        dps = fit.getTotalDps(spoolOptions=SpoolOptions(SpoolType.TIME, t, True)).total
        pt = [round(t, 1), round(dps, 1)]
        if not series or pt[1] != series[-1][1] or i == points:
            series.append(pt)
    return {
        'x': 'time_s', 'y': 'dps', 'points': series,
        'summary': {'dps_zero_spool': series[0][1],
                    'dps_full_spool': max(y for _, y in series),
                    'time_to_full_s': round(ramp, 1)},
        'assumptions': ['continuous fire on one target, no reload',
                        'spool resets on target switch or cease-fire'],
    }


def cap_vs_time(fit, points=30):
    capacity = fit.ship.getModifiedItemAttr('capacitorCapacity')
    raw = fit.getCapSimData(startingCap=capacity)
    if not raw:
        return {'x': 'time_s', 'y': 'cap_gj',
                'points': [[0, round(capacity, 1)]],
                'summary': {'stable': True, 'note': 'no cap use fitted'}}
    # downsample, keeping first/last and the minimum; sim times are seconds
    idx = sorted({0, len(raw) - 1, min(range(len(raw)), key=lambda i: raw[i][1]),
                  *(round(i * (len(raw) - 1) / (points - 1)) for i in range(points))})
    series = []
    for i in idx:
        pt = [round(raw[i][0], 1), round(raw[i][1], 1)]
        if not series or pt[0] != series[-1][0]:
            series.append(pt)
    series = series[:points + 2]
    summary = {'capacity_gj': round(capacity, 1), 'stable': bool(fit.capStable)}
    summary['stable_pct' if fit.capStable else 'lasts_s'] = round(fit.capState, 1)
    return {'x': 'time_s', 'y': 'cap_gj', 'points': series, 'summary': summary,
            'assumptions': ['every fitted module running continuously (worst case)']}


def _assumptions(fit, tgt_speed, tgt_sig):
    out = []
    out.append('target orbiting at 90 deg (max transversal)' if tgt_speed
               else 'stationary attacker and target')
    if tgt_sig is None:
        out.append('ideal target signature (no sig penalty); pass tgt_sig for a real hull')
    if any(True for _ in fit.activeDronesIter()):
        out.append('drones travel to target inside drone control range')
    if fit.factorReload:
        out.append('reload factored')
    else:
        out.append('reload not factored (burst dps)')
    return out
