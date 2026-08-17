"""Drive the eve-fitting MCP server from the command line — one JSON script in,
one JSON result list out. This is how the eval harness (and any session where
the server is not registered as MCP) reaches the engine.

    <eosenv>/bin/python drive.py --pyfa <pyfa-checkout> script.json
    echo '[{"tool":"engine_info","args":{}}]' | <eosenv>/bin/python drive.py --pyfa <pyfa-checkout>

The script is a JSON list of calls, executed in order over one server session:

    [{"tool": "import_fit", "args": {"eft": "[Rifter, x]\\n..."}, "id": "a"},
     {"tool": "get_stats",  "args": {"fit_id": "$a"}}]

An entry's optional "id" labels its result; a later string argument "$label"
is replaced by that result's fit_id. Results print as a JSON list in call
order; a failed call becomes {"error": ...} and execution continues.
"""
import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(HERE), 'mcp', 'server.py')


def unwrap(result):
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get('result', sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


async def run(pyfa, calls):
    params = StdioServerParameters(command=sys.executable, args=[SERVER, '--pyfa', pyfa])
    out, saved = [], {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            for call in calls:
                args = {k: saved[v[1:]] if isinstance(v, str) and v.startswith('$') else v
                        for k, v in call.get('args', {}).items()}
                try:
                    res = unwrap(await s.call_tool(call['tool'], args))
                except Exception as e:  # noqa: BLE001 — report and continue
                    res = {'error': str(e)}
                if call.get('id') and isinstance(res, dict) and 'fit_id' in res:
                    saved[call['id']] = res['fit_id']
                out.append(res)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    ap.add_argument('script', nargs='?', help='JSON call list; stdin if omitted')
    a = ap.parse_args()
    calls = json.load(open(a.script) if a.script else sys.stdin)
    print(json.dumps(asyncio.run(run(a.pyfa, calls)), indent=1))
