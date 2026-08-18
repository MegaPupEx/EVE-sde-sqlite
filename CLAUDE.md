# Project notes for Claude

- **Subagents run on Sonnet** (`model: "sonnet"`) unless the user explicitly
  states otherwise — owner directive 2026-08-18 after a Fable-model eval run
  consumed the account's session budget. This applies to eval subjects,
  review agents, and any other spawned agents.
- Product target for the skill stack: **Sonnet at medium effort** (owner
  correction 2026-08-18; an earlier note said Fable-mid — wrong). Eval
  subagents therefore run the product model; note they inherit the
  session's reasoning effort, which may sit above medium — read results
  as slightly optimistic on the self-checking axis.
- Layer docs: `docs/spike-log.md` is the running findings journal;
  `fitting/evals/` holds eval generations (questions + pinned keys + results).
