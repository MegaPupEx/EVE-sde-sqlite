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

            # alpha skills weaken the fit
            await call('set_skills', fit_id=fid, preset='alpha')
            s3 = await call('get_stats', fit_id=fid)
            assert s3['offense']['dps'] < s2['offense']['dps'], (s3['offense'], s2['offense'])
            await call('set_skills', fit_id=fid, preset='all-5')

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

            info = await call('engine_info')
            assert info['engine_build'], info
            await call('delete_fit', fit_id=c['fit_id'])

            print(f"\nengine_build: {info['engine_build']} | all assertions passed")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    asyncio.run(main(ap.parse_args().pyfa))
