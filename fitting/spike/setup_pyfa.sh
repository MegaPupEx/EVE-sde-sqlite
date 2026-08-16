#!/usr/bin/env bash
# One-shot setup for the candidate-A spike: fetch pyfa at the pinned commit,
# create a venv with the minimal headless deps, build eve.db from pyfa's
# bundled static data. Idempotent; safe to re-run.
#
#   ./setup_pyfa.sh [workdir]     # default workdir: ./work
#
# Then:
#   work/eosenv/bin/python run_battery.py --pyfa work/pyfa
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-$HERE/work}"
PYFA_COMMIT=8b04f3b271e614b3e103853b44a7851a63d79d0e   # pinned in docs/fitting-formulas.md

mkdir -p "$WORK"

if [ ! -d "$WORK/pyfa/.git" ]; then
    git init -q "$WORK/pyfa"
    git -C "$WORK/pyfa" remote add origin https://github.com/pyfa-org/Pyfa.git
fi
if ! git -C "$WORK/pyfa" cat-file -e "$PYFA_COMMIT" 2>/dev/null; then
    git -C "$WORK/pyfa" fetch --depth 1 origin "$PYFA_COMMIT"
fi
git -C "$WORK/pyfa" checkout -q "$PYFA_COMMIT"

if [ ! -x "$WORK/eosenv/bin/python" ]; then
    python3 -m venv "$WORK/eosenv"
fi
"$WORK/eosenv/bin/pip" install --quiet -r "$HERE/requirements.txt"

if [ ! -f "$WORK/pyfa/eve.db" ]; then
    # db_update.py imports eos.db -> root config -> wx; reuse the stub
    ( cd "$WORK/pyfa" && PYTHONPATH="$HERE/wxstub" "$WORK/eosenv/bin/python" db_update.py )
fi

echo "ready: $WORK/eosenv/bin/python $HERE/run_battery.py --pyfa $WORK/pyfa"
