"""mcp_live.py loaded the way tools/mcp_server.py loads plug-ins (its load_plugins), then called through its call_tool and
over stdio, against the fake CS2 console. tools/mcp_server.py is only imported and run, never changed."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

AUTOPORT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(AUTOPORT)
SERVER = os.path.join(REPO, 'tools', 'mcp_server.py')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='autoport_mcp_')
os.environ['AUTOPORT_LIVE_STATE'] = TMP
from fakecs2 import FakeCS2  # noqa: E402

EXPECTED = {'game_status', 'game_command', 'game_tail', 'game_wait', 'game_launch', 'game_stop', 'game_load_map', 'game_reset',
            'game_screenshot', 'game_crash_report', 'ingame_check', 'playtest', 'mode_playtest', 'script_test', 'route_test',
            'timings', 'physics_probe', 'probe_script', 'player_marks', 'script_reload'}


@unittest.skipUnless(os.path.exists(SERVER), 'tools/mcp_server.py not in this checkout')
class Loader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.dirname(SERVER))
        import mcp_server
        cls.M = mcp_server
        cls.added = set(mcp_server.load_plugins(AUTOPORT))
        import cs2live
        cs2live.STATE_DIR = TMP

    def setUp(self):
        self.fake = FakeCS2(addon='mg_test')
        import cs2live
        self.p = mock.patch.object(cs2live, 'cs2_processes', return_value=[])
        self.p.start()

    def tearDown(self):
        self.fake.close()
        self.p.stop()

    def call(self, _tool, **args):
        r = self.M.call_tool(_tool, args)
        self.assertFalse(r['isError'], r['content'][0]['text'])
        return json.loads(r['content'][0]['text'])

    def test_all_tools_registered_with_schemas(self):
        self.assertTrue(EXPECTED <= self.added, EXPECTED - self.added)
        for name in EXPECTED:
            t = self.M.TOOLS[name]
            self.assertEqual(t['inputSchema']['type'], 'object')
            self.assertTrue(t['description'])

    def test_game_command_and_wait(self):
        out = self.call('game_command', commands='echo via mcp;;echo second', wait=0.1, port=self.fake.port)
        self.assertEqual(out['lines'], ['via mcp', 'second'])
        out = self.call('game_wait', regex='^pong$', send='echo pong', timeout=5, port=self.fake.port)
        self.assertEqual(out, {'found': True, 'line': 'pong'})

    def test_status_load_and_screenshot(self):
        st = self.call('game_status', port=self.fake.port)
        self.assertTrue(st['reachable'])
        self.assertEqual(st['addon'], 'mg_test')
        self.fake.maps['mg_test'] = ['Failed to load model models/props/crate.vmdl']
        r = self.call('game_load_map', addon='mg_test', map='mg_test', port=self.fake.port)
        self.assertTrue(r['ok'])
        self.assertEqual(list(r['problems']), ['missing'])
        self.assertTrue(self.call('game_screenshot', name='x', port=self.fake.port)['path'].endswith('.jpg'))

    def test_launch_is_dry_run_by_default_and_bad_args_are_refused(self):
        r = self.call('game_launch', addon='mg_test')
        self.assertTrue(r['dry_run'])
        self.assertIn('-tools', r['argv'])
        bad = self.M.call_tool('game_command', {'commands': 'x', 'nonsense': 1})
        self.assertTrue(bad['isError'])

    def test_ingame_check_skips_without_console(self):
        r = self.call('ingame_check', addon='mg_test', seconds=1, port=1)
        self.assertEqual(r['exit'], 3)

    def test_crash_report_none(self):
        import crashdump
        with mock.patch.object(crashdump, 'GAME_BIN', TMP):
            self.assertEqual(self.call('game_crash_report')['crash'], False)


@unittest.skipUnless(os.path.exists(SERVER), 'tools/mcp_server.py not in this checkout')
class Stdio(unittest.TestCase):
    def test_tools_list_and_call_over_stdio(self):
        fake = FakeCS2(addon='mg_test')
        env = dict(os.environ, CS2MCP_PLUGIN_DIR=AUTOPORT, AUTOPORT_LIVE_STATE=TMP, PYTHONIOENCODING='utf-8')
        p = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            def rpc(i, method, params=None):
                p.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': i, 'method': method, 'params': params or {}}) + '\n').encode())
                p.stdin.flush()
                return json.loads(p.stdout.readline())
            rpc(1, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '0'}})
            p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            names = {t['name'] for t in rpc(2, 'tools/list')['result']['tools']}
            self.assertTrue(EXPECTED <= names)
            t0 = time.monotonic()
            r = rpc(3, 'tools/call', {'name': 'game_command', 'arguments': {'commands': 'echo over stdio', 'wait': 0.1, 'port': fake.port}})
            self.assertFalse(r['result']['isError'], r)
            self.assertEqual(json.loads(r['result']['content'][0]['text'])['lines'], ['over stdio'])
            self.assertLess(time.monotonic() - t0, 60)
        finally:
            p.stdin.close()
            p.wait(20)
            p.stdout.close()
            fake.close()


if __name__ == '__main__':
    unittest.main()
