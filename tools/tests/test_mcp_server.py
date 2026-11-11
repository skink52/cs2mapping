"""tools/mcp_server.py driven over stdio exactly as an MCP client does: initialize, initialized, tools/list, tools/call, errors, jobs,
a plug-in module, and the protocol stream staying clean. Uses a fake CS2 root (FGDs only; no compiler), so nothing is ever built.

  python -m unittest discover -s tools/tests -p "test_mcp_server.py" -v
"""
import json, os, queue, shutil, subprocess, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F

SERVER = os.path.join(F.TOOLS, 'mcp_server.py')
PLUGIN = '''
"""a test plug-in"""
def _echo(text='', n=1):
    print('this must not reach the protocol stream')
    return {'echo': text * int(n)}
MCP_TOOLS = [{'name': 'echo_test', 'description': 'echo', 'fn': _echo,
              'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'n': {'type': 'number'}}}}]
'''


class Client:
    def __init__(self, env):
        self.p = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.q = queue.Queue(); self.n = 0; self.raw = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=lambda: [None for _ in self.p.stderr], daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.raw.append(line)
            self.q.put(json.loads(line.decode('utf-8')))

    def send(self, obj):
        self.p.stdin.write((json.dumps(obj) + '\n').encode('utf-8')); self.p.stdin.flush()

    def send_raw(self, text):
        self.p.stdin.write(text.encode('utf-8') + b'\n'); self.p.stdin.flush()

    def recv(self, timeout=60):
        return self.q.get(timeout=timeout)

    def request(self, method, params=None):
        self.n += 1
        self.send({'jsonrpc': '2.0', 'id': self.n, 'method': method, **({'params': params} if params is not None else {})})
        r = self.recv()
        assert r.get('id') == self.n, r
        return r

    def call(self, name, **args):
        return self.request('tools/call', {'name': name, 'arguments': args})['result']

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


class Stdio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        cls.plugins = tempfile.mkdtemp(prefix='cs2mcp_plugins_')
        F.write(os.path.join(cls.plugins, 'echo_plugin.py'), PLUGIN)
        F.write(os.path.join(cls.plugins, 'not_a_plugin.py'),'raise SystemExit("must not be imported")\n')
        env = dict(os.environ, CS2_ROOT=cls.root, CS2MCP_PLUGIN_DIR=cls.plugins, PYTHONIOENCODING='utf-8')
        cls.c = Client(env)
        cls.init = cls.c.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                                'clientInfo': {'name': 'unittest', 'version': '1'}})
        cls.c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    @classmethod
    def tearDownClass(cls):
        cls.c.close()
        shutil.rmtree(cls.root, ignore_errors=True); shutil.rmtree(cls.plugins, ignore_errors=True)

    def test_01_initialize(self):
        r = self.init['result']
        self.assertEqual(r['protocolVersion'], '2025-06-18')
        self.assertIn('tools', r['capabilities'])
        self.assertEqual(r['serverInfo']['name'], 'cs2mapping')

    def test_02_tools_list(self):
        tools = {t['name']: t for t in self.c.request('tools/list')['result']['tools']}
        for name in ('guide', 'list_maps', 'map_info', 'entity_info', 'validate_map', 'check_map_problems', 'sanity_check',
                     'analyze_build_log', 'stage_pass', 'build_map', 'compile_assets', 'job_status', 'echo_test'):
            self.assertIn(name, tools)
        self.assertEqual(tools['validate_map']['inputSchema']['required'], ['vmap'])
        self.assertTrue(tools['validate_map']['annotations']['readOnlyHint'])
        self.assertFalse(tools['build_map']['annotations']['readOnlyHint'])
        # the hints must tell a client which tools can replace or delete what exists, which only add, and which only read
        hint = lambda n: (tools[n]['annotations']['readOnlyHint'], tools[n]['annotations']['destructiveHint'])
        for n in ('stage_pass', 'build_map', 'compile_assets', 'map_backups', 'material_create', 'sound_create', 'model_build', 'mechanics_build',
                  'map_edit', 'script_write'):
            if n in tools: self.assertEqual(hint(n), (False, True), n)
        if 'prop_note' in tools: self.assertEqual(hint('prop_note'), (False, False))
        for n in ('job_status', 'job_cancel'):                      # stopping a job can leave partial output: never advertised as read-only
            self.assertEqual(hint(n), (False, True), n)
        for n in ('guide', 'list_maps', 'map_info', 'entity_info', 'validate_map', 'check_map_problems', 'sanity_check', 'analyze_build_log',
                  'visual_check', 'release_plan', 'prop_search', 'script_api', 'asset_search', 'catalog_info', 'status'):
            if n in tools: self.assertEqual(hint(n), (True, False), n)
        for n in ('game_status', 'game_tail', 'game_crash_report'):
            if n in tools: self.assertEqual(hint(n), (True, False), n)
        for n in ('game_command', 'game_wait', 'game_stop', 'probe_script', 'player_marks'):
            if n in tools: self.assertEqual(hint(n), (False, True), n)
        for n in ('game_launch', 'game_screenshot', 'game_load_map', 'playtest'):
            if n in tools: self.assertEqual(hint(n), (False, False), n)
        self.assertTrue(all(set(t['annotations']) >= {'readOnlyHint', 'destructiveHint'} for t in tools.values()), 'every tool carries both hints')
        self.assertTrue(all('fn' not in t for t in tools.values()))

    def test_03_entity_info_and_validate(self):
        r = self.c.call('entity_info', classname='trigger_multiple')
        self.assertFalse(r['isError'])
        self.assertIn('OnTrigger', r['structuredContent']['outputs'])
        self.assertEqual(json.loads(r['content'][0]['text'])['classname'], 'trigger_multiple')
        v = self.c.call('validate_map', vmap=self.vmap, only='dangling_target,bad_input,excluded_class')['structuredContent']
        self.assertEqual(sorted({f['code'] for f in v['findings']}), ['bad_input', 'dangling_target', 'excluded_class'])
        s = self.c.call('sanity_check', vmap=self.vmap)['structuredContent']
        self.assertEqual(s['errors'], 1)
        info = self.c.call('map_info', vmap=self.vmap)['structuredContent']
        self.assertEqual(info['classes']['info_player_terrorist'], 3)
        maps = self.c.call('list_maps', addon='test_addon')['structuredContent']
        self.assertTrue(maps['addons'][0]['maps'][0]['path'].endswith('test_map.vmap'))

    def test_04_tool_errors_are_results(self):
        r = self.c.call('validate_map', vmap=os.path.join(self.root, 'nope.vmap'))
        self.assertTrue(r['isError']); self.assertIn('FileNotFoundError', r['content'][0]['text'])
        r = self.c.call('validate_map')
        self.assertTrue(r['isError']); self.assertIn('missing argument', r['content'][0]['text'])
        r = self.c.call('entity_info', classname='trigger_multiple', colour='red')
        self.assertTrue(r['isError'])

    def test_05_protocol_errors(self):
        r = self.c.request('tools/call', {'name': 'no_such_tool', 'arguments': {}})
        self.assertEqual(r['error']['code'], -32602)
        self.assertEqual(self.c.request('resources/list')['error']['code'], -32601)
        self.assertEqual(self.c.request('ping')['result'], {})
        self.c.send_raw('{not json')
        self.assertEqual(self.c.recv()['error']['code'], -32700)

    def test_06_plugin_and_clean_stdout(self):
        r = self.c.call('echo_test', text='ab', n=2)
        self.assertEqual(r['structuredContent'], {'echo': 'abab'})
        for line in self.c.raw:                                   # every stdout line is one JSON-RPC message
            self.assertEqual(json.loads(line)['jsonrpc'], '2.0')

    def test_07_jobs(self):
        r = self.c.call('build_map', vmap=self.vmap, preset='full', dry_run=True)['structuredContent']
        self.assertIn('-bakelighting', r['argv'])
        job = self.c.call('compile_assets', paths=[self.vmap], wait=0)['structuredContent']   # fake CS2 has no compiler: fails fast
        self.assertIn(job['state'], ('running', 'failed'))
        st = self.c.call('job_status', job=job['job'], wait=60)['structuredContent']
        self.assertEqual(st['state'], 'failed')
        self.assertTrue(any('resourcecompiler.exe not found' in ln for ln in st['log_tail']), st)
        self.assertIn(job['job'], [j['job'] for j in self.c.call('job_status')['structuredContent']['jobs']])
        bad = self.c.call('stage_pass', stage='D', addon='x', root=self.root, steps='lights;rm -rf')
        self.assertTrue(bad['isError'])

    def test_08_guide(self):
        docs = self.c.call('guide')['structuredContent']['docs']
        names = [d['doc'] for d in docs]
        self.assertIn('tools/README.md', names)
        page = self.c.call('guide', doc='tools/README.md', length=200)['structuredContent']
        self.assertEqual(len(page['text']), 200); self.assertTrue(page['more'])
        self.assertTrue(self.c.call('guide', doc='../../secret.txt')['isError'])


class Batch(unittest.TestCase):
    def test_batch_and_version_fallback(self):
        sys.path.insert(0, F.TOOLS)
        import mcp_server as M
        st = {}
        r = M.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '1999-01-01'}}, st)
        self.assertEqual(r['result']['protocolVersion'], '2025-06-18')
        self.assertIsNone(M.handle({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {}}, st))
        self.assertEqual(M.handle({'id': 3, 'method': 'ping'}, st)['error']['code'], -32600)


if __name__ == '__main__':
    unittest.main()
