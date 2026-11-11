"""A dry run changes nothing: the file tree is compared before and after, for each tool with a --dry-run that used to write or delete
(or could), run on stand-in folders in a temp dir. No CS2, no Blender.

  python -m unittest discover -s tools/tests -p "test_dryrun.py" -v
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'create')
sys.path[:0] = [os.path.dirname(HERE), CREATE]


def put(path, data=b'x'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(data)


def tree(root):
    """every folder and every file with its bytes and modification time"""
    out = {}
    for dp, dns, fns in os.walk(root):
        for d in dns: out[os.path.relpath(os.path.join(dp, d), root) + os.sep] = None
        for f in fns:
            p = os.path.join(dp, f)
            with open(p, 'rb') as h: out[os.path.relpath(p, root)] = (h.read(), os.stat(p).st_mtime_ns)
    return out


class DryRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='dryrun_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, script, *args, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([sys.executable, '-I', os.path.join(CREATE, script)] + list(args), capture_output=True, text=True, env=e, cwd=self.tmp)

    def test_blenderkit(self):
        import blenderkit
        content = os.path.join(self.tmp, 'content'); put(os.path.join(content, 'keep.txt'))
        before = tree(self.tmp)
        r = blenderkit.build(content, 'crate1', template='crate', size=(40, 40, 40), dry_run=True)
        self.assertEqual(tree(self.tmp), before)
        self.assertEqual(len(r['would_write']), 4); self.assertEqual(r['would_overwrite'], [])
        self.assertEqual(blenderkit.main([content, 'crate1', '--template', 'crate', '--dry-run']) or 0, 0)
        self.assertEqual(tree(self.tmp), before)
        self.assertEqual(blenderkit.main([content, 'crate1', '--template', 'crate', '--no-blender']) or 0, 0)   # the old meaning, under its own name
        self.assertTrue(os.path.exists(r['vmdl'])); self.assertFalse(os.path.exists(r['vmdl'][:-5] + '.fbx'))

    def test_mechkit_build_listing_only(self):
        import mechkit
        import test_mechkit
        cfg = test_mechkit.CONFIGS['abilities']
        content = os.path.join(self.tmp, 'content'); os.makedirs(content)
        files = mechkit.build(cfg, content, 'mymap', write=False)
        self.assertEqual(tree(self.tmp), {'content' + os.sep: None})
        self.assertIn('maps/scripts/mymap.js', files)
        self.assertEqual(sorted(mechkit.build(cfg, content, 'mymap')), files)        # the real run writes exactly the files the dry run listed
        for rel in files: self.assertTrue(os.path.exists(os.path.join(content, *rel.split('/'))), rel)

    def test_hats_pack_prune(self):
        out = os.path.join(self.tmp, 'cs2', 'content', 'csgo_addons', 'gmod_hats'); game = os.path.join(self.tmp, 'cs2', 'game', 'csgo_addons', 'gmod_hats')
        for hid in ('kept1', 'dropped1'):
            put(os.path.join(out, 'models', 'hats', hid, hid + '.vmdl')); put(os.path.join(out, 'materials', 'models', 'hats', hid, 'a.vmat'))
            put(os.path.join(game, 'models', 'hats', hid, hid + '.vmdl_c'))
        cat = os.path.join(self.tmp, 'catalog.json')
        with open(cat, 'w', encoding='utf-8') as f:
            json.dump({'paths': {'out': out, 'work': os.path.join(self.tmp, 'work')}, 'hats': [{'id': 'kept1'}, {'id': 'dropped1', 'chosen': False}]}, f)
        before = tree(self.tmp)
        r = self.run_tool(os.path.join('hats', 'pack.py'), cat, '--prune', '--dry-run', env={'HATS_OUT': '', 'HATS_WORK': ''})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(tree(self.tmp), before)                                      # nothing deleted, no dist folder, no zip
        self.assertIn('would prune 3', r.stdout); self.assertIn('would delete', r.stdout); self.assertIn('DRY RUN', r.stdout)
        r = self.run_tool(os.path.join('hats', 'pack.py'), cat, '--prune', '--no-zip', env={'HATS_OUT': '', 'HATS_WORK': ''})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(out, 'models', 'hats', 'dropped1')))
        self.assertTrue(os.path.exists(os.path.join(out, 'models', 'hats', 'kept1', 'kept1.vmdl')))

    def test_clean_stale(self):
        out = os.path.join(self.tmp, 'addon')
        put(os.path.join(out, 'models', 'props', 'crate', 'crate.vmdl'), b'"materials/models/props/crate/used.vmat"')
        put(os.path.join(out, 'materials', 'models', 'props', 'crate', 'used.vmat'), b'"materials/models/props/crate/used_color.png"')
        put(os.path.join(out, 'materials', 'models', 'props', 'crate', 'used_color.png'))
        put(os.path.join(out, 'materials', 'models', 'props', 'crate', 'stale.vmat'))
        props = os.path.join(self.tmp, 'props.json')
        with open(props, 'w') as f: json.dump({'crate': {}}, f)
        before = tree(self.tmp)
        env = {'CS2_ADDON_OUT': out, 'CS2_MODEL_PREFIX': 'props'}
        r = self.run_tool('clean_stale.py', props, '--dry-run', env=env)
        if os.path.exists(os.path.join(CREATE, 'toolkit.json')): self.skipTest('a local create/toolkit.json overrides the test paths')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(tree(self.tmp), before)
        self.assertIn('would remove', r.stdout); self.assertIn('stale.vmat', r.stdout)
        r = self.run_tool('clean_stale.py', props, env=env)
        self.assertFalse(os.path.exists(os.path.join(out, 'materials', 'models', 'props', 'crate', 'stale.vmat')))
        self.assertTrue(os.path.exists(os.path.join(out, 'materials', 'models', 'props', 'crate', 'used_color.png')))

    def test_mapbackup_trim(self):
        import datetime as dt, mapbackup
        vmap = os.path.join(self.tmp, 'addon', 'maps', 'm.vmap'); store = mapbackup.Store(os.path.join(self.tmp, 'store'))
        t0 = dt.datetime(2026, 1, 1, 12, 0, 0)
        for i in range(6):
            put(vmap, b'version %d' % i); store.save(vmap, now=t0 + dt.timedelta(seconds=i))
        later = t0 + dt.timedelta(days=400)
        before = tree(self.tmp)
        gone = store.trim('m', now=later, dry_run=True)
        self.assertEqual(tree(self.tmp), before)
        self.assertTrue(gone)
        self.assertEqual(store.trim('m', now=later), gone)                            # the real trim removes exactly what the dry run listed


if __name__ == '__main__':
    unittest.main()
