"""EVE SDE MCP server — layer 1 behind two tools.

    python3 server.py --sde /path/to/dir-with-eve-sde-*.sqlite

Design rules (mirrors fitting/mcp/server.py):
- Batch by default: every call re-reads the whole conversation (~45k tokens),
  so the unit of cost is the ROUND, not the query. `query` takes many
  statements at once; measured runs spent two thirds of their budget on
  one-query-per-round shell invocations.
- The gotchas belong in code, not only in prose. Measured over 29 eval
  subjects, the layer-1 reference docs were opened by ONE — so a trap that
  lives only in `references/gotchas-*.md` protects nobody. `attrs` therefore
  returns unit-corrected values, and `query` lints the raw-value traps.
- Outputs stay compact: row caps with true counts, empty sections omitted.
"""
import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _stdio import MCPServer   # stdlib only: layer 1 installs without a venv

_parser = argparse.ArgumentParser()
_parser.add_argument('--sde', default=os.environ.get('EVE_SDE_DIR', '.'))
ARGS = _parser.parse_args()

mcp = MCPServer('eve-sde')

PARTS, BUILD = [], None
_db = None


def _conn():
    """One in-memory handle with every part ATTACHed; unqualified names resolve."""
    global _db, PARTS, BUILD
    if _db is not None:
        return _db
    root = os.path.abspath(ARGS.sde)
    PARTS = sorted(f for f in os.listdir(root)
                   if f.startswith('eve-sde-') and f.endswith('.sqlite'))
    if not PARTS:
        raise RuntimeError(
            f'no eve-sde-*.sqlite in {root} — the databases are gitignored, so a '
            'fresh clone has to build them: `./setup.sh` at the repo root (~1 min, '
            'stdlib only). Say so plainly rather than answering from memory.')
    _db = sqlite3.connect(':memory:', check_same_thread=False)
    for f in PARTS:
        alias = f[len('eve-sde-'):-len('.sqlite')].replace('-', '_')
        _db.execute('ATTACH DATABASE ? AS ' + alias, (os.path.join(root, f),))
    alias0 = PARTS[0][len('eve-sde-'):-len('.sqlite')].replace('-', '_')
    BUILD = _db.execute(
        f"SELECT value FROM {alias0}.meta WHERE key='sdeBuildNumber'").fetchone()[0]
    return _db


# unitID semantics that make raw values lie (references/gotchas-dogma.md).
# Kept as data so the conversion and the warning never drift apart.
UNITS = {
    108: ('inverted', 'resonance/resistance: 0.0 = 100%, 1.0 = 0%'),
    101: ('ms', 'milliseconds despite a "s" displayName'),
    109: ('modifier', 'modifier percent: 1.1 = +10%, 0.75 = -25%'),
    105: ('pct_raw', 'percent conventions vary: -50 = -50%'),
    121: ('pct_raw', 'percent conventions vary'),
    124: ('pct_raw', 'percent conventions vary'),
    127: ('pct_raw', 'percent conventions vary'),
}
BIG_TABLES = ('type_dogma', 'types', 'moons', 'planets', 'type_effects')


# Traps this server does NOT mechanise. Named for the same reason the engine
# names `unmodeled`: a tool that silently covers some cases invites the reader
# to assume it covers all of them.
NOT_CORRECTED = [
    'ties — many attributes have huge tie groups (409 of 423 ships share one '
    'web-resist value); never lift a top row as "the best"',
    'attribute families whose NAME lies (resists, sensor strength, tech level) '
    '— match on attributeID, not name',
    'highIsGood is unreliable (remoteRepairImpedance is inverted and flagged 1)',
    'derived values — regen peaks, stacking, skills, hull bonuses: engine work, '
    'not raw attributes',
    'attributeID and unitID are separate ID spaces that overlap',
]


_UNIT_NAMES = None


def _unit_names(db):
    """unitID -> display symbol, read from the DB rather than baked in.

    Most units are honest: metres, mm, MW, GJ, HP. Warning about every one of
    them buried the two that matter — a measured session got 13 lines of "no
    correction rule" on one Vexor, including metres and millimetres. Label
    what CCP labels, override the liars, warn only on genuine unknowns.
    """
    global _UNIT_NAMES
    if _UNIT_NAMES is None:
        _UNIT_NAMES = {}
        try:
            for key, display in db.execute('SELECT _key, displayName FROM dogmaUnits'):
                if display:
                    _UNIT_NAMES[key] = display
        except sqlite3.Error:
            pass                      # a renamed table costs labels, not answers
    return _UNIT_NAMES


def _interpret(value, unit_id, db=None):
    """Return (human_value, note) for a raw dogma value."""
    if value is None:
        return None, None
    if unit_id is not None and unit_id not in UNITS:
        symbol = _unit_names(db).get(unit_id) if db is not None else None
        if symbol:
            return f'{value} {symbol}', None
        # Silence here would read as "no correction needed". A unit with no
        # rule AND no label is exactly where a future SDE build breaks this.
        return None, (f'unitID {unit_id} has no label in dogmaUnits and no correction '
                      'rule here — raw value shown; confirm it before quoting')
    if unit_id not in UNITS:
        return None, None
    kind, why = UNITS[unit_id]
    value = float(value)          # ints must still format as 0.0%, not 0%
    if kind == 'inverted':
        return f'{round((1 - value) * 100, 1)}%', why
    if kind == 'ms':
        return f'{round(value / 1000, 3)} s', why
    if kind == 'modifier':
        return f'{round((value - 1) * 100, 1)}%', why
    return None, why


def _schema_hint(db, message, stmt):
    """Turn a column/table error into the answer instead of another round.

    Measured 2026-08-19: "which T1 cruiser has the most powergrid" took eight
    calls, six of them rediscovering that this builder stores `name` where
    CCP's SDE says typeName/groupName/attributeName. The database already
    knows; saying so costs nothing and saves a round each time.
    """
    # Every real table lives in an ATTACHed part, and each schema has its own
    # sqlite_master — the main one is empty, so walk database_list.
    tables = []
    for _, schema, _path in db.execute('PRAGMA database_list'):
        try:
            tables += [r[0] for r in db.execute(
                f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")]
        except sqlite3.Error:
            pass
    tables = sorted(set(tables))
    if 'no such table' in message:
        missing = message.rsplit(':', 1)[-1].strip()
        near = [t for t in tables if missing.lower().strip('_') in t.lower()]
        return {'tables_available': sorted(near or tables)[:40]}
    if 'no such column' not in message:
        return {}
    # Report the columns of every table this statement actually mentions.
    hint = {}
    for t in tables:
        if re.search(r'\b' + re.escape(t) + r'\b', stmt):
            try:
                hint[t] = [r[1] for r in db.execute(f'PRAGMA table_info({t})')]
            except sqlite3.Error:
                pass
    return {'columns_available': hint} if hint else {'tables_available': sorted(tables)[:40]}


@mcp.tool()
def query(statements: list[str] = None, limit: int = 40, sql: str = None) -> dict:
    """SQL escape hatch for set and aggregate questions — "which ore", "how many jumps", "list every hull that…". For the stats of a type you can NAME, use `attrs` instead: it answers in one call where SQL takes several. `statements` is a LIST — put every query you already know you need in one call, because a second call re-reads the whole conversation. A '-- comment' line above a statement labels it. Every eve-sde part is pre-ATTACHed so table names need no prefix (except `meta`, in all of them); note the group table is `groups_`. Rows are capped with the true count reported; raw dogma values are linted for the unit traps."""
    # Measured over gen-10: 22 of 24 calls to the old `sql: str` form sent a
    # single statement. A string invites one statement no matter what the
    # docstring asks for, so the parameter is a list and the schema says so.
    # A bare string still works -- refusing it would cost the round the shape
    # change is meant to save -- but it is answered with a nudge.
    # `sql` is the name callers reach for first — it was this tool's own
    # parameter until gen-11. Charging a wasted round to say "wrong keyword"
    # helps nobody; take it, and nudge toward the list form in the result.
    if statements is None and sql is not None:
        statements = sql
    if statements is None:
        raise ValueError('pass `statements`: a list of SQL statements')
    coerced = isinstance(statements, str)
    sql = statements if coerced else '\n'.join(
        s if s.rstrip().endswith(';') else s + ';' for s in statements)

    db = _conn()
    blocks, label, buf = [], None, []
    for line in sql.splitlines():
        s = line.strip()
        pending = any(x.strip() for x in buf)
        if not s and not pending:
            continue                      # leading blank lines are not a statement
        if s.startswith('--') and not pending:
            label = s.lstrip('-').strip()
            continue
        buf.append(line)
        if s.endswith(';'):
            stmt = '\n'.join(buf).strip()
            if stmt.rstrip(';').strip():
                blocks.append((label, stmt))
            label, buf = None, []
    if '\n'.join(buf).strip():
        blocks.append((label, '\n'.join(buf).strip()))
    if not blocks:
        raise ValueError('no statements; separate them with ";"')

    out = []
    for label, stmt in blocks:
        item = {'label': label or 'query'}
        try:
            cur = db.execute(stmt)
        except sqlite3.Error as e:
            item['error'] = str(e)          # one bad statement never kills the batch
            item.update(_schema_hint(db, str(e), stmt))
            out.append(item)
            continue
        if cur.description is None:
            item['rows'] = 0
            out.append(item)
            continue
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        item['columns'] = cols
        item['rows'] = len(rows)
        item['data'] = [list(r) for r in rows[:limit]]
        if len(rows) > limit:
            item['truncated'] = f'showing {limit} of {len(rows)}; aggregate or LIMIT in SQL'
        notes = []
        low = stmt.lower()
        if 'value' in [c.lower() for c in cols] and 'attributeid' in low:
            notes.append('raw dogma `value` selected: unitID decides meaning '
                         '(108 inverted, 101 ms, 109 modifier-%). Use the `attrs` '
                         'tool for unit-corrected numbers.')
        if re.search(r'select\s+\*', low) and any(t in low for t in BIG_TABLES):
            notes.append('SELECT * on a large table — aggregate instead of printing rows.')
        if re.search(r'a\.name\s*(=|like)', low) and 'resonance' not in low:
            notes.append('matching attributes by name: several families lie '
                         '(resists, sensor strength, tech level). Prefer attributeIDs.')
        if notes:
            item['notes'] = notes
        out.append(item)
    result = {'sde_build': BUILD, 'parts': [p[8:-7] for p in PARTS], 'results': out}
    if coerced:
        result['note'] = ('`statements` is a list — pass each query as its own '
                          'element, and send every one you already know you need '
                          'in a single call.')
    return result


# Hull facts live on `types` as ordinary columns, not in dogma. Measured in
# gen-11: a "how much cargo" question burned 13 rounds because the model went
# looking for a dogma attribute that does not exist. Returning both halves is
# the point of this tool.
HULL_COLUMNS = ['mass', 'volume', 'capacity', 'packagedVolume', 'radius',
                'basePrice', 'portionSize', 'metaLevel', 'techLevel', 'published']
HULL_HINTS = {'capacity': 'cargo hold, m3', 'volume': 'assembled volume, m3',
              'packagedVolume': 'packaged volume, m3', 'mass': 'kg'}

# The attributes people actually ask about, by category. Anything absent on a
# given type is simply skipped; `full=True` returns everything.
_SHIP = [
    'shieldCapacity', 'armorHP', 'hp',
    'shieldEmDamageResonance', 'shieldThermalDamageResonance',
    'shieldKineticDamageResonance', 'shieldExplosiveDamageResonance',
    'armorEmDamageResonance', 'armorThermalDamageResonance',
    'armorKineticDamageResonance', 'armorExplosiveDamageResonance',
    'maxVelocity', 'agility', 'signatureRadius', 'scanResolution',
    'maxTargetRange', 'maxLockedTargets',
    'capacitorCapacity', 'rechargeRate', 'shieldRechargeRate',
    'hiSlots', 'medSlots', 'lowSlots', 'rigSlots', 'upgradeCapacity',
    'turretSlotsLeft', 'launcherSlotsLeft',
    'droneCapacity', 'droneBandwidth',
    'powerOutput', 'cpuOutput', 'warpSpeedMultiplier',
]
_MODULE = [
    'cpu', 'power', 'capacitorNeed', 'duration', 'maxRange', 'falloff',
    'trackingSpeed', 'damageMultiplier', 'speedFactor', 'speedBoostFactor',
    'shieldBonus', 'armorDamageAmount', 'massAddition', 'maxVelocityBonus',
    'signatureRadiusBonus', 'warpScrambleStrength', 'activationBlockedStrenght',
    'metaLevel', 'techLevel', 'hp',
]
_CHARGE = [
    'emDamage', 'thermalDamage', 'kineticDamage', 'explosiveDamage',
    'weaponRangeMultiplier', 'fallofMultiplier', 'aoeCloudSize', 'aoeVelocity',
    'explosionDelay', 'capacityNeeded', 'metaLevel', 'techLevel',
]
_DRONE = [
    'emDamage', 'thermalDamage', 'kineticDamage', 'explosiveDamage',
    'damageMultiplier', 'maxVelocity', 'droneBandwidthUsed', 'entityFlyRange',
    'trackingSpeed', 'optimalSigRadius', 'hp', 'armorHP', 'shieldCapacity',
]
PANELS = {6: _SHIP, 7: _MODULE, 8: _CHARGE, 18: _DRONE}


def _type_row(db, type_id):
    """The `types` row plus group/category names. Returns (dict, categoryID).

    The group table is `groups_` — `groups` is a SQL keyword, so the builder
    renamed it. Exactly the kind of thing a caller should not have to discover.
    """
    cols = {r[1] for r in db.execute('PRAGMA table_info(types)')}
    want = [c for c in HULL_COLUMNS if c in cols]
    row = db.execute(f'SELECT groupID, categoryID, {", ".join(want)} '
                     'FROM types WHERE typeID = ?', (type_id,)).fetchone()
    group_id, category_id = row[0], row[1]
    hull = {}
    for key, value in zip(want, row[2:]):
        if value is None:
            continue
        hint = HULL_HINTS.get(key)
        hull[key] = f'{value} ({hint})' if hint else value
    for label, table, key, ident in (('group', 'groups_', 'groupID', group_id),
                                     ('category', 'categories', 'categoryID', category_id)):
        try:
            got = db.execute(f'SELECT name FROM {table} WHERE {key} = ?', (ident,)).fetchone()
            if got:
                hull[label] = got[0]
        except sqlite3.Error:
            pass                              # a renamed table must not break the lookup
    return hull, category_id


# Attributes worth seeing when choosing between variants of one module. Any
# that a given family does not carry are simply absent from its rows.
LADDER_ATTRS = ['cpu', 'power', 'capacitorNeed', 'duration', 'capacityBonus',
                'damageMultiplier', 'speedFactor', 'maxRange', 'falloff',
                'trackingSpeed', 'armorDamageAmount', 'shieldBonus',
                'armorHPBonusAdd', 'signatureRadiusBonus', 'warpScrambleRange']


@mcp.tool()
def variants(items: list[str], attributes: list = None) -> dict:
    """The meta ladder for a module: every published variant of the same item — tech 1, compact/enduring/restrained metas, tech 2, storyline, faction — with fitting cost and the attributes that decide between them. Use this BEFORE naming a module, not after one is rejected: guessing a name and waiting for "unknown item" costs a round per guess and only ever reveals one name, while the ladder shows that (say) a compact shield extender is 9 CPU cheaper than the tech 2 for 200 less HP. Rows are sorted by meta level."""
    db = _conn()
    want = attributes or LADDER_ATTRS
    out = []
    for it in items:
        row = db.execute('SELECT typeID, name, variationParentTypeID FROM types '
                         'WHERE name = ? COLLATE NOCASE', (str(it),)).fetchone()
        if row is None:
            near = db.execute('SELECT name FROM types WHERE name LIKE ? AND published = 1 '
                              'ORDER BY length(name) LIMIT 5', (f'%{it}%',)).fetchall()
            out.append({'item': str(it), 'error': 'no such type',
                        'did_you_mean': [n for (n,) in near]})
            continue
        type_id, name, parent = row
        parent = parent or type_id
        fam = db.execute(
            'SELECT typeID, name, metaLevel, metaGroupID FROM types '
            'WHERE (variationParentTypeID = ? OR typeID = ?) AND published = 1 '
            'ORDER BY metaLevel, name', (parent, parent)).fetchall()
        rows = []
        for tid, tname, meta, mgroup in fam:
            vals = {}
            for aname, value, unit in db.execute(
                    'SELECT a.name, d.value, a.unitID FROM type_dogma d '
                    'JOIN dogma_attributes a ON a.attributeID = d.attributeID '
                    'WHERE d.typeID = ? AND a.name IN (%s)' % ','.join('?' * len(want)),
                    [tid] + list(want)):
                human, _ = _interpret(value, unit, db)
                vals[aname] = human if human is not None else value
            entry = {'name': tname, 'metaLevel': meta}
            grp = db.execute('SELECT name FROM meta_groups WHERE metaGroupID = ?',
                             (mgroup,)).fetchone() if mgroup else None
            if grp:
                entry['tier'] = grp[0]
            entry.update(vals)
            rows.append(entry)
        out.append({'item': name, 'variants': rows})
    return {'sde_build': BUILD, 'families': out}


@mcp.tool()
def attrs(items: list, attributes: list = None, full: bool = False) -> dict:
    """START HERE for any question about a named ship, module, charge or drone. One call walks the whole chain — name to typeID, hull columns AND dogma attributes, unit-corrected (resonances as resist %, millisecond attributes as seconds, modifier percents as ±%), each with its raw value beside it. Omit `attributes` for the panel people actually ask about; pass names/IDs for specific ones; `full` for every published attribute. Hull stats like cargo `capacity`, `mass` and `volume` are columns on `types`, NOT dogma attributes — this returns both, which hand-written SQL usually misses."""
    db = _conn()
    if not items:
        raise ValueError('items: at least one type name or typeID')
    out = []
    for it in items:
        if isinstance(it, int) or str(it).isdigit():
            row = db.execute('SELECT typeID, name FROM types WHERE typeID = ?',
                             (int(it),)).fetchone()
        else:
            row = db.execute('SELECT typeID, name FROM types WHERE name = ? COLLATE NOCASE',
                             (str(it),)).fetchone()
        if row is None:
            # substring first, then progressively shorter prefixes, so a
            # trailing typo ('Riftr') still finds 'Rifter'
            near = []
            probe = str(it)
            for pat in [f'%{probe}%'] + [probe[:n] + '%' for n in
                                         range(len(probe) - 1, 2, -1)]:
                near = db.execute(
                    'SELECT name FROM types WHERE name LIKE ? AND published = 1 '
                    'ORDER BY length(name) LIMIT 5', (pat,)).fetchall()
                if near:
                    break
            out.append({'item': str(it), 'error': 'no such type',
                        'did_you_mean': [n for (n,) in near]})
            continue
        type_id, name = row
        hull, category_id = _type_row(db, type_id)
        panel = None if (attributes or full) else PANELS.get(category_id)
        sql = ('SELECT a.attributeID, a.name, a.unitID, d.value FROM type_dogma d '
               'JOIN dogma_attributes a ON a.attributeID = d.attributeID WHERE d.typeID = ?')
        params = [type_id]
        if panel:
            sql += ' AND a.name IN (%s) COLLATE NOCASE' % ','.join('?' * len(panel))
            params += list(panel)
        elif attributes:
            ids = [int(a) for a in attributes if str(a).isdigit()]
            names = [str(a) for a in attributes if not str(a).isdigit()]
            clauses = []
            if ids:
                clauses.append('a.attributeID IN (%s)' % ','.join('?' * len(ids)))
                params += ids
            if names:
                clauses.append('a.name IN (%s) COLLATE NOCASE' % ','.join('?' * len(names)))
                params += names
            sql += ' AND (' + ' OR '.join(clauses) + ')'
        else:
            sql += ' AND a.published = 1'
        vals, hoisted, uncorrected = {}, [], set()
        for attr_id, attr_name, unit_id, value in db.execute(sql, params):
            human, why = _interpret(value, unit_id, db)
            entry = {'raw': value, 'attributeID': attr_id}
            if human is not None:
                entry['value'] = human
            if why:
                # A panel repeats the same sentence for all eight resonances,
                # and once per uncorrected unit on top of that. Say each real
                # correction once, and roll the "no rule" cases into one line.
                if not panel:
                    entry['unit_note'] = why
                elif unit_id is not None and unit_id not in UNITS:
                    uncorrected.add(unit_id)
                elif why not in hoisted:
                    hoisted.append(why)
            vals[attr_name] = entry
        if uncorrected:
            hoisted.append(
                'raw values shown for unitID ' + ', '.join(str(u) for u in sorted(uncorrected))
                + ' — no correction rule in this server; confirm meaning before quoting')
        missing = []
        if attributes:
            asked = {str(a).lower() for a in attributes if not str(a).isdigit()}
            missing = sorted(a for a in asked if a not in {k.lower() for k in vals})
        rec = {'item': name, 'typeID': type_id, 'hull': hull, 'attributes': vals}
        if hoisted:
            rec['unit_notes'] = hoisted
        if missing:
            rec['not_on_this_type'] = missing
        if panel:
            total = db.execute('SELECT COUNT(*) FROM type_dogma d JOIN dogma_attributes a '
                               'ON a.attributeID = d.attributeID '
                               'WHERE d.typeID = ? AND a.published = 1', (type_id,)).fetchone()[0]
            if total > len(vals):
                rec['more'] = (f'{total - len(vals)} further published attributes — name them '
                               'in `attributes`, or pass full=true')
        out.append(rec)
    return {'sde_build': BUILD, 'types': out}


@mcp.tool()
def sde_info() -> dict:
    """SDE build number, the parts present, and the traps this server corrects for."""
    _conn()
    db = _conn()
    unknown = db.execute(
        'SELECT unitID, COUNT(*) FROM dogma_attributes WHERE unitID IS NOT NULL '
        'AND unitID NOT IN (%s) GROUP BY unitID ORDER BY COUNT(*) DESC LIMIT 8'
        % ','.join(str(k) for k in UNITS)).fetchall()
    return {
        'sde_build': BUILD,
        'parts': [p[8:-7] for p in PARTS],
        'unit_corrections': {str(k): v[1] for k, v in UNITS.items()},
        'units_without_a_rule': [{'unitID': u, 'attributes': n} for u, n in unknown],
        'not_corrected': NOT_CORRECTED,
        'reminder': 'batch statements into one `query` call; each call re-reads the conversation',
    }


if __name__ == '__main__':
    mcp.run()
