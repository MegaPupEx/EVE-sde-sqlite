"""Drive the reference battery through pyfa's eos, headless; dump stat panels.

    python3 run_battery.py --pyfa /path/to/pyfa/checkout [--out reference/]

Requires: the pyfa checkout to have eve.db built (python3 db_update.py) and a
venv with sqlalchemy 1.4.x, logbook, python-dateutil, pyyaml, cryptography,
requests, roman. No wxPython — headless.bootstrap() stubs it.

The JSON written per fit is the spike's ground truth: pyfa's own engine
computing pyfa's own numbers. Candidate B (dogma-engine) is graded against
these files, and the MCP v1 harness inherits them.
"""
import argparse
import datetime
import json
import math
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless import bootstrap
from battery import FITS

DMG_TYPES = ('em', 'thermal', 'kinetic', 'explosive')
LAYERS = (('shield', 'shieldCapacity'), ('armor', 'armorHP'), ('hull', 'hp'))


def getItemStrict(name):
    import eos.db
    item = eos.db.getItem(name)
    if item is None:
        raise SystemExit(f"unknown item name: {name!r} — check against pyfa's DB")
    return item


def buildFit(spec, character):
    from eos.const import FittingModuleState
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    fit = Fit(Ship(getItemStrict(spec['ship'])), name=spec['name'])
    fit.character = character
    fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25,
                                      kineticAmount=25, explosiveAmount=25)
    for name, charge in spec['modules']:
        mod = Module(getItemStrict(name))
        if charge:
            mod.charge = getItemStrict(charge)
        if mod.isValidState(FittingModuleState.ACTIVE):
            mod.state = FittingModuleState.ACTIVE
        fit.modules.append(mod)
        mod.owner = fit  # ORM backref; not populated without a saveddata session
    for name, amount in spec.get('drones', ()):
        drone = Drone(getItemStrict(name))
        drone.amount = amount
        drone.amountActive = amount
        fit.drones.append(drone)
        drone.owner = fit
    return fit


def recalc(fit, factorReload):
    fit.factorReload = factorReload
    fit.clear()
    fit.calculateModifiedAttributes()


def resists(item, layer):
    prefix = '' if layer == 'hull' else layer
    out = {}
    for dmg in DMG_TYPES:
        attr = f"{prefix}{dmg.capitalize()}DamageResonance"
        attr = attr[0].lower() + attr[1:]
        out[dmg] = round(1 - item.getModifiedItemAttr(attr), 4)
    return out


def statPanel(fit):
    ship = fit.ship
    attr = ship.getModifiedItemAttr

    recalc(fit, factorReload=False)
    dpsBurst = fit.getTotalDps().total
    volley = fit.getTotalVolley().total
    droneDps = fit.getDroneDps().total
    ehp = fit.ehp
    capStable = fit.capStable
    capState = fit.capState

    recalc(fit, factorReload=True)
    dpsSustained = fit.getTotalDps().total

    sig = attr('signatureRadius')
    scanRes = attr('scanResolution')
    shieldRechargePeak = fit.calculateShieldRecharge()
    return {
        'fitting': {
            'cpu': [round(fit.cpuUsed, 2), round(attr('cpuOutput'), 2)],
            'powergrid': [round(fit.pgUsed, 2), round(attr('powerOutput'), 2)],
            'calibration': [sum(m.getModifiedItemAttr('upgradeCost') or 0 for m in fit.modules if not m.isEmpty),
                            attr('upgradeCapacity')],
        },
        'defense': {
            'hp': {layer: round(attr(a), 1) for layer, a in LAYERS},
            'resists': {layer: resists(ship, layer) for layer, _ in LAYERS},
            'ehp_uniform': {k: round(v, 1) for k, v in ehp.items()},
            'ehp_total_uniform': round(sum(ehp.values()), 1),
            'shield_regen_peak_hps': round(shieldRechargePeak, 2),
        },
        'offense': {
            'dps_burst': round(dpsBurst, 2),
            'dps_sustained': round(dpsSustained, 2),
            'dps_drones': round(droneDps, 2),
            'volley': round(volley, 2),
        },
        'capacitor': {
            'capacity_gj': round(attr('capacitorCapacity'), 1),
            'recharge_time_s': round(attr('rechargeRate') / 1000, 2),
            'stable': bool(capStable),
            'stable_pct_or_ttl_s': round(capState, 1),
        },
        'navigation': {
            'max_velocity_ms': round(fit.maxSpeed, 2),
            'align_time_s': round(fit.alignTime, 3),
            'signature_m': round(sig, 1),
            'mass_kg': round(attr('mass'), 1),
            'warp_speed_aus': round(fit.warpSpeed, 2),
        },
        'targeting': {
            'scan_resolution_mm': round(scanRes, 1),
            'lock_range_km': round(attr('maxTargetRange') / 1000, 2),
            'sensor_strength': round(fit.scanStrength, 2),
            'max_targets': fit.maxTargets,
            'lock_time_frigate_35m_s': round(40000 / scanRes / math.asinh(35) ** 2, 2),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reference'))
    args = ap.parse_args()

    bootstrap(args.pyfa)
    import eos.db  # noqa: F401 — must precede any eos.saveddata import (circular otherwise)
    from eos.saveddata.character import Character

    pyfa_commit = subprocess.run(['git', '-C', args.pyfa, 'rev-parse', 'HEAD'],
                                 capture_output=True, text=True).stdout.strip() or 'unknown'
    meta_rows = dict(sqlite3.connect(os.path.join(args.pyfa, 'eve.db'))
                     .execute("SELECT field_name, field_value FROM metadata").fetchall())
    meta = {
        'engine': 'pyfa-eos',
        'pyfa_commit': pyfa_commit,
        'engine_client_build': meta_rows.get('client_build'),
        'engine_dump_time': meta_rows.get('dump_time'),
        'character': 'all-5',
        'damage_profile': 'uniform',
        'generated': datetime.date.today().isoformat(),
    }

    os.makedirs(args.out, exist_ok=True)
    character = Character.getAll5()
    print(f"{'fit':26} {'dps':>7} {'sust':>7} {'volley':>8} {'ehp':>8} {'cap':>9} {'align':>6} {'m/s':>7}")
    for spec in FITS:
        fit = buildFit(spec, character)
        panel = statPanel(fit)
        doc = {'name': spec['name'], 'ship': spec['ship'], 'exercises': spec['exercises'],
               'meta': meta, 'modules': spec['modules'], 'drones': spec.get('drones', []),
               'stats': panel}
        path = os.path.join(args.out, f"{spec['name']}.json")
        with open(path, 'w') as f:
            json.dump(doc, f, indent=1)
        o, d, c, n = panel['offense'], panel['defense'], panel['capacitor'], panel['navigation']
        cap = f"{c['stable_pct_or_ttl_s']}%" if c['stable'] else f"{c['stable_pct_or_ttl_s']}s"
        print(f"{spec['name']:26} {o['dps_burst']:>7.1f} {o['dps_sustained']:>7.1f} {o['volley']:>8.1f} "
              f"{d['ehp_total_uniform']:>8.0f} {cap:>9} {n['align_time_s']:>6.2f} {n['max_velocity_ms']:>7.1f}")
    print(f"\nwrote {len(FITS)} panels to {args.out}")


if __name__ == '__main__':
    main()
