"""Dependency-free MCP stdio server.

Layer 1 is meant to be droppable: a SQLite file, a skill, and a `python3`.
The `mcp` SDK lives in layer 2's virtualenv, so importing it here would make
the SDE server unusable for anyone who installs the SDE skill alone — which
is exactly what happened: `.mcp.json` launched this server with a bare
`python3`, the import failed, and the server silently never connected while
`test_server.py` kept passing because it launches via `sys.executable`.

So: no third-party imports. This speaks just enough of the protocol —
initialize, tools/list, tools/call, ping — over line-delimited JSON-RPC.
"""
import inspect
import json
import sys

PROTOCOL_VERSION = '2024-11-05'

_JSON_TYPES = {
    str: 'string', int: 'integer', float: 'number',
    bool: 'boolean', list: 'array', dict: 'object',
}


def _entry(annotation):
    """One property schema. `list[str]` becomes a typed array.

    The element type is worth carrying: a bare `array` leaves the caller
    guessing, and for `query(statements)` the whole point of the parameter is
    that it holds MANY items — the schema is what says so.
    """
    origin = getattr(annotation, '__origin__', None)
    if origin is list:
        args = getattr(annotation, '__args__', ())
        item = _JSON_TYPES.get(args[0]) if args else None
        return {'type': 'array', 'items': {'type': item}} if item else {'type': 'array'}
    return {'type': _JSON_TYPES.get(annotation, 'string')}


def _schema(fn):
    """Derive an inputSchema from the function signature."""
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        entry = _entry(p.annotation)
        if p.default is inspect.Parameter.empty:
            required.append(name)
        elif p.default is not None:
            entry['default'] = p.default
        props[name] = entry
    schema = {'type': 'object', 'properties': props}
    if required:
        schema['required'] = required
    return schema


class MCPServer:
    def __init__(self, name, version='1.0.0'):
        self.name = name
        self.version = version
        self._tools = {}

    def tool(self, name=None, description=None):
        def deco(fn):
            key = name or fn.__name__
            self._tools[key] = {
                'fn': fn,
                'spec': {
                    'name': key,
                    'description': description or (inspect.getdoc(fn) or ''),
                    'inputSchema': _schema(fn),
                },
            }
            return fn
        return deco

    # --- protocol -------------------------------------------------------
    def _dispatch(self, method, params):
        if method == 'initialize':
            return {
                'protocolVersion': PROTOCOL_VERSION,
                'capabilities': {'tools': {}},
                'serverInfo': {'name': self.name, 'version': self.version},
            }
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return {'tools': [t['spec'] for t in self._tools.values()]}
        if method == 'tools/call':
            tool = self._tools.get(params.get('name'))
            if tool is None:
                raise LookupError(f"unknown tool {params.get('name')!r}")
            result = tool['fn'](**(params.get('arguments') or {}))
            text = result if isinstance(result, str) else json.dumps(result, default=str)
            return {'content': [{'type': 'text', 'text': text}], 'isError': False}
        raise NotImplementedError(method)

    def run(self, stdin=None, stdout=None):
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue                      # not ours; a framing error is not fatal
            mid = msg.get('id')
            if mid is None:
                continue                      # notification: acknowledged by silence
            try:
                reply = {'jsonrpc': '2.0', 'id': mid,
                         'result': self._dispatch(msg.get('method'), msg.get('params') or {})}
            except NotImplementedError as exc:
                reply = {'jsonrpc': '2.0', 'id': mid,
                         'error': {'code': -32601, 'message': f'method not found: {exc}'}}
            except Exception as exc:          # tool errors travel as results, not transport errors
                reply = {'jsonrpc': '2.0', 'id': mid, 'result': {
                    'content': [{'type': 'text', 'text': f'{type(exc).__name__}: {exc}'}],
                    'isError': True}}
            stdout.write(json.dumps(reply) + '\n')
            stdout.flush()
