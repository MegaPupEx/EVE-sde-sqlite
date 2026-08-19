# Cost experiments — gen-8 ten questions, three runs (2026-08-19)

Same ten held-out questions each time (already burned for accuracy, so this
series measures cost only), 10 single-turn subjects, sonnet @ medium.
Tokens are **billed** — fresh input + cache reads + cache writes + output,
per-request max to dedupe streamed rows.

| run | what changed | tokens/Q (mean) | tokens/Q (median) | requests/Q | SQL calls | engine calls | mutation→get_stats pairs | sde.py uses | batched requests |
|---|---|---|---|---|---|---|---|---|---|
| gen 8 baseline | — | 511k | 507k | 10.9 | 69 | 22 | 4 | n/a | 4/109 |
| run 2 | batching guidance in eve-fitting router | 619k (+21%) | 561k | 12.8 | 61 | 41 | 4 | n/a | 9/115 |
| run 3 | + mutate→stats fold live, + layer-1 `sde.py` helper | 552k (+8%) | 504k (−0.6%) | 11.3 | 61 | 33 | **0** | **1** | 6/113 |

## What each change actually did

**The fold worked, and it is structural.** Mutation→`get_stats` pairs went
4 → 0: `import_fit`/`create_fit`/`clone_fit`/`edit_fit` now return the panel
inline, so nobody spends a round fetching numbers the mutation already had.
It required no one to read anything. It is also small — only 4 such rounds
existed across ten questions.

**The layer-1 helper failed, for a reachability reason.** `sde.py` was used
**once in 61 SQL calls**. Cause, measured: across the ten subjects the
eve-fitting skill was explicitly loaded 8 times and **eve-sde exactly once** —
and that one load is the one `sde.py` use. Guidance placed in eve-sde's router
reaches ~10% of sessions, because subjects are told where the sqlite files are
in their prompt and go straight to inline Python (47 of 61 calls) without ever
consulting layer 1's docs.

**Guidance keeps losing to structure.** Run 2's batching block moved batched
requests 4 → 9 of ~110 while engine calls rose 22 → 41, net +21%. Run 3 walked
that back toward baseline (engine 41 → 33) but the win came from the fold, not
from anything anyone read.

## Standing conclusions

1. **Cost ≈ rounds × context.** Two-thirds of rounds are one-query-per-call
   SQL; that is still where the money is, and it is untouched.
2. **Interventions rank by how little reading they require**: tool shape (fold)
   > description/trigger text > router prose > reference-file prose. Every
   measured guidance change so far has under-delivered or backfired.
3. **A doc only acts where it is loaded.** eve-sde: 1/10. Anything that must
   change SQL behaviour has to live where the reader already is (the
   eve-fitting router, loaded 8/10) or in the tool surface itself.
