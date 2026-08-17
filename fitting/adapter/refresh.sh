#!/usr/bin/env bash
# One-command engine data refresh: rebuild pyfa's eve.db at CCP's current
# (or a named) SDE build, from the same static-data feed layer 1 builds from.
# Run it after any CCP patch; the layers then answer from the same build.
#
#   ./refresh.sh [--pyfa <checkout>] [--build N] [--force]
#
# Fetches CCP's manifest -> downloads that build's JSONL zip (only when the
# checkout's eve.db is not already at it) -> make_staticdata.py -> swaps the
# generated staticdata into the checkout -> pyfa's own db_update.py ->
# reports client_build. The download cache lives in ./cache (gitignored).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SPIKE="$HERE/../spike"
PYFA="$(cd "$HERE/../work/pyfa" 2>/dev/null && pwd || true)"
BUILD=""
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pyfa)  PYFA="$(cd "$2" && pwd)"; shift 2 ;;
        --build) BUILD="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done
[ -n "$PYFA" ] && [ -d "$PYFA" ] || { echo "no pyfa checkout (--pyfa, or run ../spike/setup_pyfa.sh first)" >&2; exit 2; }

# the venv python that setup_pyfa.sh made, sitting next to the checkout
PYTHON="$(dirname "$PYFA")/eosenv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3

if [ -z "$BUILD" ]; then
    BUILD=$("$PYTHON" - <<'EOF'
import json, urllib.request
with urllib.request.urlopen('https://developers.eveonline.com/static-data/tranquility/latest.jsonl') as r:
    print(json.load(r)['buildNumber'])
EOF
)
fi

current=""
if [ -f "$PYFA/eve.db" ]; then
    current=$("$PYTHON" -c "import sqlite3; print(dict(sqlite3.connect('$PYFA/eve.db').execute('SELECT field_name, field_value FROM metadata')).get('client_build',''))" 2>/dev/null || true)
fi
if [ "$current" = "$BUILD" ] && [ "$FORCE" != 1 ]; then
    echo "eve.db already at build $BUILD; nothing to do (--force to rebuild anyway)"
    exit 0
fi
echo "refreshing: eve.db build ${current:-none} -> $BUILD"

CACHE="$HERE/cache"
mkdir -p "$CACHE"
ZIP="$CACHE/eve-online-static-data-$BUILD-jsonl.zip"
RAW="$CACHE/sde-raw-$BUILD"
if [ ! -d "$RAW" ]; then
    [ -f "$ZIP" ] || curl -sSfL --retry 3 --retry-delay 5 -o "$ZIP" \
        "https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-$BUILD-jsonl.zip"
    "$PYTHON" -c "import zipfile; zipfile.ZipFile('$ZIP').extractall('$RAW.tmp')"
    mv "$RAW.tmp" "$RAW"
fi

GEN="$CACHE/staticdata-$BUILD"
rm -rf "$GEN"
"$PYTHON" "$HERE/make_staticdata.py" --sde-raw "$RAW" --out "$GEN" --build "$BUILD"

rm -rf "$PYFA/staticdata"
cp -r "$GEN" "$PYFA/staticdata"
rm -f "$PYFA/eve.db"
( cd "$PYFA" && PYTHONPATH="$SPIKE/wxstub" "$PYTHON" db_update.py )

got=$("$PYTHON" -c "import sqlite3; print(dict(sqlite3.connect('$PYFA/eve.db').execute('SELECT field_name, field_value FROM metadata')).get('client_build',''))")
[ "$got" = "$BUILD" ] || { echo "rebuild produced client_build=$got, expected $BUILD" >&2; exit 1; }
echo "eve.db rebuilt at client_build $got"
echo "next: rerun the battery + tests, and re-pin eval keys if numbers moved:"
echo "  $PYTHON $SPIKE/run_battery.py --pyfa $PYFA --out <candidate-dir>"
echo "  $PYTHON $SPIKE/compare_panels.py $SPIKE/reference <candidate-dir>"
