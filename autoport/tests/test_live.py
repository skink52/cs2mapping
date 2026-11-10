"""cs2live.py, livetest.py and crashdump.py against the fake CS2 console. Nothing here starts CS2 or takes focus:
launching is tested with subprocess.Popen replaced, and process/window lookups are stubbed."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='autoport_live_')
os.environ['AUTOPORT_LIVE_STATE'] = TMP
import crashdump  # noqa: E402
import cs2live  # noqa: E402
import livetest  # noqa: E402
import vconsole as V  # noqa: E402
from fakecs2 import FakeCS2  # noqa: E402

cs2live.STATE_DIR = TMP
REAL_SLEEP = time.sleep
short_sleep = lambda s: REAL_SLEEP(min(s, 0.2))


class Parsing(unittest.TestCase):
    def test_getpos(self):
        self.assertEqual(cs2live.parse_getpos(['x', 'setpos 1.5 -2 64.000000;setang 10 270 0']), (1.5, -2.0, 64.0, 10.0, 270.0, 0.0))
        self.assertIsNone(cs2live.parse_getpos(['nothing']))

    def test_status_map(self):
        line = 'loaded spawngroup(  1)  : SV:  [1: mg_lego_course | main lump | mapload]'
        self.assertEqual(cs2live.status_map([line]), 'mg_lego_course')
        self.assertTrue(cs2live.status_has_map([line], 'MG_LEGO_COURSE'))
        self.assertIsNone(cs2live.status_map(['loaded spawngroup(  1)  : SV:  [1: <empty> | main lump | mapload]']))

    def test_cvars_and_angles(self):
        self.assertEqual(cs2live.cvar_values(['mp_freezetime = 0 ( def. "15" )'], ['mp_freezetime']), {'mp_freezetime': '0'})
        self.assertEqual(cs2live.look_at([0, 0, 64], [100, 0, 64])[:2], [0.0, 0.0])
        self.assertEqual(cs2live.look_at([0, 0, 64], [0, 100, 64])[1], 90.0)
        self.assertGreater(cs2live.look_at([0, 0, 164], [100, 0, 64])[0], 0)     # looking down is positive pitch


class Images(unittest.TestCase):
    def test_png_is_valid(self):
        path = os.path.join(TMP, 'x.png')
        cs2live.write_png(path, 2, 2, bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 9, 9, 9]))
        with open(path, 'rb') as f:
            data = f.read()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        w, h = struct.unpack('>II', data[16:24])
        self.assertEqual((w, h), (2, 2))
        idat = data[data.index(b'IDAT') + 4:data.index(b'IEND') - 8]
        self.assertEqual(zlib.decompress(idat), b'\0' + bytes([255, 0, 0, 0, 255, 0]) + b'\0' + bytes([0, 0, 255, 9, 9, 9]))

    def test_frame_check(self):
        w, h = 320, 180
        flat = bytes([20, 20, 20, 255]) * (w * h)
        self.assertFalse(cs2live.frame_check(w, h, flat)['ok'])
        import random
        rnd = random.Random(1)
        noisy = bytes(rnd.randrange(256) for _ in range(w * h * 4))
        good = cs2live.frame_check(w, h, noisy)
        self.assertTrue(good['ok'], good)
        again = cs2live.frame_check(w, h, noisy, previous=good['signature'])
        self.assertIn('frame did not change after the camera move', again['reasons'])


class Launching(unittest.TestCase):
    def test_flags(self):
        argv = cs2live.launch_command('mg_x', hammer_map='mg_x', netcon=2121)
        self.assertEqual(argv[:3], [cs2live.CS2_EXE, '-addon', 'mg_x'])
        for f in ('-tools', '-steam', '-retail', '-gpuraytracing', '-novid', '+sv_steamauth_enforce', '-noassetbrowser', '-windowed',
                  '+engine_no_focus_sleep'):
            self.assertIn(f, argv)
        self.assertEqual(argv[argv.index('-asset') + 1], 'maps/mg_x.vmap')
        self.assertEqual(argv[argv.index('-netconport') + 1], '2121')

    def test_launch_minimised_without_activation_and_refuses_over_a_running_game(self):
        proc = mock.Mock(pid=4242)
        proc.poll.return_value = None
        with mock.patch.object(cs2live, 'cs2_processes', return_value=[]), \
                mock.patch.object(cs2live.subprocess, 'Popen', return_value=proc) as popen, \
                mock.patch.object(cs2live.vconsole, 'reachable', return_value=True), \
                mock.patch.object(cs2live.time, 'sleep'), mock.patch.object(cs2live, 'pid_alive', return_value=True):
            r = cs2live.launch('mg_x')
        kw = popen.call_args.kwargs
        self.assertEqual(kw['startupinfo'].wShowWindow, 7)                    # SW_SHOWMINNOACTIVE
        self.assertTrue(kw['creationflags'] & subprocess.DETACHED_PROCESS)
        self.assertEqual(kw['cwd'], cs2live.GAME_BIN)
        self.assertEqual(r['pid'], 4242)
        self.assertIn(4242, cs2live.launched_pids())
        with mock.patch.object(cs2live, 'cs2_processes', return_value=[{'pid': 1, 'mode': 'game', 'addon': None}]):
            with self.assertRaises(cs2live.GameError):
                cs2live.launch('mg_x')

    def test_stop_leaves_other_games_alone(self):
        self.assertIn('not started by autoport', cs2live.stop(999999))

    def test_focus_refused_unless_allowed(self):
        with self.assertRaises(cs2live.GameError):
            cs2live.focus(123)

    def test_lock(self):
        with cs2live.exclusive('a'):
            with self.assertRaises(cs2live.GameError):
                with cs2live.exclusive('b', wait=0.5):
                    pass
        with open(os.path.join(TMP, cs2live.LOCK), 'w') as f:
            json.dump({'pid': 999999, 'owner': 'dead', 'time': time.time()}, f)
        with mock.patch.object(cs2live, 'pid_alive', return_value=False):
            with cs2live.exclusive('c', wait=1):
                pass


class GameTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCS2()
        self.p = mock.patch.object(cs2live, 'cs2_processes', return_value=[])
        self.p.start()
        self.g = cs2live.connect(self.fake.port, addon='mg_test')

    def tearDown(self):
        self.g.c.close()
        self.fake.close()
        self.p.stop()

    def test_load_map(self):
        self.fake.maps['mg_test'] = ['Error loading resource materials/x/missing.vmat']
        r = self.g.load_map('mg_test')
        self.assertTrue(r['ok'], r)
        self.assertIn('map_workshop mg_test mg_test', self.fake.commands())
        self.assertIn('Error loading resource materials/x/missing.vmat', r['lines'])
        self.assertEqual(r['freezetime'], '0')
        self.assertTrue(r['player'])

    def test_load_map_invalid(self):
        self.fake.invalid_maps.add('nope')
        r = self.g.load_map('nope', timeout=5)
        self.assertFalse(r['ok'])
        self.assertIn('Invalid map name', r['reason'])

    def test_load_map_crash(self):
        self.fake.crash_after_load = True
        self.fake.maps['mg_test'] = []
        r = self.g.load_map('mg_test', timeout=10)
        self.assertFalse(r['ok'])
        self.assertTrue(r['crashed'])
        self.assertIn('console closed', r['reason'])

    def test_console_screenshot_and_place(self):
        self.fake.map = 'mg_test'
        path = self.g.console_screenshot('autoport_view')
        self.assertTrue(path.endswith(os.path.join('mg_test', 'screenshots/autoport_view_0001.jpg')))
        eye = self.g.place([100, 200, 0], [5, 90, 0])
        self.assertEqual([round(v) for v in eye[:5]], [100, 200, 64, 5, 90])
        self.assertTrue(self.fake.noclip)

    def test_views_console(self):
        self.fake.map = 'mg_test'
        r = self.g.views([{'name': 'spawn t', 'pos': [0, 0, 0], 'ang': [0, 45, 0]}], TMP)
        self.assertEqual(len(r['shots']), 1)
        self.assertIn('cl_drawhud 1', self.fake.commands())                  # HUD restored afterwards

    def test_reset(self):
        self.fake.map = 'mg_test'
        with mock.patch.object(cs2live.time, 'sleep'):
            r = self.g.reset()
        self.assertTrue(r['ok'])
        for c in ('-forward', 'noclip 0', 'bot_kick', 'mp_restartgame 1', 'weapon_recoil_scale 2'):
            self.assertIn(c, self.fake.commands())

    def test_walk_to_with_real_keys(self):
        self.fake.map = 'mg_test'
        self.fake.pos = [0.0, 0.0, 64.0]
        issue = livetest.walk_to(self.g, [200, 0, 0], radius=30, within=10)
        self.assertIsNone(issue)
        self.assertIn('+forward', self.fake.commands())
        self.assertIn('-duck', self.fake.commands()[-3:])                     # keys released at the end (inside the markers)

    def test_timing(self):
        self.fake.map = 'mg_test'
        r = livetest.timing(self.g, [0, 0, 0], [0, 300, 0], within=10)
        self.assertTrue(r['ok'], r)
        self.assertGreater(r['seconds'], 0.5)

    def test_scenario(self):
        self.fake.map = 'mg_test'
        self.fake.delayed['ent_fire'] = (0.2, ['S_DOOR opened'])
        steps = [{'fire': 'door1 Open', 'wait': 0.1}, {'expect': 'S_DOOR opened', 'within': 3}, {'hold': {'key': 'jump', 'seconds': 0.1}},
                 {'aim': [100, 0, 64]}, {'walk': [10, 10, 0]}, {'shot': 'after door'}, {'say': 'hello'}]
        r = livetest.scenario(self.g, steps, timeout=30, out_dir=TMP)
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['steps_done'], len(steps))
        self.assertTrue(r['shots'][0]['path'])
        cmds = self.fake.commands()
        self.assertLess(cmds.index('+jump'), len(cmds) - 1 - cmds[::-1].index('-jump'))   # held, then released
        r = livetest.scenario(self.g, [{'mouse': {'dx': 10, 'dy': 0}}], timeout=10)
        self.assertFalse(r['ok'])
        self.assertIn('--focus', r['reason'])
        r = livetest.scenario(self.g, [{'expect': 'never printed', 'within': 0.5}], timeout=10)
        self.assertIn('never printed', r['reason'])
        with self.assertRaises(ValueError):
            livetest.validate_steps([{'say': 'a;b'}])

    def test_playtest_and_script_errors(self):
        self.fake.map = 'mg_test'
        self.fake.after_load = []
        self.fake.delayed['mp_restartgame'] = (0.1, ['Uncaught TypeError: x is not a function', 'Error loading resource models/a.vmdl'])
        with mock.patch.object(livetest.time, 'sleep', side_effect=short_sleep):
            r = livetest.playtest(self.g, 'mg_test', bots=2, seconds=1, out_dir=TMP)
        self.assertEqual(self.fake.cvars['bot_quota'], '2')
        self.assertIn('jointeam 1', self.fake.commands())
        self.assertFalse(r['ok'])
        self.assertTrue(any('TypeError' in e for e in r['script_errors']))
        self.assertTrue(os.path.exists(r['log']))

    def test_mode_playtest_restores_cvars(self):
        self.fake.map = 'mg_test'
        with mock.patch.object(livetest.time, 'sleep', side_effect=short_sleep):
            r = livetest.mode_playtest(self.g, 'mg_test', 'mg_test', 1, 2, bots=0, seconds=1)
        self.assertEqual(r['mode'], {'game_type': 1, 'game_mode': 2})
        self.assertEqual((self.fake.cvars['game_type'], self.fake.cvars['game_mode']), ('0', '0'))
        self.assertEqual(self.fake.cvars['mp_freezetime'], '15')

    def test_physics_probe_spawns_probe_once(self):
        self.fake.map = 'mg_test'
        self.fake.entities = {'crate1': 'prop_physics'}
        r = livetest.physics_probe(self.g, ['crate1', 'gone'])
        self.assertEqual({e['name']: e['count'] for e in r['entities']}, {'crate1': 1, 'gone': 0})
        self.assertTrue(any(c.startswith('ent_create point_script') for c in self.fake.commands()))

    def test_marks(self):
        self.fake.map = 'mg_test'
        with mock.patch.object(livetest, 'marks_cfg_path', return_value=os.path.join(TMP, 'autoport_mark.cfg')):
            self.assertEqual(livetest.marks_install(self.g, 'F8'), 'F8')
        self.assertEqual(self.fake.binds['F8'], 'exec autoport_mark')
        lines = [V.Line(livetest.MARK_BEGIN, 1000), V.Line('setpos 1 2 66;setang 3 4 0', 1010),
                 V.Line('loaded spawngroup(  1)  : SV:  [1: mg_test | main lump | mapload]', 1020),
                 V.Line('Screenshot written to: screenshots/autoport_mark_0003.jpg', 1100),
                 V.Line('[ALL] skink52‎: door here does not open', 4000)]
        m = livetest.marks_harvest(lines)[0]
        self.assertEqual((m['eye'], m['map'], m['note']), ([1.0, 2.0, 66.0], 'mg_test', 'door here does not open'))
        self.fake.binds['F9'] = '+jump'
        self.assertIn('bound to', livetest.marks_install(self.g, 'F9'))

    def test_script_reload(self):
        self.fake.map = 'mg_test'
        livetest.script_reload(self.g, 'game_script', 'maps/scripts/game.vjs', {'spawnflags': '0'})
        cmds = self.fake.commands()
        self.assertIn('ent_fire game_script Kill', cmds)
        self.assertTrue(any(c.startswith('ent_create point_script {"targetname" "game_script" "cs_script" "maps/scripts/game.vjs"') for c in cmds))
        with self.assertRaises(ValueError):
            livetest.script_reload(self.g, 'bad name', 'x.vjs')


def minidump(path, code=0xC00000FD, module='server.dll', offset=0x1234, pid=777, start=1700000000, strings=()):
    """A small but valid minidump: header, directory, module list, exception, misc info, some console text."""
    name = module.encode('utf-16-le')
    base = 0x7FF000000000
    body = bytearray()
    off = 32 + 3 * 12                                       # header + 3 directory entries
    name_rva = off
    body += struct.pack('<I', len(name)) + name
    mod_rva = off + len(body)
    body += struct.pack('<I', 1) + struct.pack('<QIIII', base, 0x100000, 0, 0, name_rva) + b'\0' * (108 - 24)
    exc_rva = off + len(body)
    body += struct.pack('<II', 5, 0) + struct.pack('<IIQQI', code, 0, 0, base + offset, 0) + b'\0' * 140
    misc_rva = off + len(body)
    body += struct.pack('<IIII', 24, 3, pid, start) + b'\0' * 8
    for s in strings:
        body += b'\0\0' + s.encode() + b'\0\0'
    head = b'MDMP' + struct.pack('<IIIIIQ', 0xA793, 3, 32, 0, 0, 0)
    dirs = struct.pack('<III', 4, 112, mod_rva) + struct.pack('<III', 6, 168, exc_rva) + struct.pack('<III', 15, 24, misc_rva)
    with open(path, 'wb') as f:
        f.write(head + dirs + bytes(body))


class CrashDumps(unittest.TestCase):
    def test_parse_and_hint(self):
        d = tempfile.mkdtemp(prefix='dumps_', dir=TMP)
        p = os.path.join(d, 'cs2_2026_1110_120000_0_crash.mdmp')
        minidump(p, strings=['12(34.5): Uncaught Error: bad thing in maps/scripts/x.vjs', '13(40.0): FATAL ERROR: missing model'])
        r = crashdump.report(p)
        self.assertEqual(r['exception']['name'], 'STACK_OVERFLOW')
        self.assertEqual(r['module'], {'name': 'server.dll', 'offset': '0x1234'})
        self.assertEqual((r['pid'], r['process_start']), (777, 1700000000))
        self.assertIn('recursed', r['hint'])
        self.assertEqual(r['console_tail'], ['34.5s Uncaught Error: bad thing in maps/scripts/x.vjs', '40.0s FATAL ERROR: missing model'])

    def test_newest_since(self):
        d = tempfile.mkdtemp(prefix='dumps_', dir=TMP)
        old = os.path.join(d, 'cs2_a_crash.mdmp')
        minidump(old)
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        self.assertEqual(crashdump.newest(d), old)
        self.assertIsNone(crashdump.newest(d, since=time.time() - 60))
        new = os.path.join(d, 'cs2_b_accessviolation.mdmp')
        minidump(new, code=0xC0000005)
        self.assertEqual(crashdump.newest(d, since=time.time() - 60), new)

    @unittest.skipUnless(crashdump.dumps(), 'no real CS2 dumps on this PC')
    def test_real_dump_parses(self):
        r = crashdump.report(crashdump.dumps()[0])
        self.assertTrue(r['exception'] and r['modules'] > 10)


if __name__ == '__main__':
    unittest.main()
