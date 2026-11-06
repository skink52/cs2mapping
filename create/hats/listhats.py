"""Rebuild HATS.md: every converted hat with a picture (img/<id>.jpg, cut from its preview tile: a stock agent three-quarter and
side, Gordon from the GMod conversions), its CS2 path, how it was placed, its source item, and the dropped ones with the reason.

usage: python3 -I listhats.py <catalog.json>
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hatpaths


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = hatpaths.paths(cat)
    items = {it['id']: it for it in cat['items']}
    from PIL import Image
    img = os.path.join(HERE, 'img'); os.makedirs(img, exist_ok=True)
    rows, dropped, tech, n_ok = [], [], [], 0
    for h in cat['hats']:
        it = items.get(h['item'], {})
        src = f"[{it.get('title', h['item'])}](https://steamcommunity.com/sharedfiles/filedetails/?id={h['item']}) by {it.get('author', '?')}"
        if h.get('chosen', True) is False:
            dropped.append(f"| `{h['id']}` | {h.get('name', '')} | {h.get('skip_reason', '')} | {src} |"); continue
        rp = os.path.join(p['work'], 'reports', h['id'] + '.json')
        if not os.path.exists(rp): continue
        rep = json.load(open(rp, encoding='utf-8'))
        if 'error' in rep:
            dropped.append(f"| `{h['id']}` | {h.get('name', '')} | failed: {rep['error'][:80]} | {src} |"); continue
        tile = os.path.join(p['work'], 'preview', h['id'] + '_tile.png')
        if os.path.exists(tile):
            im = Image.open(tile).convert('RGB'); im = im.crop((0, 18, im.width, im.height)); im.thumbnail((480, 260))
            im.save(os.path.join(img, h['id'] + '.jpg'), quality=80)
        comp = rep.get('compile', {})
        n_ok += comp.get('ok', False)
        status = '' if comp.get('ok') else (' **COMPILE FAILED**' if comp else ' (not compiled)')
        rows.append(f"| ![{h['id']}](img/{h['id']}.jpg) | **{h.get('name', h['id'])}**<br>`{h['id']}`{status} | {rep.get('kind', '')} | `{rep['vmdl']}` | {src} |")
        fixes = ', '.join(f'{k} {h[k]}' for k in ('offset', 'rotate', 'scale', 'pre_rotate', 'kind', 'autofit') if k in h)
        placed = 'Pointshop lua' if rep.get('placement', '').startswith('pointshop') else rep.get('placement', '')
        tech.append(f"| `{h['id']}` | {placed} | {fixes} | {h.get('review', {}).get('round', '')} |")
    md = ['# Hat collection', '',
          f"{len(rows)} hats and accessories for CS2 ({n_ok} compiled), converted from Garry's Mod Workshop items and reviewed by skink52 (4 rounds,",
          "6 Nov 2026). Every hat sits on CS2's agent skeleton (on `head_0`), so the SlimeMG plugin can put it on any player model, stock",
          'agents and the converted GMod player models alike ([docs/creation/gmod-hats.md](../../docs/creation/gmod-hats.md)).', '',
          '**Picking hats for a server** (the manager): look through the pictures, note the ids, then follow slime-mg-gm',
          '`docs/hats.md` "Adding hats". The collection comes as `gmod_hats_collection_<date>.zip` (`pack.py`), like the player model library',
          '(the `gmod_playermodels` addon, [MODELS.md](../playermodels/MODELS.md)).', '',
          '**Rights first:** the Workshop authors keep their rights, and several hats are from commercial games (PAYDAY 2, Splatoon, Nintendo).',
          'Private testing until the author agrees; the source column links the item.', '',
          'Each picture: a stock CS2 agent (three-quarter and side) and Gordon, one of the GMod player models (his head sits lower: the hat',
          'moves with it through its `fit` choice).', '',
          '| Picture | Hat (id) | Kind | CS2 model | Source |', '|---|---|---|---|---|'] + rows +          ['', '## How each was placed', '', '| Id | Placed by | Hand fixes (CS2 head space: x forward, z up) | Review round |', '|---|---|---|---|'] + tech
    if dropped:
        md += ['', '## Dropped', '', '| Id | Name | Why | Source |', '|---|---|---|---|'] + dropped
    open(os.path.join(HERE, 'HATS.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print(f'HATS.md: {len(rows)} hats, {len(dropped)} dropped')


if __name__ == '__main__':
    main()
