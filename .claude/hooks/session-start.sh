#!/bin/bash
# Bootstrap a fresh Claude Code on the web container.
#
# The SDE databases and the pyfa working tree are gitignored, so a fresh clone
# has neither. Both MCP servers read their data at startup, which is why this
# runs SYNCHRONOUSLY: an async hook would let the servers start against an
# empty directory and the first question would fail.
set -euo pipefail

# Local machines already have their own setup; only bootstrap the remote one.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

if ls eve-sde-*.sqlite >/dev/null 2>&1 \
   && [ -x fitting/work/eosenv/bin/python ] && [ -f fitting/work/pyfa/eve.db ]; then
  echo "eve-sde-sqlite: already bootstrapped"
  # Bootstrapped is not the same as current. Both guards here used to test only
  # that the files EXIST, so a long-lived container never refreshed and never
  # noticed when its parts disagreed with each other -- one checkout served
  # three parts from CCP build 3466501 beside a fourth from 3470007 for days.
  # The check itself is one ~80-byte fetch; the rebuild only runs on a real
  # mismatch. `|| true` because a stale database still answers questions and
  # must never take the session down with it.
  if [ "${EVE_SDE_NO_REFRESH:-}" = "1" ]; then
    echo "layer 1: freshness check skipped (EVE_SDE_NO_REFRESH=1)"
  else
    python3 sde/freshness.py --fix || true
  fi
  exit 0
fi

echo "eve-sde-sqlite: first run in this container, building both layers..."
./setup.sh
