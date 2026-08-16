# Engine spike — candidate A: pyfa's embedded eos

Phase 1 of the fitting-engine roadmap (`docs/roadmap-fitting-mcp.md`): drive
pyfa's engine headless and produce the reference-fit battery. Findings and
the running verdict live in `docs/spike-log.md`.

## Run it

```bash
./setup_pyfa.sh              # fetch pyfa @ pinned commit, venv, build eve.db (~2 min)
work/eosenv/bin/python run_battery.py --pyfa work/pyfa
```

Requires outbound network for the first run (github.com + PyPI); afterwards
everything is local. No wxPython anywhere — `headless.py` documents the three
stubs/hooks that make eos run without the GUI.

## What's here

| File | What |
| --- | --- |
| `headless.py` | the bootstrap: wx stub, in-memory saveddata, sys.path — the spike's entanglement findings, as code |
| `battery.py` | 10 fits chosen for effect-matrix coverage (weapon systems × tank types × prop × rigs × T1/T2 hulls) |
| `run_battery.py` | builds each fit in eos, computes the full stat panel, writes `reference/<fit>.json` |
| `reference/*.json` | the ground-truth panels: pyfa's engine, pyfa's data, pinned commit and client build in every file |
| `setup_pyfa.sh` / `requirements.txt` / `wxstub/` | reproducible environment |

## What the reference JSONs are for

They are the decision criterion made concrete. Candidate B (`dogma-engine`)
is graded by reproducing these panels within rounding; whichever engine backs
MCP v1, the harness replays these same fits forever after. Each file carries
`meta.pyfa_commit` and `meta.engine_client_build` so a drifted number can
always be attributed to code vs data.

Known coverage gaps, deliberate for now (tracked in the spike log): no
implants/boosters, no alpha-clone skill set, no overheated states, no mutated
modules, uniform damage profile only.
