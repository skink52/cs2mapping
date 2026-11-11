"""create/mechkit.py + create/mech/*.js: every module's bundle runs clean on create/test/mock_point_script.mjs (Node), HUD themes, map
placement. Skipped without Node. Runtime-checked on the mock engine only; none of these mechanics has been played in CS2 yet.

  python -m unittest discover -s tools/tests -p "test_mechkit.py" -v
"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.append(F.CREATE)
import mechkit

NODE = shutil.which('node')
ENTS = [{'name': 'drone1', 'cls': 'prop_dynamic', 'origin': [0, 0, 64]}, {'name': 'car1', 'cls': 'prop_dynamic', 'origin': [100, 0, 0]},
        {'name': 'tur1', 'cls': 'prop_dynamic', 'origin': [0, 100, 0]}, {'name': 'mech_hud', 'cls': 'custom_hud_layout', 'origin': [0, 0, 0]}]
CONFIGS = {
    'abilities': {'abilities': [{'kind': k, 'key': key} for k, key in [('double_jump', None), ('dash', 'attack2'), ('jetpack', 'reload'), ('blink', 'inspect'),
                                                                      ('flight', 'walk'), ('shield', 'use'), ('invisibility', 'duck'), ('wallhack', 'attack2'),
                                                                      ('heal', 'reload')]] +
                  [{'kind': 'low_gravity', 'strength': 0.5}, {'kind': 'speed', 'strength': 1.3}, {'kind': 'jump_pad', 'strength': 900, 'push': 300}]},
    'minigames': {'minigames': [{'kind': 'gallery', 'name': 'gal', 'targets': 5, 'up': 2, 'seconds': 10}, {'kind': 'race', 'name': 'race', 'checkpoints': 4},
                                {'kind': 'collect', 'name': 'coin', 'items': 3, 'shared': True}]},
    'controls': {'controls': [{'kind': 'drone', 'prop': 'drone1'}, {'kind': 'car', 'prop': 'car1'}, {'kind': 'turret', 'prop': 'tur1', 'radius': 4000}]},
    'weapons': {'weapons': [{'weapon': 'weapon_awp', 'kind': 'pierce'}, {'weapon': 'weapon_nova', 'kind': 'explosive'},
                            {'weapon': 'weapon_ak47', 'kind': 'burst'}, {'weapon': 'weapon_deagle', 'kind': 'knockback'}]},
    'hideseek': {'hideseek': {'hide_seconds': 5, 'seek_seconds': 20, 'models': ['models/a.vmdl', 'models/b.vmdl'], 'miss_damage': 5}},
    'story': {'story': {'start': 'intro', 'steps': {'intro': {'text': 'Find the switch', 'on': {'story_switch': 'run'}, 'do': [{'fire': 'door1', 'input': 'Open'}]},
                                                    'run': {'text': 'Run!', 'seconds': 10, 'timeout': 'lose', 'on': {'story_exit': 'win'}},
                                                    'win': {'text': 'Escaped', 'do': [{'end': 'win'}]}, 'lose': {'text': 'Too slow', 'do': [{'end': 'lose'}]}}}},
    'mode': {'mode': {'name': 'deathmatch', 'commands': ['mp_respawn_on_death_t 1'], 'give': ['weapon_ak47']}},
}


@unittest.skipUnless(NODE, 'Node not installed')
class MockRuns(unittest.TestCase):
    def run_cfg(self, key, seconds=40):
        code, out = mechkit.test(CONFIGS[key], seconds=seconds, players=6, entities=ENTS)
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn('OK: no errors', out)
        return out

    def test_abilities(self): self.run_cfg('abilities')
    def test_minigames(self):
        out = self.run_cfg('minigames')
        self.assertRegex(out, r'script inputs \(gal_start')
    def test_controls(self): self.run_cfg('controls')
    def test_weapons(self): self.run_cfg('weapons')
    def test_hideseek(self): self.run_cfg('hideseek')
    def test_story(self):
        out = self.run_cfg('story')
        self.assertIn('story_switch', out)
    def test_mode(self): self.run_cfg('mode')

    def test_all_together_parses(self):
        allc = {}
        for c in CONFIGS.values(): allc.update(c)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'b.mjs')
            F.write(p, mechkit.bundle(allc).replace('import { Instance, CSInputs } from "cs_script/point_script";', 'const Instance = {}, CSInputs = {};'))
            r = subprocess.run([NODE, '--check', p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        code, out = mechkit.test(allc, seconds=30, players=4, entities=ENTS)
        self.assertEqual(code, 0, out[-2000:])


class Hud(unittest.TestCase):
    def test_themes_and_rows(self):
        cfg = dict(CONFIGS['abilities'], hud={'theme': 'neon'})
        files = mechkit.hud_files(cfg, 'mymap')
        xml = files['panorama/layout/custom_game/mymap.xml']; css = files['panorama/styles/custom_game/mymap.css']
        self.assertIn('styles/custom_game/mymap.css', xml); self.assertIn('{s:ab1}', xml); self.assertIn('#ff2bd6', css)
        ids = re.findall(r'id="([^"]+)"', xml)
        self.assertEqual(len(ids), len(set(ids)))
        for t in mechkit.THEMES: mechkit.hud_files(dict(cfg, hud={'theme': t}))
        with self.assertRaises(ValueError): mechkit.hud_files({'hud': {'theme': 'pink'}})
        b = mechkit.bundle(cfg, 'mymap')
        self.assertIn('"entity":"mymap_hud"', b); self.assertIn('abilitiesInstall();', b); self.assertNotIn('storyInstall();', b)

    def test_build_files(self):
        with tempfile.TemporaryDirectory() as d:
            files = mechkit.build(CONFIGS['story'], d, 'tale')
            self.assertEqual(files, ['maps/scripts/tale.js', 'panorama/layout/custom_game/tale.xml', 'panorama/styles/custom_game/tale.css'])


PLACE = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, primitives as P, mechkit
P.CATALOG = None
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
mechkit.place({'hideseek': {}, 'story': {'start': 'a', 'steps': {'a': {}}}}, 'tale')
mechkit.trigger(P.box((0, 0, 0), (64, 64, 64), 'materials/tools/toolstrigger.vmat'), 'story_switch', 'tale')
vmapgen.finish(d, OUT, group='t')
'''


class Place(unittest.TestCase):
    @unittest.skipUnless(__import__('fgdcat').fgd_paths(), 'CS2 not installed (the map build reads its FGDs)')
    def test_entities(self):
        root = tempfile.mkdtemp(prefix='cs2mcp_mk_')
        try:
            out = F.make_map(os.path.join(root, 'm.vmap'), PLACE)
            import vmapedit as V
            m = V.Map(out)
            byname = {m.name(e): e for e in m.entities()}
            self.assertEqual(m.P(byname['tale'], 'cs_script'), 'maps/scripts/tale.vjs')
            self.assertEqual(m.P(byname['tale_hud'], 'layout'), 'panorama/layout/custom_game/tale.vxml')
            wins = {m.name(e): m.conn_tuple(m.conns(e)[0]) for e in m.by_class('logic_relay')}
            self.assertEqual(wins['story_win'][:4], ('OnTrigger', 'tale_params', 'FireWinCondition', '8'))
            trig = m.by_class('trigger_multiple')[0]
            self.assertEqual(m.conn_tuple(m.conns(trig)[0])[:4], ('OnStartTouch', 'tale', 'RunScriptInput', 'story_switch'))
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
