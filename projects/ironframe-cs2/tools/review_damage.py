"""preview/review/damage_<key>.png (default | scorched | wrecked side by side) and preview/review/gibs.png.  usage: python -I tools/review_damage.py [key ...]"""
import json, os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create'))
import smd_view as V
_lm = V.load_vmdl_mats
V.load_vmdl_mats = lambda t, skin=None: {**{k + '.vmat': v for k, v in _lm(t, skin).items()}, **_lm(t, skin)}   # the skinned SMDs name their materials 'x.vmat'
OUT = os.path.join(PROJ, 'out', 'addon'); RV = os.path.join(PROJ, 'preview', 'review'); os.makedirs(RV, exist_ok=True)
data = json.load(open(os.path.join(OUT, '_gen', 'models.json'), encoding='utf-8'))
keys = sys.argv[1:] or ['ac3_moa', 'tf_ogre']
for k in keys:
    fr = data['frames'][k]; h = fr['height']; tiles = []
    for skin in (None, 'scorched', 'wrecked'):
        sc = V.Scene(OUT)
        for part in (fr['legs'], fr['upper']):
            if part: sc.add(part, off=(0, 0, 0), yaw=0.0, skin=skin)
        tiles.append(sc.render((h * 1.0, -h * 0.8, h * 0.55), (0, 0, h * 0.48), (640, 760), None, None, (30, 34, 42)))
    im = Image.new('RGB', (1920, 760)); [im.paste(t, (640 * i, 0)) for i, t in enumerate(tiles)]
    im.save(os.path.join(RV, 'damage_%s.png' % k)); print('damage_%s.png' % k)
sc = V.Scene(OUT)
for i in range(1, 7): sc.add('models/ifr/fx/gib_%d/gib_%d.vmdl' % (i, i), off=((i - 3.5) * 110, 0, 0), yaw=0.5)
sc.render((0, -300, 110), (0, 0, 5), (1500, 520), None, None, (30, 34, 42)).save(os.path.join(RV, 'gibs.png')); print('gibs.png')
