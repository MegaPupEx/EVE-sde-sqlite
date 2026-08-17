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
from eos.const import CalcType, FittingModuleState  # noqa: E402
import eft as eftlib  # noqa: E402
import graph as graphlib  # noqa: E402
from panel import stat_panel  # noqa: E402

graphlib._install_shims(ARGS.pyfa)

mcp = MCPServer('eve-fitting')

# All engine work runs on ONE dedicated thread. The MCP SDK dispatches sync
# tools to arbitrary worker threads, and eos's SQLAlchemy sessions hold sqlite
# objects with thread affinity — a long-lived server eventually lands two
# calls on different threads and dies with "SQLite objects created in a
# thread can only be used in that same thread" (first seen on an import that
# touched the saveddata `overrides` table, 2026-08-17). The smoke test never
# caught it: its client happens to dispatch every call to the same thread.
import concurrent.futures  # noqa: E402
import functools  # noqa: E402
import threading  # noqa: E402

_ENGINE_THREAD = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix='eos-engine')


def _engine_thread(fn):
    # Re-entrant: tools call each other (compare_fits -> get_stats), and a
    # submit from the pool's own single thread would deadlock forever.
    @functools.wraps(fn)
    def pinned(*args, **kwargs):
        if threading.current_thread().name.startswith('eos-engine'):
            return fn(*args, **kwargs)
        return _ENGINE_THREAD.submit(fn, *args, **kwargs).result()
    return pinned


FITS = {}
BOOSTS = {}       # fit_id -> [booster fit_id, ...]
PROJECTIONS = {}  # fit_id -> [projector fit_id, ...]
ENVS = {}         # fit_id -> projected env Module
_counter = 0

ENV_GROUPS = ('Effect Beacon', 'MassiveEnvironments', 'Abyssal Hazards',
              'Destructible Effect Beacon')

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


def _recalc(fit, factor_reload=False):
    # Ordering is pyfa's: command bursts BEFORE the local calc (eos consumes
    # commandBonuses as it applies them), projected fits AFTER it (the local
    # calc's clear() would wipe modifications applied earlier).
    fit.factorReload = factor_reload
    fit.clear()
    fit_id = next((k for k, v in FITS.items() if v is fit), None)
    for booster_id in BOOSTS.get(fit_id, []):
        booster = FITS.get(booster_id)
        if booster is None:
            continue
        booster.factorReload = False
        booster.clear()
        booster.calculateModifiedAttributes(targetFit=fit, type=CalcType.COMMAND)
    fit.calculateModifiedAttributes()
    for proj_id, proj_range_m in PROJECTIONS.get(fit_id, []):
        projector = FITS.get(proj_id)
        if projector is None:
            continue
        projector.factorReload = False
        projector.clear()
        if projector.getProjectionInfo(fit.ID) is None:
            from eos.db.saveddata.fit import ProjectedFit
            projector.projectedOnto[fit.ID] = ProjectedFit(projector.ID, projector)
        # None = zero range (calculateRangeFactor returns 1); meters otherwise —
        # falloff-aware strength, 0 beyond optimal + 3x falloff for most ewar
        projector.getProjectionInfo(fit.ID).projectionRange = proj_range_m
        projector.calculateModifiedAttributes(targetFit=fit, type=CalcType.PROJECTED)


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
    # Count rack usage by slot VALUE: eos getSlotsUsed compares `mod.slot is
    # type` (enum identity), and EFT-built modules carry plain ints, so it
    # silently counts zero. Found by eval run 3 — a 4-mid fit validated clean.
    from collections import Counter
    used_by_slot = Counter(int(m.slot) for m in fit.modules
                           if not m.isEmpty and m.slot is not None)
    for slot, label, attr_name in (
            (FittingSlot.LOW, 'low', 'lowSlots'), (FittingSlot.MED, 'med', 'medSlots'),
            (FittingSlot.HIGH, 'high', 'hiSlots'), (FittingSlot.RIG, 'rig', 'rigSlots'),
            (FittingSlot.SUBSYSTEM, 'subsystem', 'maxSubSystems')):
        total = attr(attr_name) or 0
        over = used_by_slot.get(int(slot), 0) - total
        if over > 0:
            out.append(f'{label} slots over by {over:g}')
    for hp, label in ((FittingHardpoint.TURRET, 'turret'), (FittingHardpoint.MISSILE, 'launcher')):
        free = fit.getHardpointsFree(hp)
        if free < 0:
            out.append(f'{label} hardpoints over by {-free}')
    # Hull restrictions (canFitShipType/Group, fitsToShipType, Standup split)
    # and the capital-size rule — a Bastion Module on a Rifter must not
    # validate clean. eos's own checks, module by module.
    from eos.saveddata.citadel import Citadel
    capital_hull = isinstance(fit.ship, Citadel) or (attr('isCapitalSize') or 0) == 1
    for mod in fit.modules:
        if mod.isEmpty:
            continue
        if not fit.canFit(mod.item):
            out.append(f'{mod.item.typeName} cannot be fitted to {fit.ship.item.typeName}')
        elif not capital_hull and mod.isCapitalSize:
            out.append(f'{mod.item.typeName} is capital-sized; {fit.ship.item.typeName} is not')
    bw = sum(d.getModifiedItemAttr('droneBandwidthUsed') * d.amountActive for d in fit.drones)
    if bw > (attr('droneBandwidth') or 0):
        out.append(f'drone bandwidth over: {bw:g} / {attr("droneBandwidth") or 0:g}')
    vol = sum(d.item.attributes['volume'].value * d.amount for d in fit.drones)
    if vol > (attr('droneCapacity') or 0):
        out.append(f'drone bay over: {vol:g} / {attr("droneCapacity") or 0:g} m3')
    if fit.fighters:
        tubes = attr('fighterTubes') or 0
        if len(fit.fighters) > tubes:
            out.append(f'fighter tubes over: {len(fit.fighters)} / {tubes:g}')
        fvol = sum(f.item.attributes['volume'].value * max(f.amount, 0) for f in fit.fighters)
        fbay = attr('fighterCapacity') or 0
        if fvol > fbay:
            out.append(f'fighter bay over: {fvol:g} / {fbay:g} m3')
    return out


def _summary(fit_id):
    from collections import Counter
    from eos.const import FittingHardpoint, FittingSlot
    fit = _fit(fit_id)
    _recalc(fit)
    attr = fit.ship.getModifiedItemAttr
    used = Counter(int(m.slot) for m in fit.modules
                   if not m.isEmpty and m.slot is not None)
    slots = {}
    for slot, label, attr_name in (
            (FittingSlot.HIGH, 'high', 'hiSlots'), (FittingSlot.MED, 'med', 'medSlots'),
            (FittingSlot.LOW, 'low', 'lowSlots'), (FittingSlot.RIG, 'rig', 'rigSlots'),
            (FittingSlot.SUBSYSTEM, 'subsystem', 'maxSubSystems')):
        total = int(attr(attr_name) or 0)
        if total or used.get(int(slot)):
            slots[label] = [used.get(int(slot), 0), total]
    hardpoints = {}
    for hpoint, label, attr_name in (
            (FittingHardpoint.TURRET, 'turret', 'turretSlotsLeft'),
            (FittingHardpoint.MISSILE, 'launcher', 'launcherSlotsLeft')):
        total = int(attr(attr_name) or 0)
        hp_used = total - fit.getHardpointsFree(hpoint)
        if total or hp_used:
            hardpoints[label] = [hp_used, total]
    out = {
        'fit_id': fit_id,
        'ship': fit.ship.item.typeName,
        'name': fit.name,
        'cpu': [round(fit.cpuUsed, 2), round(attr('cpuOutput'), 2)],
        'powergrid': [round(fit.pgUsed, 2), round(attr('powerOutput'), 2)],
        'slots': slots,
        'problems': _problems(fit),
    }
    if hardpoints:
        out['hardpoints'] = hardpoints
    return out


@mcp.tool()
@_engine_thread
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
@_engine_thread
def create_fit(ship: str, name: str = 'unnamed') -> dict:
    """Create an empty fit for a ship type; returns fit_id + fitting summary."""
    spec = eftlib.FitSpec(ship, name)
    fit_id = _new_id()
    FITS[fit_id] = eftlib.build_fit(spec)
    return _summary(fit_id)


@mcp.tool()
@_engine_thread
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
@_engine_thread
def delete_fit(fit_id: str) -> dict:
    """Discard a fit."""
    _fit(fit_id)
    del FITS[fit_id]
    BOOSTS.pop(fit_id, None)
    PROJECTIONS.pop(fit_id, None)
    ENVS.pop(fit_id, None)
    for ids in BOOSTS.values():
        if fit_id in ids:
            ids.remove(fit_id)
    for key in PROJECTIONS:
        PROJECTIONS[key] = [(p, r) for p, r in PROJECTIONS[key] if p != fit_id]
    return {'deleted': fit_id}


@mcp.tool()
@_engine_thread
def export_fit(fit_id: str) -> str:
    """Export a fit as EFT text (game-client / zkillboard / pyfa interop)."""
    return eftlib.render_eft(_fit(fit_id))


@mcp.tool()
@_engine_thread
def edit_fit(fit_id: str, ops: list) -> dict:
    """Apply ops to a fit. Each op: {op:'add'|'remove'|'charge'|'state'|'mode', item:name, charge?:name, state?:'offline'|'online'|'active'|'overheated', quantity?:int(drones), keep_slot?:bool (remove: leave an [Empty] gap in place)}. 'charge'/'state' apply to every matching module; 'add' fills the first gap in the rack; 'mode' sets a tactical-destroyer mode item. Returns summary + problems."""
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
            elif item.category.name == 'Fighter':
                from eos.saveddata.fighter import Fighter
                fighter = Fighter(item)
                if op.get('quantity'):
                    fighter.amount = int(op['quantity'])
                fit.fighters.append(fighter)
                fighter.owner = fit
            elif item.category.name == 'Implant':
                if item.group.name == 'Booster':
                    from eos.saveddata.booster import Booster
                    fit.boosters.append(Booster(item))
                else:
                    from eos.saveddata.implant import Implant
                    fit.implants.append(Implant(item))
            else:
                mod = Module(item)
                if op.get('charge'):
                    charge = eftlib._lookup(op['charge'])
                    if charge is None:
                        raise ValueError(f'unknown charge {op["charge"]!r}')
                    if not mod.isValidCharge(charge):
                        raise ValueError(f'{charge.typeName!r} does not fit {item.typeName!r} '
                                         '(wrong size or charge group)')
                    mod.charge = charge
                if mod.isValidState(FittingModuleState.ACTIVE):
                    mod.state = FittingModuleState.ACTIVE
                fit.modules.append(mod)
                mod.owner = fit
        elif kind == 'remove':
            for kept in (fit.fighters, fit.drones, fit.implants, fit.boosters):
                hit = next((x for x in kept if x.item.typeName == item_name), None)
                if hit is not None:
                    kept.remove(hit)
                    break
            else:
                for mod in list(fit.modules):
                    if not mod.isEmpty and mod.item.typeName == item_name:
                        if op.get('keep_slot'):
                            slot_idx = fit.modules.index(mod)
                            fit.modules.free(slot_idx)
                            # eos's dummy has no owner; calc paths read
                            # module.owner.factorReload even on empties
                            fit.modules[slot_idx].owner = fit
                        else:
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
                    if not mod.isValidCharge(charge):
                        raise ValueError(f'{charge.typeName!r} does not fit {item_name!r} '
                                         '(wrong size or charge group)')
                    mod.charge = charge
                    hits += 1
            if not hits:
                raise ValueError(f'{item_name!r} not fitted')
        elif kind == 'mode':
            from eos.saveddata.mode import Mode
            item = eftlib._lookup(item_name)
            if item is None or item.group.name != 'Ship Modifiers':
                raise ValueError(f'unknown mode {item_name!r}; want e.g. "Confessor Defense Mode"')
            fit.mode = Mode(item)
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
_all0_char = None


@mcp.tool()
@_engine_thread
def set_skills(fit_id: str, preset: str) -> dict:
    """Set the pilot skills: 'all-0' | 'alpha' | 'all-5'. Default on import/create is all-5 (omega assumption)."""
    # The alpha pilot must be its own Character: getAll5() returns a shared
    # saveddata object, and flipping alphaCloneID on it silently turns every
    # fit alpha (found by the eval harness, 2026-08-17).
    from eos.saveddata.character import Character
    global _alpha_char, _all0_char
    fit = _fit(fit_id)
    if preset == 'all-5':
        char = Character.getAll5()
        char.alphaCloneID = None
        fit.character = char
    elif preset == 'all-0':
        if _all0_char is None:
            _all0_char = Character('MCP All 0')   # in-memory; getAll0() would hit saveddata
        fit.character = _all0_char
    elif preset == 'alpha':
        if _alpha_char is None:
            _alpha_char = Character('MCP Alpha', 5)   # in-memory only, never saved
            _alpha_char.alphaCloneID = 1
        fit.character = _alpha_char
    else:
        raise ValueError("preset must be 'all-0', 'alpha' or 'all-5'")
    return {'fit_id': fit_id, 'skills': preset}


def _env_candidates(text):
    rows = sqlite3.connect(os.path.join(ARGS.pyfa, 'eve.db')).execute(
        """SELECT t.typeName FROM invtypes t JOIN invgroups g ON g.groupID=t.groupID
           WHERE g.name IN (?,?,?,?) AND t.typeName LIKE '%'||?||'%' AND t.published=1
           ORDER BY t.typeName LIMIT 8""", (*ENV_GROUPS, text)).fetchall()
    return [r[0] for r in rows]


@mcp.tool()
@_engine_thread
def set_env(fit_id: str, effect: str = '') -> dict:
    """Set the system-wide environment on a fit ('Class 5 Wolf Rayet Effects', 'Strong Metaliminal Dark Storm Environment', ...); '' clears. Affects this fit only — set the same env on any fit you compare it to."""
    from eos.saveddata.module import Module
    fit = _fit(fit_id)
    prev = ENVS.pop(fit_id, None)
    if prev is not None and prev in fit.projectedModules:
        fit.projectedModules.remove(prev)
    if not effect:
        return {'fit_id': fit_id, 'env': None}
    item = eftlib._lookup(effect)
    if item is None or item.group.name not in ENV_GROUPS:
        raise ValueError(f'unknown environment {effect!r}; candidates: {_env_candidates(effect)}')
    mod = Module(item)
    fit.projectedModules.append(mod)
    if mod not in fit.projectedModules:
        raise ValueError(f'{effect!r} is not projectable')
    mod.owner = fit
    ENVS[fit_id] = mod
    return {'fit_id': fit_id, 'env': item.typeName}


@mcp.tool()
@_engine_thread
def set_projected(fit_id: str, projector_fit_ids: list) -> dict:
    """Project other fits' active modules/drones onto this fit ([] clears): remote reps, ewar, neuts. Entries: 'f2' (zero range = full strength) or {fit_id:'f2', range_km:20} — strength then follows each module's optimal+falloff (most ewar is zero past optimal+3x falloff). The projector's own skills/hull scale everything."""
    _fit(fit_id)
    entries = []
    for p in projector_fit_ids:
        pid = p.get('fit_id') if isinstance(p, dict) else p
        rng_km = p.get('range_km') if isinstance(p, dict) else None
        if pid == fit_id:
            raise ValueError('a fit cannot project onto itself here; fit a second copy')
        _fit(pid)
        entries.append((pid, None if rng_km is None else float(rng_km) * 1000))
    PROJECTIONS[fit_id] = entries
    return {'fit_id': fit_id, 'projected_by': [
        {'fit_id': pid, **({} if rng is None else {'range_km': rng / 1000})}
        for pid, rng in entries]}


@mcp.tool()
@_engine_thread
def set_booster(fit_id: str, booster_fit_ids: list) -> dict:
    """Attach command-burst booster fits by fit_id ([] clears). The booster fit's own hull/skills/mindlink scale its bursts; strongest same buff wins, bursts never stack."""
    _fit(fit_id)
    for b in booster_fit_ids:
        if b == fit_id:
            raise ValueError('a fit cannot boost itself')
        _fit(b)
    BOOSTS[fit_id] = list(booster_fit_ids)
    return {'fit_id': fit_id, 'boosters': list(booster_fit_ids)}


@mcp.tool()
@_engine_thread
def graph(fit_id: str, kind: str, target: dict = None, distance_km: float = 5.0,
          item: str = None) -> dict:
    """Bounded curve: <=30 points + summary + named assumptions. kind: 'dps_vs_range' | 'dps_vs_target_speed' | 'cap_vs_time' | 'dps_vs_time' (spool ramp) | 'ewar_vs_range' (needs item: a projected module on THIS fit). target for dps kinds: {speed_ms, sig_m, atk_speed_ms}; distance_km applies to dps_vs_target_speed."""
    fit = _fit(fit_id)
    _recalc(fit)
    t = target or {}
    if kind == 'dps_vs_range':
        return graphlib.dps_vs_range(fit, tgt_speed=t.get('speed_ms', 0.0),
                                     tgt_sig=t.get('sig_m'), atk_speed=t.get('atk_speed_ms', 0.0))
    if kind == 'dps_vs_target_speed':
        return graphlib.dps_vs_target_speed(fit, distance_km=distance_km, tgt_sig=t.get('sig_m'))
    if kind == 'cap_vs_time':
        return graphlib.cap_vs_time(fit)
    if kind == 'dps_vs_time':
        return graphlib.dps_vs_time(fit)
    if kind == 'ewar_vs_range':
        if not item:
            raise ValueError("ewar_vs_range needs item: the projected module's name")
        return graphlib.ewar_vs_range(fit, item)
    raise ValueError("kind must be 'dps_vs_range', 'dps_vs_target_speed', "
                     "'cap_vs_time', 'dps_vs_time' or 'ewar_vs_range'")


@mcp.tool()
@_engine_thread
def applied_dps(fit_id: str, distance_km: float, target: dict) -> dict:
    """Applied (not paper) dps vs a real target: target {sig_m required, speed_ms?, atk_speed_ms?}. pyfa's full application model — turret tracking/sig, missile explosion radius+velocity, drone mobility — at full spool; raw vs applied split per source class."""
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.module import Module
    from eos.const import FittingHardpoint
    fit = _fit(fit_id)
    _recalc(fit)
    if not target or target.get('sig_m') is None:
        raise ValueError("target needs sig_m (and usually speed_ms) — "
                         "pull the hull's base values from layer 1")
    dist = float(distance_km) * 1000
    tgt_speed = float(target.get('speed_ms', 0))
    dmg = graphlib._dmg_map(fit)
    amap = graphlib._application_map(fit, dist, tgt_speed, float(target['sig_m']),
                                     float(target.get('atk_speed_ms', 0)))

    def bucket(key):
        if isinstance(key, Drone):
            return 'drones'
        if isinstance(key, Fighter):
            return 'fighters'
        if isinstance(key, Module) and key.hardpoint == FittingHardpoint.MISSILE:
            return 'missiles'
        if isinstance(key, Module) and key.hardpoint == FittingHardpoint.TURRET:
            return 'turrets'
        return 'other'

    raw_total = applied_total = 0.0
    by = {}
    for key, d in dmg.items():
        raw = d.total
        applied = (d * amap.get(key, 0)).total
        b = by.setdefault(bucket(key), [0.0, 0.0])
        b[0] += raw
        b[1] += applied
        raw_total += raw
        applied_total += applied
    return {'fit_id': fit_id, 'distance_km': distance_km,
            'target': {'sig_m': target['sig_m'], 'speed_ms': tgt_speed},
            'dps_raw': round(raw_total, 1), 'dps_applied': round(applied_total, 1),
            'application_pct': round(100 * applied_total / raw_total, 1) if raw_total else 0,
            'by_source': {k: [round(r, 1), round(a, 1)] for k, (r, a) in sorted(by.items())}}


@mcp.tool()
@_engine_thread
def get_stats(fit_id: str, profile: dict = None, spool: float = None) -> dict:
    """Full stat panel. profile: optional damage weights {em,thermal,kinetic,explosive}, default uniform. spool: 0..1 for spool-up weapons (default 1 = full spool; floor and ramp time ride in offense.spool). All ship values include skills/modules; resists as fractions."""
    from eos.saveddata.damagePattern import DamagePattern
    fit = _fit(fit_id)
    p = profile or {}
    fit.damagePattern = DamagePattern(
        emAmount=p.get('em', 25), thermalAmount=p.get('thermal', 25),
        kineticAmount=p.get('kinetic', 25), explosiveAmount=p.get('explosive', 25))
    panel = stat_panel(fit, recalc=lambda f, factor_reload: _recalc(f, factor_reload),
                       spool=spool)
    panel['problems'] = _problems(fit)
    # A silent zero-spool number once cost a graded eval miss: name the level.
    spool_info = panel['offense'].get('spool')
    if spool_info:
        panel.setdefault('notes', []).append(
            f"spool-up weapons: dps/volley at {round(spool_info['level'] * 100)}% spool "
            f"(floor {spool_info['dps_zero_spool']}, full ramp {spool_info['time_to_full_s']} s)")
    # Siege-class states (bastion/siege/triage share dogma group 'Siege
    # Module'): the numbers assume the state is running; name what it costs.
    siege = sorted({m.item.typeName for m in fit.modules
                    if not m.isEmpty and m.item.group.name == 'Siege Module'
                    and m.state >= FittingModuleState.ACTIVE})
    if siege:
        panel.setdefault('notes', []).append(
            f'{", ".join(siege)} active: stats assume the state is running; '
            'ship is immobile and remote assistance is impeded for the duration')
    return panel


@mcp.tool()
@_engine_thread
def module_attrs(fit_id: str, item: str, attrs: list) -> dict:
    """Modified per-module attribute values (skills/ship bonuses/heat/mutations applied) for every fitted module or drone named `item`. attrs: dogma attribute names, e.g. ['maxRange','speedFactor']; null = not on that module. Overheat first via edit_fit state op to read heated values."""
    from eos.db.gamedata.queries import getAttributeInfo
    for name in attrs:
        if getAttributeInfo(name) is None:
            raise ValueError(f'unknown attribute {name!r} (dogma names, e.g. maxRange)')
    fit = _fit(fit_id)
    _recalc(fit)
    state_names = {v: k for k, v in STATES.items()}
    out = []
    for mod in fit.modules:
        if not mod.isEmpty and mod.item.typeName == item:
            vals = {n: (round(v, 4) if isinstance(v, float) else v)
                    for n in attrs for v in [mod.getModifiedItemAttr(n)]}
            out.append({'item': mod.item.typeName,
                        'state': state_names.get(mod.state, str(mod.state)),
                        'attrs': vals})
    for drone in fit.drones:
        if drone.item.typeName == item:
            vals = {n: (round(v, 4) if isinstance(v, float) else v)
                    for n in attrs for v in [drone.getModifiedItemAttr(n)]}
            out.append({'item': drone.item.typeName, 'amount': drone.amount,
                        'attrs': vals})
    if not out:
        raise ValueError(f'{item!r} not fitted')
    return {'fit_id': fit_id, 'modules': out}


@mcp.tool()
@_engine_thread
def sweep(fit_id: str, item: str, candidates: list, metrics: list = None) -> dict:
    """Try each candidate module in place of fitted module `item` (every copy swapped; charge/state carried when valid) and return one compact row per candidate with the named panel metrics (dotted paths, e.g. 'offense.dps', 'defense.ehp.total'; default dps/ehp/speed) plus cpu_free/pg_free/problems. The fit is restored afterwards. Max 20 candidates."""
    from eos.saveddata.module import Module
    if len(candidates) > 20:
        raise ValueError(f'{len(candidates)} candidates; cap is 20 per sweep')
    metrics = metrics or ['offense.dps', 'defense.ehp.total',
                          'navigation.max_velocity_ms']
    fit = _fit(fit_id)
    idxs = [i for i, m in enumerate(fit.modules)
            if not m.isEmpty and m.item.typeName == item]
    if not idxs:
        raise ValueError(f'{item!r} not fitted')
    originals = [fit.modules[i] for i in idxs]

    def pick(panel, path):
        node = panel
        for part in path.split('.'):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def row(label):
        panel = stat_panel(fit, recalc=lambda f, factor_reload: _recalc(f, factor_reload))
        attr = fit.ship.getModifiedItemAttr
        r = {'candidate': label}
        r.update({p: pick(panel, p) for p in metrics})
        r['cpu_free'] = round((attr('cpuOutput') or 0) - fit.cpuUsed, 2)
        r['pg_free'] = round((attr('powerOutput') or 0) - fit.pgUsed, 2)
        r['problems'] = len(_problems(fit))
        return r

    rows = [row(f'{item} (fitted)')]
    try:
        for name in candidates:
            cand_item = eftlib._lookup(name)
            if cand_item is None:
                rows.append({'candidate': name, 'error': 'unknown item'})
                continue
            # construct all candidate copies BEFORE touching the fit, so a
            # bad candidate (a drone name, say) leaves the fit untouched
            try:
                cands = []
                for orig in originals:
                    mod = Module(cand_item)
                    if orig.charge is not None and mod.isValidCharge(orig.charge):
                        mod.charge = orig.charge
                    if mod.isValidState(orig.state):
                        mod.state = orig.state
                    elif mod.isValidState(FittingModuleState.ACTIVE):
                        mod.state = FittingModuleState.ACTIVE
                    cands.append(mod)
            except ValueError as e:
                rows.append({'candidate': name, 'error': str(e)})
                continue
            # replace in position — never remove/append, which would disturb
            # rack layout ([Empty ...] gaps) on layout-conscious fits
            for i, mod in zip(idxs, cands):
                fit.modules.replace(i, mod)
                mod.owner = fit
            rows.append(row(name))
            for i, orig in zip(idxs, originals):
                fit.modules.replace(i, orig)
    finally:
        for i, orig in zip(idxs, originals):
            if fit.modules[i] is not orig:
                fit.modules.replace(i, orig)
        _recalc(fit)
    return {'fit_id': fit_id, 'swapped_count': len(originals), 'rows': rows}


@mcp.tool()
@_engine_thread
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
@_engine_thread
def validate_fit(fit_id: str) -> dict:
    """In-game legality: fitting resources, slots, hardpoints, drone limits."""
    problems = _problems(_fit(fit_id))
    return {'fit_id': fit_id, 'legal': not problems, 'problems': problems}


@mcp.tool()
@_engine_thread
def required_skills(fit_id: str, full: bool = False) -> dict:
    """Skills (with levels) needed to use the whole fit. Default lists only the training-queue ends (prerequisites implied by other entries are pruned) plus any skills an alpha clone cannot train high enough; full=true returns the entire prerequisite closure."""
    fit = _fit(fit_id)
    need, items = {}, {}

    def walk(item):
        for skill_item, level in item.requiredSkills.items():
            name = skill_item.typeName
            if need.get(name, 0) < int(level):
                need[name] = int(level)
                items[name] = skill_item
                walk(skill_item)

    walk(fit.ship.item)
    for mod in fit.modules:
        if not mod.isEmpty:
            walk(mod.item)
            if mod.charge is not None:
                walk(mod.charge)
    for group in (fit.drones, fit.fighters, fit.boosters, fit.implants):
        for thing in group:
            walk(thing.item)

    # static prerequisite closure of a single skill (levels are fixed:
    # training a skill to any level needs its whole prereq tree)
    closures = {}

    def closure_of(skill_item):
        name = skill_item.typeName
        if name not in closures:
            closures[name] = {}
            for s2, l2 in skill_item.requiredSkills.items():
                closures[name][s2.typeName] = max(closures[name].get(s2.typeName, 0), int(l2))
                for n3, l3 in closure_of(s2).items():
                    closures[name][n3] = max(closures[name].get(n3, 0), l3)
        return closures[name]

    ends = {s: lvl for s, lvl in need.items()
            if not any(closure_of(items[o]).get(s, 0) >= lvl
                       for o in need if o != s)}

    caps = dict(sqlite3.connect(os.path.join(ARGS.pyfa, 'eve.db')).execute(
        'SELECT typeID, level FROM alphaCloneSkills').fetchall())
    alpha_blocked = {s: lvl for s, lvl in need.items()
                     if caps.get(items[s].ID, 0) < lvl}

    out = {'fit_id': fit_id, 'skills': dict(sorted(need.items() if full else ends.items()))}
    if not full and len(need) > len(ends):
        out['implied_prereqs'] = len(need) - len(ends)
    if alpha_blocked:
        out['alpha_blocked'] = dict(sorted(alpha_blocked.items()))
    out['note'] = 'minimums to use, not to use well'
    return out


@mcp.tool()
@_engine_thread
def engine_info() -> dict:
    """Engine + data build. Compare engine_build to the SDE skill's build; any skew means numbers may disagree with layer 1."""
    meta = dict(sqlite3.connect(os.path.join(ARGS.pyfa, 'eve.db'))
                .execute('SELECT field_name, field_value FROM metadata').fetchall())
    return {
        'engine': 'pyfa-eos (headless)',
        'engine_build': meta.get('client_build'),
        'unmodeled': ['industrial core state',
                      'structures', 'custom skill sheets',
                      'fighter ability toggles (standard attack only)',
                      'heat burnout timers (overload bonuses ARE modeled: state overheated)'],
        'skills_presets': ['all-0', 'alpha', 'all-5'],
    }


if __name__ == '__main__':
    mcp.run()
