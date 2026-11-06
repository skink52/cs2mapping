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
    rows, dropped, n_ok = [], [], 0
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
            im = Image.open(tile).convert('RGB'); im.thumbnail((360, 160)); im.save(os.path.join(img, h['id'] + '.jpg'), quality=78)
        comp = rep.get('compile', {})
        status = 'compiled' if comp.get('ok') else ('COMPILE FAILED' if comp else 'not compiled')
        n_ok += comp.get('ok', False)
        placed = 'Pointshop lua' if rep.get('placement', '').startswith('pointshop') else rep.get('placement', '')
        fixes = ', '.join(f'{k} {h[k]}' for k in ('offset', 'rotate', 'scale', 'pre_rotate', 'kind', 'autofit') if k in h)
        rows.append(f"| ![](img/{h['id']}.jpg) | `{h['id']}` {h.get('name', '')} | {rep.get('kind', '')} | {placed}{'; ' + fixes if fixes else ''} | {status} | {src} |")
    md = ['# Converted hats', '',
          f'{len(rows)} hats ({n_ok} compiled), from `catalog.json` by `listhats.py`. Each picture: a stock CS2 agent (tm_leet_variantf) three-quarter',
          'and side, and Gordon (a GMod conversion, with his fit choice). Paths: `models/hats/<id>/<id>.vmdl` in the `gmod_hats` addon.',
          'How they are placed: [docs/creation/gmod-hats.md](../../docs/creation/gmod-hats.md). Rights: private testing until the author agrees.', '',
          '| Picture | Hat | Kind | Placed by | Status | Source |', '|---|---|---|---|---|---|'] + rows
    if dropped:
        md += ['', '## Dropped', '', '| Id | Name | Why | Source |', '|---|---|---|---|'] + dropped
    open(os.path.join(HERE, 'HATS.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print(f'HATS.md: {len(rows)} hats, {len(dropped)} dropped')


if __name__ == '__main__':
    main()
