# eve-fitting MCP server (v1.5)

pyfa's engine behind 16 terse tools. A Claude session launches this process
locally over stdio; fits live in the server's memory and travel as short IDs
(`f1`, `f2`) — the conversation never carries a fit, only the numbers asked
for. EFT text is the sole import/export payload.

## Measured token economics (test_server.py prints these)

| item | tokens |
| --- | --- |
| standing schema overhead (all 16 tools) | **~1,550** |
| `get_stats` full panel | ~260 |
| `graph` (≤30-point curve + summary) | ~110–190 |
| `edit_fit` / `import_fit` / `clone_fit` summary | ~30 |
| `compare_fits` (diff-only output) | ~150–300 |
| `validate_fit`, `set_skills`, `set_env`, `set_booster`, `delete_fit` | ≤ ~25 |

A full fit-iteration step (edit + stats) is ~290 tokens; a thirty-step
fitting conversation costs ~9k tokens of tool traffic against the roadmap's
40–80k envelope. The consumer this is sized for is a Sonnet-class chat
answering question after question without hitting rate or context limits.

## Setup

```bash
../spike/setup_pyfa.sh work                     # pyfa @ pinned commit + venv + eve.db
work/eosenv/bin/pip install mcp
# optional but recommended — rebuild eve.db at CCP's current SDE build:
#   see ../adapter/README.md
work/eosenv/bin/python test_server.py --pyfa work/pyfa    # smoke test
```

Register in a project `.mcp.json` (or Claude Desktop's config, same shape):

```json
{
  "mcpServers": {
    "eve-fitting": {
      "command": "/abs/path/fitting/mcp/work/eosenv/bin/python",
      "args": ["/abs/path/fitting/mcp/server.py", "--pyfa", "/abs/path/fitting/mcp/work/pyfa"]
    }
  }
}
```

## Tools

Lifecycle: `create_fit`, `import_fit` (EFT, multi-fit capable), `clone_fit`,
`delete_fit`, `export_fit`.
Mutation: `edit_fit` (ops list: add/remove/charge/state/mode — charge and
state apply to all matching modules; mode sets a T3D tactical mode; add
covers modules, drones, fighters, implants and drugs by item category),
`set_skills` (`all-0` | `alpha` | `all-5`), `set_env` (system environment —
wormhole class beacons, metaliminal storms, abyssal hazards; applies to
that fit only), `set_booster` (command-burst fits, computed recursively —
the booster's own hull/skills scale the burst, strongest same buff wins),
`set_projected` (other fits' remote reps/ewar/neuts applied at zero
range).
Read: `get_stats` (full panel, optional damage-profile weights),
`required_skills` (training-queue ends, alpha-trainability flags; full closure on demand), `graph`
(`dps_vs_range` / `dps_vs_target_speed` / `cap_vs_time` — ≤30 points +
summary + named assumptions), `compare_fits` (differing figures only),
`validate_fit` (named constraint violations), `engine_info` (data build +
the explicit unmodeled list).

Design rules, enforced not aspirational: one-line tool descriptions (the
teaching belongs in the fitting-knowledge skill, schemas are paid every
turn); unit-suffixed keys so a medium-effort model never guesses; empty
sections omitted; anything unmodeled is named in `engine_info`, never
silently ignored.

## Implementation notes

- Saveddata runs on a temp **file**, not `:memory:` — MCP tools execute on
  worker threads, sqlite in-memory databases are per-connection, and the
  schema must be created once (`eos.db.saveddata_meta.create_all()`, the
  same call pyfa.py makes at startup).
- Built against the `mcp` Python SDK 2.0 (`mcp.server.mcpserver.MCPServer`).
- Graph math is pyfa's own: application factors from
  `graphs/data/fitDamageStats/calc/application.py` (imported behind
  synthetic package entries that shadow the wx GUI `__init__`s, with
  `GraphSettings` shimmed to pyfa's pinned defaults), cap series from
  eos's event simulation (`fit.getCapSimData`).
- eos *consumes* command bonuses as it applies them, so the server reruns
  every booster's COMMAND pass before each calculation
  (`panel.stat_panel`'s injectable `recalc`). Symptom if regressed: burst
  bonuses appear once, then vanish on the next `get_stats`.
- Projection ordering is load-bearing: bursts run BEFORE the subject's
  local calc (eos consumes their bonuses during it), projected fits run
  AFTER it (the local calc's clear() would wipe them). `_recalc` is the
  single place that knows this.
- Mutated (abyssal) modules and drones use pyfa's EFT dialect: the fitted
  line carries the *base* item name plus an ` [N]` reference, and a
  trailing section maps each N to base item / mutaplasmid / rolled
  attributes (absolute values). eos clamps out-of-range rolls to the
  mutaplasmid's band; export → reimport round-trips to identical stats. A
  bare abyssal type name with no mutation block is rejected loudly — the
  roll is the data.
- Not yet here (tracked in the roadmap's v2 list): siege states,
  spool-up, structures, custom skill sheets, fighter ability toggles.
