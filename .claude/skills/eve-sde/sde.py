#!/usr/bin/env python3
"""Run many SDE queries in ONE call. Reads SQL on stdin, prints labelled results.

    python3 sde.py <<'SQL'
    -- rifter hull
    SELECT name, mass FROM types WHERE name = 'Rifter';
    -- its published turret variants
    SELECT COUNT(*) FROM types WHERE groupID = 55 AND published = 1;
    SQL

Every `eve-sde-*.sqlite` part found is attached automatically, so table names
work unqualified (`meta` still needs qualifying — it exists in every part).
A `-- comment` immediately above a statement becomes that block's label.

Why this exists: each separate shell call re-reads the whole conversation
(~45k tokens). Ten questions asked in ten calls cost ten context re-reads;
asked here they cost one. Batch every query you already know you need.

Rows are capped (default 40, --limit N to change) and the true count is always
reported, so a wide query truncates instead of flooding the conversation.
"""
import os
import sqlite3
import sys

LIMIT = 40
argv = [a for a in sys.argv[1:]]
if '--limit' in argv:
    i = argv.index('--limit')
    LIMIT = int(argv[i + 1])
    del argv[i:i + 2]

root = os.environ.get('EVE_SDE_DIR')
if not root:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.getcwd(), here, *[os.path.abspath(os.path.join(here, *['..'] * n))
                                      for n in range(1, 5)]):
        if any(f.startswith('eve-sde-') and f.endswith('.sqlite')
               for f in os.listdir(cand)):
            root = cand
            break
if not root:
    sys.exit("no eve-sde-*.sqlite found; set EVE_SDE_DIR to the directory holding them")

db = sqlite3.connect(':memory:')
parts = sorted(f for f in os.listdir(root)
               if f.startswith('eve-sde-') and f.endswith('.sqlite'))
for f in parts:
    alias = f[len('eve-sde-'):-len('.sqlite')].replace('-', '_')
    db.execute("ATTACH DATABASE ? AS " + alias, (os.path.join(root, f),))

sql = sys.stdin.read()
if not sql.strip():
    sys.exit("no SQL on stdin — pipe statements in, separated by ';'")

# split into statements, keeping the comment line(s) above each as its label
blocks, label, buf = [], None, []
for line in sql.splitlines():
    s = line.strip()
    if s.startswith('--') and not buf:
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

print(f"[{len(parts)} parts attached: {', '.join(p[8:-7] for p in parts)}]")
for n, (label, stmt) in enumerate(blocks, 1):
    print(f"\n=== {n}. {label or 'query'} ===")
    try:
        cur = db.execute(stmt)
    except sqlite3.Error as e:
        print(f"ERROR: {e}")
        continue
    if cur.description is None:
        print("(no rows returned)")
        continue
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:LIMIT]:
        print(" | ".join('' if v is None else str(v) for v in r))
    if len(rows) > LIMIT:
        print(f"... {len(rows) - LIMIT} more rows (of {len(rows)}); aggregate or LIMIT in SQL")
    else:
        print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
