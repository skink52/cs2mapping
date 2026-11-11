"""pclocal.py apply / rollback against a stand-in CS2 folder in a temp dir (real files; no CS2, no junction to a real addon).

  python -m unittest discover -s autoport/tests -p "test_pclocal.py" -v
"""
import contextlib, glob, io, json, os, shutil, sys, tempfile, unittest
from unittest import mock
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


class Deliver(unittest.TestCase):
    """deliver: prep.py's [staged, PC path] pairs. CS2 and the Source 1 workspace are stand-in folders."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pclocal_')
        self.cs2 = os.path.join(self.tmp, 'Program Files (x86)', 'cs2'); self.s1 = os.path.join(self.tmp, 'source1')
        self.root = os.path.join(self.s1, 'cs2port', 'work'); self.staged = os.path.join(self.tmp, 'prep', 'pc')
        os.makedirs(self.cs2); os.makedirs(self.s1)
        self._old = (pclocal.CS2, pclocal.S1); pclocal.CS2, pclocal.S1 = self.cs2, self.s1
        self.vmf = os.path.join(self.s1, 'maps', 'mg_test.vmf'); self.zip = os.path.join(self.s1, 'cs2port', 'assets', 'mg_test.zip')
        self.info = os.path.join(self.cs2, 'content', 'csgo_addons', 'mg_test', 'addoninfo.txt')
        self.pairs = []
        for name, dst, data in (('a.vmf', self.vmf, b'vmf'), ('a.zip', self.zip, b'zip bytes'), ('addoninfo.txt', self.info, b'info')):
            put(os.path.join(self.staged, name), data); self.pairs.append([os.path.join(self.staged, name), dst])

    def tearDown(self):
        pclocal.CS2, pclocal.S1 = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def manifest(self, pairs=None, raw=None):
        p = os.path.join(self.tmp, 'manifest_%d.json' % len(os.listdir(self.tmp)))
        with open(p, 'w', encoding='utf-8') as f: f.write(raw if raw is not None else json.dumps(self.pairs if pairs is None else pairs))
        return p

    def snapshot(self):
        return {os.path.relpath(os.path.join(dp, f), self.tmp): get(os.path.join(dp, f))
                for base in (self.cs2, self.s1) for dp, _, fs in os.walk(base) for f in fs}

    def quiet(self, *a, **k):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): out = pclocal.deliver(*a, root=self.root, **k)
        return out, buf.getvalue()

    def refused(self, manifest, force=False):
        before = self.snapshot()
        with self.assertRaises(SystemExit) as cm: pclocal.deliver([manifest], force, root=self.root)
        self.assertEqual(self.snapshot(), before, 'a refused delivery must change nothing')
        return str(cm.exception)

    def test_delivers_and_rolls_back(self):
        man, text = self.quiet([self.manifest()], False)
        self.assertIn('3 files delivered', text)                                   # the line autoport has always logged
        self.assertEqual((get(self.vmf), get(self.zip), get(self.info)), (b'vmf', b'zip bytes', b'info'))
        self.assertTrue(man['complete']); self.assertTrue(all(f['after'] for f in man['files']))
        self.assertFalse([f for dp, _, fs in os.walk(self.tmp) for f in fs if f.endswith('.part')])
        record = glob.glob(os.path.join(self.root, 'out', 'deliver_*.json'))[0]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): out = pclocal.rollback(record, self.root)
        self.assertEqual(len(out['removed']), 3)
        self.assertFalse(os.path.exists(self.vmf))

    def test_dry_run_changes_nothing(self):
        put(self.vmf, b'an older decompile')
        before = self.snapshot()
        man, text = self.quiet([self.manifest()], False, dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(os.path.exists(self.root))                                # no manifest, no backup folder
        self.assertIn('would create 2 and overwrite 1', text); self.assertIn('stops unless --force', text)

    def test_existing_file_stops_unless_forced_then_is_backed_up(self):
        put(self.vmf, b'an older decompile')
        self.assertIn('--force', self.refused(self.manifest()))
        man, _ = self.quiet([self.manifest()], True)
        self.assertEqual(get(self.vmf), b'vmf')
        rec = [f for f in man['files'] if f['dst'] == self.vmf][0]
        self.assertEqual(get(rec['backup']), b'an older decompile')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): pclocal.rollback(glob.glob(os.path.join(self.root, 'out', 'deliver_*.json'))[0], self.root)
        self.assertEqual(get(self.vmf), b'an older decompile'); self.assertFalse(os.path.exists(self.zip))

    def test_identical_files_are_not_rewritten(self):
        self.quiet([self.manifest()], False)
        t = os.path.getmtime(self.vmf); n = len(glob.glob(os.path.join(self.root, 'out', 'deliver_*.json')))
        man, text = self.quiet([self.manifest()], False)
        self.assertEqual(os.path.getmtime(self.vmf), t); self.assertEqual(man['files'], [])
        self.assertEqual(len(glob.glob(os.path.join(self.root, 'out', 'deliver_*.json'))), n)

    def test_destinations_outside_the_allowed_folders_are_refused(self):
        outside = os.path.join(self.tmp, 'elsewhere', 'x.txt')
        for dst in (outside, os.path.join(self.cs2, '..', '..', 'elsewhere', 'x.txt'), 'relative\\x.txt', self.cs2):
            msg = self.refused(self.manifest([[self.pairs[0][0], dst]] + self.pairs[1:]))
            self.assertIn('nothing copied', msg)
        self.assertFalse(os.path.exists(outside))

    def test_bad_manifests_are_refused(self):
        self.assertIn('missing', self.refused(self.manifest([[os.path.join(self.staged, 'gone.vmf'), self.vmf]] + self.pairs[1:])))
        self.assertIn('two files', self.refused(self.manifest(self.pairs + [[self.pairs[1][0], self.vmf]])))
        for raw in ('{not json', '{"a": 1}', '[["only one"]]', '[[1, 2]]'):
            self.assertIn('nothing copied', self.refused(self.manifest(raw=raw)))
        self.assertIn('cannot read', self.refused(os.path.join(self.tmp, 'no_such_manifest.json')))

    def test_copy_that_does_not_match_its_source_is_caught(self):
        import safepath
        real = shutil.copyfile
        def corrupting(src, dst, *a, **k):                                         # the disk hands back different bytes for one file
            real(src, dst, *a, **k)
            if src.endswith('a.zip'):
                with open(dst, 'r+b') as f: f.write(b'XXX')
        put(self.zip, b'the zip from last time')
        with mock.patch.object(safepath.shutil, 'copyfile', corrupting):
            with self.assertRaises(SystemExit) as cm: pclocal.deliver([self.manifest()], True, root=self.root)
        self.assertIn('did not verify', str(cm.exception)); self.assertIn('rollback', str(cm.exception))
        self.assertEqual(get(self.zip), b'the zip from last time')                 # the bad copy never replaced the existing file
        self.assertFalse(os.path.exists(self.zip + '.part'))
        self.assertFalse(os.path.exists(self.info))                                # the run stopped there
        record = glob.glob(os.path.join(self.root, 'out', 'deliver_*.json'))[0]
        with open(record, encoding='utf-8') as f: self.assertFalse(json.load(f)['complete'])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): pclocal.rollback(record, self.root)   # the interrupted run can be undone from its record
        self.assertFalse(os.path.exists(self.vmf))


if __name__ == '__main__':
    unittest.main()
