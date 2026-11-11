"""Pack togmod.py's GMod addons for the Workshop and write SteamCMD upload files. Uploads nothing itself.

    python3 -I gmod_publish.py <gmod_ports.json> [--only slug,..] [--visibility 2] [--id slug=publishedfileid ...]

Per model, under <out>/upload/<slug>/: content/addon.gma (GMA v3, the layout gmad.exe writes; only the file types the Workshop
accepts for a model addon: models .mdl/.vvd/.phy/.vtx, materials .vmt/.vtf, lua), preview.jpg (512x512 from the preview)
and workshop.vdf for SteamCMD's workshop_build_item (app 4000). Upload (your own Steam account; SteamCMD asks for the
password and Steam Guard code itself):

    steamcmd +login <account> +workshop_build_item <out>/upload/<slug>/workshop.vdf +quit

publishedfileid 0 creates a new item; SteamCMD writes the new id back into workshop.vdf and later runs keep it (or set
"workshop_id" in the json), so they update the item. visibility: 0 public, 1 friends only, 2 private (default), 3 unlisted.
These are rips of commercial games (Riot, Hazelight): keep them private unless you have the rights holder's permission.
"""
import argparse, glob, io, json, os, struct, subprocess, sys, time, zlib
import numpy as np

ALLOWED = ('.mdl', '.vvd', '.phy', '.vtx', '.vmt', '.vtf', '.lua')


def write_gma(src, dst, title, desc, tags, author='skink52'):
    files = []
    for p in sorted(glob.glob(os.path.join(src, '**', '*'), recursive=True)):
        if os.path.isfile(p) and p.lower().endswith(ALLOWED):
            rel = os.path.relpath(p, src).replace('\\', '/').lower()
            if rel.split('/')[0] in ('models', 'materials', 'lua'): files.append((rel, open(p, 'rb').read()))
    b = io.BytesIO()
    b.write(b'GMAD'); b.write(bytes([3])); b.write(struct.pack('<QQ', 0, int(time.time()))); b.write(b'\0')
    meta = json.dumps({'description': desc, 'type': 'model', 'tags': tags[:2]})
    for s in (title, meta, author): b.write(s.encode('utf-8') + b'\0')
    b.write(struct.pack('<i', 1))
    for i, (rel, data) in enumerate(files, 1):
        b.write(struct.pack('<I', i)); b.write(rel.encode('utf-8') + b'\0'); b.write(struct.pack('<qI', len(data), zlib.crc32(data) & 0xffffffff))
    b.write(struct.pack('<I', 0))
    for _, data in files: b.write(data)
    raw = b.getvalue()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f: f.write(raw + struct.pack('<I', zlib.crc32(raw) & 0xffffffff))
    return files


def preview_jpg(png, dst):
    from PIL import Image
    im = Image.open(png).convert('RGB')
    w, h = im.size
    im = im.crop((0, 0, min(w, h * 2 // 3), h))          # the first view of the sheet
    s = max(im.size); bg = Image.new('RGB', (s, s), im.getpixel((2, h - 2))); bg.paste(im, ((s - im.size[0]) // 2, 0))
    bg.resize((512, 512)).save(dst, quality=92)


def pack_members(cfg, pk):
    by = {m['slug']: m for m in cfg['models']}
    return [by[x] for x in pk['members']]


def build_pack(cfg, pk):
    """addons/<pack>/: every member's models and materials, one lua file registering them all, one addon.json"""
    import shutil
    slug = pk.get('slug') or ''
    if not slug or slug in ('.', '..') or os.path.basename(slug) != slug or any(c in slug for c in '\\/:'):
        sys.exit('pack slug %r must be a plain folder name (the folder addons/<slug> is deleted and rebuilt)' % slug)
    out = cfg['out']; dst = os.path.join(out, 'addons', slug)
    if os.path.isdir(dst): shutil.rmtree(dst)           # rebuilt from the members each time (a dropped member must go)
    lua = ['-- %s: made by togmod.py / gmod_publish.py' % pk['name']]
    for m in pack_members(cfg, pk):
        src = os.path.join(out, 'addons', m['slug'])
        if not glob.glob(os.path.join(src, 'models', '**', '*.mdl'), recursive=True):
            raise SystemExit('pack %s: %s is not compiled' % (pk['slug'], m['slug']))
        for sub in ('models', 'materials'):
            shutil.copytree(os.path.join(src, sub), os.path.join(dst, sub), dirs_exist_ok=True)
        for f in glob.glob(os.path.join(src, 'lua', 'autorun', '*.lua')):
            lua += [l for l in open(f, encoding='utf-8').read().splitlines() if not l.startswith('--')]
    os.makedirs(os.path.join(dst, 'lua', 'autorun'), exist_ok=True)
    open(os.path.join(dst, 'lua', 'autorun', pk['slug'] + '_pm.lua'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lua) + '\n')
    json.dump({'title': pk['name'], 'type': 'model', 'tags': pk.get('tags', ['fun', 'cartoon']), 'ignore': ['*.psd', '*.png', '*.txt']},
              open(os.path.join(dst, 'addon.json'), 'w', encoding='utf-8'), indent='\t')


def pack_preview(cfg, pk, dst):
    """a grid of the members' clean front views, 512x512"""
    from PIL import Image
    ms = pack_members(cfg, pk); n = len(ms)
    cols = int(np.ceil(np.sqrt(n * 1.6))); rows = int(np.ceil(n / cols))
    cw, ch = 512 // cols, 512 // rows
    img = Image.new('RGB', (512, 512), (40, 44, 52))
    for i, m in enumerate(ms):
        f = os.path.join(cfg['out'], 'preview', m['slug'] + '_front.png')
        if not os.path.exists(f): continue
        im = Image.open(f).convert('RGB')
        bb = Image.eval(im, lambda v: 255 if v > 60 else 0).getbbox() or (0, 0, im.size[0], im.size[1])
        im = im.crop(bb); im.thumbnail((cw, ch))
        img.paste(im, ((i % cols) * cw + (cw - im.size[0]) // 2, (i // cols) * ch + (ch - im.size[1]) // 2))
    img.save(dst, quality=92)


def vdf_str(s): return s.replace('\\', '\\\\').replace('"', '\\"')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('json'); ap.add_argument('--only'); ap.add_argument('--visibility', type=int, default=2)
    a = ap.parse_args()
    cfg = json.load(open(a.json, encoding='utf-8'))
    out = cfg['out']
    items = list(cfg['models'])
    for pk in cfg.get('packs', []):                   # packs: several models in one addon (one Workshop item)
        if a.only and pk['slug'] not in a.only.split(','): continue
        build_pack(cfg, pk); items.append(dict(pk, pack=True))
    for it in items:
        slug = it['slug']
        if a.only and slug not in a.only.split(','): continue
        add = os.path.join(out, 'addons', slug)
        if not glob.glob(os.path.join(add, 'models', '**', '*.mdl'), recursive=True):
            print('%s: not compiled yet (no .mdl in %s): skipped' % (slug, add)); continue
        up = os.path.join(out, 'upload', slug)
        wid = str(it.get('workshop_id') or 0)
        old = os.path.join(up, 'workshop.vdf')          # SteamCMD writes the new item's id back into the VDF: keep it
        if wid == '0' and os.path.exists(old):
            import re
            m = re.search(r'"publishedfileid"\s+"(\d+)"', open(old, encoding='utf-8', errors='replace').read())
            if m: wid = m.group(1)
        aj = json.load(open(os.path.join(add, 'addon.json'), encoding='utf-8'))
        desc = it.get('description') or ('Player models: ' + ', '.join(m['name'] for m in pack_members(cfg, it)) + '. Each keeps its own proportions on the stock HL2 animations.' if it.get('pack') else None) or '%s as a player model (%s). Animated with the stock %s animations; own proportions kept.' % (
            it['name'], it.get('franchise', ''), 'female' if it.get('sex') == 'female' else 'male')
        gma = os.path.join(up, 'content', 'addon.gma')
        files = write_gma(add, gma, it['name'], desc, aj.get('tags', ['fun']))
        gmad = cfg.get('gmad') or r'D:\SteamLibrary\steamapps\common\GarrysMod\bin\gmad.exe'
        if os.path.exists(gmad):          # Garry's Mod's own packer checks the file whitelist and addon.json; use its archive
            r = subprocess.run([gmad, 'create', '-folder', add, '-out', gma], capture_output=True, text=True)
            if r.returncode or 'Successfully' not in r.stdout: print('%s: gmad failed, kept the built-in archive:\n%s' % (slug, r.stdout[-400:]))
            elif 'Files ignored: 0' not in r.stdout: print('%s: gmad left files out:\n%s' % (slug, r.stdout[-400:]))
        pv = os.path.join(out, 'preview', slug + '_front.png')        # togmod's clean three-quarter view (a pack: its grid)
        if not os.path.exists(pv): pv = os.path.join(out, 'preview', slug + '_bind.png')
        if it.get('pack'): pack_preview(cfg, it, os.path.join(up, 'preview.jpg'))
        elif os.path.exists(pv): preview_jpg(pv, os.path.join(up, 'preview.jpg'))
        vdf = ['"workshopitem"', '{', '\t"appid" "4000"', '\t"publishedfileid" "%s"' % wid,
               '\t"contentfolder" "%s"' % vdf_str(os.path.abspath(os.path.join(up, 'content'))),
               '\t"previewfile" "%s"' % vdf_str(os.path.abspath(os.path.join(up, 'preview.jpg'))),
               '\t"visibility" "%d"' % a.visibility, '\t"title" "%s"' % vdf_str(it['name']),
               '\t"description" "%s"' % vdf_str(desc), '\t"changenote" "%s"' % ('First upload' if wid == '0' else 'Update'), '}']
        open(os.path.join(up, 'workshop.vdf'), 'w', encoding='utf-8', newline='\n').write('\n'.join(vdf) + '\n')
        print('%s: %d files, %.1f MB -> %s' % (slug, len(files), os.path.getsize(os.path.join(up, 'content', 'addon.gma')) / 1e6, up))
    print('\nUpload each (your account; SteamCMD prompts for password/Steam Guard):\n  steamcmd +login <account> +workshop_build_item %s +quit'
          % os.path.join(out, 'upload', '<slug>', 'workshop.vdf'))


if __name__ == '__main__':
    main()
