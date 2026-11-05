"""Batch: every chosen catalog item -> downloaded, extracted, converted to a CS2 player model, previewed, compiled, reported.

usage: python3 -I pipeline.py <catalog.json> [--only slug,slug] [--no-download] [--no-preview] [--compile] [--rc <resourcecompiler.exe>]

Writes (paths from the catalog's "paths" block):
  <out>/models/player/gmod/<slug>/...      the content addon (compile it with --compile, Hammer or ModelDoc)
  <work>/preview/<slug>_{source,bind,posed}.png and contact_sheet.png
  <work>/reports/<slug>.json and summary.md  (sizes, scale, materials, missing textures, compile result)
Prints one progress line per step; each model is independent (a failure is reported and the batch carries on).
"""
import json, os, subprocess, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch, gmod2cs2

RC_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe'


def compile_vmdl(rc, path, log_path):
    t = time.time()
    r = subprocess.run([rc, '-i', path, '-nop4'], capture_output=True, text=True, errors='replace')
    open(log_path, 'w', encoding='utf-8').write(r.stdout + r.stderr)
    bad = [l.strip() for l in (r.stdout + r.stderr).splitlines() if any(k in l.lower() for k in ('error', 'warning', 'failed')) and ' 0 failed' not in l]
    ok = ' 1 compiled, 0 failed' in r.stdout
    return {'ok': ok, 'seconds': round(time.time() - t, 1), 'problems': bad[:20], 'log': log_path}


def contact_sheet(work, slugs):
    from PIL import Image, ImageDraw
    tiles = []
    for s in slugs:
        p = os.path.join(work, 'preview', s + '_posed.png')
        if os.path.exists(p):
            im = Image.open(p); w, h = im.size
            tiles.append((s, im.crop((0, 0, w // 3, h)).resize((w // 6, h // 2))))
    if not tiles: return None
    cols = 5; tw, th = tiles[0][1].size
    sheet = Image.new('RGB', (cols * tw, ((len(tiles) + cols - 1) // cols) * (th + 16)), (46, 50, 58))
    d = ImageDraw.Draw(sheet)
    for k, (s, im) in enumerate(tiles):
        x, y = (k % cols) * tw, (k // cols) * (th + 16)
        sheet.paste(im, (x, y + 16)); d.text((x + 4, y + 2), s, fill=(230, 230, 230))
    out = os.path.join(work, 'preview', 'contact_sheet.png'); sheet.save(out)
    return out


def main():
    cat = json.load(open(sys.argv[1]))
    p = fetch.paths(cat)
    p['out'] = os.environ.get('PM_OUT', p.get('out')); p['template'] = os.environ.get('PM_TEMPLATE', p.get('template'))
    only = None; rc = RC_DEFAULT
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a.startswith('--only='): only = set(a[7:].split(','))
        if a == '--rc': rc = args[i + 1]
    items = [it for it in cat['items'] if it.get('chosen') and (not only or it['slug'] in only)]
    rep_dir = os.path.join(p['work'], 'reports'); os.makedirs(rep_dir, exist_ok=True)
    prev = None if '--no-preview' in sys.argv else os.path.join(p['work'], 'preview')
    tpl = gmod2cs2.Template(p['template'])
    results = []
    for k, it in enumerate(items):
        slug = it['slug']; t0 = time.time()
        print('[%d/%d] %s (%s)' % (k + 1, len(items), slug, it['id']), flush=True)
        rep = {'slug': slug, 'id': it['id'], 'title': it['title'], 'author': it['author'], 'mdl': it['mdl'],
               'workshop': 'https://steamcommunity.com/sharedfiles/filedetails/?id=%s' % it['id']}
        try:
            if '--no-download' not in sys.argv: fetch.download(p, it['id'])
            root = fetch.extract(p, it['id'])
            roots = [root] + [os.path.join(p['work'], 'extract', str(x)) for x in it.get('depends', [])]
            print('   converting %s' % it['mdl'], flush=True)
            r = gmod2cs2.convert(os.path.join(root, *it['mdl'].split('/')), slug, roots, tpl, p['out'], it.get('skin', 0),
                                 it.get('bodygroups'), it.get('maxtex', 2048), prev, log=lambda s: print(s, flush=True))
            rep.update(r)
            miss = [m['source'] for m in r['materials'] if m.get('flat') or m.get('missing')]
            print('   %d vertices, %d triangles, %d materials, scale %.3f%s (%.0f s)' % (r['vertices'], r['triangles'], len(r['materials']), r['scale'],
                  ', missing textures: ' + ', '.join(miss) if miss else '', time.time() - t0), flush=True)
            if prev:
                import handcheck
                handcheck.check(os.path.join(root, *it['mdl'].split('/')), tpl, os.path.join(prev, slug + '_hands.png'), slug, choices=it.get('bodygroups'))
                print('   hands/wrists check: %s' % os.path.join(prev, slug + '_hands.png'), flush=True)
            if '--compile' in sys.argv:
                vm = os.path.join(p['out'], *r['vmdl'].split('/'))
                c = compile_vmdl(rc, vm, os.path.join(rep_dir, slug + '_compile.log'))
                rep['compile'] = c
                print('   compile: %s in %.0f s%s' % ('OK' if c['ok'] else 'FAILED', c['seconds'], ('; ' + ' | '.join(c['problems'][:3])) if c['problems'] else ''), flush=True)
            rep['status'] = 'ok' if rep.get('compile', {}).get('ok', True) else 'compile failed'
            if rep['status'] == 'ok' and r.get('warnings'): rep['status'] = 'WARN: ' + '; '.join(r['warnings'])
        except Exception as ex:
            rep['status'] = 'failed: %s' % ex
            print('   FAILED: %s' % ex, flush=True); traceback.print_exc()
        json.dump(rep, open(os.path.join(rep_dir, slug + '.json'), 'w'), indent=1)
        results.append(rep)
    # summary
    lines = ['# GMod -> CS2 player models: batch report', '',
             '| slug | source | verts | tris | scale | joint offset (mean / max u) | materials (flat) | compile | status |', '|---|---|---|---|---|---|---|---|---|']
    for r in results:
        flat = sum(1 for m in r.get('materials', []) if m.get('flat'))
        jo = r.get('joint_offsets') or {}
        jtxt = '%.1f / %.1f (%s)' % (sum(jo.values()) / len(jo), max(jo.values()), max(jo, key=jo.get)) if jo else ''
        lines.append('| %s | [%s](%s) by %s | %s | %s | %s | %s | %s (%d) | %s | %s |' % (
            r['slug'], r['title'], r['workshop'], r['author'], r.get('vertices', ''), r.get('triangles', ''), r.get('scale', ''), jtxt,
            len(r.get('materials', [])), flat, 'OK' if r.get('compile', {}).get('ok') else ('-' if 'compile' not in r else 'FAILED'), r['status']))
    open(os.path.join(rep_dir, 'summary.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    if prev: print('contact sheet:', contact_sheet(p['work'], [r['slug'] for r in results if r['status'].startswith(('ok', 'WARN'))]))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
