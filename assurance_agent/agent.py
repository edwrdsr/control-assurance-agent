"""A bounded, read-only assurance agent with an auditable tool-use sequence.

This is an autonomous, deterministic agent workflow, not an LLM-powered planner.
It invokes named tools based on findings and a strict step budget. A human
retains authority over any remediation or policy change.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .core import assess, diff_catalogs, digest, get_path


class AssuranceAgent:
    def __init__(self, max_evidence_lookups: int = 5):
        if max_evidence_lookups < 0:
            raise ValueError('lookup budget must be nonnegative')
        self.budget = max_evidence_lookups
        self.trace: list[dict[str, Any]] = []

    def _tool(self, name: str, inputs: dict, result: dict):
        self.trace.append({
            'step': len(self.trace) + 1,
            'tool': name,
            'inputs_sha256': digest(inputs),
            'result_sha256': digest(result),
        })

    def run(self, *, controls: list[dict], snapshot: dict, evidence: dict,
            before: dict, after: dict, mappings: dict) -> dict:
        self.trace = []
        state = copy.deepcopy(snapshot['state'])
        provenance = {k: f"snapshot:{snapshot['system']}" for k in flatten_paths(state)}
        findings = assess(controls, state, provenance)
        self._tool('evaluate_controls', {'controls': controls, 'state': state},
                   {'statuses': {r.id: r.status for r in findings}})

        lookups: list[dict] = []
        remaining = self.budget
        # Agent investigates UNKNOWN controls using only the approved local evidence tool.
        for item in findings:
            if item.status != 'UNKNOWN' or remaining == 0:
                continue
            remaining -= 1
            found, value = get_path(evidence.get('fields', {}), item.field)
            result = {'found': found, 'field': item.field, 'value': value if found else None}
            self._tool('lookup_local_evidence', {'field': item.field}, result)
            lookups.append({'field': item.field, 'found': found})
            if found:
                set_path(state, item.field, value)
                provenance[item.field] = f"fixture-evidence:{evidence.get('source', 'unknown')}"

        reevaluated = assess(controls, state, provenance)
        self._tool('evaluate_controls', {'controls': controls, 'state': state},
                   {'statuses': {r.id: r.status for r in reevaluated}})
        changes = diff_catalogs(before, after)
        self._tool('compare_catalog_versions', {'before': before, 'after': after},
                   {'changes': [{'control_id': c['control_id'], 'change': c['change']} for c in changes]})
        for change in changes:
            change['mapped_tests'] = mappings.get(change['control_id'], [])
            change['requires_human_review'] = True

        status_count = {status: sum(r.status == status for r in reevaluated)
                        for status in ('PASS', 'FAIL', 'UNKNOWN', 'ERROR')}
        requests = [
            {'control_id': r.id, 'recommended_action':
                ('Investigate nonconforming state and validate with a control owner.'
                 if r.status == 'FAIL' else
                 'Obtain authoritative evidence from the control owner.'
                 if r.status == 'UNKNOWN' else
                 'Resolve evaluation error before any conclusion.')}
            for r in reevaluated if r.status != 'PASS'
        ]
        requests.extend({
            'control_id': c['control_id'],
            'recommended_action': 'Review standards change and associated organizational tests: '
                                  + ', '.join(c['mapped_tests'] or ['none mapped']) + '.',
        } for c in changes)
        return {
            'kind': 'bounded_offline_assurance_demo',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'system': snapshot['system'],
            'inputs_sha256': {k: digest(v) for k, v in {
                'controls': controls, 'snapshot': snapshot, 'evidence': evidence,
                'baseline_catalog': before, 'updated_catalog': after, 'mappings': mappings,
            }.items()},
            'counts': status_count,
            'findings': [r.to_dict() for r in reevaluated],
            'investigations': lookups,
            'standards_changes': changes,
            'human_review_requests': requests,
            'trace': self.trace,
            'constraints': [
                'All input files are synthetic or locally supplied.',
                'No external API calls, LLM calls, or remediation actions.',
                'Catalog comparison is structural, not a legal or compliance conclusion.',
                'Every suggested next step requires a human reviewer.',
            ],
        }


def flatten_paths(node: dict, prefix: str = '') -> list[str]:
    paths = []
    for k, val in node.items():
        full = f'{prefix}.{k}' if prefix else k
        if isinstance(val, dict):
            paths.extend(flatten_paths(val, full))
        else:
            paths.append(full)
    return paths


def set_path(node: dict, path: str, value: Any) -> None:
    parts = path.split('.')
    target = node
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value
