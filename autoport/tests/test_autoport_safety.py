"""autoport.py: --dry-run writes nothing (not even a log line), and "is CS2 running" means this install's cs2.exe.
Runs autoport's real main() in a child process with a temp pipeline folder; the plan steps that need BSPs are stubbed.

  python -m unittest discover -s autoport/tests -p "test_autoport_safety.py" -v
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
AUTOPORT = os.path.dirname(HERE); TOOLS = os.path.join(os.path.dirname(AUTOPORT), 'tools')

CHILD = r'''
import json, os, sys
sys.path[:0] = [%(autoport)r, %(tools)r]
import common, launch, autoport
class Plan:                                   # what build_plan returns, as far as main() looks at it
    class profile: name = 'minigame'
    addon = 'mg_test'; go = True
launch.resolve = lambda names, interactive: (['x.bsp'], ['mg_notfound'])
launch.build_plan = lambda bsps, names, online: [Plan()]
launch.preflight = lambda ttt: ([], ['a warning that the real run writes to the dated log'])
def show_plan(plans, not_found):
    launch.log('review', 'mg_test', 'launch', 'Left out: an existing port was found')      # as the real show_plan does
    print('PLAN SHOWN')
launch.show_plan = show_plan
mode = sys.argv.pop(1)
if mode == 'dry':
    sys.argv = ['autoport.py', 'mg_test', '--dry-run', '--no-online']
    code = autoport.main()
else:
    common.log('review', 'mg_test', 'launch', 'a line')                                    # the same call outside a dry run
    code = 0
tree = sorted(os.path.relpath(os.path.join(dp, f), common.PORT) for dp, ds, fs in os.walk(common.PORT) for f in fs + ds)
print('RESULT ' + json.dumps({'code': code, 'tree': tree}))
'''


class DryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='autoport_dry_')
        self.port = os.path.join(self.tmp, 'cs2port'); os.makedirs(self.port)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def child(self, mode):
        env = dict(os.environ, CS2PORT=self.port, CS2MAPPING=os.path.dirname(AUTOPORT), PYTHONIOENCODING='utf-8')
        r = subprocess.run([sys.executable, '-c', CHILD % {'autoport': AUTOPORT, 'tools': TOOLS}, mode], capture_output=True, text=True, env=env, cwd=self.tmp)
        line = [l for l in r.stdout.splitlines() if l.startswith('RESULT ')]
        self.assertTrue(line, r.stdout[-1500:] + r.stderr[-1500:])
        return json.loads(line[0][7:]), r.stdout

    def test_dry_run_writes_nothing(self):
        res, out = self.child('dry')
        self.assertIn('PLAN SHOWN', out)
        self.assertEqual(res['code'], 0)
        self.assertEqual(res['tree'], [], 'a dry run must leave the pipeline folder exactly as it was (no logs, no state)')

    def test_the_same_log_call_outside_a_dry_run_does_write(self):
        res, _ = self.child('log')                                   # shows the check above can fail: this is what a dry run used to do
        self.assertTrue(any(p.endswith('.log') for p in res['tree']), res['tree'])


class WhichCs2(unittest.TestCase):
    def test_only_this_install_counts(self):
        sys.path[:0] = [AUTOPORT, TOOLS]
        os.environ.setdefault('CS2MAPPING', os.path.dirname(AUTOPORT))
        import autoport
        cs2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive' if os.name == 'nt' else '/games/cs2'
        j = os.path.join
        self.assertTrue(autoport.is_this_install(j(cs2, 'game', 'bin', 'win64', 'cs2.exe'), cs2))
        self.assertTrue(autoport.is_this_install('', cs2))                                   # path unreadable: assume it matters
        self.assertFalse(autoport.is_this_install(j(os.path.dirname(cs2), 'cs2server', 'game', 'bin', 'win64', 'cs2.exe'), cs2))
        self.assertFalse(autoport.is_this_install(cs2 + ' Server' + os.sep + 'cs2.exe', cs2))  # a sibling folder whose name starts the same
        if os.name == 'nt':
            self.assertTrue(autoport.is_this_install(j(cs2.upper(), 'game', 'bin', 'win64', 'cs2.exe'), cs2))
            self.assertFalse(autoport.is_this_install(r'C:\cs2server\game\bin\win64\cs2.exe', cs2))

    def test_running_check_uses_the_paths(self):
        sys.path[:0] = [AUTOPORT, TOOLS]
        import autoport
        from unittest import mock
        server = os.path.join(os.path.dirname(os.path.abspath(autoport.CS2)), 'elsewhere', 'cs2.exe')
        with mock.patch.object(autoport, 'cs2_paths', return_value=[server]): self.assertFalse(autoport.cs2_running())
        with mock.patch.object(autoport, 'cs2_paths', return_value=[server, os.path.join(autoport.CS2, 'game', 'bin', 'win64', 'cs2.exe')]):
            self.assertTrue(autoport.cs2_running())
        with mock.patch.object(autoport, 'cs2_paths', return_value=[]): self.assertFalse(autoport.cs2_running())


if __name__ == '__main__':
    unittest.main()
