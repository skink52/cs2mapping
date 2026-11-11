"""mapbackup.py: compressed copies, dedupe, tiers, pins, restore (with its own undo), source snapshots, addon scan.

  python -m unittest discover -s tools/tests -p "test_mapbackup.py" -v
"""
import contextlib, datetime as dt, io, os, shutil, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import mapbackup as B


class Backups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='cs2mcp_bak_')
        self.store = B.Store(os.path.join(self.tmp, 'store'))
        self.addon = os.path.join(self.tmp, 'addon'); os.makedirs(os.path.join(self.addon, 'maps'))
        os.makedirs(os.path.join(self.addon, 'materials'))
        self.vmap = os.path.join(self.addon, 'maps', 'm.vmap')
        F.write(self.vmap, b'version 1' * 1000, 'wb')
        F.write(os.path.join(self.addon, 'materials', 'a.vmat'), 'Layer0 { shader "csgo_complex.vfx" }')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_dedupe_restore(self):
        e1 = self.store.save(self.vmap, sources=[self.addon])
        self.assertLess(e1['packed'], e1['size'])
        self.assertIsNone(self.store.save(self.vmap))                     # same bytes: skipped
        F.write(self.vmap, b'version 2' * 1000, 'wb')
        self.store.save(self.vmap)
        self.assertEqual(len(self.store.entries('m')), 2)
        r = self.store.restore('m', e1['stamp'])
        with open(self.vmap, 'rb') as f: self.assertEqual(f.read(), b'version 1' * 1000)
        self.assertEqual(self.store.read(self.store.entries('m')[-1]), b'version 2' * 1000)   # version 2 is still kept
        F.write(self.vmap, b'hand edit' * 1000, 'wb')                     # an edit nobody backed up ...
        self.store.restore('m', e1['stamp'])
        self.assertEqual(self.store.entries('m')[-1]['kind'], 'before-restore')                # ... is saved before the restore
        other = os.path.join(self.tmp, 'copy.vmap')
        self.store.restore('m', 'latest', to=other)
        with self.assertRaises(FileExistsError): self.store.restore('m', 'latest', to=other)

    def test_tiers(self):
        now = dt.datetime(2026, 11, 10, 12, 0, 0)
        stamps = []
        for minutes in range(0, 60 * 24 * 40, 30):                         # a copy every 30 minutes for 40 days
            stamps.append((now - dt.timedelta(minutes=minutes)).strftime(B.STAMP))
        stamps.sort()
        keep = B.Store.keep_set(stamps, now)
        self.assertTrue(set(stamps[-3:]) <= keep)                           # newest 3
        self.assertLess(len(keep), 3 + 25 + 15 + 9)                         # hourly + daily + weekly buckets, overlapping
        self.assertGreater(len(keep), 30)
        self.assertIn(stamps[0], keep)                                     # 40 days old: the oldest of its week (8 weekly buckets)
        self.assertNotIn(stamps[1], keep)                                  # same week, not the oldest

    def test_trim_and_pin(self):
        base = dt.datetime(2026, 1, 1)
        for i in range(6):
            F.write(self.vmap, ('v%d' % i).encode() * 100, 'wb')
            self.store.save(self.vmap, now=base + dt.timedelta(seconds=i))
        es = self.store.entries('m')
        self.assertEqual(len(es), 4)                                        # newest 3 + the oldest of that hour / day / week
        first = es[0]['stamp']
        later = base + dt.timedelta(days=400)
        self.assertEqual(self.store.trim('m', now=later, dry_run=True), [first])   # its buckets have expired
        self.store.pin('m', first, 'milestone')
        self.assertEqual(self.store.trim('m', now=later), [])               # pinned copies stay forever
        self.assertEqual(len(self.store.entries('m')), 4)

    def test_sources_snapshot_dedupe_and_restore(self):
        s1 = self.store.snapshot([self.addon])
        time.sleep(0.01)
        s2 = self.store.snapshot([self.addon])
        objs = sum(len(fs) for _, _, fs in os.walk(os.path.join(self.store.root, 'sources', 'objects')))
        self.assertEqual(objs, 1)                                           # the vmap is left out; the vmat is stored once
        out = os.path.join(self.tmp, 'restored')
        r = self.store.restore_sources(s2, out)
        self.assertEqual(r['files'], 1)
        self.assertTrue(os.path.exists(os.path.join(out, 'addon', 'materials', 'a.vmat')))
        self.assertNotEqual(s1, s2)

    def test_scan(self):
        old = time.time() - 600
        os.utime(self.vmap, (old, old))
        done = self.store.scan(self.addon)
        self.assertEqual([d['map'] for d in done], ['m.vmap'])
        self.assertEqual(self.store.scan(self.addon), [])                   # unchanged: nothing new
        self.assertIsNotNone(self.store.entries('m')[-1]['sources'])
        F.write(self.vmap, b'fresh', 'wb')                                  # just written: may still be saving
        self.assertEqual(self.store.scan(self.addon), [])

    def test_cli(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(B.main(['save', self.vmap, '--store', self.store.root, '--pin', 'v1']), 0)
        self.assertEqual(self.store.entries('m')[0]['pin'], 'v1')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(B.main(['restore', 'nothing', '--store', self.store.root]), 2)

    def test_damaged_copy_is_caught_and_restore_changes_nothing(self):
        e = self.store.save(self.vmap)
        self.assertEqual(self.store.verify(), {'checked': 1, 'bad': []})
        F.write(self.vmap, b'work since the backup', 'wb')
        with open(e and self.store.entries('m')[0]['file'], 'r+b') as f:          # flip bytes in the middle of the stored copy
            f.seek(20); f.write(b'\x00\x00\x00\x00')
        bad = self.store.verify('m')
        self.assertEqual((bad['checked'], len(bad['bad'])), (1, 1))
        with self.assertRaises(OSError): self.store.restore('m')
        with open(self.vmap, 'rb') as f: self.assertEqual(f.read(), b'work since the backup')   # not overwritten
        self.assertEqual(len(self.store.entries('m')), 1)                          # and no "before-restore" copy was made
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(B.main(['verify', '--store', self.store.root]), 1)

    def test_recorded_hash_must_match(self):
        import json
        self.store.save(self.vmap)
        e = self.store.entries('m')[0]; jp = e['file'][:-len('.vmap.xz')] + '.json'
        meta = json.load(open(jp, encoding='utf-8')); meta['sha256'] = '0' * 64
        F.write(jp, json.dumps(meta))
        self.assertEqual(len(self.store.verify()['bad']), 1)
        with self.assertRaises(OSError): self.store.restore('m', to=os.path.join(self.tmp, 'elsewhere.vmap'))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'elsewhere.vmap')))


if __name__ == '__main__':
    unittest.main()
