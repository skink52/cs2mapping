"""tools/jsapi.py (deprecated cs_script calls moved to the current API, call by call), the generators that now write the current
API, and create/test/api.py's hints, allowlist and JSON. Static checks: "unit tested" / "simulated", nothing here runs CS2.

  python -m unittest discover -s tools/tests -p "test_jsapi.py" -v
"""
import contextlib, glob, io, json, os, shutil, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE); REPO = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS); sys.path.insert(0, os.path.join(REPO, 'create', 'test'))
import jsapi, api

HEAD = 'import { Instance } from "cs_script/point_script";\n'
DTS = os.path.join(REPO, 'create', 'test', 'point_script.d.ts')


def mig(body, head=HEAD):
    new, done, manual = jsapi.migrate(head + body)
    return new.split('\n', 1)[1], new.split('\n', 1)[0], done, manual


class Lexer(unittest.TestCase):
    def code(self, src):
        m = jsapi.lex(src)
        return ''.join(c if m[i] else '_' for i, c in enumerate(src))

    def test_strings_comments_templates_and_regex_are_not_code(self):
        self.assertEqual(self.code('a("x)") // b(\nc'), 'a(____) _____\nc')
        self.assertEqual(self.code("f('it\\'s') /* g( */ h"), "f(_______) ________ h")
        self.assertEqual(self.code('t(`a ${b(")")} c`)'), 't(_____b(___)____)')
        self.assertEqual(self.code('s.replace(/"\\//g, x) / 2'), 's.replace(______, x) / 2')
        self.assertEqual(self.code('x = a / b / c'), 'x = a / b / c')                 # division, not a regex

    def test_unterminated_text_is_an_error_not_a_guess(self):
        for bad in ('a("x', 'a(`x ${y', 'a(`x'):
            with self.assertRaises(ValueError): jsapi.lex(bad)


class Migrate(unittest.TestCase):
    def test_same_parameters_new_home(self):
        body, head, done, manual = mig('Instance.Msg("a" + b);\nInstance.ServerCommand(`say ${x}`);\nif (Instance.IsWarmupPeriod()) Instance.SetRoundRemainingTime(0);\n'
                                       'for (const e of Instance.FindEntitiesByName(n)) e.Kill();\nInstance.DisconnectOutput(id);\n')
        self.assertEqual(body, 'Console.Log("a" + b);\nConsole.ServerCommand(`say ${x}`);\nif (GameRules.IsWarmupPeriod()) GameRules.SetRoundRemainingTime(0);\n'
                               'for (const e of Entities.FindByName(n)) e.Kill();\nEntities.DisconnectOutput(id);\n')
        self.assertEqual(head, 'import { Instance, Entities, Console, GameRules } from "cs_script/point_script";')
        self.assertEqual((len(done), manual), (6, []))

    def test_single_entity_lookup_takes_the_first_of_the_array(self):
        body, _, _, _ = mig('const d = Instance.FindEntityByName("door" + (i + 1)); const w = Instance.FindEntityByClass("worldspawn")?.GetAbsOrigin();\n')
        self.assertEqual(body, 'const d = Entities.FindByName("door" + (i + 1))[0]; const w = Entities.FindByClass("worldspawn")[0]?.GetAbsOrigin();\n')

    def test_fire_by_name_keeps_its_config_object(self):
        body, _, _, _ = mig('Instance.EntFireAtName({ name: "relay", input: "Trigger", value: f(a, b), delay: 0.1 });\n')
        self.assertEqual(body, 'Entities.FireInput({ name: "relay", input: "Trigger", value: f(a, b), delay: 0.1 });\n')

    def test_fire_at_target_moves_the_target_out(self):
        body, head, _, manual = mig('Instance.EntFireAtTarget({ target: pawn, input, value: v, activator: pawn, delay });\n'
                                    'Instance.EntFireAtTarget({ input: "Kill", target: q.g });\nInstance.EntFireAtTarget({ target, input: "Wake" });\n')
        self.assertEqual(body, 'pawn.FireInput({ input, value: v, activator: pawn, delay });\nq.g.FireInput({ input: "Kill" });\ntarget.FireInput({ input: "Wake" });\n')
        self.assertEqual(head, HEAD.strip()); self.assertEqual(manual, [])            # no new global needed

    def test_connect_output_becomes_a_config(self):
        body, _, _, _ = mig('const id = Instance.ConnectOutput(btn, "OnPressed", ({ activator }) => { go(activator, 1); });\n')
        self.assertEqual(body, 'const id = Entities.ConnectOutput({ target: btn, output: "OnPressed", callback: ({ activator }) => { go(activator, 1); } });\n')

    def test_a_call_inside_another(self):
        body, _, done, _ = mig('Instance.RegisterCheatCommand("dbg", () => { Instance.Msg(Instance.FindEntityByName("a") ? "y" : "n"); });\n')
        self.assertEqual(body, 'Console.RegisterCheatCommand("dbg", () => { Console.Log(Entities.FindByName("a")[0] ? "y" : "n"); });\n')
        self.assertEqual(len(done), 3)

    def test_forms_no_rule_covers_are_left_exactly_as_written(self):
        cases = {'Instance.EntFireAtName("relay", "Trigger", "", 1);\n': 'positional',
                 'Instance.EntFireAtName(cfg);\n': 'variable',
                 'Instance.EntFireAtTarget(ent, "Kill");\n': 'positional',
                 'Instance.EntFireAtTarget({ target: pick(a, b), input: "Kill" });\n': 'expression',
                 'Instance.EntFireAtTarget({ ...base, input: "Kill" });\n': 'config',
                 'Instance.OnBeforePlayerDamage((e) => ({ abort: true }));\n': 'OnModifyPlayerDamage',
                 'const log = Instance.Msg;\n': 'value',
                 'Instance.ConnectOutput(a, b);\n': 'expected'}
        for src, word in cases.items():
            body, head, done, manual = mig(src)
            self.assertEqual((body, head, done), (src, HEAD.strip(), []), src)
            self.assertEqual(len(manual), 1, src); self.assertIn(word, manual[0]['why'], src); self.assertEqual(manual[0]['line'], 2)

    def test_text_in_strings_and_comments_is_not_touched(self):
        src = '// Instance.Msg("x")\nconst help = "call Instance.Msg(text)"; /* Instance.FindEntityByName */\nconst t = `Instance.Msg(${1})`;\n'
        self.assertEqual(mig(src)[0], src)

    def test_a_script_with_its_own_console_is_left_for_a_person(self):
        src = 'const Console = { Log() {} };\nInstance.Msg("x");\n'
        body, _, done, manual = mig(src)
        self.assertEqual((body, done), (src, [])); self.assertIn('its own Console', manual[0]['why'])

    def test_instance_that_is_not_the_api_is_ignored(self):
        src = 'const Instance = makeFake();\nInstance.Msg("x");\n'
        self.assertEqual(jsapi.migrate(src), (src, [], []))

    def test_second_run_changes_nothing(self):
        once = jsapi.migrate(HEAD + 'Instance.Msg("a"); Instance.FindEntityByName("b");\n')[0]
        self.assertEqual(jsapi.migrate(once), (once, [], []))

    def test_every_rewrite_is_declared_by_the_typings(self):
        """the rules name real members: Valve's point_script.d.ts is the judge, not this file"""
        decls = api.parse(DTS)
        have = {(d['container'], d['name']) for d in decls if d['kind'] == 'member'}
        for g, name in list(jsapi.SAME.values()) + list(jsapi.FIRST.values()) + [('Entities', 'FireInput'), ('Entities', 'ConnectOutput')]:
            self.assertIn((api.GLOBALS[g], name), have, '%s.%s' % (g, name))
        self.assertIn(('Entity', 'FireInput'), have)
        self.assertIn(('IPointScript', 'OnModifyPlayerDamage'), have); self.assertIn(('IPointScript', 'OnScriptReload'), have)
        for old in list(jsapi.SAME) + list(jsapi.FIRST) + ['EntFireAtName', 'EntFireAtTarget', 'ConnectOutput', 'OnBeforePlayerDamage']:
            d = [x for x in decls if x['container'] == 'IPointScript' and x['name'] == old]
            self.assertTrue(d and all(x['deprecated'] for x in d), old + ' should still be declared, and deprecated')


class Imports(unittest.TestCase):
    def test_adds_what_is_used_and_keeps_the_rest(self):
        js = 'import { Instance, CSPlayerPawn } from "cs_script/point_script";\nEntities.FindByName("a"); Console.Log("b"); // GameRules.X\n'
        self.assertTrue(jsapi.ensure_imports(js).startswith('import { Instance, Entities, Console, CSPlayerPawn } from "cs_script/point_script";\n'))
        self.assertEqual(jsapi.ensure_imports(jsapi.ensure_imports(js)), jsapi.ensure_imports(js))

    def test_single_quotes_no_import_and_nothing_to_add(self):
        self.assertTrue(jsapi.ensure_imports("import { Instance } from 'cs_script/point_script';\nGameRules.GetRoundsPlayed();\n").startswith("import { Instance, GameRules } from 'cs_script/point_script';"))
        self.assertTrue(jsapi.ensure_imports('Console.Log("x");\n').startswith('import { Console } from "cs_script/point_script";\n\n'))
        self.assertEqual(jsapi.ensure_imports('const a = my.Console.Log;\n'), 'const a = my.Console.Log;\n')


class Generators(unittest.TestCase):
    """What stage C writes into a map's script: no deprecated call, and an import line that names what it uses."""
    MODULES = ('gen_script', 'animprops', 'envglobal', 'gameui', 'physlaunch', 'roundend', 'gravity', 'physpush')

    def setUp(self):
        self.decls = api.parse(DTS); self.tmp = tempfile.mkdtemp(prefix='jsapi_gen_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def check(self, js, name='g.js'):
        p = os.path.join(self.tmp, name)
        with open(p, 'w', encoding='utf-8') as f: f.write(js)
        return api.check(self.decls, p)

    def test_generator_sources_hold_no_deprecated_call(self):
        for mod in self.MODULES:
            path = os.path.join(TOOLS, mod + '.py')
            if not os.path.exists(path): continue
            with open(path, encoding='utf-8') as f: src = f.read()
            if 'cs_script/point_script' not in src: src = HEAD + src               # templates that rely on another module's import line
            p = os.path.join(self.tmp, mod + '.py')
            with open(p, 'w', encoding='utf-8') as f: f.write(src)
            unknown, dep = api.check(self.decls, p)
            self.assertEqual(dep, [], mod); self.assertEqual([u for u in unknown if u[1].startswith(('Instance', 'Entities', 'Console', 'GameRules'))], [], mod)

    def test_patched_scripts_import_what_they_use(self):
        import envglobal, physlaunch, animprops, gen_script
        old = 'import { Instance, CSPlayerPawn } from "cs_script/point_script";\n//   header\nInstance.OnRoundStart(() => {});\n'
        outs = {'envglobal': envglobal.patch_script(old, {'names': ['g'], 'initial': {}, 'autos': []}),
                'physlaunch': physlaunch.patch_script(old, [{'dest': 'd'}]),
                'animprops': animprops.patch_script(old, [{'name': 'p', 'frames': 2, 'fps': 5, 'owner': 'o', 'ownerClass': ''}]),
                'gen_script': gen_script.build('mg_x', 'mg_x_io', commands=['say hi'])}
        for mod, js in outs.items():
            first = js.split('\n', 1)[0]
            self.assertTrue(first.startswith('import {') and 'cs_script/point_script' in first, mod)
            used = [g for g in ('Entities', 'Console', 'GameRules') if (g + '.') in js]
            self.assertTrue(used, mod + ' should use the current API')
            for g in used: self.assertIn(g, first, '%s: %s is used but not imported' % (mod, g))
            unknown, dep = self.check(js, mod + '.js')
            self.assertEqual(dep, [], mod); self.assertEqual(unknown, [], mod)
        self.assertEqual(envglobal.patch_script(outs['envglobal'], {'names': ['g'], 'initial': {}, 'autos': []}).count('import {'), 1)   # a rerun

    def test_port_scripts_in_the_repo_are_on_the_current_api(self):
        files = sorted(glob.glob(os.path.join(REPO, 'ports', '*', 'scripts', '*.js')))
        self.assertGreater(len(files), 40)
        for f in files:
            unknown, dep = api.check(self.decls, f)
            self.assertEqual((unknown, dep), ([], []), os.path.relpath(f, REPO))
            with open(f, encoding='utf-8') as fh: self.assertEqual(jsapi.migrate(fh.read())[1:], ([], []), os.path.relpath(f, REPO))


class Checker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jsapi_api_')
        self.js = os.path.join(self.tmp, 'm.js')
        with open(self.js, 'w', encoding='utf-8') as f:
            f.write('import { Instance, Entities } from "cs_script/point_script";\nInstance.Msg("x");\nInstance.FindEntityByName("a");\nEntities.FindByName("a");\nInstance.NotARealCall();\n')
        self.allow = os.path.join(self.tmp, 'allow.txt')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_api(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()): rc = api.main(list(args))
        return rc, out.getvalue()

    def test_deprecated_and_invalid_are_told_apart_with_the_replacement(self):
        rc, text = self.run_api('--no-allow', '--check', self.js)
        self.assertEqual(rc, 1)                                                      # the invalid call fails without --strict
        self.assertIn('m.js:2: DEPRECATED Instance.Msg is deprecated; use Console.Log', text)
        self.assertIn('m.js:3: DEPRECATED Instance.FindEntityByName is deprecated; use Entities.FindByName(name)[0]', text)
        self.assertIn('m.js:5: INVALID Instance.NotARealCall is not in the typings', text)
        self.assertNotIn('m.js:4', text)                                             # the current call is fine
        self.assertIn('1 invalid, 2 deprecated', text)

    def test_strict_fails_on_deprecated_unless_allowed_with_a_reason(self):
        with open(self.js, 'w', encoding='utf-8') as f: f.write(HEAD + 'Instance.Msg("x");\nInstance.FindEntityByName("a");\n')
        self.assertEqual(self.run_api('--no-allow', '--check', self.js)[0], 0)
        self.assertEqual(self.run_api('--no-allow', '--strict', '--check', self.js)[0], 1)
        with open(self.allow, 'w', encoding='utf-8') as f: f.write('# kept\n%s  Instance.Msg  checked in game with this call\n' % self.js.replace('\\', '/'))
        rc, text = self.run_api('--allow', self.allow, '--strict', '--check', self.js)
        self.assertEqual(rc, 1); self.assertIn('ALLOWED Instance.Msg', text); self.assertIn('[kept: checked in game with this call]', text)
        self.assertIn('DEPRECATED Instance.FindEntityByName', text)
        with open(self.allow, 'a', encoding='utf-8') as f: f.write('*/m.js  *  baseline\n')
        rc, text = self.run_api('--allow', self.allow, '--strict', '--check', self.js)
        self.assertEqual(rc, 0); self.assertIn('2 allowed', text)

    def test_the_allowlist_never_excuses_an_invalid_call_and_needs_a_reason(self):
        with open(self.allow, 'w', encoding='utf-8') as f: f.write('*  *  everything\n')
        self.assertEqual(self.run_api('--allow', self.allow, '--strict', '--check', self.js)[0], 1)
        with open(self.allow, 'w', encoding='utf-8') as f: f.write('*.js  Instance.Msg\n')
        with self.assertRaises(SystemExit): self.run_api('--allow', self.allow, '--check', self.js)

    def test_json_output_and_glob(self):
        rc, text = self.run_api('--no-allow', '--json', '--check', os.path.join(self.tmp, '*.js'))
        d = json.loads(text)
        self.assertEqual((rc, d['scripts'], d['invalid'], d['deprecated'], d['ok'], d['level']), (1, 1, 1, 2, False, 'simulated'))
        f = {x['call']: x for x in d['findings']}
        self.assertEqual(f['Instance.Msg']['kind'], 'deprecated'); self.assertIn('Console.Log', f['Instance.Msg']['replacement'])
        self.assertEqual(f['Instance.NotARealCall']['kind'], 'invalid'); self.assertEqual(f['Instance.Msg']['line'], 2)
        self.assertEqual(self.run_api('--check', os.path.join(self.tmp, 'none*.js'))[0], 2)

    def test_lookup_says_deprecated_what_to_use_and_shows_a_repo_example(self):
        rc, text = self.run_api('FindEntityByName')
        self.assertEqual(rc, 0); self.assertIn('DEPRECATED', text); self.assertIn('use instead: Entities.FindByName(name)[0]', text)
        rc, text = self.run_api('--json', '--examples', '1', 'IEntities', 'FindByName')
        d = json.loads(text)['declarations'][0]
        self.assertEqual((d['name'], d['deprecated'], d['replacement']), ('FindByName', False, '')); self.assertIn('Entity[]', d['sig'])
        self.assertTrue(d['examples'] and 'FindByName(' in d['examples'][0])
        self.assertEqual(self.run_api('NoSuchCallAnywhere')[0], 1)

    def test_the_repo_allowlist_is_well_formed_and_only_names_deprecated_calls(self):
        decls = api.parse(DTS); dep = {'Instance.' + d['name'] for d in decls if d['container'] == 'IPointScript' and d['deprecated']}
        rows = api.load_allow(api.ALLOW)
        self.assertTrue(rows)
        for pat, name, reason in rows:
            self.assertTrue(name == '*' or name in dep, name); self.assertGreater(len(reason), 10, pat)


if __name__ == '__main__':
    unittest.main()
