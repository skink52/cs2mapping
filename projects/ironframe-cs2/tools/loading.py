"""IRONFRAME loading screen, radar and icon: a thin wrapper over create/loading.py (slides, radar PSD + overview txt, map icon).
tools/vmap.py calls write_slides / write_radar / write_icon at the end of a map build; this CLI re-does the pictures from the
saved relief + preview without rebuilding the map:

    python -I tools/loading.py <addon out dir> [arena]        (default IF_ARENA; needs preview/arenas/<arena>_relief.png)
"""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
_spec = importlib.util.spec_from_file_location('cs2_loading', os.path.join(CREATE, 'loading.py'))
_L = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_L)
write_slides, write_radar, write_overview, write_icon, cover, shade = _L.write_slides, _L.write_radar, _L.write_overview, _L.write_icon, _L.cover, _L.shade
def write_extras(out, game_out, map_name, title):
    """map credits (game/maps/<map>.txt), Steam description (<addon> STEAM DESCRIPTION.txt) and the 1024 Workshop icon (preview/workshop_icon.jpg)"""
    import loading_art as A
    gm = os.path.join(game_out, 'maps'); os.makedirs(gm, exist_ok=True)
    open(os.path.join(gm, map_name + '.txt'), 'w', newline='\n', encoding='utf-8').write('\n'.join(A.credits_lines(title)) + '\n')
    open(os.path.join(out, map_name + ' STEAM DESCRIPTION.txt'), 'w', newline='\n', encoding='utf-8').write(A.description(title))
    pv = os.path.join(ROOT, 'preview'); os.makedirs(pv, exist_ok=True)
    import pixel_slides as PS   # pixel Workshop icon (preview/workshop_icon.png); map_slides.py rewrites it with the slides
    PS.workshop_icon().save(os.path.join(pv, 'workshop_icon.png'))


ICON = 'M32 2 L58 16 L58 48 L32 62 L6 48 L6 16 Z M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z'   # hexagon frame


def main(a):
    if not a: sys.exit(__doc__)
    sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
    import json
    from PIL import Image
    import names as N
    import arenas.common as C
    out = a[0]; arena = a[1] if len(a) > 1 else N.ARENA
    rel_p = os.path.join(ROOT, 'preview', 'arenas', '%s_relief.png' % arena)
    if not os.path.exists(rel_p): sys.exit('no %s: run tools/vmap.py first' % rel_p)
    aj = json.load(open(os.path.join(out, '_gen', 'arena.json')))
    b = aj['bounds']; rel = Image.open(rel_p)
    write_radar(out, N.MAP, rel, (b['min'][0], b['min'][1], b['max'][0], b['max'][1]), game_out=os.path.join(ROOT, 'out', 'game'))
    write_icon(out, N.MAP, ICON)
    names = write_slides(out, N.MAP, C.slides({}, rel, os.path.join(ROOT, 'preview', 'arenas', '%s.png' % arena), N.TITLE))
    write_extras(out, os.path.join(ROOT, 'out', 'game'), N.MAP, N.TITLE)
    vm = os.environ.get('IF_CURRENT_VMAP') or 'C:/source1/links/content_addons/%s/maps/%s.vmap' % (N.MAP, N.MAP)
    if os.environ.get('IF_SLIDES', 'pixel') == 'pixel' and os.path.exists(vm):   # pixel slides of the mapper's real vmap replace the poster slides
        import map_slides as MS
        MS.main([vm, out, N.MAP, N.TITLE] + ([os.environ['IF_SLIDE_BOX']] if os.environ.get('IF_SLIDE_BOX') else ['-7300,-7300,-600,7300,7300,6200']))
    print('loading: radar, icon, %d slides for %s' % (len(names), N.MAP))


if __name__ == '__main__':
    main(sys.argv[1:])
