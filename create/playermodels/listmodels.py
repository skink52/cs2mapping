"""The list of every converted model: catalog entries with chosen=true + their reports -> MODELS.md.

usage: python3 -I listmodels.py <catalog.json> [out.md]      (default: MODELS.md next to the catalog)

One row per model: a picture in CS2's pose, CS2 model path (what SetModel takes), name, batch, source workshop item and author,
triangles, compile result, warnings. Re-run after every batch.

Pictures: img/<slug>.jpg next to the catalog (front and three-quarter view, ~8 KB), cut from the converter's
<work>/preview/<slug>_posed.png; made again when the preview is newer. A model without a preview keeps the picture it has.

Also writes GALLERY.md (the browsing page: a picture grid, A-Z with a letter bar, fun skins first) and img/poses/<slug>.jpg
(the front view in each still pose, cut from <work>/preview/<slug>_poses.png; a gallery picture links to it).
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch

PIC_H = 220           # picture height (pixels)
POSE_H = 260          # pose strip height
POSE_NAMES = ('shooting', 'run', 'crouch', 'arms up', 'knife', 'twist')   # poses.pose_sheet's tile order (3 tiles a row, 2 views a tile)
GALLERY_COLS = 5


def link(it):
    """the source page: the Workshop item, or a catalog item's own url (an FBX import)"""
    return it.get('url') or 'https://steamcommunity.com/sharedfiles/filedetails/?id=%s' % it['id']


def picture(slug, previews, img_dir):
    """img/<slug>.jpg from the posed preview (3 views side by side on a flat background, a caption line on top): the front and
    three-quarter views, each cropped to the model, side by side. Returns the path relative to MODELS.md, or ''."""
    out = os.path.join(img_dir, slug + '.jpg')
    src = os.path.join(previews, slug + '_posed.png')
    if os.path.exists(src) and (not os.path.exists(out) or os.path.getmtime(src) > os.path.getmtime(out)):
        from PIL import Image, ImageChops
        im = Image.open(src).convert('RGB')
        w, h = im.size
        bg = im.getpixel((w - 2, h - 2))
        panels = []
        for k in (0, 2):                                     # front, three-quarter
            p = im.crop((k * w // 3, 24, (k + 1) * w // 3, h))
            box = ImageChops.difference(p, Image.new('RGB', p.size, bg)).convert('L').point(lambda v: 255 if v > 12 else 0).getbbox()
            if box: p = p.crop((max(0, box[0] - 6), max(0, box[1] - 6), min(p.width, box[2] + 6), min(p.height, box[3] + 6)))
            panels.append(p.resize((max(1, round(p.width * PIC_H / p.height)), PIC_H), Image.LANCZOS))
        pic = Image.new('RGB', (sum(p.width for p in panels) + 4, PIC_H), bg)
        x = 0
        for p in panels: pic.paste(p, (x, 0)); x += p.width + 4
        os.makedirs(img_dir, exist_ok=True)
        pic.save(out, quality=80, optimize=True)
    return 'img/%s.jpg' % slug if os.path.exists(out) else ''


def pose_strip(slug, previews, img_dir):
    """img/poses/<slug>.jpg: the front view of every pose in the pose sheet, side by side, captioned. Returns the path or ''."""
    out = os.path.join(img_dir, 'poses', slug + '.jpg')
    src = os.path.join(previews, slug + '_poses.png')
    if os.path.exists(src) and (not os.path.exists(out) or os.path.getmtime(src) > os.path.getmtime(out)):
        from PIL import Image, ImageChops, ImageDraw
        im = Image.open(src).convert('RGB')
        tw, th = im.width // 3, 520                          # a tile: two views, the front one on the left, label on top
        vw = tw // 2
        views = [im.crop(((k % 3) * tw, (k // 3) * th + 22, (k % 3) * tw + vw, (k // 3 + 1) * th)) for k in range(len(POSE_NAMES))]
        bg = views[0].getpixel((vw - 2, 2))
        box = None
        for v in views:                                      # one crop for all poses, so they line up
            b = ImageChops.difference(v, Image.new('RGB', v.size, bg)).convert('L').point(lambda x: 255 if x > 12 else 0).getbbox()
            if b: box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        box = box or (0, 0, vw, th - 22)
        box = (max(0, box[0] - 6), max(0, box[1] - 6), min(vw, box[2] + 6), min(th - 22, box[3] + 6))
        cap = 16
        k = POSE_H / (box[3] - box[1])
        pw = max(1, round((box[2] - box[0]) * k))
        strip = Image.new('RGB', (pw * len(views) + 4 * (len(views) - 1), POSE_H + cap), bg)
        d = ImageDraw.Draw(strip)
        for i, (v, n) in enumerate(zip(views, POSE_NAMES)):
            x = i * (pw + 4)
            strip.paste(v.crop(box).resize((pw, POSE_H), Image.LANCZOS), (x, cap))
            d.text((x + 4, 2), n, fill=(220, 220, 220))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        strip.save(out, quality=78, optimize=True)
    return 'img/poses/%s.jpg' % slug if os.path.exists(out) else ''


def gallery(cards, out_dir, n_models):
    """GALLERY.md: a picture grid to browse by eye. cards: dicts with name, slug, id, pic, poses, fun, warn, dupes"""
    def letter(c):
        ch = next((x for x in c['name'].upper() if x.isalnum()), '#')
        return ch if 'A' <= ch <= 'Z' else '#'

    def grid(cs):
        rows = ['<table>']
        for i in range(0, len(cs), GALLERY_COLS):
            rows.append('<tr>')
            for c in cs[i:i + GALLERY_COLS]:
                img = '<img src="%s" height="130" alt="%s">' % (c['pic'], c['slug']) if c['pic'] else '(no picture)'
                if c['poses']: img = '<a href="%s" title="every pose">%s</a>' % (c['poses'], img)
                tags = []
                if c['fun']: tags.append('fun')
                if c['dupes']: tags.append('similar: ' + ', '.join(c['dupes']))
                elif c['warn']: tags.append('fit warning')
                rows.append('<td align="center" valign="bottom">%s<br><a href="%s"><b>%s</b></a><br><sub>by %s<br><code>%s</code>%s</sub></td>' % (
                    img, c['url'], html.escape(c['name']), html.escape(c['author']), c['slug'], ('<br>' + html.escape('; '.join(tags))) if tags else ''))
            rows.append('</tr>')
        return rows + ['</table>', '']

    for c in cards: c['name'] = re.sub(r'^\[[^\]]*\]\s*', '', c['name'])   # an author's tag ("[K] Deadpool") is not part of the name
    cards = sorted(cards, key=lambda c: (c['name'].lower(), c['slug']))
    letters = sorted({letter(c) for c in cards}, key=lambda x: (x == '#', x))
    txt = ['# Player model gallery', '',
           '%d GMod player models converted for CS2, A to Z. Click a picture for the model in every test pose '
           '(shooting, run, crouch, arms up, twist); click a name for its Workshop page (the Workshop author is under it). ' % n_models +
           'The full table (model paths, triangles, warnings, batches) is [MODELS.md](MODELS.md). Generated by `listmodels.py`.', '',
           '**Jump to:** [Fun skins](#fun-skins) · ' + ' · '.join('[%s](#%s)' % (x, 'other' if x == '#' else x.lower()) for x in letters), '',
           '"fun": a cartoon or joke model (kept rigid). "similar": another model of the same character is in the list (both kept). '
           '"fit warning": see its row in MODELS.md.', '',
           '## Fun skins', ''] + grid([c for c in cards if c['fun']])
    for x in letters:
        txt += ['## %s' % ('Other' if x == '#' else x), ''] + grid([c for c in cards if letter(c) == x]) + ['[back to top](#player-model-gallery)', '']
    path = os.path.join(out_dir, 'GALLERY.md')
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(txt) + '\n')
    print('%s: %d cards' % (path, len(cards)))


def main():
    cat_path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(cat_path)), 'MODELS.md')
    cat = json.load(open(cat_path, encoding='utf-8'))
    p = fetch.paths(cat)
    img_dir = os.path.join(os.path.dirname(os.path.abspath(out)), 'img')
    rows, n_ok, n_warn, cards = [], 0, 0, []
    for it in cat['items']:
        if not it.get('chosen'): continue
        rp = os.path.join(p['work'], 'reports', it['slug'] + '.json')
        r = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
        comp = r.get('compile', {})
        status = 'not converted yet' if not r else ('compiled' if comp.get('ok') else 'compile FAILED' if comp else 'converted, not compiled')
        warn = '; '.join(r.get('warnings', []))
        if it.get('possible_dupes'): warn = '; '.join(x for x in (warn, 'possible duplicate of ' + ', '.join('`%s`' % d for d in it['possible_dupes'])) if x)
        stand = [m['source'] for m in r.get('materials', []) if m.get('standin') or m.get('glass') or m.get('flat')]
        if comp.get('ok'): n_ok += 1
        if warn: n_warn += 1
        pic = picture(it['slug'], os.path.join(p['work'], 'preview'), img_dir)
        cards.append({'name': it.get('name', it['slug']), 'slug': it['slug'], 'id': it['id'], 'url': link(it), 'pic': pic, 'fun': it.get('fun'), 'author': it['author'],
                      'poses': pose_strip(it['slug'], os.path.join(p['work'], 'preview'), img_dir), 'warn': bool(r.get('warnings')),
                      'dupes': it.get('possible_dupes', [])})
        pic = '<img src="%s" height="110" alt="%s">' % (pic, it['slug']) if pic else ''
        rows.append('| %d | %s | `models/player/gmod/%s/%s.vmdl` | %s | [%s](%s) by %s | %s | %s | %s |' % (
            it.get('batch', 0), pic, it['slug'], it['slug'], it.get('name', it['slug']), it['title'].replace('|', '/'), link(it), it['author'],
            r.get('triangles', ''), status, (('**WARN** ' + warn) if warn else '') + (('; ' if warn else '') + 'stand-in/glass: ' + ', '.join(stand) if stand else '')))
    rows.sort(key=lambda r: (int(r.split('|')[1]), r.split('|')[3]))
    txt = ['# Converted player models', '',
           'Every GMod player model converted by this toolkit (generated by `listmodels.py` from `catalog.json` and the reports; re-run after a batch).',
           'Addon: `gmod_playermodels` (content: `csgo_addons/gmod_playermodels`). In a map: a hidden `prop_dynamic` of the model so it is precached, then',
           '`pawn.SetModel("<model>")`. Rights: local testing only unless the author agrees (see [the guide](../../docs/creation/gmod-playermodels.md#rights)).',
           '', 'To browse by picture, see [GALLERY.md](GALLERY.md).', '', '%d models, %d compiled, %d with fit warnings. Per-batch notes: %s.' % (len(rows), n_ok, n_warn, ', '.join('[%s](%s)' % (f, f) for f in sorted(x for x in os.listdir(os.path.dirname(os.path.abspath(out))) if re.match(r'BATCH\d+\.md$', x)))), '',
           "Each picture is the converted model in CS2's own pose (skinned to the agent skeleton the game animates), front and three-quarter.", '',
           '| batch | picture | CS2 model | name | workshop item | tris | status | notes |', '|---|---|---|---|---|---|---|---|'] + rows
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(txt) + '\n')
    print('%s: %d models' % (out, len(rows)))
    gallery(cards, os.path.dirname(os.path.abspath(out)), len(rows))


if __name__ == '__main__':
    main()
