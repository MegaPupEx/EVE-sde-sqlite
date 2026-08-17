"""Compute the engine-truth keys for the eval set and print them as JSON.

    <eosenv>/bin/python make_keys.py --pyfa <pyfa-checkout>

Every class-1 key (and the engine half of every class-2 key) in
questions.md comes from this script, so keys are re-derivable on any data
build: re-run, diff, and update the pinned numbers if the build moved.
"""
import argparse
import asyncio
import json
import os

import drive

HERE = os.path.dirname(os.path.abspath(__file__))
BATTERY = os.path.join(os.path.dirname(HERE), 'spike', 'reference', 'battery.eft')

GURISTAS = {'em': 0, 'thermal': 20, 'kinetic': 80, 'explosive': 0}


def battery_fit(name):
    for block in open(BATTERY).read().split('\n\n\n'):
        if block.strip() and name in block.splitlines()[0]:
            return block.strip()
    raise KeyError(name)


async def main(pyfa):
    calls = [
        {'tool': 'engine_info', 'args': {}},
        # E1 — Caracal EHP: uniform vs Guristas profile
        {'tool': 'import_fit', 'args': {'eft': battery_fit('caracal')}, 'id': 'cara'},
        {'tool': 'get_stats', 'args': {'fit_id': '$cara'}},
        {'tool': 'get_stats', 'args': {'fit_id': '$cara', 'profile': GURISTAS}},
        # E2 — Rifter align time
        {'tool': 'import_fit', 'args': {'eft': battery_fit('rifter')}, 'id': 'rif'},
        {'tool': 'get_stats', 'args': {'fit_id': '$rif'}},
        # E3 — Hurricane volley vs dps
        {'tool': 'import_fit', 'args': {'eft': battery_fit('hurricane')}, 'id': 'cane'},
        {'tool': 'get_stats', 'args': {'fit_id': '$cane'}},
        # E4 — Rifter on alpha-clone skills
        {'tool': 'set_skills', 'args': {'fit_id': '$rif', 'preset': 'alpha'}},
        {'tool': 'get_stats', 'args': {'fit_id': '$rif'}},
        # E5 — 7th artillery on the Hurricane
        {'tool': 'clone_fit', 'args': {'fit_id': '$cane', 'name': 'seventh-gun'}, 'id': 'cane7'},
        {'tool': 'edit_fit', 'args': {'fit_id': '$cane7', 'ops': [
            {'op': 'add', 'item': '720mm Howitzer Artillery II'}]}},
        {'tool': 'validate_fit', 'args': {'fit_id': '$cane7'}},
        # T1 — 3rd Gyrostabilizer in place of the Tracking Enhancer
        {'tool': 'clone_fit', 'args': {'fit_id': '$cane', 'name': 'third-gyro'}, 'id': 'gyro3'},
        {'tool': 'edit_fit', 'args': {'fit_id': '$gyro3', 'ops': [
            {'op': 'remove', 'item': 'Tracking Enhancer II'},
            {'op': 'add', 'item': 'Gyrostabilizer II'}]}},
        {'tool': 'get_stats', 'args': {'fit_id': '$gyro3'}},
        # T2 — Vexor: armor brawl tank swapped for shield
        {'tool': 'import_fit', 'args': {'eft': battery_fit('vexor')}, 'id': 'vex'},
        {'tool': 'clone_fit', 'args': {'fit_id': '$vex', 'name': 'shield-vexor'}, 'id': 'vexs'},
        {'tool': 'edit_fit', 'args': {'fit_id': '$vexs', 'ops': [
            {'op': 'remove', 'item': '1600mm Steel Plates II'},
            {'op': 'remove', 'item': 'X5 Enduring Stasis Webifier'},
            {'op': 'remove', 'item': 'Medium Trimark Armor Pump I'},
            {'op': 'add', 'item': 'Large Shield Extender II'},
            {'op': 'add', 'item': 'Drone Damage Amplifier II'},
            {'op': 'add', 'item': 'Medium Core Defense Field Extender I'}]}},
        {'tool': 'compare_fits', 'args': {'fit_id_a': '$vex', 'fit_id_b': '$vexs'}},
        # T3 — Abaddon cap: how long does it actually last
        {'tool': 'import_fit', 'args': {'eft': battery_fit('abaddon')}, 'id': 'abd'},
        {'tool': 'get_stats', 'args': {'fit_id': '$abd'}},
    ]
    res = await drive.run(pyfa, calls)
    for r in res:
        if isinstance(r, dict) and 'error' in r:
            raise SystemExit(f'call failed: {r["error"]}')

    keys = {
        'engine_build': res[0]['engine_build'],
        'E1_caracal_ehp_uniform': res[2]['defense']['ehp']['total'],
        'E1_caracal_ehp_guristas': res[3]['defense']['ehp']['total'],
        'E2_rifter_align_s': res[5]['navigation']['align_time_s'],
        'E3_hurricane': {k: res[7]['offense'][k] for k in ('volley', 'dps', 'dps_sustained')},
        'E4_rifter_alpha_clone': {
            'dps': res[9]['offense']['dps'],
            'ehp_uniform': res[9]['defense']['ehp']['total'],
            'max_velocity_ms': res[9]['navigation']['max_velocity_ms']},
        'E4_rifter_all5': {
            'dps': res[5]['offense']['dps'],
            'ehp_uniform': res[5]['defense']['ehp']['total'],
            'max_velocity_ms': res[5]['navigation']['max_velocity_ms']},
        'E5_seventh_gun_problems': res[12]['problems'],
        'T1_hurricane_dps_2gyro_te': res[7]['offense']['dps'],
        'T1_hurricane_dps_3gyro': res[15]['offense']['dps'],
        'T2_vexor_armor_vs_shield_diffs': res[19]['diffs'],
        'T3_abaddon_cap': res[21]['capacitor'],
    }
    print(json.dumps(keys, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    asyncio.run(main(ap.parse_args().pyfa))
