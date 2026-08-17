"""EVE fitting engine MCP server — pyfa's eos behind ~10 terse tools.

    python3 server.py --pyfa /path/to/pyfa-checkout      # stdio transport

Design rules (docs/roadmap-fitting-mcp.md, token budget):
- Fits are stateful server-side objects addressed by short IDs; EFT text is
  the only import/export payload. The conversation never re-sends a fit.
- Tool descriptions are one line each — the teaching lives in the
  fitting-knowledge skill, never here, because schemas are paid every turn.
- Outputs are compact dicts with unit-suffixed keys; empty sections omitted.
- Anything unmodeled is named, never silently ignored.
"""
import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'engine'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'spike'))

from mcp.server.mcpserver import MCPServer

from headless import bootstrap  # noqa: E402

_parser = argparse.ArgumentParser()
_parser.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'),
                     required='PYFA_PATH' not in os.environ)
ARGS = _parser.parse_args()
bootstrap(ARGS.pyfa)

# Saveddata must be a file, not :memory:: MCP tools run on worker threads and
# sqlite :memory: is per-connection, so each thread would see an empty schema.
import tempfile  # noqa: E402
import eos.config as _eos_config  # noqa: E402
_eos_config.saveddata_connectionstring = \
    'sqlite:///' + os.path.join(tempfile.mkdtemp(prefix='eve-fitting-mcp-'), 'saveddata.db')

import eos.db  # noqa: E402,F401 — must precede eos.saveddata imports
eos.db.saveddata_meta.create_all()  # what pyfa.py does at startup
from eos.const import FittingModuleState  # noqa: E402
import eft as eftlib  # noqa: E402
from panel import stat_panel  # noqa: E402

mcp = MCPServer('eve-fitting')

FITS = {}
_counter = 0

STATES = {'offline': FittingModuleState.OFFLINE, 'online': FittingModuleState.ONLINE,
          'active': FittingModuleState.ACTIVE, 'overheated': FittingModuleState.OVERHEATED}


def _new_id():
    global _counter
    _counter += 1
    return f'f{_counter}'


def _fit(fit_id):
    if fit_id not in FITS:
        raise ValueError(f'unknown fit_id {fit_id!r}; known: {sorted(FITS)}')
    return FITS[fit_id]


def _recalc(fit):
    fit.factorReload = False
    fit.clear()
    fit.calculateModifiedAttributes()


def _problems(fit):
    """Named in-game legality violations. Empty list = legal."""
    from eos.const import FittingHardpoint, FittingSlot
    _recalc(fit)
    out = []
    attr = fit.ship.getModifiedItemAttr
    for used, total, name in (
            (fit.cpuUsed, attr('cpuOutput'), 'cpu'),
            (fit.pgUsed, attr('powerOutput'), 'powergrid'),
            (fit.calibrationUsed, attr('upgradeCapacity') or 0, 'calibration')):
        if used > (total or 0):
            out.append(f'{name} over: {used:g} / {total or 0:g}')
    for slot, label in ((FittingSlot.LOW, 'low'), (FittingSlot.MED, 'med'),
                        (FittingSlot.HIGH, 'high'), (FittingSlot.RIG, 'rig'),
                        (FittingSlot.SUBSYSTEM, 'subsystem')):
        free = fit.getSlotsFree(slot)
        if free < 0:
            out.append(f'{label} slots over by {-free}')
    for hp, label in ((FittingHardpoint.TURRET, 'turret'), (FittingHardpoint.MISSILE, 'launcher')):
        free = fit.getHardpointsFree(hp)
        if free < 0:
            out.append(f'{label} hardpoints over by {-free}')
    bw = sum(d.getModifiedItemAttr('droneBandwidthUsed') * d.amountActive for d in fit.drones)
    if bw > (attr('droneBandwidth') or 0):
        out.append(f'drone bandwidth over: {bw:g} / {attr("droneBandwidth") or 0:g}')
    vol = sum(d.item.attributes['volume'].value * d.amount for d in fit.drones)
    if vol > (attr('droneCapacity') or 0):
        out.append(f'drone bay over: {vol:g} / {attr("droneCapacity") or 0:g} m3')
    return out


def _summary(fit_id):
    fit = _fit(fit_id)
    _recalc(fit)
    attr = fit.ship.getModifiedItemAttr
    return {
        'fit_id': fit_id,
        'ship': fit.ship.item.typeName,
        'name': fit.name,
        'cpu': [round(fit.cpuUsed, 2), round(attr('cpuOutput'), 2)],
        'powergrid': [round(fit.pgUsed, 2), round(attr('powerOutput'), 2)],
        'problems': _problems(fit),
    }


@mcp.tool()
def import_fit(eft: str) -> dict:
    """Import an EFT-format fit; returns fit_id + fitting summary. Multi-fit text imports all."""
    specs = eftlib.parse_eft(eft)
    out = []
    for spec in specs:
        fit_id = _new_id()
        FITS[fit_id] = eftlib.build_fit(spec)
        out.append(_summary(fit_id))
    return out[0] if len(out) == 1 else {'fits': out}


@mcp.tool()
def create_fit(ship: str, name: str = 'unnamed') -> dict:
    """Create an empty fit for a ship type; returns fit_id + fitting summary."""
    spec = eftlib.FitSpec(ship, name)
    fit_id = _new_id()
    FITS[fit_id] = eftlib.build_fit(spec)
    return _summary(fit_id)


@mcp.tool()
def clone_fit(fit_id: str, name: str = '') -> dict:
    """Copy an existing fit; returns the new fit_id."""
    fit = _fit(fit_id)
    spec = eftlib.parse_eft(eftlib.render_eft(fit))[0]
    if name:
        spec.name = name
    new_id = _new_id()
    FITS[new_id] = eftlib.build_fit(spec)
    return _summary(new_id)


@mcp.tool()
def delete_fit(fit_id: str) -> dict:
    """Discard a fit."""
    _fit(fit_id)
    del FITS[fit_id]
    return {'deleted': fit_id}


@mcp.tool()
def export_fit(fit_id: str) -> str:
    """Export a fit as EFT text (game-client / zkillboard / pyfa interop)."""
    return eftlib.render_eft(_fit(fit_id))


@mcp.tool()
def edit_fit(fit_id: str, ops: list) -> dict:
    """Apply ops to a fit. Each op: {op:'add'|'remove'|'charge'|'state', item:name, charge?:name, state?:'offline'|'online'|'active'|'overheated', quantity?:int(drones)}. 'charge'/'state' apply to every matching module. Returns summary + problems."""
    from eos.saveddata.drone import Drone
    from eos.saveddata.module import Module
    fit = _fit(fit_id)
    for op in ops:
        kind = op.get('op')
        item_name = op.get('item', '')
        if kind == 'add':
            item = eftlib._lookup(item_name)
            if item is None:
                raise ValueError(f'unknown item {item_name!r}')
            if item.category.name == 'Drone':
                qty = int(op.get('quantity', 1))
                drone = Drone(item)
                drone.amount = qty
                drone.amountActive = qty
                fit.drones.append(drone)
                drone.owner = fit
            else:
                mod = Module(item)
                if op.get('charge'):
                    charge = eftlib._lookup(op['charge'])
                    if charge is None:
                        raise ValueError(f'unknown charge {op["charge"]!r}')
                    mod.charge = charge
                if mod.isValidState(FittingModuleState.ACTIVE):
                    mod.state = FittingModuleState.ACTIVE
                fit.modules.append(mod)
                mod.owner = fit
        elif kind == 'remove':
            for drone in list(fit.drones):
                if drone.item.typeName == item_name:
                    fit.drones.remove(drone)
                    break
            else:
                for mod in list(fit.modules):
                    if not mod.isEmpty and mod.item.typeName == item_name:
                        fit.modules.remove(mod)
                        break
                else:
                    raise ValueError(f'{item_name!r} not fitted')
        elif kind == 'charge':
            charge = eftlib._lookup(op.get('charge', ''))
            if charge is None:
                raise ValueError(f'unknown charge {op.get("charge")!r}')
            hits = 0
            for mod in fit.modules:
                if not mod.isEmpty and mod.item.typeName == item_name:
                    mod.charge = charge
                    hits += 1
            if not hits:
                raise ValueError(f'{item_name!r} not fitted')
        elif kind == 'state':
            state = STATES.get(op.get('state', ''))
            if state is None:
                raise ValueError(f'bad state {op.get("state")!r}; use {sorted(STATES)}')
            hits = 0
            for mod in fit.modules:
                if not mod.isEmpty and mod.item.typeName == item_name:
                    mod.state = state if mod.isValidState(state) else mod.state
                    hits += 1
            if not hits:
                raise ValueError(f'{item_name!r} not fitted')
        else:
            raise ValueError(f'bad op {kind!r}; use add/remove/charge/state')
    return _summary(fit_id)


_alpha_char = None


@mcp.tool()
def set_skills(fit_id: str, preset: str) -> dict:
    """Set the pilot: 'all-5' or 'alpha' (alpha-clone skill set)."""
    # The alpha pilot must be its own Character: getAll5() returns a shared
    # saveddata object, and flipping alphaCloneID on it silently turns every
    # fit alpha (found by the eval harness, 2026-08-17).
    from eos.saveddata.character import Character
    global _alpha_char
    fit = _fit(fit_id)
    if preset == 'all-5':
        char = Character.getAll5()
        char.alphaCloneID = None
        fit.character = char
    elif preset == 'alpha':
        if _alpha_char is None:
            _alpha_char = Character('MCP Alpha', 5)   # in-memory only, never saved
            _alpha_char.alphaCloneID = 1
        fit.character = _alpha_char
    else:
        raise ValueError("preset must be 'all-5' or 'alpha'")
    return {'fit_id': fit_id, 'skills': preset}


@mcp.tool()
def get_stats(fit_id: str, profile: dict = None) -> dict:
    """Full stat panel. profile: optional damage weights {em,thermal,kinetic,explosive}, default uniform. All ship values include skills/modules; resists as fractions."""
    from eos.saveddata.damagePattern import DamagePattern
    fit = _fit(fit_id)
    p = profile or {}
    fit.damagePattern = DamagePattern(
        emAmount=p.get('em', 25), thermalAmount=p.get('thermal', 25),
        kineticAmount=p.get('kinetic', 25), explosiveAmount=p.get('explosive', 25))
    panel = stat_panel(fit)
    panel['problems'] = _problems(fit)
    return panel


@mcp.tool()
def compare_fits(fit_id_a: str, fit_id_b: str) -> dict:
    """Stat panels diffed: only figures differing >0.1%, as {stat: [a, b]}."""
    diffs = {}
    panels = [get_stats(f) for f in (fit_id_a, fit_id_b)]

    def walk(a, b, prefix):
        keys = set(a) | set(b)
        for k in sorted(keys):
            path = f'{prefix}.{k}' if prefix else str(k)
            va, vb = a.get(k), b.get(k)
            if isinstance(va, dict) and isinstance(vb, dict):
                walk(va, vb, path)
            elif isinstance(va, (int, float)) and isinstance(vb, (int, float)) \
                    and not isinstance(va, bool) and not isinstance(vb, bool):
                if abs(va - vb) / max(abs(va), abs(vb), 1e-9) > 0.001:
                    diffs[path] = [va, vb]
            elif va != vb:
                diffs[path] = [va, vb]
    walk(panels[0], panels[1], '')
    return {'a': fit_id_a, 'b': fit_id_b, 'diffs': diffs}


@mcp.tool()
def validate_fit(fit_id: str) -> dict:
    """In-game legality: fitting resources, slots, hardpoints, drone limits."""
    problems = _problems(_fit(fit_id))
    return {'fit_id': fit_id, 'legal': not problems, 'problems': problems}


@mcp.tool()
def engine_info() -> dict:
    """Engine + data build. Compare engine_build to the SDE skill's build; any skew means numbers may disagree with layer 1."""
    meta = dict(sqlite3.connect(os.path.join(ARGS.pyfa, 'eve.db'))
                .execute('SELECT field_name, field_value FROM metadata').fetchall())
    return {
        'engine': 'pyfa-eos (headless)',
        'engine_build': meta.get('client_build'),
        'unmodeled': ['command bursts', 'projected fits', 'environment effects',
                      'mutated modules', 'fighters', 'T3D modes', 'siege states',
                      'spool-up', 'structures'],
        'skills_presets': ['all-5', 'alpha'],
    }


if __name__ == '__main__':
    mcp.run()
