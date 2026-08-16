"""Generate pyfa's staticdata/ inputs from CCP's current JSONL static-data export.

    python3 make_staticdata.py --sde-raw <dir-of-extracted-jsonl> --out <dir> [--build N]
    # then: replace <pyfa>/staticdata with <out> and run pyfa's own db_update.py

This closes the version skew between pyfa's bundled data (a Phobos client
dump on pyfa's release cadence) and the SDE build the eve-sde skill tracks:
pyfa's db_update.py runs unmodified over files we generate from the same
CCP feed the layer-1 database builds from. One data source, engine included.

Shape notes (each verified against pyfa @ 8b04f3b bundled staticdata and
db_update.py's readers — see docs/spike-log.md):
- fsd_built/* are {str(id): row} dicts chunked 10k entries per .N.json file;
  phobos/metadata and phobos/traits are lists.
- Localized dicts ({"en": ..}) become suffixed fields; CCP "en" is pyfa
  "en-us". CCP no longer ships Italian; pyfa's translation_mapping does not
  require it.
- traits: processTraits does row['traits_<lang>'] inside try/except and
  silently DROPS the row on any missing language — every row must carry all
  of en-us, fr, ja, ko, ru, zh (fall back to English text).
- requiredskillsfortypes is not in CCP's export; derived here from typeDogma
  requiredSkill attribute pairs, which is also where the data originates.
- isDefault and published arrive as JSON bools; pyfa's files use 0/1. eos
  filters on truthiness so either works, but we emit ints to match.
"""
import argparse
import json
import os
import time
import urllib.request

LANG = {'en': 'en-us', 'de': 'de', 'es': 'es', 'fr': 'fr', 'it': 'it',
        'ja': 'ja', 'ko': 'ko', 'ru': 'ru', 'zh': 'zh'}
TRAIT_LANGS = ('en-us', 'fr', 'ja', 'ko', 'ru', 'zh', 'de', 'es')
# requiredSkillN attribute -> its level attribute (dogma, layer-1 documented)
REQ_SKILL_PAIRS = {182: 277, 183: 278, 184: 279, 1285: 1286, 1289: 1287, 1290: 1288}
CHUNK = 10000


def rows(raw, name):
    with open(os.path.join(raw, f'{name}.jsonl'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def unbool(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, list):
        return [unbool(x) for x in v]
    if isinstance(v, dict):
        return {k: unbool(x) for k, x in v.items()}
    return v


def loc(out, base, d):
    for lang, text in (d or {}).items():
        if lang in LANG:
            out[f'{base}_{LANG[lang]}'] = text


def write(outdir, sub, name, data):
    d = os.path.join(outdir, sub)
    os.makedirs(d, exist_ok=True)
    if isinstance(data, list):
        chunks = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)] or [[]]
    else:
        keys = list(data)
        chunks = [{k: data[k] for k in keys[i:i + CHUNK]} for i in range(0, len(keys), CHUNK)] or [{}]
    for i, chunk in enumerate(chunks):
        with open(os.path.join(d, f'{name}.{i}.json'), 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, separators=(',', ':'))
    print(f'  {sub}/{name}: {len(data)} entries, {len(chunks)} chunk(s)')


def keyed(raw, name, rename=None, localize=(), drop=('_key',)):
    """Generic transform: JSONL -> {str(_key): row} with renames + localization."""
    rename = rename or {}
    out = {}
    for r in rows(raw, name):
        row = {}
        for k, v in r.items():
            if k in localize:
                loc(row, rename.get(k, k), v)
            elif k not in drop:
                row[rename.get(k, k)] = unbool(v)
        out[str(r['_key'])] = row
    return out


def number_str(bonus, unit_id):
    s = f'{bonus:g}'
    if unit_id == 105:
        return s + '%'
    if unit_id == 104:
        return s + 'x'
    return s


def make_traits(raw, type_names):
    """CCP typeBonus -> phobos traits: per-language display sections."""
    def section(bonuses, header):
        out = {lang: {'header': header.get(lang, header['en-us']), 'bonuses': []}
               for lang in TRAIT_LANGS}
        for b in bonuses:
            texts = b.get('bonusText', {})
            en = texts.get('en', '')
            for lang in TRAIT_LANGS:
                entry = {'text': texts.get({'en-us': 'en'}.get(lang, lang), en)}
                if 'bonus' in b:
                    entry['number'] = number_str(b['bonus'], b.get('unitID'))
                out[lang]['bonuses'].append(entry)
        return out

    data = []
    for r in rows(raw, 'typeBonus'):
        per_lang = {lang: {} for lang in TRAIT_LANGS}
        skill_sections = []
        for sk in r.get('types', ()):
            names = type_names.get(sk['_key'], {})
            header = {lang: f"{names.get({'en-us': 'en'}.get(lang, lang), names.get('en', '?'))} bonuses (per skill level):"
                      for lang in TRAIT_LANGS}
            skill_sections.append(section(sk['_value'], header))
        for lang in TRAIT_LANGS:
            if skill_sections:
                per_lang[lang]['skills'] = [s[lang] for s in skill_sections]
        for src, dst, label in ((r.get('roleBonuses'), 'role', 'Role Bonus:'),
                                (r.get('miscBonuses'), 'misc', 'Misc Bonus:')):
            if src:
                sec = section(src, {'en-us': label})
                for lang in TRAIT_LANGS:
                    per_lang[lang][dst] = sec[lang]
        row = {'typeID': r['_key']}
        for lang in TRAIT_LANGS:
            row[f'traits_{lang}'] = per_lang[lang]
        data.append(row)
    return data


def make_reqskills(raw):
    out = {}
    for r in rows(raw, 'typeDogma'):
        attrs = {a['attributeID']: a['value'] for a in r.get('dogmaAttributes', ())}
        reqs = {}
        for skill_attr, level_attr in REQ_SKILL_PAIRS.items():
            if skill_attr in attrs and level_attr in attrs:
                reqs[str(int(attrs[skill_attr]))] = int(attrs[level_attr])
        if reqs:
            out[str(r['_key'])] = reqs
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sde-raw', required=True, help='dir of extracted CCP JSONL files')
    ap.add_argument('--out', required=True, help='output staticdata dir')
    ap.add_argument('--build', type=int, help='SDE build number (fetched from CCP if omitted)')
    args = ap.parse_args()
    raw = args.sde_raw

    build = args.build
    if build is None:
        with urllib.request.urlopen(
                'https://developers.eveonline.com/static-data/tranquility/latest.jsonl', timeout=60) as r:
            build = json.loads(r.read())['buildNumber']

    type_names = {r['_key']: r.get('name', {}) for r in rows(raw, 'types')}

    write(args.out, 'fsd_built', 'types',
          keyed(raw, 'types', rename={'name': 'typeName', 'description': 'description'},
                localize=('name', 'description')))
    write(args.out, 'fsd_built', 'groups',
          keyed(raw, 'groups', rename={'name': 'groupName'}, localize=('name',)))
    write(args.out, 'fsd_built', 'categories',
          keyed(raw, 'categories', rename={'name': 'categoryName'}, localize=('name',)))
    write(args.out, 'fsd_built', 'dogmaattributes',
          keyed(raw, 'dogmaAttributes',
                rename={'attributeCategoryID': 'categoryID', 'displayName': 'displayName',
                        'tooltipDescription': 'tooltipDescription', 'tooltipTitle': 'tooltipTitle'},
                localize=('displayName', 'tooltipDescription', 'tooltipTitle')))
    write(args.out, 'fsd_built', 'dogmaeffects',
          {k: dict(v, effectID=int(k)) for k, v in
           keyed(raw, 'dogmaEffects',
                 rename={'name': 'effectName', 'effectCategoryID': 'effectCategory'},
                 localize=('description',)).items()})
    write(args.out, 'fsd_built', 'typedogma',
          {k: {'dogmaAttributes': v.get('dogmaAttributes', []),
               'dogmaEffects': v.get('dogmaEffects', [])}
           for k, v in keyed(raw, 'typeDogma').items()})
    write(args.out, 'fsd_built', 'dogmaunits',
          keyed(raw, 'dogmaUnits', localize=('displayName', 'description')))
    write(args.out, 'fsd_built', 'marketgroups',
          keyed(raw, 'marketGroups', localize=('name', 'description')))
    write(args.out, 'fsd_built', 'metagroups',
          keyed(raw, 'metaGroups', localize=('name',)))
    # CCP ships attributeIDs as [{_key, min, max}]; pyfa expects {attrID: {min, max}}
    write(args.out, 'fsd_built', 'dynamicitemattributes',
          {str(r['_key']): {
              'attributeIDs': {str(a['_key']): {k: v for k, v in a.items() if k != '_key'}
                               for a in r.get('attributeIDs', ())},
              'inputOutputMapping': r.get('inputOutputMapping', [])}
           for r in rows(raw, 'dynamicItemAttributes')})
    write(args.out, 'fsd_built', 'iconids', keyed(raw, 'icons'))
    write(args.out, 'fsd_built', 'requiredskillsfortypes', make_reqskills(raw))
    write(args.out, 'fsd_lite', 'clonegrades',
          keyed(raw, 'cloneGrades', rename={'name': 'internalDescription'}))
    write(args.out, 'fsd_lite', 'dbuffcollections', keyed(raw, 'dbuffCollections'))
    write(args.out, 'phobos', 'traits', make_traits(raw, type_names))
    write(args.out, 'phobos', 'metadata',
          [{'field_name': 'client_build', 'field_value': build},
           {'field_name': 'dump_time', 'field_value': int(time.time())}])
    print(f'staticdata generated for build {build} -> {args.out}')


if __name__ == '__main__':
    main()
