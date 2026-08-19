"""Smoke test for the eve-sde MCP server, driven over real stdio.

    python3 test_server.py --sde <dir with eve-sde-*.sqlite>

Asserts the batch runner, the unit corrections (the traps that measured eval
subjects got wrong), and reports response sizes in tokens.
"""
import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


def tokens(obj):
    return len(json.dumps(obj)) // 4


def unwrap(result):
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get('result', sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


def deployed_command(sde):
    """Launch the server exactly the way `.mcp.json` does.

    Launching with `sys.executable` hid a real outage: the test ran under
    layer 2's virtualenv (which has the `mcp` SDK) while `.mcp.json` used a
    bare `python3` (which does not), so the server failed to connect in every
    real session while the test stayed green. Read the command from the
    config so the two can never drift again.
    """
    cfg = os.path.join(os.path.dirname(os.path.dirname(HERE)), '.mcp.json')
    with open(cfg) as fh:
        entry = json.load(fh)['mcpServers']['eve-sde']
    args = [a if a != '.' else sde for a in entry['args']]
    return entry['command'], args


async def main(sde):
    command, args = deployed_command(sde)
    print(f'launching as .mcp.json does: {command} {" ".join(args)}')
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = await s.list_tools()
            schema = [{'name': t.name, 'description': t.description,
                       'inputSchema': t.input_schema} for t in tools.tools]
            print(f'{len(tools.tools)} tools; standing schema ~{tokens(schema)} tokens')

            async def call(_tool, **kw):
                out = unwrap(await s.call_tool(_tool, kw))
                print(f'  {_tool:10} -> ~{tokens(out)} tokens')
                return out

            # batch: four statements, one round, one bad statement isolated
            q = await call('query', sql="""
-- rifter hull
SELECT name, mass FROM types WHERE name = 'Rifter';
-- scram strengths
SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
JOIN dogma_attributes a ON a.attributeID = d.attributeID
WHERE a.name = 'warpScrambleStrength' AND t.name LIKE 'Warp Scrambler%';
-- deliberately broken
SELECT * FROM no_such_table;
""")
            r = q['results']
            assert len(r) == 3, r
            assert r[0]['label'] == 'rifter hull' and r[0]['data'][0][0] == 'Rifter', r[0]
            assert r[1]['rows'] == 2, r[1]
            assert 'error' in r[2] and r[0].get('data'), 'a bad statement must not kill the batch'
            assert q['sde_build'], q
            # the raw-value lint fires on statement 2 (selects `value` by attribute)
            assert any('unitID' in n for n in r[1].get('notes', [])), r[1]

            # unit corrections — the traps measured subjects actually got wrong
            a = await call('attrs', items=['Rifter'],
                           attributes=['shieldEmDamageResonance', 'shieldRechargeRate'])
            at = a['types'][0]['attributes']
            res = at['shieldEmDamageResonance']
            assert res['raw'] == 1.0 and res['value'] == '0.0%', res
            rech = at['shieldRechargeRate']
            assert rech['raw'] == 625000 and rech['value'] == '625.0 s', rech

            # a genuinely inverted, non-obviously-named resistance
            web = await call('attrs', items=['Erebus'], attributes=[2115])
            v = list(web['types'][0]['attributes'].values())[0]
            assert v['value'] == '80.0%', v   # titans resist webs 80%, raw 0.2

            # unknown type suggests neighbours instead of failing blind
            bad = await call('attrs', items=['Riftr'])
            assert bad['types'][0].get('did_you_mean'), bad

            info = await call('sde_info')
            assert '108' in info['unit_corrections'], info
            print(f"\nsde_build: {info['sde_build']} | parts: {','.join(info['parts'])}"
                  f" | all assertions passed")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sde', default=os.environ.get('EVE_SDE_DIR', '.'))
    asyncio.run(main(ap.parse_args().sde))
