"""Emit the reference battery as EFT text for pasting into desktop pyfa.

    python3 export_eft.py --pyfa work/pyfa   >  reference/battery.eft

Purpose: the human spot-check in docs/spike-log.md. Copy one block, then in
pyfa: Edit > Import from Clipboard, set the character to All 5 and the damage
profile to Uniform, and compare the stat panel against the matching
reference/<fit>.json. pyfa's own EFT exporter lives in the wx-entangled
service layer, so this emits the format directly from eos slot data.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless import bootstrap
from battery import FITS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pyfa', default=os.environ.get('PYFA_PATH'), required='PYFA_PATH' not in os.environ)
    args = ap.parse_args()

    bootstrap(args.pyfa)
    import eos.db  # noqa: F401 — must precede eos.saveddata imports
    from eos.const import FittingSlot
    from eos.saveddata.module import Module

    order = (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH, FittingSlot.RIG,
             FittingSlot.SUBSYSTEM, FittingSlot.SERVICE)
    for spec in FITS:
        slots = {s: [] for s in order}
        for name, charge in spec['modules']:
            mod = Module(eos.db.getItem(name))
            line = f"{name}, {charge}" if charge else name
            slots.setdefault(mod.slot, []).append(line)
        print(f"[{spec['ship']}, {spec['name']}]")
        blocks = ['\n'.join(slots[s]) for s in order if slots[s]]
        print('\n\n'.join(blocks))
        if spec.get('drones'):
            print()
            for name, amount in spec['drones']:
                print(f"{name} x{amount}")
        print('\n')


if __name__ == '__main__':
    main()
