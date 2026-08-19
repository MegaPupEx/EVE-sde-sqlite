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
        raise RuntimeError(f'no eve-sde-*.sqlite in {root}')
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


def _interpret(value, unit_id):
    """Return (human_value, note) for a raw dogma value."""
    if value is None:
        return None, None
    if unit_id is not None and unit_id not in UNITS:
        # Silence here would read as "no correction needed". A unit this server
        # has no rule for is exactly where a future SDE build breaks it.
        return None, (f'unitID {unit_id} has no correction rule in this server — '
                      'raw value shown; confirm its meaning before quoting')
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


@mcp.tool()
def query(statements: list[str], limit: int = 40) -> dict:
    """Run SDE statements. `statements` is a LIST — put every query you already know you need in one call, because a second call re-reads the whole conversation. A '-- comment' line above a statement labels it. Every eve-sde part is pre-ATTACHed so table names need no prefix (except `meta`, which exists in all of them). Rows are capped with the true count reported; raw dogma values are linted for the unit traps."""
    # Measured over gen-10: 22 of 24 calls to the old `sql: str` form sent a
    # single statement. A string invites one statement no matter what the
    # docstring asks for, so the parameter is a list and the schema says so.
    # A bare string still works -- refusing it would cost the round the shape
    # change is meant to save -- but it is answered with a nudge.
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


@mcp.tool()
def attrs(items: list, attributes: list = None) -> dict:
    """Dogma attributes for named types, UNIT-CORRECTED: resonances come back as resist %, millisecond attributes as seconds, modifier percents as ±%, each with its raw value beside it. items: type names (exact) or typeIDs. attributes: attribute names or IDs; omitted returns every published attribute on the type. This is the honest read — raw `type_dogma.value` inverts for 58 resistance attributes and lies about units for 92 more."""
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
        sql = ('SELECT a.attributeID, a.name, a.unitID, d.value FROM type_dogma d '
               'JOIN dogma_attributes a ON a.attributeID = d.attributeID WHERE d.typeID = ?')
        params = [type_id]
        if attributes:
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
        vals = {}
        for attr_id, attr_name, unit_id, value in db.execute(sql, params):
            human, why = _interpret(value, unit_id)
            entry = {'raw': value, 'attributeID': attr_id}
            if human is not None:
                entry['value'] = human
            if why:
                entry['unit_note'] = why
            vals[attr_name] = entry
        missing = []
        if attributes:
            asked = {str(a).lower() for a in attributes if not str(a).isdigit()}
            missing = sorted(a for a in asked if a not in {k.lower() for k in vals})
        rec = {'item': name, 'typeID': type_id, 'attributes': vals}
        if missing:
            rec['not_on_this_type'] = missing
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
