"""Is layer 1 current, and does it agree with itself?

    python3 sde/freshness.py            # report only
    python3 sde/freshness.py --fix      # rebuild when stale, report when offline

Two failures this catches, both found the hard way on 2026-08-20:

* **Mixed parts.** The split databases are separate files. A checkout ended up
  with `items`/`industry`/`universe` at build 3466501 and `misc` at 3470007,
  because parts had been fetched piecemeal from two different releases. Every
  answer then mixed two CCP releases, and the build number reported to the
  caller was whichever part happened to sort first.
* **Silently stale.** `setup.sh` and the session-start hook both guarded on
  *existence* -- `ls eve-sde-*.sqlite` -- so once a container had any parts it
  never refreshed and never noticed. The publish pipeline was healthy the whole
  time; only the working copy drifted.

CCP's manifest is ~80 bytes, so the check is cheap enough to run on every
session start. The rebuild is not, which is why it only happens on a real
mismatch, builds into a temporary directory, and moves the parts into place
only once they all exist -- a failed rebuild leaves the old data untouched
rather than deleting it and dying.
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILDER = os.path.join(ROOT, '.claude', 'skills', 'eve-sde', 'scripts', 'build_sde_db.py')
MANIFEST = 'https://developers.eveonline.com/static-data/tranquility/latest.jsonl'


def local_builds(root):
    """{filename: build number or None} for every part present."""
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'eve-sde-*.sqlite'))):
        name = os.path.basename(path)
        try:
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
                row = db.execute(
                    "SELECT value FROM meta WHERE key='sdeBuildNumber'").fetchone()
            out[name] = str(row[0]) if row else None
        except sqlite3.Error:
            out[name] = None          # unreadable counts as wrong, never as fine
    return out


def ccp_build(timeout):
    """CCP's current build number, or None if the network is not there."""
    try:
        with urllib.request.urlopen(MANIFEST, timeout=timeout) as r:
            return str(json.loads(r.read().decode())['buildNumber'])
    except Exception:                 # noqa: BLE001 — offline is a valid state
        return None


def rebuild(root):
    """Rebuild every part at CCP's current build, atomically.

    Built in a temporary directory and moved into place only once the parts are
    all there. `split_db` skips a group whose tables are absent WITHOUT removing
    an existing file for it, so building over the top of a stale set can leave
    one part behind at the old build — which is how the mixed set survived.
    Replacing the whole directory contents sidesteps that entirely.
    """
    with tempfile.TemporaryDirectory(dir=root, prefix='.sde-build-') as tmp:
        subprocess.run(
            [sys.executable, BUILDER, '--db', os.path.join(tmp, 'eve-sde.sqlite'),
             '--complete', '--positions', '--split', '--parts-only'],
            check=True)
        fresh = sorted(glob.glob(os.path.join(tmp, 'eve-sde-*.sqlite')))
        if not fresh:
            raise RuntimeError('the build produced no parts; keeping what we had')
        for old in glob.glob(os.path.join(root, 'eve-sde-*.sqlite')):
            os.remove(old)
        for part in fresh:
            shutil.move(part, os.path.join(root, os.path.basename(part)))
        return [os.path.basename(p) for p in fresh]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=ROOT)
    ap.add_argument('--fix', action='store_true',
                    help='rebuild when stale; without it, only report')
    ap.add_argument('--timeout', type=float, default=15)
    a = ap.parse_args()

    parts = local_builds(a.dir)
    if not parts:
        print('layer 1: no databases present — run ./setup.sh')
        return 2

    builds = set(parts.values())
    mixed = len(builds) > 1 or None in builds
    current = ccp_build(a.timeout)
    have = sorted(b for b in builds if b)
    behind = bool(current) and builds != {current}

    if mixed:
        print('layer 1: MIXED — parts disagree with each other:')
        for name, build in sorted(parts.items()):
            print(f'    {name:<28} {build or "unreadable"}')
    if current is None:
        # Warn-only fallback: without the manifest we cannot know what current
        # is, but a set that disagrees with ITSELF is wrong regardless.
        print(f'layer 1: cannot reach CCP to check for a newer build '
              f'(have {", ".join(have) or "nothing readable"})'
              + ('; the mismatch above still needs a rebuild' if mixed else ''))
        return 1 if mixed else 0
    if not (mixed or behind):
        print(f'layer 1: current at build {current}')
        return 0
    if not mixed:
        print(f'layer 1: behind — parts at {", ".join(have)}, CCP is at {current}')
    if not a.fix:
        print('layer 1: run `python3 sde/freshness.py --fix` to rebuild')
        return 1

    print(f'layer 1: rebuilding at build {current} (~1 min)...')
    try:
        made = rebuild(a.dir)
    except Exception as exc:           # noqa: BLE001 — never leave a session
        print(f'layer 1: rebuild FAILED ({exc}); the existing databases are '
              'untouched and still ' + ('mixed' if mixed else 'stale')
              + ' — answers from them may not match the live game')
        return 1
    now = local_builds(a.dir)
    if len(set(now.values())) != 1:
        print(f'layer 1: rebuild left a mixed set: {now}')
        return 1
    print(f'layer 1: rebuilt {len(made)} parts at build {next(iter(set(now.values())))}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
