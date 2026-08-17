"""Smoke test: drive the MCP server over real stdio like a Claude session would.

    <venv>/bin/python test_server.py --pyfa <pyfa-checkout>

Asserts the full tool surface works and reports the token economics: the
standing schema overhead and the size of every response. Panel numbers are
checked against the pinned reference battery.
"""
import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.join(os.path.dirname(HERE), 'spike')


def tokens(obj):
    return len(json.dumps(obj)) // 4


def unwrap(result):
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get('result', sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


async def main(pyfa):
    ref = json.load(open(os.path.join(SPIKE, 'reference', 'rifter-ac-brawler.json')))
    eft_text = open(os.path.join(SPIKE, 'reference', 'battery.eft')).read()
    rifter_eft = eft_text.split('\n\n\n')[0]

    params = StdioServerParameters(
        command=sys.executable, args=[os.path.join(HERE, 'server.py'), '--pyfa', pyfa])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()

            tools = await s.list_tools()
            schema_json = [{'name': t.name, 'description': t.description,
                            'inputSchema': t.input_schema} for t in tools.tools]
            print(f'{len(tools.tools)} tools; standing schema overhead ~{tokens(schema_json)} tokens')

            async def call(_tool, **kw):
                out = unwrap(await s.call_tool(_tool, kw))
                print(f'  {_tool:14} -> ~{tokens(out)} tokens')
                return out

            # import + stats vs pinned reference
            imp = await call('import_fit', eft=rifter_eft)
            fid = imp['fit_id']
            assert imp['problems'] == [], imp['problems']
            assert imp['slots']['low'][1] == 4 and imp['slots']['high'][1] == 3, imp['slots']
            assert imp['hardpoints']['turret'] == [3, 3], imp.get('hardpoints')
            stats = await call('get_stats', fit_id=fid)
            assert stats['offense']['dps'] == round(ref['stats']['offense']['dps_burst'], 1), stats['offense']
            assert stats['defense']['ehp']['total'] == round(ref['stats']['defense']['ehp_total_uniform']), stats['defense']['ehp']
            assert 'reps_hps' in stats['defense'], 'AAR rep rate missing'

            # damage profile changes EHP
            em = await call('get_stats', fit_id=fid, profile={'em': 100})
            assert em['defense']['ehp']['total'] != stats['defense']['ehp']['total']

            # edit: swap ammo -> dps moves; offline MWD -> speed drops
            base_speed = stats['navigation']['max_velocity_ms']
            await call('edit_fit', fit_id=fid, ops=[
                {'op': 'charge', 'item': '150mm Light AutoCannon II', 'charge': 'Barrage S'},
                {'op': 'state', 'item': '5MN Y-T8 Compact Microwarpdrive', 'state': 'online'}])
            s2 = await call('get_stats', fit_id=fid)
            assert s2['offense']['dps'] != stats['offense']['dps']
            assert s2['navigation']['max_velocity_ms'] < base_speed / 3

            # alpha skills weaken the fit — and switching back must fully restore:
            # the alpha preset once mutated the shared All-5 character, silently
            # turning every fit alpha for the rest of the session
            await call('set_skills', fit_id=fid, preset='alpha')
            s3 = await call('get_stats', fit_id=fid)
            assert s3['offense']['dps'] < s2['offense']['dps'], (s3['offense'], s2['offense'])
            await call('set_skills', fit_id=fid, preset='all-0')
            s3z = await call('get_stats', fit_id=fid)
            assert s3z['offense']['dps'] < s3['offense']['dps'], 'all-0 must be below alpha'
            await call('set_skills', fit_id=fid, preset='all-5')
            s3b = await call('get_stats', fit_id=fid)
            assert s3b['offense']['dps'] == s2['offense']['dps'], 'all-5 not restored after alpha'
            fresh = await call('import_fit', eft=rifter_eft)
            fresh_stats = await call('get_stats', fit_id=fresh['fit_id'])
            assert fresh_stats['offense']['dps'] == stats['offense']['dps'], \
                'alpha preset leaked into a freshly imported fit'
            await call('delete_fit', fit_id=fresh['fit_id'])

            # clone + compare: the diff names what changed
            c = await call('clone_fit', fit_id=fid, name='variant')
            await call('edit_fit', fit_id=c['fit_id'], ops=[
                {'op': 'remove', 'item': 'Gyrostabilizer II'},
                {'op': 'add', 'item': 'Damage Control II'}])
            cmp_out = await call('compare_fits', fit_id_a=fid, fit_id_b=c['fit_id'])
            assert any('dps' in k for k in cmp_out['diffs']), cmp_out['diffs']

            # validation catches hardpoint overflow
            await call('edit_fit', fit_id=c['fit_id'], ops=[
                {'op': 'add', 'item': '150mm Light AutoCannon II'}])
            v = await call('validate_fit', fit_id=c['fit_id'])
            assert not v['legal'] and any('turret' in p for p in v['problems']), v

            # export round-trips through import
            eft_out = await call('export_fit', fit_id=fid)
            eft_str = eft_out if isinstance(eft_out, str) else eft_out['result']
            re_imp = await call('import_fit', eft=eft_str)
            assert re_imp['ship'] == 'Rifter'

            # environment: C5 wolf-rayet multiplies small-turret dps; clearing restores
            base = await call('get_stats', fit_id=fid)
            env = await call('set_env', fit_id=fid, effect='Class 5 Wolf Rayet Effects')
            assert env['env'] == 'Class 5 Wolf Rayet Effects'
            wr = await call('get_stats', fit_id=fid)
            ratio = wr['offense']['dps'] / base['offense']['dps']
            assert 2.5 < ratio < 2.8, f'WR dps ratio {ratio}'
            await call('set_env', fit_id=fid, effect='')
            back = await call('get_stats', fit_id=fid)
            assert back['offense']['dps'] == base['offense']['dps'], 'env did not clear'
            try:
                await call('set_env', fit_id=fid, effect='Wolf Rayet')
                raise AssertionError('fuzzy env name should error with candidates')
            except RuntimeError as e:
                assert 'Class 1 Wolf Rayet Effects' in str(e), e

            # command bursts: shield burst raises shield cap; strongest booster wins
            subj = await call('import_fit', eft='[Caracal, subj]\nLarge Shield Extender II')
            drake = await call('import_fit', eft='[Drake, boostA]\nShield Command Burst II, Shield Extension Charge')
            vult = await call('import_fit', eft='[Vulture, boostB]\nShield Command Burst II, Shield Extension Charge')
            s_base = await call('get_stats', fit_id=subj['fit_id'])
            await call('set_booster', fit_id=subj['fit_id'], booster_fit_ids=[drake['fit_id']])
            s_one = await call('get_stats', fit_id=subj['fit_id'])
            r1 = s_one['defense']['hp']['shield'] / s_base['defense']['hp']['shield']
            assert 1.10 < r1 < 1.20, f'drake burst ratio {r1}'
            await call('set_booster', fit_id=subj['fit_id'],
                       booster_fit_ids=[drake['fit_id'], vult['fit_id']])
            s_two = await call('get_stats', fit_id=subj['fit_id'])
            await call('set_booster', fit_id=subj['fit_id'], booster_fit_ids=[vult['fit_id']])
            s_vult = await call('get_stats', fit_id=subj['fit_id'])
            assert s_two['defense']['hp']['shield'] == s_vult['defense']['hp']['shield'], \
                'two same bursts must not stack (strongest wins)'
            assert s_vult['defense']['hp']['shield'] > s_one['defense']['hp']['shield'], \
                'command-ship hull must scale the burst'

            # projected fits: a web halves speed; a neut kills the cap; [] restores
            vic = await call('import_fit', eft='[Rifter, victim]\n5MN Y-T8 Compact Microwarpdrive')
            v_base = await call('get_stats', fit_id=vic['fit_id'])
            ewar = await call('import_fit', eft='[Vigil, ew]\nStasis Webifier I')
            await call('set_projected', fit_id=vic['fit_id'], projector_fit_ids=[ewar['fit_id']])
            v_web = await call('get_stats', fit_id=vic['fit_id'])
            wr_ratio = v_web['navigation']['max_velocity_ms'] / v_base['navigation']['max_velocity_ms']
            assert 0.45 < wr_ratio < 0.55, f'projected web ratio {wr_ratio}'
            neut = await call('import_fit', eft='[Curse, neut]\nMedium Energy Neutralizer II')
            await call('set_projected', fit_id=vic['fit_id'],
                       projector_fit_ids=[ewar['fit_id'], neut['fit_id']])
            v_neut = await call('get_stats', fit_id=vic['fit_id'])
            assert not v_neut['capacitor']['stable'] and \
                v_neut['capacitor']['lasts_s'] < v_base['capacitor'].get('lasts_s', 1e9), v_neut['capacitor']
            # projection at range: inside optimal = full web; far beyond
            # optimal + 3x falloff = no effect; the curve names the band
            ma_web = await call('module_attrs', fit_id=ewar['fit_id'],
                                item='Stasis Webifier I', attrs=['maxRange', 'falloffEffectiveness'])
            web_opt_km = ma_web['modules'][0]['attrs']['maxRange'] / 1000
            await call('set_projected', fit_id=vic['fit_id'],
                       projector_fit_ids=[{'fit_id': ewar['fit_id'], 'range_km': web_opt_km / 2}])
            v_in = await call('get_stats', fit_id=vic['fit_id'])
            assert v_in['navigation']['max_velocity_ms'] == v_web['navigation']['max_velocity_ms'], \
                'inside optimal must equal zero-range strength'
            await call('set_projected', fit_id=vic['fit_id'],
                       projector_fit_ids=[{'fit_id': ewar['fit_id'], 'range_km': web_opt_km * 8}])
            v_out = await call('get_stats', fit_id=vic['fit_id'])
            assert v_out['navigation']['max_velocity_ms'] == v_base['navigation']['max_velocity_ms'], \
                'far beyond falloff must be no effect'
            g_ew = await call('graph', fit_id=ewar['fit_id'], kind='ewar_vs_range',
                              item='Stasis Webifier I')
            assert g_ew['summary']['optimal_km'] == web_opt_km, g_ew['summary']
            assert g_ew['points'][0][1] == 100.0 and g_ew['points'][-1][1] < 5, g_ew['points'][-3:]
            await call('set_projected', fit_id=vic['fit_id'], projector_fit_ids=[])
            v_clear = await call('get_stats', fit_id=vic['fit_id'])
            assert v_clear['navigation']['max_velocity_ms'] == v_base['navigation']['max_velocity_ms']

            # applied_dps: application collapses against a small fast target and
            # recovers against a big slow one; missiles and turrets both modeled
            ad_frig = await call('applied_dps', fit_id=fid, distance_km=1.5,
                                 target={'sig_m': 35, 'speed_ms': 700})
            ad_bs = await call('applied_dps', fit_id=fid, distance_km=1.5,
                               target={'sig_m': 400, 'speed_ms': 100})
            # perfect turret application runs ~1.015x paper (wrecking-shot
            # expectation, pyfa's own model) — allow it, catch anything larger
            assert ad_frig['dps_applied'] < ad_bs['dps_applied'] <= ad_bs['dps_raw'] * 1.02, \
                (ad_frig, ad_bs)
            assert 'turrets' in ad_bs['by_source'], ad_bs
            mis = await call('import_fit', eft='[Caracal, rlml]\n'
                             'Rapid Light Missile Launcher II, Caldari Navy Scourge Light Missile\n'
                             'Rapid Light Missile Launcher II, Caldari Navy Scourge Light Missile')
            am_frig = await call('applied_dps', fit_id=mis['fit_id'], distance_km=10,
                                 target={'sig_m': 35, 'speed_ms': 700})
            am_bs = await call('applied_dps', fit_id=mis['fit_id'], distance_km=10,
                               target={'sig_m': 400, 'speed_ms': 100})
            assert 'missiles' in am_frig['by_source'], am_frig
            assert am_frig['application_pct'] < am_bs['application_pct'], (am_frig, am_bs)
            await call('delete_fit', fit_id=mis['fit_id'])

            # fighters: squadron dps lands in the panel, tube overflow is named
            than = await call('create_fit', ship='Thanatos')
            await call('edit_fit', fit_id=than['fit_id'], ops=[
                {'op': 'add', 'item': 'Firbolg I'}])
            f_stats = await call('get_stats', fit_id=than['fit_id'])
            assert f_stats['offense'].get('dps_fighters', 0) > 300, f_stats['offense']
            for _ in range(6):
                await call('edit_fit', fit_id=than['fit_id'], ops=[
                    {'op': 'add', 'item': 'Firbolg I'}])
            f_val = await call('validate_fit', fit_id=than['fit_id'])
            assert any('fighter tubes' in p for p in f_val['problems']), f_val

            # implants and drugs apply and remove cleanly
            imp_fit = await call('import_fit', eft='[Rifter, pods]')
            i_base = await call('get_stats', fit_id=imp_fit['fit_id'])
            await call('edit_fit', fit_id=imp_fit['fit_id'], ops=[
                {'op': 'add', 'item': "Zainou 'Gnome' Shield Management SM-703"},
                {'op': 'add', 'item': 'Quafe Zero Classic'}])
            i_on = await call('get_stats', fit_id=imp_fit['fit_id'])
            assert abs(i_on['defense']['hp']['shield'] / i_base['defense']['hp']['shield'] - 1.03) < 0.005
            assert abs(i_on['navigation']['max_velocity_ms'] / i_base['navigation']['max_velocity_ms'] - 1.05) < 0.005
            await call('edit_fit', fit_id=imp_fit['fit_id'], ops=[
                {'op': 'remove', 'item': 'Quafe Zero Classic'}])
            i_off = await call('get_stats', fit_id=imp_fit['fit_id'])
            assert i_off['navigation']['max_velocity_ms'] == i_base['navigation']['max_velocity_ms']

            # spool weapons get a named note; wrong-size charges are rejected
            ved = await call('create_fit', ship='Vedmak')
            await call('edit_fit', fit_id=ved['fit_id'], ops=[
                {'op': 'add', 'item': 'Heavy Entropic Disintegrator II', 'charge': 'Occult M'}])
            v_stats = await call('get_stats', fit_id=ved['fit_id'])
            assert any('spool' in n for n in v_stats.get('notes', [])), 'spool note missing'
            # spool is modeled: default full, floor + ramp named, param moves dps,
            # dps_vs_time is the monotone ramp ending at the full-spool number
            sp = v_stats['offense']['spool']
            assert sp['level'] == 1.0 and sp['dps_zero_spool'] < v_stats['offense']['dps'], sp
            assert sp['time_to_full_s'] > 0, sp
            v0 = await call('get_stats', fit_id=ved['fit_id'], spool=0)
            assert v0['offense']['dps'] == sp['dps_zero_spool'], (v0['offense'], sp)
            gt = await call('graph', fit_id=ved['fit_id'], kind='dps_vs_time')
            ys = [y for _, y in gt['points']]
            assert ys == sorted(ys) and ys[0] < ys[-1], gt['points']
            assert gt['summary']['dps_full_spool'] == v_stats['offense']['dps'], gt['summary']
            try:
                await call('graph', fit_id=fid, kind='dps_vs_time')
                raise AssertionError('dps_vs_time on a non-spool fit must be rejected')
            except RuntimeError as e:
                assert 'no spool-up weapons' in str(e), e
            try:
                await call('edit_fit', fit_id=ved['fit_id'], ops=[
                    {'op': 'charge', 'item': 'Heavy Entropic Disintegrator II', 'charge': 'Occult L'}])
                raise AssertionError('L charge in an M gun must be rejected')
            except RuntimeError as e:
                assert 'does not fit' in str(e), e

            # rack overflow is flagged (eval run 3: a 4-mid fit once validated clean)
            oni = await call('import_fit', eft='[Omen Navy Issue, slots]\n'
                             '10MN Afterburner II\nWarp Scrambler II\n'
                             'X5 Enduring Stasis Webifier\nCap Recharger II')
            assert oni['slots']['med'] == [4, 3], oni['slots']  # summary shows the rack
            oni_val = await call('validate_fit', fit_id=oni['fit_id'])
            assert any('med slots over by 1' in p for p in oni_val['problems']), oni_val
            await call('delete_fit', fit_id=oni['fit_id'])

            # T3D mode swap moves signature
            conf = await call('create_fit', ship='Confessor')
            await call('edit_fit', fit_id=conf['fit_id'], ops=[
                {'op': 'mode', 'item': 'Confessor Defense Mode'}])
            m_def = await call('get_stats', fit_id=conf['fit_id'])
            await call('edit_fit', fit_id=conf['fit_id'], ops=[
                {'op': 'mode', 'item': 'Confessor Sharpshooter Mode'}])
            m_sharp = await call('get_stats', fit_id=conf['fit_id'])
            assert m_def['navigation']['signature_m'] < m_sharp['navigation']['signature_m'], \
                'defense mode must shrink sig vs sharpshooter'

            # graphs: bounded, with summaries
            g = await call('graph', fit_id=fid, kind='dps_vs_range')
            assert len(g['points']) <= 32 and g['summary']['peak_dps'] > 0, g['summary']
            g2 = await call('graph', fit_id=fid, kind='cap_vs_time')
            assert len(g2['points']) <= 32 and g2['summary']['capacity_gj'] > 0
            assert not g2['summary']['stable'] and g2['points'][-1][1] == 0, g2['summary']
            g3 = await call('graph', fit_id=fid, kind='dps_vs_target_speed',
                            target={'sig_m': 40}, distance_km=2)
            assert g3['points'][0][1] >= g3['points'][-1][1], 'dps must not rise with target speed'

            # full-fit skill requirements: ends by default, closure on full=true
            req = await call('required_skills', fit_id=fid)
            ends = req['skills']
            assert 'Small Autocannon Specialization' in ends, ends  # the AC II leaf
            assert 'Gunnery' not in ends, f'implied prereq not pruned: {ends}'
            assert req.get('implied_prereqs', 0) > 0, req
            req_full = await call('required_skills', fit_id=fid, full=True)
            closure = req_full['skills']
            assert closure.get('Small Projectile Turret') == 5, closure
            assert 'Gunnery' in closure and 'Minmatar Frigate' in closure, closure
            assert len(closure) > len(ends), (len(closure), len(ends))

            # mutated (abyssal) modules: pyfa's [N] dialect, absolute rolled
            # values, eos clamping, and an identical export->reimport round trip
            plain_eft = ('[Rifter, plain]\nGyrostabilizer II\n\n'
                         '150mm Light AutoCannon II, Republic Fleet EMP S')
            muta_eft = ('[Rifter, muta]\nGyrostabilizer II [1]\n\n'
                        '150mm Light AutoCannon II, Republic Fleet EMP S\n\n'
                        '[1] Gyrostabilizer II\n'
                        '  Decayed Gyrostabilizer Mutaplasmid\n'
                        '  damageMultiplier 1.1088\n')  # max roll: 1.008 x 1.1
            mp = await call('import_fit', eft=plain_eft)
            mm = await call('import_fit', eft=muta_eft)
            p_dps = (await call('get_stats', fit_id=mp['fit_id']))['offense']['dps']
            m_dps = (await call('get_stats', fit_id=mm['fit_id']))['offense']['dps']
            assert m_dps > p_dps, (m_dps, p_dps)
            mx = await call('export_fit', fit_id=mm['fit_id'])
            assert '[1] Gyrostabilizer II' in mx and 'Mutaplasmid' in mx, mx
            mr = await call('import_fit', eft=mx)
            r_dps = (await call('get_stats', fit_id=mr['fit_id']))['offense']['dps']
            assert r_dps == m_dps, f'round trip drifted: {r_dps} != {m_dps}'
            mc = await call('import_fit',
                            eft=muta_eft.replace('damageMultiplier 1.1088',
                                                 'damageMultiplier 2.0'))
            c_dps = (await call('get_stats', fit_id=mc['fit_id']))['offense']['dps']
            assert c_dps == m_dps, f'absurd roll must clamp to max: {c_dps} != {m_dps}'
            try:
                await call('import_fit', eft='[Rifter, bare]\nAbyssal Gyrostabilizer')
                raise AssertionError('bare abyssal item name must be rejected')
            except RuntimeError as e:
                assert 'mutation block' in str(e), e
            # drones mutate through the same dialect (base dmgMult is 1.92 here
            # — roll above it or the test proves nothing)
            md = await call('import_fit', eft=(
                '[Tristan, mutdrone]\nDrone Damage Amplifier II\n\n'
                'Hobgoblin II x5 [1]\n\n'
                '[1] Hobgoblin II\n'
                '  Exigent Light Drone Firepower Mutaplasmid\n'
                '  damageMultiplier 2.3\n'))
            d_dps = (await call('get_stats', fit_id=md['fit_id']))['offense']['dps_drones']
            dx = await call('export_fit', fit_id=md['fit_id'])
            dr = await call('import_fit', eft=dx)
            dr_dps = (await call('get_stats', fit_id=dr['fit_id']))['offense']['dps_drones']
            assert dr_dps == d_dps, f'drone round trip drifted: {dr_dps} != {d_dps}'
            for f in (mp, mm, mr, mc, md, dr):
                await call('delete_fit', fit_id=f['fit_id'])

            # module_attrs: per-module modified values, heat-aware (the class
            # of question: "web range vs point range, both overheated")
            web = await call('import_fit', eft='[Vigilant, webtest]\n'
                             'Federation Navy Stasis Webifier\nWarp Disruptor II')
            ma = await call('module_attrs', fit_id=web['fit_id'],
                            item='Federation Navy Stasis Webifier', attrs=['maxRange'])
            cold = ma['modules'][0]['attrs']['maxRange']
            await call('edit_fit', fit_id=web['fit_id'], ops=[
                {'op': 'state', 'item': 'Federation Navy Stasis Webifier', 'state': 'overheated'},
                {'op': 'state', 'item': 'Warp Disruptor II', 'state': 'overheated'}])
            hot_web = await call('module_attrs', fit_id=web['fit_id'],
                                 item='Federation Navy Stasis Webifier', attrs=['maxRange'])
            hot_pt = await call('module_attrs', fit_id=web['fit_id'],
                                item='Warp Disruptor II', attrs=['maxRange'])
            assert hot_web['modules'][0]['state'] == 'overheated', hot_web
            assert abs(hot_web['modules'][0]['attrs']['maxRange'] / cold - 1.3) < 0.01, \
                (cold, hot_web)  # web overload: +30% range
            assert abs(hot_pt['modules'][0]['attrs']['maxRange'] / 24000 - 1.2) < 0.01, \
                hot_pt  # point overload: +20% range
            try:
                await call('module_attrs', fit_id=web['fit_id'],
                           item='Warp Disruptor II', attrs=['maxRnge'])
                raise AssertionError('typo attribute name must be rejected')
            except RuntimeError as e:
                assert 'unknown attribute' in str(e), e
            await call('delete_fit', fit_id=web['fit_id'])

            # sweep: candidate enumeration in one call, fit restored afterwards
            # (the class of question: "meta plate to free fitting for a better rep?")
            sw_fit = await call('import_fit', eft='[Rifter, sweeptest]\n'
                                '200mm Steel Plates II\nGyrostabilizer II\n\n'
                                '5MN Y-T8 Compact Microwarpdrive\n\n'
                                '150mm Light AutoCannon II, Republic Fleet EMP S\n'
                                '150mm Light AutoCannon II, Republic Fleet EMP S\n'
                                '150mm Light AutoCannon II, Republic Fleet EMP S')
            before = await call('get_stats', fit_id=sw_fit['fit_id'])
            sw = await call('sweep', fit_id=sw_fit['fit_id'], item='Gyrostabilizer II',
                            candidates=['Counterbalanced Compact Gyrostabilizer',
                                        'Gyrostabilizer I', 'Hobgoblin II'],
                            metrics=['offense.dps'])
            rows = {r['candidate']: r for r in sw['rows']}
            base_dps = rows['Gyrostabilizer II (fitted)']['offense.dps']
            assert base_dps > rows['Counterbalanced Compact Gyrostabilizer']['offense.dps'] \
                > 0, rows
            assert rows['Gyrostabilizer I']['offense.dps'] < base_dps, rows
            assert 'error' in rows['Hobgoblin II'], 'a drone is not a module candidate'
            assert 'cpu_free' in rows['Gyrostabilizer I'], rows
            after = await call('get_stats', fit_id=sw_fit['fit_id'])
            assert after['offense']['dps'] == before['offense']['dps'], \
                'sweep must restore the fit'
            await call('delete_fit', fit_id=sw_fit['fit_id'])

            # rack layout: [Empty ... slot] placeholders survive round-trip in
            # position (heat-conscious layouts), and edit add fills the gap
            lay = await call('import_fit', eft='[Rifter, layout]\n'
                             '150mm Light AutoCannon II\n[Empty High slot]\n'
                             '150mm Light AutoCannon II')
            lx = await call('export_fit', fit_id=lay['fit_id'])
            lay_lines = [l for l in lx.splitlines() if 'AutoCannon' in l or 'Empty High' in l]
            assert lay_lines == ['150mm Light AutoCannon II', '[Empty High slot]',
                                 '150mm Light AutoCannon II'], lay_lines
            await call('edit_fit', fit_id=lay['fit_id'], ops=[
                {'op': 'add', 'item': '150mm Light AutoCannon II'}])
            lx2 = await call('export_fit', fit_id=lay['fit_id'])
            assert '[Empty High slot]' not in lx2, 'edit add should fill the gap'
            # keep_slot remove leaves the gap in position (in-game semantics)
            await call('edit_fit', fit_id=lay['fit_id'], ops=[
                {'op': 'remove', 'item': '150mm Light AutoCannon II', 'keep_slot': True}])
            lx3 = await call('export_fit', fit_id=lay['fit_id'])
            lay_lines3 = [l for l in lx3.splitlines() if 'AutoCannon' in l or 'Empty High' in l]
            assert lay_lines3 == ['[Empty High slot]', '150mm Light AutoCannon II',
                                  '150mm Light AutoCannon II'], lay_lines3
            # sweep replaces in position: layout untouched afterwards
            sw_lay = await call('sweep', fit_id=lay['fit_id'],
                                item='150mm Light AutoCannon II',
                                candidates=['200mm AutoCannon II'],
                                metrics=['offense.dps'])
            assert len(sw_lay['rows']) == 2, sw_lay
            lx4 = await call('export_fit', fit_id=lay['fit_id'])
            assert lx4 == lx3, 'sweep must not disturb rack layout'
            await call('delete_fit', fit_id=lay['fit_id'])

            # siege-class states: bastion's preMul resist chain multiplies the
            # hardener's postPercent chain at full strength (engine-verified
            # 0.675 x 0.700 = 0.4725); hull restriction rejects bastion
            # off-marauder; siege multiplies dps and pins speed to 0; triage
            # boosts remote rep amount and cycle
            gol = await call('import_fit', eft='[Golem, bast]\n'
                             'Multispectrum Shield Hardener II\n\nBastion Module I')
            g_stats = await call('get_stats', fit_id=gol['fit_id'])
            em = g_stats['defense']['resists']['shield']['em']
            assert abs(em - 0.5275) < 0.002, f'bastion+hardener em resist {em}'
            assert any('Bastion' in n for n in g_stats.get('notes', [])), g_stats.get('notes')
            gv = await call('validate_fit', fit_id=gol['fit_id'])
            assert gv['legal'], gv
            bad = await call('import_fit', eft='[Rifter, bad]\nBastion Module I')
            bv = await call('validate_fit', fit_id=bad['fit_id'])
            assert any('cannot be fitted' in p for p in bv['problems']), bv
            # the same check covers the whole canFitShipType/Group class
            cloak = await call('import_fit', eft='[Rifter, cloak]\nCovert Ops Cloaking Device II')
            cv = await call('validate_fit', fit_id=cloak['fit_id'])
            assert any('cannot be fitted' in p for p in cv['problems']), cv
            await call('delete_fit', fit_id=cloak['fit_id'])
            phx = await call('import_fit', eft='[Phoenix, siege]\n'
                             'XL Torpedo Launcher II, Mjolnir XL Torpedo\nSiege Module II')
            p_stats = await call('get_stats', fit_id=phx['fit_id'])
            assert p_stats['offense']['dps'] > 1500, p_stats['offense']
            assert p_stats['navigation']['max_velocity_ms'] == 0, p_stats['navigation']
            mino = await call('import_fit', eft='[Minokawa, tri]\n'
                              'Capital Remote Shield Booster II\nTriage Module II')
            tri = await call('module_attrs', fit_id=mino['fit_id'],
                             item='Capital Remote Shield Booster II',
                             attrs=['shieldBonus', 'duration'])
            assert tri['modules'][0]['attrs']['shieldBonus'] > 7000, tri
            assert tri['modules'][0]['attrs']['duration'] == 5000, tri
            for f in (gol, bad, phx, mino):
                await call('delete_fit', fit_id=f['fit_id'])

            # Upwell structures: Citadel branch, standup weapons, service fuel,
            # service rack in summaries, legality in both directions
            ast = await call('import_fit', eft='[Astrahus, home]\n'
                             'Standup Ballistic Control System I\n\n'
                             'Standup Multirole Missile Launcher I, Standup Cruise Missile\n\n'
                             'Standup Cloning Center I')
            assert ast['slots'].get('service') == [1, 3], ast['slots']
            a_stats = await call('get_stats', fit_id=ast['fit_id'])
            assert a_stats['offense']['dps'] > 900, a_stats['offense']
            assert a_stats['defense']['ehp']['total'] > 20_000_000, a_stats['defense']['ehp']
            assert a_stats['navigation']['max_velocity_ms'] == 0, a_stats['navigation']
            svc = a_stats['services']
            assert svc['fuel_blocks_per_hour'] == 10 and svc['fitted'][0]['fuel_to_online'] == 720, svc
            assert a_stats['defense']['incoming_dps_cap']['hull'] == 5000, \
                a_stats['defense'].get('incoming_dps_cap')
            av = await call('validate_fit', fit_id=ast['fit_id'])
            assert av['legal'], av
            await call('edit_fit', fit_id=ast['fit_id'], ops=[
                {'op': 'add', 'item': 'Standup Cloning Center I'},
                {'op': 'add', 'item': 'Standup Reprocessing Facility I'},
                {'op': 'add', 'item': 'Standup Market Hub I'}])
            av2 = await call('validate_fit', fit_id=ast['fit_id'])
            assert any('service slots over by 1' in p for p in av2['problems']), av2
            bad_s = await call('import_fit', eft='[Astrahus, bad]\nGyrostabilizer II')
            bs_val = await call('validate_fit', fit_id=bad_s['fit_id'])
            assert any('cannot be fitted' in p for p in bs_val['problems']), bs_val
            bad_r = await call('import_fit', eft='[Rifter, bad2]\nStandup Cloning Center I')
            br_val = await call('validate_fit', fit_id=bad_r['fit_id'])
            assert any('cannot be fitted' in p for p in br_val['problems']), br_val
            for f in (ast, bad_s, bad_r):
                await call('delete_fit', fit_id=f['fit_id'])

            info = await call('engine_info')
            assert info['engine_build'], info
            assert 'environment effects' not in info['unmodeled'], 'env is modeled now'
            assert 'mutated modules' not in info['unmodeled'], 'mutations are modeled now'
            assert not any('siege' in u for u in info['unmodeled']), 'siege states modeled now'
            await call('delete_fit', fit_id=c['fit_id'])

            print(f"\nengine_build: {info['engine_build']} | all assertions passed")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    asyncio.run(main(ap.parse_args().pyfa))
