# Staticdata adapter: one data source for the engine

Feeds pyfa's engine from the same CCP static-data feed the layer-1 SDE
database builds from, killing the version skew the spike observed (pyfa
bundled build 3424810 vs CCP current 3466501). pyfa's own `db_update.py`
runs **unmodified** over files this adapter generates — we match its input
format rather than fork its build.

## Use

```bash
# 1. fetch + extract CCP's current JSONL export (same zip layer 1 uses)
curl -sSLO https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-<BUILD>-jsonl.zip
python3 -c "import zipfile; zipfile.ZipFile('eve-online-static-data-<BUILD>-jsonl.zip').extractall('sde-raw')"

# 2. generate pyfa's staticdata layout
python3 make_staticdata.py --sde-raw sde-raw --out staticdata-gen --build <BUILD>

# 3. swap into the pyfa checkout and rebuild its DB with its own script
rm -rf <pyfa>/staticdata && cp -r staticdata-gen <pyfa>/staticdata
( cd <pyfa> && rm -f eve.db && PYTHONPATH=../spike/wxstub python3 db_update.py )
```

`eve.db` then reports `client_build = <BUILD>` — the engine and the SDE
skill answer from the same build, and `engine_info()` skew checks go quiet.

## Verified

Built this way at build 3466501 and re-ran the full reference battery:
**440 stat-panel leaves compared against the pinned build-3424810
references, zero differences** (CCP changed nothing these fits touch in
those five weeks). When a future build does move numbers,
`../spike/compare_panels.py` output *is* the balance-change report.

## Format notes (found the hard way, encoded in the script)

- CCP now ships `dynamicItemAttributes.attributeIDs` as a list of
  `{_key, min, max}`; pyfa expects `{attrID: {min, max}}`.
- `dogmaEffects.description` is a localized dict in CCP data and must be
  expanded to `description_<lang>` fields like every other localized string
  (CCP "en" ⇒ pyfa "en-us").
- pyfa's `processTraits` silently drops any trait row missing one of its
  required languages — every generated row carries all of them, falling
  back to English text.
- `requiredskillsfortypes` is absent from CCP's export; it is derived from
  `typeDogma` requiredSkill attribute pairs (182/277, 183/278, 184/279,
  1285/1286, 1289/1287, 1290/1288), which is where the data originates
  anyway.
- Trait text is display-only in pyfa (real bonuses are dogma effects), so
  its HTML assembly being cosmetic is by design, not a shortcut.
