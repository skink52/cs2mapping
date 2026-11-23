"""D3: post_import_cleanup keeps the importer's / compiler's own error line for a failed model; stockmodels.py repoints CS:GO chicken,
hostage and agent props to CS2's stock models.

  python -m unittest discover -s tools/tests -p "test_borrowed_d3.py" -v
"""
import importlib, os, sys, types, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import vmapedit as V, watervol, stockmodels, dmx

CS2 = {'models/chicken/chicken.vmdl', 'models/hostage/hostage.vmdl', 'characters/models/ctm_fbi/ctm_fbi.vmdl',
       'characters/models/ctm_fbi/ctm_fbi_variantc.vmdl', 'characters/models/ctm_sas/ctm_sas.vmdl',
       'characters/models/ctm_st6/ctm_st6_variante.vmdl', 'characters/models/tm_phoenix/tm_phoenix.vmdl',
       'characters/models/tm_professional/tm_professional_varf.vmdl'}


def cleanup_module():
    """scripts/post_import_cleanup.py with Valve's utils stubbed (not in git)"""
    if 'post_import_cleanup' in sys.modules: return sys.modules['post_import_cleanup']
    stub = 'utils' not in sys.modules
    if stub:
        u = types.ModuleType('utils'); u.utlc = types.SimpleNamespace(print_I=print); sys.modules['utils'] = u; sys.modules['utils.utlc'] = u.utlc
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
    try: return importlib.import_module('post_import_cleanup')
    finally:
        sys.path.pop(0)
        if stub: sys.modules.pop('utils', None); sys.modules.pop('utils.utlc', None)


class ErrorLine(unittest.TestCase):
    def setUp(s): s.pc = cleanup_module()

    def test_picks_the_real_error(s):
        log = ('Creating render device for graphics adapter 0\nBeginning conversion of 1 models...\nConversion of chicken\n'
               'Failed to create CModelDocPhysicsHullFile Node\nERROR: Unable to load animation "chicken_walk"\n0 mdl files successfully converted\n')
        s.assertEqual(s.pc.error_line(log), 'ERROR: Unable to load animation "chicken_walk"')

    def test_noise_only_and_empty(s):
        s.assertEqual(s.pc.error_line('Conversion of x\nFailed to create CModelDocPhysicsHullFile Node\n'), 'Failed to create CModelDocPhysicsHullFile Node')
        s.assertEqual(s.pc.error_line('Conversion of x\nWriting 0 Animations:Done\n'), 'Writing 0 Animations:Done')
        s.assertEqual(s.pc.error_line(''), '')
        s.assertTrue(len(s.pc.error_line('error ' + 'x' * 500)) <= 220)


class StockModels(unittest.TestCase):
    def test_remap(s):
        r = stockmodels.remap
        s.assertEqual(r('models/chicken/chicken.mdl', CS2), ('models/chicken/chicken.vmdl', 'same'))
        s.assertEqual(r('models/characters/hostage_03.vmdl', CS2), ('models/hostage/hostage.vmdl', 'family'))
        s.assertEqual(r('models/player/ctm_fbi_variantc.vmdl', CS2), ('characters/models/ctm_fbi/ctm_fbi_variantc.vmdl', 'same'))
        s.assertEqual(r('models/player/ctm_fbi_variantd.vmdl', CS2), ('characters/models/ctm_fbi/ctm_fbi.vmdl', 'family'))
        s.assertEqual(r('models/player/ctm_st6_varianta.mdl', CS2), ('characters/models/ctm_st6/ctm_st6_variante.vmdl', 'variant'))
        s.assertEqual(r('models/player/tm_professional_var3.mdl', CS2), ('characters/models/tm_professional/tm_professional_varf.vmdl', 'variant'))
        s.assertEqual(r('models/player/tm_pirate_variantb.mdl', CS2), ('characters/models/tm_phoenix/tm_phoenix.vmdl', 'team'))
        s.assertEqual(r('models/player/custom_player/legacy/ctm_gign.mdl', CS2), ('characters/models/ctm_sas/ctm_sas.vmdl', 'team'))
        s.assertEqual(r('models/player/custom/chickenleet/chickenleet.mdl', CS2), (None, None))   # custom model: left alone
        s.assertEqual(r('models/props/cs_italy/dead_chicken.vmdl', CS2), (None, None))
        s.assertEqual(r('models/chicken/chicken_zombie.mdl', CS2), (None, None))                  # CS2 lacks it

    def test_run(s):
        m = V.Map(watervol.TEMPLATE); dmx.geta(m.E[m.world], b'children')[2] = []
        a = m.new_entity('prop_dynamic', [0, 0, 0], {'model': 'models/player/tm_pirate_variantb.vmdl'})
        b = m.new_entity('prop_dynamic', [0, 0, 0], {'model': 'models/chicken/chicken.vmdl'})
        k = m.new_entity('prop_dynamic', [0, 0, 0], {'model': 'models/props/crate.vmdl'})
        class C: pass
        c = C(); c.log = []; c.todo = []
        c.cs2v = types.SimpleNamespace(files={p + '_c': 0 for p in CS2})
        stockmodels.run(m, c)
        s.assertEqual(m.P(a, 'model'), 'characters/models/tm_phoenix/tm_phoenix.vmdl')
        s.assertEqual(m.P(b, 'model'), 'models/chicken/chicken.vmdl')                   # already CS2's path: untouched
        s.assertEqual(m.P(k, 'model'), 'models/props/crate.vmdl')
        s.assertTrue(any('stand' in t for t in c.todo)); s.assertTrue(any('1 props' in l for l in c.log))

    def test_no_vpk(s):
        class C: pass
        c = C(); c.log = []; c.todo = []; c.cs2v = None
        stockmodels.run(None, c); s.assertTrue(c.todo and not c.log)


if __name__ == '__main__':
    unittest.main()
