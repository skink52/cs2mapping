"""Reuse of the Hellmatch (mg_freedm) addon's files in Hellmatch ZE. Reads the Hellmatch addons, never writes them.

usage: hm_assets.py sprites <addon_out> <world_frames.json>
           writes <addon_out>/_gen/sprite_models.json from the Hellmatch script's SPRITE_MODELS (so sprites.py, the slow
           sprite-model build, is not run: the compiled sprite models are copied instead) and fails if the ZE game uses
           a world frame Hellmatch has no model for (then run tools/sprites.py, HZE_SPRITES=1 in build_all.sh)
       hm_assets.py plan <addon_out> [--out build/copy_plan.json]
           sorts every file the ZE build wrote into: identical to the Hellmatch source (its compiled file can be copied
           from the Hellmatch GAME addon) or new (must be compiled), and lists the Hellmatch-only files ZE also needs
           (sprite models, their materials) to copy as source + compiled. Prints a summary; --out writes the full list.
"""
import hashlib, json, os, re, sys

CS2 = os.environ.get('CS2_ROOT', r'C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive')
HM_CONTENT = os.environ.get('HELLMATCH_CONTENT', CS2 + '/content/csgo_addons/mg_freedm')
HM_GAME = os.environ.get('HELLMATCH_GAME', CS2 + '/game/csgo_addons/mg_freedm')


def sprite_models():
    src = open(os.path.join(HM_CONTENT, 'maps/scripts/freedm.js'), encoding='utf-8').read()
    m = re.search(r'const SPRITE_MODELS = (\{.*?\});\n', src, re.S)
    if not m: raise SystemExit('hm_assets: no SPRITE_MODELS in the Hellmatch script')
    return json.loads(m.group(1))


def cmd_sprites(out, frames_path):
    sm = sprite_models()
    allf = json.load(open(frames_path))
    frames = [k for k, _ in allf]
    missing = [[k, b] for k, b in allf if k not in sm]
    os.makedirs(os.path.join(out, '_gen'), exist_ok=True)
    if missing:
        # frames Hellmatch never drew (it strips keys from its levels): build just those with sprites.py
        import subprocess
        mp = os.path.join(os.path.dirname(os.path.abspath(frames_path)), 'missing_frames.json')
        json.dump(missing, open(mp, 'w'))
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sprites.py'), out, mp], check=True)
        new = json.load(open(os.path.join(out, '_gen/sprite_models.json')))
        print('hm_assets: built %d sprite models Hellmatch lacks: %s' % (len(new), ' '.join(sorted(new))))
        sm = dict(sm, **new)
        # the voxel models' shared palette materials stay Hellmatch's (its compiled sprite models are copied, not rebuilt)
        import shutil
        pal = os.path.join(HM_CONTENT, 'materials/fdm/pal')
        if os.path.isdir(pal):
            shutil.rmtree(os.path.join(out, 'materials/fdm/pal'), ignore_errors=True)
            shutil.copytree(pal, os.path.join(out, 'materials/fdm/pal'))
    json.dump(sm, open(os.path.join(out, '_gen/sprite_models.json'), 'w'))
    print('hm_assets: %d sprite models (Hellmatch + %d new; ZE uses %d frames)' % (len(sm), len(missing), len(frames)))


def sha(p):
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()


def same_content(a, b):
    """byte-identical, or the same pixels (PNG) / samples (WAV) when only the encoder's bytes differ"""
    if os.path.getsize(a) == os.path.getsize(b) and sha(a) == sha(b): return True
    ext = os.path.splitext(a)[1].lower()
    try:
        if ext == '.png':
            from PIL import Image
            import numpy as np
            x, y = Image.open(a), Image.open(b)
            return x.size == y.size and x.mode == y.mode and np.array_equal(np.asarray(x), np.asarray(y))
        if ext == '.wav':
            import wave
            with wave.open(a) as x, wave.open(b) as y:
                return x.getparams()[:3] == y.getparams()[:3] and x.readframes(x.getnframes()) == y.readframes(y.getnframes())
    except Exception:
        return False
    return False


# source extension -> how CS2 names the compiled file
def compiled_names(rel):
    base, ext = os.path.splitext(rel)
    ext = ext.lower()
    if ext in ('.vmdl', '.vmat', '.vsndevts', '.vmap'): return [rel + '_c']
    if ext in ('.wav', '.mp3'): return [base + '.vsnd_c']
    if ext == '.png' and rel.startswith('panorama/'): return [base + '_png.vtex_c']
    if ext == '.xml' and rel.startswith('panorama/'): return [base + '.vxml_c']
    if ext == '.css' and rel.startswith('panorama/'): return [base + '.vcss_c']
    if ext == '.js': return [base + '.vjs_c']
    return []   # smd, material pngs (compiled into vtex_c files named by the compiler), txt, json


SKIP_DIRS = ('_gen',)


def walk(root):
    for dp, dn, fn in os.walk(root):
        rel_dir = os.path.relpath(dp, root).replace('\\', '/')
        if rel_dir.split('/')[0] in SKIP_DIRS: continue
        for f in fn:
            yield (rel_dir + '/' + f if rel_dir != '.' else f)


def cmd_plan(out, plan_out=None):
    same, new = [], []
    for rel in sorted(walk(out)):
        hp = os.path.join(HM_CONTENT, rel)
        if os.path.exists(hp) and same_content(hp, os.path.join(out, rel)):
            comp = [c for c in compiled_names(rel) if os.path.exists(os.path.join(HM_GAME, c))]
            same.append((rel, comp))
        else:
            new.append(rel)
    # Hellmatch-only files ZE needs as they are: the sprite models and their materials (not built by the ZE pipeline)
    extra = []
    for sub in ('models/fdm/spr', 'materials/fdm/spr', 'materials/fdm/pal', 'models/fdm/null.vmdl'):
        p = os.path.join(HM_CONTENT, sub)
        if os.path.isdir(p):
            extra += [sub + '/' + r for r in walk(p)]
        elif os.path.exists(p):
            extra.append(sub)
    gextra = []
    for sub in ('models/fdm/spr', 'materials/fdm/spr', 'materials/fdm/pal'):
        p = os.path.join(HM_GAME, sub)
        if os.path.isdir(p): gextra += [sub + '/' + r for r in walk(p)]
    if os.path.exists(os.path.join(HM_GAME, 'models/fdm/null.vmdl_c')): gextra.append('models/fdm/null.vmdl_c')

    def group(rels):
        g = {}
        for r in rels:
            parts = r.split('/')
            k = '/'.join(parts[:3]) if len(parts) > 3 else '/'.join(parts[:-1]) or '.'
            g[k] = g.get(k, 0) + 1
        return g
    plan = {
        'hellmatch_content': HM_CONTENT, 'hellmatch_game': HM_GAME,
        'copy_compiled_identical': [{'source': r, 'compiled': c} for r, c in same],
        'identical_but_no_compiled_file': [r for r, c in same if not c and compiled_names(r)],
        'compile_new': new,
        'copy_from_hellmatch_content': extra,
        'copy_from_hellmatch_game': gextra,
    }
    if plan_out:
        os.makedirs(os.path.dirname(plan_out) or '.', exist_ok=True)
        json.dump(plan, open(plan_out, 'w'), indent=1)
    print('identical to Hellmatch, compiled copy available: %d files (%d compiled)' % (
        sum(1 for _, c in same if c), sum(len(c) for _, c in same)))
    for k, n in sorted(group([r for r, c in same if c]).items()): print('   %5d  %s' % (n, k))
    print('identical source, no compiled file found (compile): %d' % len(plan['identical_but_no_compiled_file']))
    for k, n in sorted(group(plan['identical_but_no_compiled_file']).items()): print('   %5d  %s' % (n, k))
    print('new or changed (compile): %d files' % len(new))
    for k, n in sorted(group(new).items()): print('   %5d  %s' % (n, k))
    print('Hellmatch-only, copy as is: %d content files, %d compiled files' % (len(extra), len(gextra)))
    for k, n in sorted(group(gextra).items()): print('   %5d  %s' % (n, k))
    return plan


if __name__ == '__main__':
    if len(sys.argv) < 3: raise SystemExit(__doc__)
    if sys.argv[1] == 'sprites': cmd_sprites(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'plan': cmd_plan(sys.argv[2], sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None)
    else: raise SystemExit(__doc__)
