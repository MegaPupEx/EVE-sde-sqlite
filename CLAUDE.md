# Project notes for Claude

- **Subagents run on Sonnet** (`model: "sonnet"`) unless the user explicitly
  states otherwise — owner directive 2026-08-18 after a Fable-model eval run
  consumed the account's session budget. This applies to eval subjects,
  review agents, and any other spawned agents.
- Product target for the skill stack: the owner's chat sessions on Fable at
  medium effort; evals run on Sonnet as the affordable proxy floor — a stack
  that works on Sonnet works above it.
- Layer docs: `docs/spike-log.md` is the running findings journal;
  `fitting/evals/` holds eval generations (questions + pinned keys + results).
