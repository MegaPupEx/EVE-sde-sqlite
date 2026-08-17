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

            info = await call('engine_info')
            assert info['engine_build'], info
            assert 'environment effects' not in info['unmodeled'], 'env is modeled now'
            await call('delete_fit', fit_id=c['fit_id'])

            print(f"\nengine_build: {info['engine_build']} | all assertions passed")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    asyncio.run(main(ap.parse_args().pyfa))
