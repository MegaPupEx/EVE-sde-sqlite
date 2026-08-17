# Fitting evals

The layer-2 half of the loop that produced the SDE skill's 16 pinned
fixes: graded questions, a no-skill control, and every miss root-caused to
**model vs docs vs engine** — docs misses get fixed in
`.claude/skills/eve-fitting/` and pinned here, engine misses get fixed in
`fitting/`, recurring model misses get promoted into the docs.

| File | What |
| --- | --- |
| `questions.md` | the graded set: prompts, pinned keys, rubric |
| `keys-<build>.json` | engine-computed keys, filename carries the data build |
| `make_keys.py` | recomputes every engine key over the live MCP server |
| `drive.py` | run any JSON list of tool calls against the server (how eval subjects reach the engine without MCP registration) |
| `results-*.md` | dated graded runs: control vs with-skill, root causes, fixes |

## Running

```bash
../spike/setup_pyfa.sh "$PWD/../work"        # once; then:
../work/eosenv/bin/python make_keys.py --pyfa ../work/pyfa
echo '[{"tool":"engine_info","args":{}}]' | ../work/eosenv/bin/python drive.py --pyfa ../work/pyfa
```

An eval run gives each question to a fresh Sonnet-class session twice —
once with only `drive.py` access (control), once also instructed to load
the eve-fitting skill — and grades both against `questions.md`'s keys on
the four axes (K numbers, M mechanics, D discipline, P pilot-answer).

Findings already pinned by key generation itself (2026-08-17, before the
first graded run):

- **Engine:** `set_skills('alpha')` mutated pyfa's shared All-5 character,
  silently turning every fit in the session alpha. Fixed in `server.py`;
  `test_server.py` now asserts restoration and fresh-import isolation.
- **Docs:** `reading-stats.md` claimed the battery Caracal loses EHP vs
  Guristas; the engine says it *gains* (16.9k → 18.5k — the hardener
  covers kin/therm). Rewritten with pinned numbers; the lesson ("compute,
  don't reason from the bare hull") is now the example itself.
- **Battery wart, now load-bearing:** the Hurricane (1,681/1,425) and
  Vexor (985/875) reference fits are PG-over — coverage fits, never
  legality-checked. E5/T2 use that as a discipline probe.

**Grading axes, generation 3 onward:** K/M/D/P plus **C (concision)** —
graded against the skill's answer-economy budgets (fit review ~200 words,
follow-up ~100, lookup ~50; verdict once, numbers once, provenance one
line). Run-3 answers (`results3-2026-08-17.md`) are the "before" corpus.
