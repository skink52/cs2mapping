"""Batch: every chosen catalog item -> downloaded, extracted, converted to a CS2 player model, previewed, compiled, reported.

usage: python3 -I pipeline.py <catalog.json> [--only slug,slug] [--batch=N] [--no-download] [--no-preview] [--compile] [--rc <exe>]
                              [--jobs N] [--timeout S]

Writes (paths from the catalog's "paths" block):
  <out>/models/player/gmod/<slug>/...      the content addon (compile it with --compile, Hammer or ModelDoc)
  <work>/preview/<slug>_{source,bind,posed}.png and contact_sheet.png
  <work>/reports/<slug>.json and summary.md  (sizes, scale, materials, missing textures, compile result)
Mode per model: the catalog's "mode", else 'own' (the model's own leg joints; arms, torso and head on CS2's), or 'rigid' for
"fun": true models (cartoon feet came out wrong with own legs; skink52's in-game check, 6 Nov 2026).
Prints one progress line per step; each model is independent (a failure is reported and the batch carries on).
--jobs N: N models at once, each in its own process (the converter is single-threaded: a 6-core PC ran 6 at ~60% CPU, 3-4x faster),
with its output in <work>/logs/models/<slug>.log; --timeout S (default 1800) kills a model that runs longer (one spun for 2 h) and
reports it failed. The summary and contact sheet are written once, at the end.
"""
import json, os, re, subprocess, sys, time, traceback
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Workshop titles: any script, any console

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch, gmod2cs2

RC_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe'


def compile_vmdl(rc, path, log_path):
    t = time.time()
    r = subprocess.run([rc, '-i', path, '-nop4'], capture_output=True, text=True, errors='replace')
    open(log_path, 'w', encoding='utf-8').write(r.stdout + r.stderr)
    bad = [l.strip() for l in (r.stdout + r.stderr).splitlines() if re.search(r'(?i)^\s*(error|warning)\b|\berror:|failed to|cannot ', l) and ' 0 failed' not in l]
    ok = ' 1 compiled, 0 failed' in r.stdout
    return {'ok': ok, 'seconds': round(time.time() - t, 1), 'problems': bad[:20], 'log': log_path}


def contact_sheet(work, slugs, name='contact_sheet'):
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
    out = os.path.join(work, 'preview', name + '.png'); sheet.save(out)
    return out


def parallel(items, jobs, timeout, p, rep_dir):
    """each item in its own `pipeline.py --only <slug> --child` process, `jobs` at a time; a process over `timeout` s is killed"""
    from concurrent.futures import ThreadPoolExecutor
    keep = [a for a in sys.argv[2:] if a in ('--no-download', '--no-preview', '--compile')]
    if '--rc' in sys.argv: keep += ['--rc', sys.argv[sys.argv.index('--rc') + 1]]
    logs = os.path.join(p['work'], 'logs', 'models'); os.makedirs(logs, exist_ok=True)
    done = [0]
    def one(it):
        slug = it['slug']; t0 = time.time()
        with open(os.path.join(logs, slug + '.log'), 'w', encoding='utf-8') as lf:
            try:
                rc = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), sys.argv[1], '--only', slug, '--child'] + keep,
                                    stdout=lf, stderr=subprocess.STDOUT, timeout=timeout).returncode
                why = None if rc == 0 else 'exit %d' % rc
            except subprocess.TimeoutExpired:
                why = 'timed out after %.0f s (killed)' % timeout
        rp = os.path.join(rep_dir, slug + '.json')
        rep = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) and os.path.getmtime(rp) >= t0 else None
        if rep is None:
            rep = {'slug': slug, 'id': it['id'], 'title': it['title'], 'author': it['author'], 'mdl': it['mdl'],
                   'workshop': it.get('url') or 'https://steamcommunity.com/sharedfiles/filedetails/?id=%s' % it['id'], 'status': 'failed: %s' % (why or 'no report')}
            json.dump(rep, open(rp, 'w'), indent=1)
        done[0] += 1
        print('[%d/%d] %s: %s (%.0f s)' % (done[0], len(items), slug, rep.get('status', '?')[:100], time.time() - t0), flush=True)
        return rep
    with ThreadPoolExecutor(jobs) as ex:
        return list(ex.map(one, items))


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = fetch.paths(cat)
    p['out'] = os.environ.get('PM_OUT', p.get('out')); p['template'] = os.environ.get('PM_TEMPLATE', p.get('template'))
    only = None; batch = None; batches = None; rc = RC_DEFAULT
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a.startswith('--only='): only = set(a[7:].split(','))
        if a == '--only' and i + 1 < len(args): only = set(args[i + 1].split(','))   # both spellings: the usage line shows this one
        if a.startswith('--batch='): batch = int(a[8:]) if ',' not in a else None; batches = [int(x) for x in a[8:].split(',')]
        if a == '--rc': rc = args[i + 1]
    items = [it for it in cat['items'] if it.get('chosen') and (not only or it['slug'] in only) and (batches is None or it.get('batch') in batches)]
    rep_dir = os.path.join(p['work'], 'reports'); os.makedirs(rep_dir, exist_ok=True)
    prev = None if '--no-preview' in sys.argv else os.path.join(p['work'], 'preview')
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 1
    timeout = float(args[args.index('--timeout') + 1]) if '--timeout' in args else 1800.0
    results, loop_items = [], items
    if jobs > 1 and '--child' not in args:
        results = parallel(items, jobs, timeout, p, rep_dir); loop_items = []
    tpl = gmod2cs2.Template(p['template']) if loop_items else None
    for k, it in enumerate(loop_items):
        slug = it['slug']; t0 = time.time()
        print('[%d/%d] %s (%s)' % (k + 1, len(items), slug, it['id']), flush=True)
        rep = {'slug': slug, 'id': it['id'], 'title': it['title'], 'author': it['author'], 'mdl': it['mdl'],
               'workshop': it.get('url') or 'https://steamcommunity.com/sharedfiles/filedetails/?id=%s' % it['id']}
        try:
            if it.get('fbx'):                # a rigged FBX (not a GMod item): Blender export + materials (fbxprep.py)
                import fbxprep
                root, it = fbxprep.prepare(p['work'], it, log=lambda s: print(s, flush=True))[0], dict(it, mdl=it['slug'] + '.npz')
            else:
                if '--no-download' not in sys.argv: fetch.download(p, it['id'])
                root = fetch.extract(p, it['id'])
            roots = [root] + [os.path.join(p['work'], 'extract', str(x)) for x in it.get('depends', [])] + fetch.base_roots(fetch.paths(cat))
            print('   converting %s' % it['mdl'], flush=True)
            r = gmod2cs2.convert(os.path.join(root, *it['mdl'].split('/')), slug, roots, tpl, p['out'], it.get('skin', 0),
                                 it.get('bodygroups'), it.get('maxtex', 2048), prev, log=lambda s: print(s, flush=True),
                                 mode=it.get('mode') or ('rigid' if it.get('fun') else 'own'), scale=it.get('scale'))
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
    if '--child' in args: return
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
    open(os.path.join(rep_dir, 'summary%s.md' % ('_batch%d' % batch if batch else '')), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    if prev: print('contact sheet:', contact_sheet(p['work'], [r['slug'] for r in results if r['status'].startswith(('ok', 'WARN'))], 'contact_sheet' + ('_batch%d' % batch if batch else '')))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
