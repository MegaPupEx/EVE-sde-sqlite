# What a question actually costs (2026-08-19)

Measured after gens 9–11. This supersedes the working assumptions behind every
cost intervention attempted so far, most of which were aimed at the wrong term.

## The model

    cost ≈ rounds × floor

A "round" is one model request: every tool call and the final answer each cost
one. The conversation is re-read in full on every round, so the floor is paid
again each time.

Decomposition of gen-11 (5 subjects × 3 turns, 4,570,461 billed tokens):

| term | tokens | share |
|---|---|---|
| fixed floor re-read every round | 3,726,825 | **82%** |
| accumulated payload (tool results, fits, tables) | 818,879 | 18% |
| output | 24,757 | 1% |

## The floor is not ours

| configuration | first-round context |
|---|---|
| bare Claude Code session, outside the project | 40,970 |
| in the project, no MCP servers | 41,729 |
| both MCP servers registered | 41,906 |
| observed floor in gen-11 sessions | 43,845 |

**~41k of the ~44k floor is the harness** — its system prompt, built-in tool
definitions, and the deferred tool-name list. Everything this project ships —
two skills, two MCP servers, CLAUDE.md — accounts for **under 1,000 tokens** of
it. MCP tool schemas cost almost nothing at rest because they are deferred
(see below); they are only paid once fetched.

Per-round growth after the floor is small: typically +200 to +1,500 tokens,
with occasional +5,000 when a skill loads or a large result lands.

### Consequence

Halving the skill, trimming reference docs, or shaving the tool schema each
move well under 1% of a question's cost. Four successive interventions
(doc placement, router prose, batching guidance, the list-shaped `query`) all
landed inside the noise because **they were arithmetically incapable of moving
the number**. The only term with leverage is `rounds`.

## Where the rounds go

85 rounds over 15 turns (5.7 per turn):

| rounds | purpose |
|---|---|
| 37 | layer-1 data |
| 19 | layer-2 engine |
| 12 | ToolSearch (fetching MCP tool schemas) |
| 5 | Skill (loading the router) |

## On deferred tools — tested, and not controllable here

MCP tool schemas are verbose, so this build does not put them in the system
prompt. It lists the tool *names* and requires a `ToolSearch` call to fetch a
schema before the tool can be called: context traded for a round.

Turning that off would save the 12 ToolSearch rounds (~490k, ~11% of the run).
**It cannot be turned off from this side.** Tested:

- `toolSearchEnabled: false` via `--settings` — no effect (41,912 vs 41,906).
  The field exists in the binary but is scoped to third-party/Cowork config and
  is additionally model-gated.
- `--tools` naming the MCP tools explicitly — ToolSearch still fired.

What remains actionable is reducing *how many* ToolSearch calls happen: gen-11
averaged 2.4 per session, and a single fetch covering both servers would make
that 1. Modest, but free.

## Revised priorities

1. **Collapse dependency chains into one tool call.** The largest reducible
   block is the 37 layer-1 data rounds. SDE lookups are inherently sequential
   (typeID before attributes, unitID before the value means anything), so
   batching independent statements does not help — gen-11 proved that. What
   helps is a tool that walks the chain server-side. `attrs` already does, and
   was used 0 times against 35 `query` calls. Make chain-collapsing tools the
   front door, `query` the escape hatch, and give `attrs` a useful default
   panel so the first call is usually sufficient. Target: one data round per
   layer-1 question.
2. **Measure in rounds, not tokens.** Billed tokens swung ±18% on a control arm
   nothing touched, across gens 9–11 — the metric cannot resolve the effects
   being tested at n=5. Rounds are near-integer, far more stable, and convert
   to cost at ~41k each. Report rounds; derive tokens.
3. **Stop optimizing skill and doc size.** Under 1k of a 41k floor. Finished.
4. **Re-measure the floor on the target surface.** 41k was measured in the
   Claude Code CLI on a machine carrying a large global skill and plugin
   listing. A different surface, or a clean install with only these two skills,
   has a different floor. Item 5 cannot be decided without that number.
5. **Decide whether the architecture fits the product.** A 2-round answer costs
   ~85k and cannot go lower; a realistic 3–4 rounds is ~150k. If that is too
   expensive for the intended use, no tool tuning fixes it — the alternative is
   a non-agentic fast path for simple lookups (one model call, no tool loop),
   with the agent reserved for genuine fit work.
