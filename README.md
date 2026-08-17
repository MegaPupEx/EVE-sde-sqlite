# eve-sde-sqlite

Tools that let a Claude chat answer EVE Online questions accurately, with
sources, at low token cost. Three layers, each verified against the one
below it:

| Layer | What it answers | Status |
| --- | --- | --- |
| **1. SDE skill** (`.claude/skills/eve-sde`) | what the game data says — ships, modules, dogma, industry, the universe | done; auto-released |
| **2. Fitting engine** (`fitting/` + `.claude/skills/eve-fitting`) | what happens when you combine things — fits, stats, stacking | engine + MCP server + knowledge skill; eval loop running |
| **3. Knowledge base** | what players know — mechanics, doctrine, strategy | planned |

Design and status: [`docs/roadmap-fitting-mcp.md`](docs/roadmap-fitting-mcp.md) ·
[`docs/spike-log.md`](docs/spike-log.md) ·
[`docs/fitting-formulas.md`](docs/fitting-formulas.md)

## Layer 1 — the SDE as SQLite, plus the skill that reads it safely

CCP ships EVE's static data as ~100 JSONL files. `build_sde_db.py` turns
them into one indexed SQLite database; the skill documents the traps —
columns that return plausible wrong numbers instead of errors.

**Download** ([Releases](../../releases/latest), republished within hours of
each CCP build, split by domain so each part fits claude.ai's 30 MB
per-file upload limit):

| Part | Size | Covers |
| --- | --- | --- |
| `eve-sde-moons.sqlite.xz` | ~20 MB | all 344k moons |
| `eve-sde-universe.sqlite.xz` | ~8 MB | systems, planets, gates, stations, coordinates |
| `eve-sde-items.sqlite.xz` | ~7 MB | types, dogma attributes/effects, reprocessing |
| `eve-sde-world.sqlite.xz` | ~1.4 MB | missions, agents, corps, certificates |
| `eve-sde-industry.sqlite.xz` | ~0.5 MB | blueprints, PI schematics |
| `eve-sde-cosmetic.sqlite.xz` + `misc` | ~0.4 MB | skins, icons, the remainder |

```bash
BASE=https://github.com/MegaPupEx/EVE-sde-sqlite-Claude-skill/releases/latest/download
curl -sSLO $BASE/eve-sde-universe.sqlite.xz && xz -d eve-sde-*.xz   # keep published names
```

**Or build from CCP directly** (stdlib only, ~30 s, always current build):

```bash
python3 .claude/skills/eve-sde/scripts/build_sde_db.py --complete            # 107 tables
python3 .claude/skills/eve-sde/scripts/build_sde_db.py --complete --split --compress xz
```

**Query**: each part is a complete database; `ATTACH` several and join
across them (most real questions need two). Python's built-in `sqlite3`
needs no install. The SDE is full of columns that return plausible wrong
numbers rather than errors — the trap catalogue and full column reference
live in [`SKILL.md`](.claude/skills/eve-sde/SKILL.md); read it before
trusting a result. Claims are pinned to build 3466501 —
`scripts/verify_claims.py` re-checks all 138 on any newer build.

**Use as a skill**: loads automatically in this repo. Elsewhere:
`cp -r .claude/skills/eve-sde ~/.claude/skills/`, or zip that folder and
upload under Settings → Capabilities → Skills in the Claude apps, then
attach the `.xz` parts a question needs.

Not in the SDE (use [ESI](https://esi.evetech.net)): market prices, kills,
sovereignty, character data.

## Layer 2 — the fitting engine

Wraps **pyfa's** battle-tested calculation engine (`eos`) headless — no
GUI, no reimplemented math — and serves it to Claude as an MCP server with
stateful fits addressed by ID. Verified panel-for-panel identical to
desktop pyfa; runs on the same SDE build as layer 1.

| Piece | What |
| --- | --- |
| [`fitting/mcp/`](fitting/mcp/) | the server: 14 tools (import/edit/stats/graph/env/bursts…), ~1,280 tokens standing, ~290 per edit+stats step |
| [`fitting/engine/`](fitting/engine/) | EFT parse/build/render + the stat panel |
| [`fitting/adapter/`](fitting/adapter/) | regenerates pyfa's data from CCP's current export — engine and skill share one data source |
| [`fitting/spike/`](fitting/spike/) | reproducible setup + the 10-fit reference battery every change is graded against |

```bash
fitting/spike/setup_pyfa.sh work && work/eosenv/bin/pip install mcp
work/eosenv/bin/python fitting/mcp/test_server.py --pyfa work/pyfa   # full smoke test
```

Registration and tool list: [`fitting/mcp/README.md`](fitting/mcp/README.md).
Unlike layer 1, the engine is a *process*, not an upload: it needs Python,
a pyfa checkout and the MCP registration — Claude Code and Claude Desktop
territory. The interpretation half is a normal skill:
[`.claude/skills/eve-fitting`](.claude/skills/eve-fitting/SKILL.md) teaches
what the engine's numbers mean (stat reading, tradeoffs, a numbered trap
catalogue) and the answer discipline (name your layer, your build, your
skill preset, and anything unmodeled). Its graded eval loop lives in
[`fitting/evals/`](fitting/evals/) — first run: 69% without the skill,
98% with.

## Automation

`.github/workflows/sde-release.yml` polls CCP every 3 hours and republishes
the layer-1 parts when the build number changes — after every archive
round-trips, passes integrity checks, and fits the upload limit.
