import unittest
from assurance_agent.core import apply, assess, diff_catalogs
from assurance_agent.agent import AssuranceAgent


class CoreTests(unittest.TestCase):
    def test_type_safe_equality(self):
        self.assertFalse(apply('eq', 1, True))

    def test_missing_evidence_is_unknown(self):
        c = [{'id': 'X', 'title': 'x', 'field': 'a', 'operator': 'eq', 'expected': True, 'severity': 'high'}]
        self.assertEqual(assess(c, {}, {})[0].status, 'UNKNOWN')

    def test_wrong_type_is_error(self):
        c = [{'id': 'X', 'title': 'x', 'field': 'a', 'operator': 'lte', 'expected': 30, 'severity': 'high'}]
        self.assertEqual(assess(c, {'a': 'today'}, {})[0].status, 'ERROR')

    def test_diff_added_and_modified(self):
        before = {'catalog': {'controls': [{'id':'a','title':'A'}, {'id':'b','title':'B'}]}}
        after = {'catalog': {'controls': [{'id':'a','title':'A2'}, {'id':'b','title':'B'}, {'id':'c','title':'C'}]}}
        self.assertEqual([(x['control_id'], x['change']) for x in diff_catalogs(before, after)],
                         [('a','MODIFIED'), ('c','ADDED')])

    def test_no_changes(self):
        same = {'catalog': {'controls': [{'id':'a','title':'A'}]}}
        self.assertEqual(diff_catalogs(same, same), [])

    def test_evidence_lookup_and_approval_boundary(self):
        controls = [{'id': 'BK', 'title': 'Backups', 'field': 'backup.days', 'operator': 'lte',
                     'expected': 30, 'severity': 'high'}]
        agent = AssuranceAgent(max_evidence_lookups=1)
        result = agent.run(controls=controls, snapshot={'system': 'test', 'state': {}},
                           evidence={'fields': {'backup': {'days': 15}}, 'source': 'demo'},
                           before={'catalog': {'controls': []}},
                           after={'catalog': {'controls': []}}, mappings={})
        self.assertEqual(result['findings'][0]['status'], 'PASS')
        self.assertEqual(result['findings'][0]['source'], 'fixture-evidence:demo')
        self.assertTrue(any(t['tool']=='lookup_local_evidence' for t in result['trace']))

    def test_budget_keeps_missing_evidence_unknown(self):
        controls = [{'id': 'BK', 'title': 'Backups', 'field': 'backup.days', 'operator': 'lte',
                     'expected': 30, 'severity': 'high'}]
        result = AssuranceAgent(0).run(
            controls=controls, snapshot={'system': 'test', 'state': {}},
            evidence={'fields': {'backup': {'days': 15}}},
            before={'catalog': {'controls': []}},
            after={'catalog': {'controls': []}}, mappings={})
        self.assertEqual(result['findings'][0]['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
