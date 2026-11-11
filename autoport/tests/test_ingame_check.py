"""ingame_check.py: the line rules, the baseline, a full check against the fake CS2 (clean, problems, crash, skipped) and the
autoport hook. Nothing launches CS2."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='autoport_ingame_')
os.environ['AUTOPORT_LIVE_STATE'] = TMP
import cs2live  # noqa: E402
import ingame_check as IC  # noqa: E402
from fakecs2 import FakeCS2  # noqa: E402
from test_live import minidump  # noqa: E402

cs2live.STATE_DIR = TMP


class Rules(unittest.TestCase):
    CASES = [
        ('Counter-Terrorists Win!', None),
        ('Terrorist bot joined', None),
        ('Annotation: Error loading file : Missing file', None),
        ("Error loading resource file 'materials/port/wall01.vmat_c' (Error: ERROR_FILEOPEN)", 'missing'),
        ('Failed to load model models/props/crate.vmdl', 'missing'),
        ('Uncaught TypeError: Cannot read properties of undefined', 'io'),
        ('Method CBaseEntity.GetAbsOrigin invoked on an invalid entity.', 'io'),
        ("Couldn't find output named OnPressedd", 'io'),
        ("Entity door1 (func_door) has no input named 'Opne'", 'io'),
        ('Invalid map name: mg_nope', 'error'),
        ('FATAL ERROR: something bad', 'error'),
        ("Unknown command 'mp_team_intro_time'!", 'minor'),
        ('Warning: something no rule has seen', 'unknown'),
        ('loaded spawngroup(  1)  : SV:  [1: mg_x | main lump | mapload]', None),
        ("65535 [NoChan]    0    0 challenging      0unknown ''", None),
        ('errors: 0', None),
    ]

    def test_table(self):
        for text, kind in self.CASES:
            self.assertEqual(IC.classify_line(text), kind, text)

    def test_channel_fallback(self):
        self.assertEqual(IC.classify_line('Something failed oddly', 'Entity System'), 'io')

    def test_baseline(self):
        lines = ['Warning: stock engine thing 123', 'Warning: mg_x specific 5']
        path = os.path.join(TMP, 'baseline.json')
        IC.record_baseline(['Warning: stock engine thing 999'], ('stock', 'de_dust2'), path)
        found = IC.classify(lines, IC.load_baseline(path), ('mg_x', 'mg_x'))
        self.assertEqual(found, {'unknown': ['Warning: mg_x specific 5']})


class Check(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCS2(addon='mg_test')
        self.out = tempfile.mkdtemp(prefix='out_', dir=TMP)
        self.p = mock.patch.object(cs2live, 'cs2_processes', return_value=[])
        self.p.start()

    def tearDown(self):
        self.fake.close()
        self.p.stop()

    def check(self, **kw):
        return IC.check('mg_test', 'mg_test', seconds=kw.pop('seconds', 1), port=self.fake.port, out_dir=self.out, **kw)

    def test_clean_map(self):
        r = self.check(screenshot=True)
        self.assertEqual(r['exit'], 0, r['notes'])
        self.assertTrue(r['load']['ok'])
        self.assertEqual(r['notes'][0][0], 'playtest')
        self.assertTrue(r['screenshot'].endswith('.jpg'))
        self.assertTrue(os.path.exists(r['report']) and os.path.exists(r['report'][:-3] + '.json'))
        with open(r['report'], encoding='utf-8') as f:
            self.assertNotIn('old line from before', f.read())   # the backlog isn't this map's

    def test_problems_are_sorted_and_noted(self):
        self.fake.maps['mg_test'] = ["Error loading resource file 'materials/port/wall01.vmat_c' (Error: ERROR_FILEOPEN)",
                                     "Entity door1 (func_door) has no input named 'Opne'"]
        self.fake.after_load = ['Uncaught TypeError: x is not a function', 'S_MAP echo from the map script: ready']
        r = self.check()
        self.assertEqual(r['exit'], 1)
        kinds = {k for k, _ in r['notes']}
        self.assertEqual(kinds, {'missing', 'io'})
        self.assertEqual(len(r['issues']['io']), 2)
        with open(r['report'][:-3] + '.json', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn('S_MAP echo from the map script: ready', [l['text'] for l in data['console']])   # echo output is read
        self.assertIn('Entity System', {l['chan'] for l in data['console']})

    def test_load_fails(self):
        self.fake.invalid_maps.add('mg_test')
        r = IC.check('mg_test', 'mg_test', seconds=1, port=self.fake.port, out_dir=self.out, load_timeout=3)
        self.assertEqual(r['exit'], 2)
        self.assertTrue(any(k == 'error' and 'did not load' in t for k, t in r['notes']))

    def test_crash_reads_new_dump(self):
        dumps = tempfile.mkdtemp(prefix='dumps_', dir=TMP)
        self.fake.crash_after_load = True
        with mock.patch.object(IC.crashdump, 'GAME_BIN', dumps):
            threading_dump = lambda: minidump(os.path.join(dumps, 'cs2_2026_1110_1_0_crash.mdmp'), code=0xC0000005, module='server.dll')
            self.fake.after_load = []
            self.fake.on_crash = threading_dump             # the dump exists before the console drops, as with a real crash
            r = self.check(seconds=3)
        self.assertEqual(r['exit'], 2)
        self.assertTrue(r['crashed'])
        self.assertIn('ACCESS_VIOLATION', r['crash']['summary'])
        self.assertTrue(any(k == 'error' and 'CS2 crashed' in t for k, t in r['notes']))

    def test_skipped_without_console(self):
        r = IC.check('mg_test', seconds=1, port=1, out_dir=self.out)
        self.assertEqual(r['exit'], 3)
        self.assertIn('no CS2 console', r['skipped'])

    def test_autoport_hook(self):
        class M:
            addon = 'mg_test'
            notes = []

            def note(self, kind, text, reopen=False):
                self.notes.append((kind, text, reopen))
        self.fake.maps['mg_test'] = ['Failed to load model models/props/crate.vmdl']
        m = M()
        code = IC.run_for_autoport(m, seconds=1, port=self.fake.port, out_dir=self.out)
        self.assertEqual(code, 1)
        self.assertIn(('missing', True), {(k, r) for k, _, r in m.notes})
        self.assertTrue(any(k == 'review' and 'In-game report' in t for k, t, _ in m.notes))
        m2 = M()
        m2.notes = []
        with mock.patch.object(IC.vconsole, 'reachable', return_value=False):
            self.assertEqual(IC.run_for_autoport(m2, seconds=1, out_dir=self.out), 3)
        self.assertEqual(m2.notes[0][0], 'playtest')



class SpawnViews(unittest.TestCase):
    def test_from_vmf(self):
        d = tempfile.mkdtemp(prefix='vmf_', dir=TMP)
        with open(os.path.join(d, 'mg_v.vmf'), 'w') as f:
            f.write('entity\n{\n\t"id" "1"\n\t"classname" "info_player_terrorist"\n\t"angles" "0 90 0"\n\t"origin" "10 20 30"\n}\n'
                    'entity\n{\n\t"classname" "info_player_counterterrorist"\n\t"origin" "-5 0 8"\n}\n')
        with mock.patch.object(IC, 'VMF_DIR', d):
            v = IC.spawn_views('mg_v')
        self.assertEqual([x['pos'] for x in v], [[10.0, 20.0, 30.0], [-5.0, 0.0, 8.0]])
        self.assertEqual(v[0]['ang'], [0.0, 90.0, 0.0])


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
