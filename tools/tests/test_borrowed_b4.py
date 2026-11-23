"""B4 repair.numeric_names: names the importer read as numbers ("000" -> "0", "1.01" -> "1.010000") get the VMF text back.

  python -m unittest discover -s tools/tests -p "test_borrowed_b4.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, repair, dmx

VMF = '''world
{
	"classname" "worldspawn"
}
entity
{
	"classname" "path_track"
	"targetname" "001"
	"target" "1.01"
}
entity
{
	"classname" "path_track"
	"targetname" "1.01"
}
entity
{
	"classname" "logic_relay"
	"targetname" "go"
	connections
	{
		"OnTrigger" "001\x1bEnable\x1b\x1b0\x1b-1"
	}
}
entity
{
	"classname" "info_target"
	"targetname" "07"
}
entity
{
	"classname" "info_target"
	"targetname" "7"
}
'''


class Ctx:
    def __init__(s): s.log = []; s.todo = []


class NumericNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.vmf = os.path.join(self.tmp, 'm.vmf')
        with open(self.vmf, 'w', encoding='utf-8') as fh: fh.write(VMF)
        m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
        self.a = m.new_entity('path_track', [0, 0, 0], {'targetname': '1', 'target': '1.010000'})
        self.b = m.new_entity('path_track', [64, 0, 0], {'targetname': '1.010000'})
        r = m.new_entity('logic_relay', [0, 64, 0], {'targetname': 'go'})
        m.add_conn(r, 'OnTrigger', '1', 'Enable')
        self.c7 = m.new_entity('info_target', [0, 0, 64], {'targetname': '7'})
        self.m = m; self.relay = r

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_forms(self):
        self.assertEqual(repair.imported_form('000'), '0')
        self.assertEqual(repair.imported_form('1.01'), '1.010000')
        self.assertIsNone(repair.imported_form('7')); self.assertIsNone(repair.imported_form('door1'))

    def test_restore(self):
        c = Ctx()
        n = repair.numeric_names(self.m, c, self.vmf)
        m = self.m
        self.assertEqual((m.name(self.a), m.P(self.a, 'target'), m.name(self.b)), ('001', '1.01', '1.01'))
        self.assertEqual(m.conn_tuple(m.conns(self.relay)[0])[1], '001')
        self.assertEqual(m.name(self.c7), '7')                     # "07" and "7" both import as "7": left, and listed
        self.assertEqual(n, 4)
        self.assertTrue(c.todo and '"7"' in c.todo[0])
        self.assertEqual(repair.numeric_names(m, Ctx(), self.vmf), 0)   # rerun changes nothing


if __name__ == '__main__':
    unittest.main()
