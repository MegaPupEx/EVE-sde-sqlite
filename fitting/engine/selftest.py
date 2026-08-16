"""EFT parser self-test against the pinned reference battery.

    python3 selftest.py --pyfa <pyfa-checkout>

Three checks:
1. parse: reference/battery.eft parses into 10 fits with the exact module,
   charge and drone lists battery.py defines.
2. build+calculate: fits built from the PARSED text produce stat panels
   identical to the pinned reference JSONs (the parser cannot have dropped
   or misclassified anything that matters).
3. round-trip: render_eft(build_fit(parse_eft(x))) reparses to the same spec.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.join(os.path.dirname(HERE), 'spike')
sys.path.insert(0, HERE)
sys.path.insert(0, SPIKE)

from headless import bootstrap  # noqa: E402  (spike dir)
from eft import parse_eft, build_fit, render_eft  # noqa: E402


def entry_set(spec):
    # parse is text-only: "Module, Charge" stays one line until build-time lookup
    mods = sorted(e['name'] for e in spec.entries if e['quantity'] is None)
    stacks = sorted((e['name'], e['quantity']) for e in spec.entries if e['quantity'] is not None)
    return mods, stacks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    args = ap.parse_args()
    bootstrap(args.pyfa)
    import eos.db  # noqa: F401 — must precede eos.saveddata imports
    import run_battery  # spike's statPanel, so panels are computed identically

    failures = 0

    eft_text = open(os.path.join(SPIKE, 'reference', 'battery.eft')).read()
    specs = parse_eft(eft_text)
    from battery import FITS
    assert len(specs) == len(FITS), f'{len(specs)} parsed vs {len(FITS)} defined'

    for spec, defined in zip(specs, FITS):
        # 1: parse fidelity vs battery.py definition (same joined-line form)
        want_mods = sorted(f'{n}, {c}' if c else n for n, c in defined['modules'])
        want_stacks = sorted((n, q) for n, q in defined.get('drones', ()))
        got_mods, got_stacks = entry_set(spec)
        if (got_mods, got_stacks) != (want_mods, want_stacks):
            print(f'PARSE MISMATCH {spec.name}: {got_mods} {got_stacks}')
            failures += 1
            continue

        # 2: panel identity vs pinned reference
        fit = build_fit(spec)
        panel = run_battery.statPanel(fit)
        ref = json.load(open(os.path.join(SPIKE, 'reference', f'{spec.name}.json')))['stats']
        if panel != ref:
            print(f'PANEL MISMATCH {spec.name}')
            for section in ref:
                if panel.get(section) != ref[section]:
                    print(f'  {section}: {ref[section]} -> {panel.get(section)}')
            failures += 1
            continue

        # 3: render round-trip
        rendered = render_eft(fit)
        respec = parse_eft(rendered)[0]
        if entry_set(respec) != (got_mods, got_stacks) or respec.ship != spec.ship:
            print(f'ROUNDTRIP MISMATCH {spec.name}')
            failures += 1
            continue

        print(f'ok {spec.name}')

    print(f'\n{len(specs) - failures}/{len(specs)} fits pass parse -> build -> panel -> render round-trip')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
