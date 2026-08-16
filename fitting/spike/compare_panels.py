"""Diff two directories of battery stat panels, leaf by leaf.

    python3 compare_panels.py <reference_dir> <candidate_dir> [--tol 0.001]

The grading tool the spike's decision criterion calls for: candidate-engine
panels vs the pinned pyfa references — and equally, same engine on a newer
data build, where the diff IS the balance-change report between builds.
Non-numeric leaves must match exactly; numeric leaves within relative
tolerance (default 0.1%). meta.* is informational and skipped.
"""
import argparse
import json
import os
import sys


def leaves(obj, prefix=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f'{prefix}.{k}' if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, f'{prefix}[{i}]')
    else:
        yield prefix, obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference')
    ap.add_argument('candidate')
    ap.add_argument('--tol', type=float, default=0.001, help='relative tolerance for numbers')
    args = ap.parse_args()

    ref_files = sorted(f for f in os.listdir(args.reference) if f.endswith('.json'))
    total = diffs = missing = 0
    for fn in ref_files:
        ref = json.load(open(os.path.join(args.reference, fn)))
        cand_path = os.path.join(args.candidate, fn)
        if not os.path.exists(cand_path):
            print(f'MISSING {fn}')
            missing += 1
            continue
        cand = json.load(open(cand_path))
        ref_leaves = dict(leaves(ref.get('stats', ref)))
        cand_leaves = dict(leaves(cand.get('stats', cand)))
        for path, rv in ref_leaves.items():
            total += 1
            cv = cand_leaves.get(path, '<absent>')
            if isinstance(rv, (int, float)) and isinstance(cv, (int, float)) and not isinstance(rv, bool):
                scale = max(abs(rv), abs(cv), 1e-9)
                if abs(rv - cv) / scale > args.tol:
                    print(f'{fn[:-5]:26} {path:55} {rv} -> {cv}')
                    diffs += 1
            elif rv != cv:
                print(f'{fn[:-5]:26} {path:55} {rv!r} -> {cv!r}')
                diffs += 1
        for path in cand_leaves.keys() - ref_leaves.keys():
            print(f'{fn[:-5]:26} {path:55} <absent> -> {cand_leaves[path]!r}')
            diffs += 1
    print(f'\n{total} leaves compared: {diffs} differ, {missing} files missing')
    sys.exit(1 if (diffs or missing) else 0)


if __name__ == '__main__':
    main()
