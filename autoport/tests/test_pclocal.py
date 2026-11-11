"""pclocal.py apply / rollback against a stand-in CS2 folder in a temp dir (real files; no CS2, no junction to a real addon).

  python -m unittest discover -s autoport/tests -p "test_pclocal.py" -v
"""
import contextlib, glob, io, json, os, shutil, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pclocal


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(data)


def get(path):
    with open(path, 'rb') as f: return f.read()


class Apply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pclocal_')
        self.cs2 = os.path.join(self.tmp, 'Program Files (x86)', 'cs2'); self.root = os.path.join(self.tmp, 'work')
        self._cs2, pclocal.CS2 = pclocal.CS2, self.cs2
        self.content = os.path.join(self.cs2, 'content', 'csgo_addons', 'mg_test'); self.game = os.path.join(self.cs2, 'game', 'csgo_addons', 'mg_test')
        put(os.path.join(self.content, 'maps', 'mg_test.vmap'), b'importer output')
        put(os.path.join(self.content, 'materials', 'wall.vmat'), b'old material')
        put(os.path.join(self.root, 'out', 'mg_test', 'maps', 'mg_test.vmap'), b'stage C output')
        put(os.path.join(self.root, 'out', 'mg_test', 'materials', 'wall.vmat'), b'new material')
        put(os.path.join(self.root, 'out', 'mg_test', 'maps', 'scripts', 'mg_test_io.js'), b'// script')
        put(os.path.join(self.root, 'out', 'mg_test_game', 'resource', 'overviews', 'mg_test.txt'), b'radar')

    def tearDown(self):
        pclocal.CS2 = self._cs2
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_quiet(self, fn, *a, **k):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): out = fn(*a, **k)
        return out, buf.getvalue()

    def test_dry_run_lists_and_changes_nothing(self):
        man, text = self.run_quiet(pclocal.apply, 'mg_test', self.root, dry_run=True)
        self.assertIn('DRY RUN', text); self.assertIn('would create 2 and overwrite 2', text)
        self.assertEqual(get(os.path.join(self.content, 'maps', 'mg_test.vmap')), b'importer output')
        self.assertFalse(os.path.exists(self.game))
        self.assertEqual(glob.glob(os.path.join(self.root, 'out', '*_apply_*.json')), [])
        self.assertFalse(os.path.exists(os.path.join(self.root, 'apply_backups')))

    def test_apply_then_rollback(self):
        man, text = self.run_quiet(pclocal.apply, 'mg_test', self.root)
        self.assertIn('4 changed files copied back for mg_test', text)                  # the line autoport's log has always had
        self.assertEqual(get(os.path.join(self.content, 'maps', 'mg_test.vmap')), b'stage C output')
        self.assertEqual(get(os.path.join(self.game, 'resource', 'overviews', 'mg_test.txt')), b'radar')
        baks = glob.glob(os.path.join(self.content, 'maps', 'mg_test.vmap.bak_*'))
        self.assertEqual(len(baks), 1); self.assertEqual(get(baks[0]), b'importer output')   # the map's backup stays next to it
        rec = {f['rel']: f for f in man['files']}
        self.assertEqual(get(rec['content/materials/wall.vmat']['backup']), b'old material')
        self.assertTrue(rec['content/materials/wall.vmat']['backup'].startswith(os.path.join(self.root, 'apply_backups', 'mg_test')))
        manifests = glob.glob(os.path.join(self.root, 'out', 'mg_test_apply_*.json'))
        self.assertEqual(len(manifests), 1); self.assertTrue(json.load(open(manifests[0], encoding='utf-8'))['complete'])

        again, text = self.run_quiet(pclocal.apply, 'mg_test', self.root)               # nothing differs now
        self.assertIn('0 changed files', text)

        out, text = self.run_quiet(pclocal.rollback, manifests[0], self.root)
        self.assertEqual((len(out['restored']), len(out['removed']), out['skipped']), (2, 2, []))
        self.assertEqual(get(os.path.join(self.content, 'maps', 'mg_test.vmap')), b'importer output')
        self.assertEqual(get(os.path.join(self.content, 'materials', 'wall.vmat')), b'old material')
        self.assertFalse(os.path.exists(os.path.join(self.content, 'maps', 'scripts', 'mg_test_io.js')))

    def test_bad_addon_names_touch_nothing(self):
        put(os.path.join(self.root, 'out', 'evil', 'x.txt'), b'x')
        for name in ('..', '../evil', '..\\evil', 'a/b', ''):
            with self.assertRaises(ValueError, msg=repr(name)): pclocal.apply(name, self.root)
        self.assertEqual(get(os.path.join(self.content, 'maps', 'mg_test.vmap')), b'importer output')

    def test_rollback_by_addon_name_and_missing_manifest(self):
        self.run_quiet(pclocal.apply, 'mg_test', self.root)
        out, _ = self.run_quiet(pclocal.rollback, 'mg_test', self.root, dry_run=True)
        self.assertEqual(len(out['restored']), 2)
        self.assertEqual(get(os.path.join(self.content, 'maps', 'mg_test.vmap')), b'stage C output')   # dry run
        with self.assertRaises(SystemExit): pclocal.rollback('mg_other', self.root)


if __name__ == '__main__':
    unittest.main()
