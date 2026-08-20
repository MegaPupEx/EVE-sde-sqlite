#!/usr/bin/env bash
# Bootstrap a fresh clone so both MCP servers can start.
#
#   ./setup.sh              # both layers
#   ./setup.sh --sde-only   # layer 1 only (fast: no pyfa clone, no venv)
#
# Idempotent: each step is skipped if its output already exists. The SDE
# databases and the pyfa working tree are gitignored, so a fresh container
# has neither and the servers have nothing to serve until this runs.
set -euo pipefail
cd "$(dirname "$0")"

# Two sessions bootstrapping the same checkout at once would both download and
# build into the same paths and clobber each other. Serialise: the second
# waits, then finds the work already done and skips it. (On Claude Code on the
# web each chat gets its own container, so this only matters when several
# sessions share one machine.)
exec 9>".setup.lock"
if command -v flock >/dev/null 2>&1; then
    flock 9 || { echo "could not take the setup lock" >&2; exit 1; }
fi

SDE_ONLY=0
[ "${1:-}" = "--sde-only" ] && SDE_ONLY=1

# --- layer 1: the SDE databases (stdlib only, ~1 min, downloads ~99 MB) ---
if ls eve-sde-*.sqlite >/dev/null 2>&1; then
    echo "layer 1: databases already present"
    # ...which says nothing about whether they are CURRENT, or whether the
    # parts agree with one another. Rebuilds only on a real mismatch.
    python3 sde/freshness.py --fix || true
else
    echo "layer 1: building SDE databases from CCP (~1 min)..."
    # --db sets the stem the split parts inherit. It must be `eve-sde` because
    # that is what the server and the skill glob for; the script's own default
    # produces `sde-*.sqlite`, which builds fine and is then invisible to both.
    python3 .claude/skills/eve-sde/scripts/build_sde_db.py \
        --db eve-sde.sqlite --complete --positions --split --parts-only
    # --parts-only skips compressing the monolith but still leaves it behind;
    # the parts carry everything, so it is ~160 MB of dead weight.
    rm -f eve-sde.sqlite
    ls eve-sde-*.sqlite >/dev/null 2>&1 || {
        echo "layer 1: FAILED — the build produced no eve-sde-*.sqlite parts" >&2
        exit 1
    }
    echo "layer 1: built $(ls eve-sde-*.sqlite | wc -l) parts"
fi

if [ "$SDE_ONLY" = "1" ]; then
    echo "done (layer 1 only). The eve-sde MCP server can serve now."
    exit 0
fi

# --- layer 2: pyfa + the headless venv (clones a repo, ~2-4 min) ---
if [ -x fitting/work/eosenv/bin/python ] && [ -f fitting/work/pyfa/eve.db ]; then
    echo "layer 2: engine already built"
else
    echo "layer 2: fetching pyfa and building the headless engine (~2-4 min)..."
    fitting/spike/setup_pyfa.sh fitting/work
fi
# the fitting server needs the MCP SDK inside that venv; layer 1 needs nothing
fitting/work/eosenv/bin/python -c 'import mcp' 2>/dev/null \
    || fitting/work/eosenv/bin/pip install --quiet mcp

echo
echo "ready. Both servers should connect on the next session start:"
echo "  claude mcp list"
