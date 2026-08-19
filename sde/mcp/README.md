# eve-sde MCP server (layer 1)

Two tools over the SDE sqlite parts, registered independently of layer 2 so
the layers install in any combination.

```bash
python3 sde/mcp/server.py --sde .        # stdio; --sde is the dir with eve-sde-*.sqlite
python3 sde/mcp/test_server.py --sde .   # smoke test
```

`.mcp.json` entry:

```json
"eve-sde": { "command": "python3", "args": ["sde/mcp/server.py", "--sde", "."] }
```

## Why it exists

Two measured problems, one shape:

1. **Cost.** Two thirds of eval tool calls were one-query-per-round shell
   invocations; each round re-reads the whole conversation (~45k tokens).
   `query` takes many statements at once.
2. **Reachability.** Across 29 eval subjects the layer-1 reference docs were
   opened by **one** — zero direct file reads. Trap knowledge that lives only
   in `references/gotchas-*.md` protects nobody, so the traps that can be
   mechanised live here instead.

## Tools

| tool | what it does |
| --- | --- |
| `query(sql, limit=40)` | many statements in one round; every part pre-ATTACHed; `-- comment` above a statement labels it; one bad statement reports its error without killing the batch; rows capped with the true count; lints the raw-value traps |
| `attrs(items, attributes)` | dogma attributes **unit-corrected** — resonances as resist %, unitID-101 attributes as seconds, modifier percents as ±%, each beside its raw value; unknown type names suggest neighbours |
| `sde_info()` | build number, parts present, the corrections applied |

`attrs` is the one that matters: raw `type_dogma.value` inverts for 58
resistance attributes (unitID 108: `1.0` = 0% resist) and misreports units for
92 more (unitID 101 is milliseconds behind a "s" display name). Both classes
produced wrong answers in measured eval runs.

Standing schema cost: ~390 tokens.
