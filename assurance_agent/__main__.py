import argparse
import json
from pathlib import Path
from .agent import AssuranceAgent
from .report import write_outputs


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def main():
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description='Bounded offline control assurance agent (synthetic data).')
    p.add_argument('--data', type=Path, default=root / 'data', help='Directory with synthetic or local JSON inputs')
    p.add_argument('--out', type=Path, default=root / 'out', help='Report output folder')
    p.add_argument('--lookup-budget', type=int, default=5)
    args = p.parse_args()
    inputs = {name: load(args.data / file) for name, file in {
        'control_doc': 'controls.json', 'snapshot': 'snapshot.json', 'evidence': 'evidence.json',
        'before': 'catalog-before.json', 'after': 'catalog-after.json', 'mappings': 'mappings.json',
    }.items()}
    result = AssuranceAgent(args.lookup_budget).run(
        controls=inputs['control_doc']['controls'], snapshot=inputs['snapshot'],
        evidence=inputs['evidence'], before=inputs['before'],
        after=inputs['after'], mappings=inputs['mappings'],
    )
    write_outputs(result, args.out)
    print(f"Controls: {result['counts']} | Standards changes: {len(result['standards_changes'])}")
    print(f'Reports: {args.out.resolve() / "report.html"} and report.json')


if __name__ == '__main__':
    main()
