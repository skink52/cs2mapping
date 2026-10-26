"""csgo_complex vmat + texture set (color/normal/rough/metal/ao) for a built weapon, written under <out>/materials/<sub>/.

from material import make_material; make_material(out, sub, name, {"color": path, ...}, size=2048, flip_green=False)"""
import os
from PIL import Image

def make_material(out, sub, name, tex, size=2048, flip_green=False):
    """tex: dict kind->path for color/normal/rough/metal/ao. Writes PNGs + csgo_complex vmat under out/materials/sub/."""
    tdir = os.path.join(out, 'materials', sub); os.makedirs(tdir, exist_ok=True)
    paths = {}
    def put(kind, img):
        p = os.path.join(tdir, f'{name}_{kind}.png'); img.save(p); paths[kind] = f'materials/{sub}/{name}_{kind}.png'
    for kind, mode, flat in [('color','RGB',(110,78,48)), ('normal','RGB',(128,128,255)), ('rough','L',200), ('metal','L',0), ('ao','L',255)]:
        if kind in tex:
            im = Image.open(tex[kind]); im = im.convert(mode)
            if kind == 'normal' and flip_green:
                r, g, b = im.split(); im = Image.merge('RGB', (r, Image.eval(g, lambda v: 255-v), b))
            if size and max(im.size) > size: im = im.resize((size, size), Image.LANCZOS)
            put(kind, im)
        elif kind in ('color','normal','rough'): put(kind, Image.new(mode, (4,4), flat))
    metal = 'metal' in paths
    vmat = f'''// THIS FILE IS AUTO-GENERATED

Layer0
{{
\tshader "csgo_complex.vfx"

\t//---- PBR ----
\tF_SPECULAR 1
{"\tF_METALNESS_TEXTURE 1" if metal else ""}
\t//---- Ambient Occlusion ----
\tg_flAmbientOcclusionDirectDiffuse "0.000"
\tg_flAmbientOcclusionDirectSpecular "0.000"
\tTextureAmbientOcclusion "{paths.get('ao', 'materials/default/default_ao.tga')}"

\t//---- Color ----
\tg_flModelTintAmount "1.000"
\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
\tTextureColor "{paths['color']}"

\t//---- Fog ----
\tg_bFogEnabled "1"

\t//---- Metalness ----
\tg_flMetalness "0.000"
\tTextureMetalness "{paths.get('metal', 'materials/default/default_metal.tga')}"

\t//---- Normal ----
\tTextureNormal "{paths['normal']}"

\t//---- Roughness ----
\tTextureRoughness "{paths['rough']}"

\t//---- Texture Address Mode ----
\tg_nTextureAddressModeU "0"
\tg_nTextureAddressModeV "0"
}}
'''
    open(os.path.join(tdir, name + '.vmat'), 'w', newline='\n').write(vmat)
    return paths
