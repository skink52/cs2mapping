"""create/vsmart.py: SmartProp tree and lint on a hand-written .vsmart (no game needed)."""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'create'))
import vsmart  # noqa: E402

DOC = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->
{
	_class = "CSmartPropRoot"
	m_Variables =
	[
		{ _class = "CSmartPropVariable_Float" m_VariableName = "Spacing" m_DefaultValue = 64.0 },
		{ _class = "CSmartPropVariable_Int" m_VariableName = "Count" m_DefaultValue = "" },
	]
	m_Children =
	[
		{
			_class = "CSmartPropElement_FitOnLine"
			m_nElementID = 1
			m_Children =
			[
				{ _class = "CSmartPropElement_Model" m_nElementID = 2 m_sModelName = "models/dev/fence_panel.vmdl"
				  m_vModelScale = { m_Components = [ { m_Expression = "LinearScale()" }, 1.0, 1.0 ] } },
				{ _class = "CSmartPropElement_Model" m_nElementID = 2 m_sModelName = "models/dev/fence_post.vmdl"
				  m_SelectionCriteria = [ { _class = "CSmartPropSelectionCriteria_EndCap" m_bEnd = true } ]
				  m_vModelScale = { m_Components = [ { m_Expression = "LinearScale()" }, 1.0, 1.0 ] } },
				{ _class = "CSmartPropElement_Group" m_nElementID = 3
				  m_Modifiers = [ { _class = "CSmartPropOperation_RandomRotation" m_flAngle = { m_Expression = "360 / count" } } ]
				  m_SelectionCriteria = [ { _class = "CSmartPropSelectionCriteria_Expression" m_Expression = "Height > 10" } ] },
				{ _class = "CSmartPropElement_Group" m_nElementID = 4
				  m_Modifiers = [ { _class = "CSmartPropOperation_SetOrientation" m_Yaw = { m_Expression = "atan(spacing / max(1, Count))" } } ] },
			]
		},
	]
}
'''


class VsmartTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.vsmart')
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(DOC)

    def tearDown(self):
        os.remove(self.path)

    def test_lint_finds_each_problem_once(self):
        res = vsmart.lint(self.path)
        checks = sorted(f['check'] for f in res['findings'])
        self.assertFalse(res['clean'])
        self.assertEqual(checks.count('untyped-default'), 1)           # Count = ""
        self.assertEqual(checks.count('duplicate-element-id'), 1)      # two 2s
        self.assertEqual(checks.count('endcap-linear-scale'), 1)       # the end post, not the panel
        self.assertEqual(checks.count('unguarded-division'), 1)        # 360 / count (not "spacing / max(...)")
        self.assertEqual(checks.count('unknown-variable'), 1)          # Height; Count / spacing match case-insensitively
        self.assertNotIn('unguarded-trig', checks)                     # atan(spacing / max(...)) is guarded

    def test_tree(self):
        lines = vsmart.tree(vsmart.load(self.path))
        self.assertEqual(lines[1].strip().split()[0], 'FitOnLine')
        self.assertIn('if EndCap', lines[3])
        self.assertIn('mods RandomRotation', lines[4])

    def test_missing_model_with_content(self):
        d = tempfile.mkdtemp()
        res = vsmart.lint(self.path, content=d)
        self.assertEqual(sum(f['check'] == 'missing-model' for f in res['findings']), 2)


if __name__ == '__main__':
    unittest.main()
