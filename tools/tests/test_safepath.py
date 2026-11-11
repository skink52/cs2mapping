"""safepath.py: addon names, containment, links, copy plans, verified backups, manifests and rollback. Real files in a temp folder.

  python -m unittest discover -s tools/tests -p "test_safepath.py" -v
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import safepath as S


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(data)


def get(path):
    with open(path, 'rb') as f: return f.read()


def junction(link, target):
    """an NTFS junction on Windows, a symlink elsewhere; None when the platform refuses"""
    try:
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', link, target], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.symlink(target, link, target_is_directory=True)
        return link
    except (OSError, subprocess.CalledProcessError):
        return None


class Names(unittest.TestCase):
    def test_plain_names_pass(self):
        for n in ('mg_arcs_multigames', 'ba_jail_seaside', 'ttt_island17_pezversion', 'de-dust.v2', 'a'):
            self.assertEqual(S.addon_name(n), n)

    def test_paths_and_traps_are_refused(self):
        for n in ('', '.', '..', '../x', '..\\x', 'a/b', 'a\\b', 'C:', 'C:\\x', 'x:y', ' lead', 'trail ', 'dot.', 'nul', 'COM1', 'con.txt',
                  'a\nb', 'a*b', 'a?b', None, 5):
            with self.assertRaises(ValueError, msg=repr(n)): S.addon_name(n)


class Inside(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='safepath_')
        self.root = os.path.join(self.tmp, 'addons', 'my addon')        # a space in the path, as in "Program Files (x86)"
        os.makedirs(self.root)

    def tearDown(self):
        link = os.path.join(self.root, 'link')
        if S.is_link(link): os.rmdir(link) if os.name == 'nt' else os.unlink(link)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_containment_is_lexical(self):
        self.assertTrue(S.inside(self.root, self.root))
        self.assertTrue(S.inside(self.root, os.path.join(self.root, 'maps', 'm.vmap')))
        self.assertTrue(S.inside(self.root, os.path.join(self.root, 'maps', '..', 'm.vmap')))
        self.assertFalse(S.inside(self.root, os.path.join(self.root, '..', 'other', 'm.vmap')))
        self.assertFalse(S.inside(self.root, self.root + ' two'))                 # a sibling whose name starts the same
        self.assertFalse(S.inside(self.root, os.path.dirname(self.root)))

    @unittest.skipUnless(os.name == 'nt', 'drive letters and case-insensitive paths are Windows behaviour')
    def test_windows_case_and_drives(self):
        self.assertTrue(S.inside(self.root.upper(), os.path.join(self.root.lower(), 'x')))
        self.assertTrue(S.inside(self.root.replace('\\', '/'), os.path.join(self.root, 'x')))
        other = 'D:\\' if not self.root.upper().startswith('D:') else 'C:\\'
        self.assertFalse(S.inside(self.root, other + 'x'))

    def test_a_junction_is_a_link_and_stays_inside(self):
        target = os.path.join(self.tmp, 'elsewhere'); os.makedirs(target)
        link = junction(os.path.join(self.root, 'link'), target)
        if not link: self.skipTest('cannot make a junction / symlink here')
        self.assertTrue(S.is_link(link))
        self.assertFalse(S.is_link(target))
        self.assertFalse(S.is_link(os.path.join(self.root, 'missing')))
        # the pipeline works through content\<addon> junctions that may point at another drive: still "inside" the root as written
        self.assertTrue(S.inside(self.root, os.path.join(link, 'maps', 'm.vmap')))


class Copies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='safepath_')
        self.src = os.path.join(self.tmp, 'out'); self.dst = os.path.join(self.tmp, 'addon')
        self.bak = os.path.join(self.tmp, 'backups'); self.man = os.path.join(self.tmp, 'logs', 'apply.json')
        put(os.path.join(self.src, 'maps', 'm.vmap'), b'new map')
        put(os.path.join(self.src, 'materials', 'a.vmat'), b'same')
        put(os.path.join(self.src, 'materials', 'new.vmat'), b'brand new')
        put(os.path.join(self.dst, 'maps', 'm.vmap'), b'old map, hand edited')
        put(os.path.join(self.dst, 'materials', 'a.vmat'), b'same')
        put(os.path.join(self.dst, 'materials', 'untouched.vmat'), b'not in the source tree')

    def tearDown(self):
        for dp, dns, _ in os.walk(self.tmp):
            for d in dns:
                p = os.path.join(dp, d)
                if S.is_link(p): os.rmdir(p) if os.name == 'nt' else os.unlink(p)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tree(self, root):
        return {os.path.relpath(os.path.join(dp, f), root).replace('\\', '/'): get(os.path.join(dp, f))
                for dp, _, fs in os.walk(root) for f in fs}

    def test_plan(self):
        ops = {p['rel']: p['op'] for p in S.plan_copy(self.src, self.dst)}
        self.assertEqual(ops, {'maps/m.vmap': 'modify', 'materials/a.vmat': 'same', 'materials/new.vmat': 'create'})
        sm = S.summarise(S.plan_copy(self.src, self.dst))
        self.assertEqual((sm['create'], sm['modify'], sm['same']), (1, 1, 1))
        self.assertEqual(sm['bytes_written'], len(b'new map') + len(b'brand new'))
        self.assertEqual(sm['bytes_backed_up'], len(b'old map, hand edited'))
        self.assertEqual(S.plan_copy(os.path.join(self.tmp, 'missing'), self.dst), [])

    def test_dry_run_changes_nothing(self):
        before = self.tree(self.tmp)
        man = S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man, dry_run=True)
        self.assertEqual(self.tree(self.tmp), before)
        self.assertFalse(os.path.exists(self.man)); self.assertFalse(os.path.exists(self.bak))
        self.assertEqual(sorted((f['op'], f['rel']) for f in man['files']), [('create', 'materials/new.vmat'), ('modify', 'maps/m.vmap')])

    def test_apply_backs_up_then_rollback_restores(self):
        before = self.tree(self.dst)
        man = S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man, label='t')
        self.assertTrue(man['complete'])
        self.assertEqual(get(os.path.join(self.dst, 'maps', 'm.vmap')), b'new map')
        self.assertEqual(get(os.path.join(self.dst, 'materials', 'untouched.vmat')), b'not in the source tree')
        with open(self.man, encoding='utf-8') as f: rec = {x['rel']: x for x in json.load(f)['files']}
        self.assertEqual(get(rec['maps/m.vmap']['backup']), b'old map, hand edited')
        self.assertEqual(rec['maps/m.vmap']['after'], S.sha256_file(os.path.join(self.dst, 'maps', 'm.vmap')))
        self.assertIsNone(rec['materials/new.vmat']['backup'])
        self.assertFalse([f for dp, _, fs in os.walk(self.dst) for f in fs if f.endswith('.part')])
        out = S.rollback(self.man)
        self.assertEqual((len(out['restored']), len(out['removed']), out['skipped']), (1, 1, []))
        self.assertEqual(self.tree(self.dst), before)

    def test_rollback_leaves_a_file_edited_since(self):
        S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man)
        put(os.path.join(self.dst, 'maps', 'm.vmap'), b'edited in Hammer after the apply')
        put(os.path.join(self.dst, 'materials', 'new.vmat'), b'also edited')
        dry = S.rollback(self.man, dry_run=True)
        out = S.rollback(self.man)
        self.assertEqual(len(dry['skipped']), 2)
        self.assertEqual((out['restored'], out['removed'], len(out['skipped'])), ([], [], 2))
        self.assertEqual(get(os.path.join(self.dst, 'maps', 'm.vmap')), b'edited in Hammer after the apply')
        self.assertEqual(get(os.path.join(self.dst, 'materials', 'new.vmat')), b'also edited')

    def test_rollback_refuses_a_damaged_backup(self):
        man = S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man)
        bak = [f['backup'] for f in man['files'] if f['backup']][0]
        put(bak, b'bit rot')
        out = S.rollback(self.man)
        self.assertEqual(out['restored'], [])
        self.assertIn('no longer matches', out['skipped'][0]['why'])
        self.assertEqual(get(os.path.join(self.dst, 'maps', 'm.vmap')), b'new map')

    def test_interrupted_apply_leaves_a_usable_manifest(self):
        plan = S.plan_copy(self.src, self.dst)
        os.remove(plan[-1]['src'])                                    # the last source file vanishes mid-run
        with self.assertRaises(OSError): S.apply_plan(plan, self.bak, self.man)
        with open(self.man, encoding='utf-8') as f: man = json.load(f)
        self.assertFalse(man['complete'])
        self.assertEqual([f['rel'] for f in man['files']], ['maps/m.vmap'])
        S.rollback(self.man)
        self.assertEqual(get(os.path.join(self.dst, 'maps', 'm.vmap')), b'old map, hand edited')

    def test_custom_backup_path(self):
        man = S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man,
                           backup_path=lambda p: p['dst'] + '.bak_x' if p['dst'].endswith('.vmap') else None)
        self.assertEqual(get(os.path.join(self.dst, 'maps', 'm.vmap.bak_x')), b'old map, hand edited')
        self.assertTrue(man['files'][0]['backup'].endswith('.bak_x'))

    def test_folder_where_a_file_should_go(self):
        os.remove(os.path.join(self.dst, 'materials', 'a.vmat')); os.makedirs(os.path.join(self.dst, 'materials', 'a.vmat'))
        with self.assertRaises(ValueError): S.plan_copy(self.src, self.dst)

    def test_links_in_the_source_tree_are_not_copied(self):
        outside = os.path.join(self.tmp, 'outside'); put(os.path.join(outside, 'secret.txt'), b'not ours')
        if not junction(os.path.join(self.src, 'linked'), outside): self.skipTest('cannot make a junction / symlink here')
        self.assertNotIn('linked/secret.txt', [p['rel'] for p in S.plan_copy(self.src, self.dst)])

    def test_destination_reached_through_a_junction(self):
        real = os.path.join(self.tmp, 'other drive', 'addon'); shutil.move(self.dst, real)
        if not junction(self.dst, real): self.skipTest('cannot make a junction / symlink here')
        S.apply_plan(S.plan_copy(self.src, self.dst), self.bak, self.man)
        self.assertEqual(get(os.path.join(real, 'maps', 'm.vmap')), b'new map')     # written through the link, as the pipeline does
        S.rollback(self.man)
        self.assertEqual(get(os.path.join(real, 'maps', 'm.vmap')), b'old map, hand edited')


if __name__ == '__main__':
    unittest.main()
