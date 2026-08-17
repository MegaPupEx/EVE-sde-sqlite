"""Engine keys for eval set 2 (the v1.5 surface). Prints JSON; pin as
keys2-<build>.json. Companion to make_keys.py (set 1, untouched)."""
import argparse
import asyncio
import json
import os

import drive

HERE = os.path.dirname(os.path.abspath(__file__))
BATTERY = os.path.join(os.path.dirname(HERE), 'spike', 'reference', 'battery.eft')


def battery_fit(name):
    for block in open(BATTERY).read().split('\n\n\n'):
        if block.strip() and name in block.splitlines()[0]:
            return block.strip()
    raise KeyError(name)


async def main(pyfa):
    calls = [
        {'tool': 'engine_info', 'args': {}},
        # G1 — Drake in a C3 Wolf-Rayet: shield resists suffer
        {'tool': 'import_fit', 'args': {'eft': battery_fit('drake')}, 'id': 'drake'},
        {'tool': 'get_stats', 'args': {'fit_id': '$drake'}},
        {'tool': 'set_env', 'args': {'fit_id': '$drake', 'effect': 'Class 3 Wolf Rayet Effects'}},
        {'tool': 'get_stats', 'args': {'fit_id': '$drake'}},
        {'tool': 'set_env', 'args': {'fit_id': '$drake', 'effect': ''}},
        # G2/G3 — Hurricane graphs: range falloff, and tracking vs a frigate
        {'tool': 'import_fit', 'args': {'eft': battery_fit('hurricane')}, 'id': 'cane'},
        {'tool': 'graph', 'args': {'fit_id': '$cane', 'kind': 'dps_vs_range'}},
        {'tool': 'graph', 'args': {'fit_id': '$cane', 'kind': 'dps_vs_target_speed',
                                   'target': {'sig_m': 40}, 'distance_km': 2}},
        # G4 — battery Punisher under one Curse medium neut
        {'tool': 'import_fit', 'args': {'eft': battery_fit('punisher')}, 'id': 'pun'},
        {'tool': 'get_stats', 'args': {'fit_id': '$pun'}},
        {'tool': 'import_fit', 'args': {'eft': '[Curse, neut]\nMedium Energy Neutralizer II'}, 'id': 'curse'},
        {'tool': 'set_projected', 'args': {'fit_id': '$pun', 'projector_fit_ids': ['$curse']}},
        {'tool': 'get_stats', 'args': {'fit_id': '$pun'}},
        # G5 — burst source matters: Drake vs Vulture vs both
        {'tool': 'import_fit', 'args': {'eft': '[Caracal, subj]\nLarge Shield Extender II'}, 'id': 'subj'},
        {'tool': 'get_stats', 'args': {'fit_id': '$subj'}},
        {'tool': 'import_fit', 'args': {'eft': '[Drake, boostA]\nShield Command Burst II, Shield Extension Charge'}, 'id': 'bA'},
        {'tool': 'import_fit', 'args': {'eft': '[Vulture, boostB]\nShield Command Burst II, Shield Extension Charge'}, 'id': 'bB'},
        {'tool': 'set_booster', 'args': {'fit_id': '$subj', 'booster_fit_ids': ['$bA']}},
        {'tool': 'get_stats', 'args': {'fit_id': '$subj'}},
        {'tool': 'set_booster', 'args': {'fit_id': '$subj', 'booster_fit_ids': ['$bB']}},
        {'tool': 'get_stats', 'args': {'fit_id': '$subj'}},
        {'tool': 'set_booster', 'args': {'fit_id': '$subj', 'booster_fit_ids': ['$bA', '$bB']}},
        {'tool': 'get_stats', 'args': {'fit_id': '$subj'}},
        # G6 — the unknown pilot's Rifter: all-0 floor vs all-5 ceiling
        {'tool': 'import_fit', 'args': {'eft': battery_fit('rifter')}, 'id': 'rif'},
        {'tool': 'set_skills', 'args': {'fit_id': '$rif', 'preset': 'all-0'}},
        {'tool': 'get_stats', 'args': {'fit_id': '$rif'}},
        # G7 — one Firbolg squadron on a Thanatos
        {'tool': 'create_fit', 'args': {'ship': 'Thanatos'}, 'id': 'than'},
        {'tool': 'edit_fit', 'args': {'fit_id': '$than', 'ops': [{'op': 'add', 'item': 'Firbolg I'}]}},
        {'tool': 'get_stats', 'args': {'fit_id': '$than'}},
    ]
    res = await drive.run(pyfa, calls)
    for r in res:
        if isinstance(r, dict) and 'error' in r:
            raise SystemExit(f'call failed: {r["error"]}')

    keys = {
        'engine_build': res[0]['engine_build'],
        'G1_drake_uniform_ehp': res[2]['defense']['ehp']['total'],
        'G1_drake_c3wr_ehp': res[4]['defense']['ehp']['total'],
        'G1_drake_c3wr_shield_resists': res[4]['defense']['resists']['shield'],
        'G1_drake_c3wr_regen': res[4]['defense'].get('reps_hps'),
        'G2_hurricane_range_summary': res[7]['summary'],
        'G3_hurricane_vs_frigate': {'points_head': res[8]['points'][:4],
                                    'summary': res[8]['summary']},
        'G4_punisher_cap_before': res[10]['capacitor'],
        'G4_punisher_cap_neuted': res[13]['capacitor'],
        'G5_shield_hp': {
            'base': res[15]['defense']['hp']['shield'],
            'drake_burst': res[19]['defense']['hp']['shield'],
            'vulture_burst': res[21]['defense']['hp']['shield'],
            'both': res[23]['defense']['hp']['shield']},
        'G6_rifter_all0': {
            'dps': res[26]['offense']['dps'],
            'ehp_uniform': res[26]['defense']['ehp']['total'],
            'max_velocity_ms': res[26]['navigation']['max_velocity_ms']},
        'G7_thanatos_firbolg': {
            'dps_fighters': res[29]['offense'].get('dps_fighters'),
            'dps': res[29]['offense']['dps']},
    }
    print(json.dumps(keys, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    asyncio.run(main(ap.parse_args().pyfa))
