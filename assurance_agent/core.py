"""Deterministic control tests and security-standard diffing.

No LLM outputs can influence PASS/FAIL. JSON fixtures represent synthetic systems.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Finding:
    id: str
    title: str
    severity: str
    status: str
    field: str
    expected: Any
    observed: Any
    source: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def digest(value: Any) -> str:
    content = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(content).hexdigest()


def get_path(obj: dict, dotted_path: str) -> tuple[bool, Any]:
    cursor: Any = obj
    for part in dotted_path.split('.'):
        if not isinstance(cursor, dict) or part not in cursor:
            return False, None
        cursor = cursor[part]
    return True, cursor


def apply(operator: str, actual: Any, expected: Any) -> bool:
    if operator == 'eq':
        # Keep booleans and integers distinct: True is 1 in Python.
        return type(actual) is type(expected) and actual == expected
    if operator == 'lte':
        if type(actual) not in (int, float) or type(expected) not in (int, float):
            raise ValueError('lte requires numeric values')
        return actual <= expected
    if operator == 'gte':
        if type(actual) not in (int, float) or type(expected) not in (int, float):
            raise ValueError('gte requires numeric values')
        return actual >= expected
    raise ValueError(f'unsupported operator: {operator}')


def assess(controls: list[dict], state: dict, evidence_sources: dict[str, str]) -> list[Finding]:
    results = []
    for control in controls:
        key = control['field']
        exists, actual = get_path(state, key)
        source = evidence_sources.get(key, 'system snapshot') if exists else 'none'
        if not exists or actual is None:
            status, reason = 'UNKNOWN', 'Evidence is missing; compliance cannot be determined.'
        else:
            try:
                passed = apply(control['operator'], actual, control['expected'])
                status = 'PASS' if passed else 'FAIL'
                reason = ('Observed state satisfies the specified check.' if passed
                          else 'Observed state does not satisfy the specified check.')
            except ValueError as exc:
                status, reason = 'ERROR', str(exc)
        results.append(Finding(
            id=control['id'], title=control['title'], severity=control['severity'],
            status=status, field=key, expected=control['expected'],
            observed=actual if exists else None, source=source, explanation=reason,
        ))
    return results


def _collect_controls(node: dict) -> list[dict]:
    """Accept OSCAL-like catalog objects, including nested groups/controls."""
    found: list[dict] = []
    for control in node.get('controls', []):
        parts = []
        for item in control.get('parts', []):
            # Comparison uses available text; no claim of semantic equivalence.
            parts.append(json.dumps(item, sort_keys=True, separators=(',', ':')))
        found.append({
            'id': control['id'],
            'title': control.get('title', ''),
            'parts': parts,
        })
        found.extend(_collect_controls(control))
    for group in node.get('groups', []):
        found.extend(_collect_controls(group))
    return found


def index_catalog(document: dict) -> dict[str, dict]:
    catalog = document.get('catalog', document)
    indexed: dict[str, dict] = {}
    for row in _collect_controls(catalog):
        if row['id'] in indexed:
            raise ValueError(f"duplicate catalog id: {row['id']}")
        indexed[row['id']] = row
    return indexed


def diff_catalogs(before: dict, after: dict) -> list[dict]:
    """Structural changes only; changed text may be editorial, not substantive."""
    original = index_catalog(before)
    updated = index_catalog(after)
    changes: list[dict] = []
    for cid in sorted(original.keys() | updated.keys()):
        if cid not in original:
            change = 'ADDED'
        elif cid not in updated:
            change = 'REMOVED'
        elif original[cid] != updated[cid]:
            change = 'MODIFIED'
        else:
            continue
        changes.append({
            'control_id': cid,
            'change': change,
            'before': original.get(cid),
            'after': updated.get(cid),
        })
    return changes
