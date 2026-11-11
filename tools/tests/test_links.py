"""Links below a root: safepath refuses to write, restore or delete through a junction nobody named; job cancellation in the MCP server.
Real junctions on Windows, symlinks elsewhere; skipped where the platform refuses to make one.

  python -m unittest discover -s tools/tests -p "test_links.py" -v
"""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import safepath as S


def put(path, data=b'x'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(data)


def get(path):
    with open(path, 'rb') as f: return f.read()


def junction(link, target):
    try:
        os.makedirs(os.path.dirname(link), exist_ok=True)
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', link, target], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.symlink(target, link, target_is_directory=True)
        return link
    except (OSError, subprocess.CalledProcessError):
        return None


def unlink_all(root):
    """remove every link under root without touching what it points at, then the tree"""
    for dp, dns, _ in os.walk(root):
        for d in list(dns):
            p = os.path.join(dp, d)
            if S.is_link(p):
                os.rmdir(p) if os.name == 'nt' else os.unlink(p)
                dns.remove(d)
    shutil.rmtree(root, ignore_errors=True)


class NestedLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='links_')
        self.addon = os.path.join(self.tmp, 'addons', 'mg_test'); self.other = os.path.join(self.tmp, 'other addon')
        self.src = os.path.join(self.tmp, 'out'); self.bak = os.path.join(self.tmp, 'bak'); self.man = os.path.join(self.tmp, 'man.json')
        put(os.path.join(self.addon, 'maps', 'm.vmap'), b'map'); put(os.path.join(self.other, 'precious.vmat'), b'someone else\'s file')
        put(os.path.join(self.src, 'materials', 'precious.vmat'), b'OVERWRITTEN'); put(os.path.join(self.src, 'maps', 'm.vmap'), b'new map')

    def tearDown(self):
        unlink_all(self.tmp)

    def plant(self):
        """materials -> another addon, inside the addon we were told to work in"""
        link = junction(os.path.join(self.addon, 'materials'), self.other)
        if not link: self.skipTest('cannot make a junction / symlink here')
        return link

    def test_links_below_and_target(self):
        link = self.plant()
        self.assertEqual(S.links_below(self.addon, os.path.join(link, 'a', 'b.vmat')), [link])
        self.assertEqual(S.links_below(self.addon, os.path.join(self.addon, 'maps', 'm.vmap')), [])
        self.assertEqual(S.links_below(self.addon, self.addon), [])
        self.assertEqual(S.links_below(self.addon, os.path.join(self.addon, 'not', 'there', 'yet.txt')), [])     # missing parts are not links
        self.assertTrue(os.path.samefile(S.link_target(link), self.other))
        self.assertIsNone(S.link_target(self.addon))
        with self.assertRaises(ValueError): S.links_below(self.addon, os.path.join(self.tmp, 'elsewhere'))
        with self.assertRaises(ValueError) as cm: S.check_no_nested_links(self.addon, os.path.join(link, 'x'))
        self.assertIn('rmdir', str(cm.exception))

    def test_the_root_itself_may_be_a_junction(self):
        work = junction(os.path.join(self.tmp, 'work', 'content', 'mg_test'), self.addon)
        if not work: self.skipTest('cannot make a junction / symlink here')
        os.remove(os.path.join(self.src, 'materials', 'precious.vmat'))
        plan = S.plan_copy(self.src, work)                                   # the pipeline's layout: allowed
        S.apply_plan(plan, self.bak, self.man, roots=[work])
        self.assertEqual(get(os.path.join(self.addon, 'maps', 'm.vmap')), b'new map')

    def test_plan_copy_refuses_a_link_below_the_destination(self):
        self.plant()
        with self.assertRaises(ValueError): S.plan_copy(self.src, self.addon)
        self.assertEqual(get(os.path.join(self.other, 'precious.vmat')), b'someone else\'s file')
        self.assertEqual(get(os.path.join(self.addon, 'maps', 'm.vmap')), b'map')                 # nothing at all was copied
        ops = {p['rel']: p['op'] for p in S.plan_copy(self.src, self.addon, allow_links=True)}    # the caller can say it means it
        self.assertEqual(ops['materials/precious.vmat'], 'modify')

    def test_plan_pairs_refuses_a_link_below_the_allowed_root(self):
        link = self.plant()
        pairs = [[os.path.join(self.src, 'materials', 'precious.vmat'), os.path.join(link, 'precious.vmat')]]
        with self.assertRaises(ValueError): S.plan_pairs(pairs, [self.addon])
        self.assertEqual(len(S.plan_pairs(pairs, [self.addon], allow_links=True)), 1)

    def test_a_link_planted_after_planning_is_caught_before_the_write(self):
        os.makedirs(os.path.join(self.addon, 'materials'))
        plan = S.plan_copy(self.src, self.addon)                             # clean when planned
        os.rmdir(os.path.join(self.addon, 'materials')); self.plant()        # then swapped for a junction
        with self.assertRaises(ValueError): S.apply_plan(plan, self.bak, self.man, roots=[self.addon])
        self.assertEqual(get(os.path.join(self.other, 'precious.vmat')), b'someone else\'s file')
        self.assertFalse(os.path.exists(os.path.join(self.other, 'precious.vmat.part')))

    def test_rollback_will_not_delete_or_restore_through_a_new_link(self):
        os.makedirs(os.path.join(self.addon, 'materials'))
        S.apply_plan(S.plan_copy(self.src, self.addon), self.bak, self.man, roots=[self.addon])
        made = os.path.join(self.addon, 'materials', 'precious.vmat')
        self.assertEqual(get(made), b'OVERWRITTEN')
        os.remove(made); os.rmdir(os.path.join(self.addon, 'materials')); self.plant()
        put(os.path.join(self.other, 'precious.vmat'), b'OVERWRITTEN')       # same bytes the run wrote, but in the other addon
        out = S.rollback(self.man)
        self.assertEqual(get(os.path.join(self.other, 'precious.vmat')), b'OVERWRITTEN')          # not removed through the link
        self.assertTrue(any('link' in s['why'] for s in out['skipped']))
        self.assertEqual(get(os.path.join(self.addon, 'maps', 'm.vmap')), b'map')                 # the rest of the rollback still happened

    def test_write_atomic(self):
        link = self.plant()
        with self.assertRaises(ValueError): S.write_atomic(os.path.join(link, 'precious.vmat'), b'X', root=self.addon)
        with self.assertRaises(ValueError): S.write_atomic(link, b'X')                            # the path itself is a link
        self.assertEqual(get(os.path.join(self.other, 'precious.vmat')), b'someone else\'s file')
        self.assertEqual(S.write_atomic(os.path.join(self.addon, 'maps', 'm.vmap'), b'ok', root=self.addon)['op'], 'modify')


class JobCancel(unittest.TestCase):
    """the MCP server's job_cancel and job_status(cancel=true) on a real child process"""
    def setUp(self):
        import mcp_server as M
        self.M = M
        self.job = M.Job('test', 'sleeper', [sys.executable, '-c', 'import time; print("up", flush=True); time.sleep(60)'], os.getcwd())
        M.JOBS[self.job.id] = self.job
        for _ in range(100):
            if self.job.proc and self.job.lines: break
            time.sleep(0.05)

    def tearDown(self):
        if self.job.proc and self.job.ended is None: self.job.proc.kill()
        self.M.JOBS.pop(self.job.id, None)

    def test_job_cancel_stops_it_and_says_so(self):
        self.assertEqual(self.M.t_job(self.job.id)['state'], 'running')                           # reading does not stop it
        self.assertIsNone(self.job.ended)
        r = self.M.t_job_cancel(self.job.id, wait=10)
        self.assertTrue(r['cancelled']); self.assertNotEqual(r['state'], 'running')
        self.assertIsNotNone(self.job.proc.poll())
        again = self.M.t_job_cancel(self.job.id, wait=1)
        self.assertFalse(again['cancelled'])                                                      # nothing left to stop
        with self.assertRaises(ValueError): self.M.t_job_cancel('no-such-job')

    def test_job_status_cancel_still_works(self):
        r = self.M.t_job(self.job.id, wait=10, cancel=True)
        self.assertNotEqual(r['state'], 'running')

    def test_hints(self):
        ann = lambda n: self.M.TOOLS[n]['annotations']
        for n in ('job_cancel', 'job_status'):
            self.assertFalse(ann(n)['readOnlyHint'], n); self.assertTrue(ann(n)['destructiveHint'], n)
        self.assertEqual(self.M.TOOLS['job_cancel']['inputSchema']['required'], ['job'])


if __name__ == '__main__':
    unittest.main()
