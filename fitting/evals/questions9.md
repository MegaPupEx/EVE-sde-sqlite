# Eval generation 9 — cost by layer need (2026-08-19)

Purpose: measure how token cost varies with **which layers a question needs**,
and with **turn type**. 15 subjects × 3 turns:

- T1 — the categorised question
- T2 — a follow-up on the same topic (warm context, resident fits)
- T3 — an unrelated question (warm session, cold topic)

Arms: 5 subjects whose T1 needs **layer 1 only** (raw SDE lookup), 5 needing
**layer 2 only** (fit math on a supplied fit), 5 needing **both**.

Cost is the deliverable; answers are not graded against pinned keys this round.

## L1 — raw data only
1. Iteron Mark V vs Bestower cargo → T2 which aligns faster empty → T3 (L2 q)
2. Rifter blueprint minerals → T2 same for a Thrasher → T3 (L2 q)
3. Jita region + security → T2 jumps to Amarr → T3 (L2 q)
4. Drake base shield recharge time *(unitID-101 ms trap)* → T2 same for a Ferox → T3 (L2 q)
5. Best tritanium yield per m³ ore → T2 isogen instead → T3 (L2 q)

## L2 — fit math only (fit supplied in the prompt)
1. Cap stability of a supplied Vexor → T2 swap a mid → T3 (L1 q)
2. EHP of a supplied Drake vs Guristas → T2 vs Sansha → T3 (L1 q)
3. 3 gyros vs 2 gyros + tracking enhancer on a Hurricane → T2 at 30 km → T3 (L1 q)
4. Caracal vs Enyo at 15 km → T2 at 5 km → T3 (L1 q)
5. Align time of a supplied Stabber ± nanofiber → T2 add a second → T3 (L1 q)

## Both — lookup feeding fit math
1. Drake vs Guristas: which resist hole to plug → T2 cheapest module for it → T3
2. Best T1 frigate hull for a shield kite fit → T2 fit it → T3
3. Gila drone bonus vs Vexor Navy Issue → T2 which wins on a 3-min rat → T3
4. Cheapest rig to push a supplied fit past 20k EHP → T2 what it costs in speed → T3
5. Rifter passive shield regen vs a frigate rat *(ms trap + regen formula)* → T2 with a rig → T3

## Measurement note

Run on the CURRENT stack (eve-fitting MCP + skills, layer-1 access via raw
SQL). The new `eve-sde` MCP server is registered in `.mcp.json` but a session
reads that at startup, so it is NOT live for this run — these numbers are the
**baseline** the with-server run gets compared against.
