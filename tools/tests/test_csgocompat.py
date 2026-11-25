"""csgocompat passes, texfix matscroll / BSPSource scale snap, lighting style names (cs2-slop-porting 2026-11-24 recheck, 25 Nov 2026).

  python -m unittest discover -s tools/tests -p "test_csgocompat.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vmapedit as V, watervol, dmx, csgocompat as CC, texfix, lighting

VMF = '''world
{
	"classname" "worldspawn"
}
entity
{
	"classname" "func_door"
	"targetname" "door"
	"origin" "0 0 0"
}
entity
{
	"classname" "info_target"
	"targetname" "door"
	"origin" "500 0 0"
}
'''


class Ctx:
    def __init__(s, root=''): s.log = []; s.todo = []; s.files = {}; s.root = root; s.addon = 'm'; s.src = None; s.content = root
    def write(s, rel, data): s.files[rel] = data.encode() if isinstance(data, str) else data


def empty_map():
    m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
    return m


class LightStyles(unittest.TestCase):
    def test_names(self):
        self.assertEqual(lighting.LIGHT_STYLE_NAMES[1], 'flicker_1')
        self.assertEqual(lighting.LIGHT_PATTERN_NAMES['mamamamamama'], 'fast_strobe')
        self.assertEqual(len(lighting.LIGHT_PATTERN_NAMES), 11)


class Compat(unittest.TestCase):
    def setUp(self):
        m = self.m = empty_map()
        self.light = m.new_entity('light_omni2', [0, 0, 0], {'targetname': 'lamp', 'clientSideEntity': '1', 'directlight': '1',
                                                             'light_style': 'mmnmmommommnonmmonqnmmo'})
        self.tele = m.new_entity('trigger_teleport', [0, 0, 0], {'target': 'dest', 'UseLandmarkAngles': '1'})
        self.amb = m.new_entity('ambient_generic', [0, 0, 0], {'targetname': 'music', 'spawnflags': '0'})
        self.prop = m.new_entity('prop_dynamic', [0, 0, 0], {'DefaultAnim': 'idle'})
        self.br = m.new_entity('func_breakable', [0, 0, 0], {'targetname': 'box', 'health': '10'})
        self.lit = m.new_entity('light_barn', [0, 0, 0], {'targetname': 'spot'})
        r = self.relay = m.new_entity('logic_relay', [0, 0, 0], {'targetname': 'go'})
        m.add_conn(r, 'OnTrigger', 'lamp', 'TurnOff')
        m.add_conn(r, 'OnTrigger', 'lamp', 'SetPattern', 'mamamamamama')
        m.add_conn(r, 'OnTrigger', 'music', 'Volume', '0')
        m.add_conn(r, 'OnTrigger', 'box', 'AddOutput', 'health 50')
        m.add_conn(r, 'OnTrigger', 'box', 'AddOutput', 'rendermode 10')
        m.add_conn(r, 'OnTrigger', 'spot', 'AddOutput', 'rendercolor 255 0 0')
        m.add_conn(r, 'OnTrigger', 'box', 'AddOutput', 'OnUser1 lamp:TurnOn::0:1')
        m.add_conn(r, 'OnTrigger', '!activator', 'AddOutput', 'health 500')

    def conns(self):
        return [self.m.conn_tuple(x)[:4] for x in self.m.conns(self.relay)]

    def test_all(self):
        m, c = self.m, Ctx()
        n = CC.run(m, c, {'compat'})
        self.assertGreater(n, 0)
        self.assertEqual(m.P(self.light, 'clientSideEntity'), '0')
        self.assertEqual(m.P(self.light, 'directlight'), '2')
        self.assertEqual(m.P(self.light, 'light_style'), 'flicker_1')
        self.assertEqual(m.P(self.tele, 'use_landmark_angles'), '1')
        self.assertEqual(m.P(self.prop, 'IdleAnim'), 'idle')
        cs = self.conns()
        self.assertIn(('OnTrigger', 'lamp', 'Disable', ''), cs)
        self.assertIn(('OnTrigger', 'lamp', 'SetStyle', 'fast_strobe'), cs)
        i_stop = cs.index(('OnTrigger', 'music', 'StopSound', '')); i_vol = cs.index(('OnTrigger', 'music', 'Volume', '0'))
        self.assertLess(i_stop, i_vol)                                    # in front: same-time events fire in queue order
        self.assertIn(('OnTrigger', 'box', 'SetHealth', '50'), cs)
        self.assertIn(('OnTrigger', 'spot', 'SetColor', '255 0 0'), cs)
        self.assertIn(('OnTrigger', 'box', 'AddOutput', 'OnUser1>lamp>TurnOn>>0>1'), cs)
        self.assertFalse(any(p == 'rendermode 10' for _o, _t, _i, p in cs))
        self.assertIn(('OnTrigger', '!activator', 'AddOutput', 'health 500'), cs)   # left for the io script
        self.assertTrue(any('!activator health' in t for t in c.todo))
        before = self.conns()
        self.assertEqual(CC.run(m, Ctx(), {'compat'}), 0)                 # rerun-safe
        self.assertEqual(self.conns(), before)

    def test_opt_in_not_in_compat(self):
        c = Ctx(); CC.run(self.m, c, {'compat'})
        self.assertFalse(any('physboxmass' in l or 'debugwatch' in l for l in c.log + c.todo))


class SharedParent(unittest.TestCase):
    def test_first_in_vmf(self):
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, 'source1', 'maps'))
            with open(os.path.join(tmp, 'source1', 'maps', 'm.vmf'), 'w', encoding='utf-8') as fh: fh.write(VMF)
            m = empty_map()
            other = m.new_entity('info_target', [500, 0, 0], {'targetname': 'door'})
            door = m.new_entity('func_door', [0, 0, 0], {'targetname': 'door'})
            kid = m.new_entity('prop_dynamic', [0, 0, 0], {'parentname': 'door'})
            r = m.new_entity('logic_relay', [0, 0, 0], {'targetname': 'go'}); m.add_conn(r, 'OnTrigger', 'door', 'Open')
            c = Ctx(tmp)
            self.assertEqual(CC.sharedparent(m, c), 1)
            self.assertEqual(m.name(door), 'door__parent'); self.assertEqual(m.name(other), 'door')
            self.assertEqual(m.P(kid, 'parentname'), 'door__parent')
            self.assertIn(('OnTrigger', 'door__parent', 'Open', ''), [m.conn_tuple(x)[:4] for x in m.conns(r)])
            self.assertEqual(CC.sharedparent(m, Ctx(tmp)), 0)
        finally: shutil.rmtree(tmp, ignore_errors=True)


class TexFix(unittest.TestCase):
    def test_snap(self):
        self.assertEqual(texfix._snap_decompile_scale(0.0313), 0.03125)
        self.assertEqual(texfix._snap_decompile_scale(0.1563), 0.15625)
        self.assertEqual(texfix._snap_decompile_scale(0.3), 0.3)
        self.assertEqual(texfix._snap_decompile_scale(0.25), 0.25)

    def test_proxies(self):
        raw = (b'"LightmappedGeneric"\n{ "$basetexture" "x"\n "Proxies" { "TextureScroll" { "texturescrollvar" "$basetexturetransform" '
               b'"texturescrollrate" .5 "texturescrollangle" 90 }\n "AnimatedTexture" { "animatedtexturevar" "$basetexture"\n'
               b' "animatedtextureframerate" 10 } } }')
        px = texfix.vmt_proxies(raw)
        self.assertEqual(px['texturescroll'][0], {'texturescrollvar': '$basetexturetransform', 'texturescrollrate': '.5', 'texturescrollangle': '90'})
        self.assertEqual(px['animatedtexture'][0]['animatedtextureframerate'], '10')


if __name__ == '__main__':
    unittest.main()
