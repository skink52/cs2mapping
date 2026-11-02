import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import numpy as np
from PIL import Image
import assets
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'addon')
for name, kind, tex, tint in [('lobby_wall', 'w', 'BIGBRIK2', 0.8), ('lobby_floor', 'f', 'FLOOR0_1', 0.75), ('lobby_ceil', 'f', 'CEIL5_1', 0.6)]:
    img = assets.texture(tex) if kind == 'w' else assets.flat(tex)
    big = np.repeat(np.repeat(img, 4, 0), 4, 1)[..., :3]
    os.makedirs(OUT + '/materials/fdm', exist_ok=True)
    Image.fromarray(big).save(OUT + '/materials/fdm/%s_color.png' % name)
    open(OUT + '/materials/fdm/%s.vmat' % name, 'w').write('// FreeDM lobby\nLayer0\n{\n\tshader "csgo_unlitgeneric.vfx"\n\tF_BLEND_MODE 0\n\tTextureColor "materials/fdm/%s_color.png"\n\tg_vColorTint "[%.3f %.3f %.3f 0.000000]"\n}\n' % (name, tint, tint, tint))
