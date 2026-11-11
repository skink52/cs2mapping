#!/usr/bin/env python3
"""deploy_monsoon.py: copy the generated mg_monsoon addon into the CS2 addon folders. Dry run unless --apply.

  python -I tools/deploy_monsoon.py                 what a deploy would do: counts, sizes, gates. Changes nothing, writes nothing.
  python -I tools/deploy_monsoon.py --list          the same, plus every file that would be created or replaced
  python -I tools/deploy_monsoon.py --apply         do it
  python -I tools/deploy_monsoon.py --rollback out/deploy/mg_monsoon_deploy_<stamp>.json [--apply]

What goes where
  out/addon  ->  <content addons>\\mg_monsoon     (default C:\\source1\\links\\content_addons; CS2_ROOT or --content overrides)
  out/game   ->  <game addons>\\mg_monsoon        (default C:\\source1\\links\\game_addons;    CS2_ROOT or --game overrides)
  docs/README_MONSOON.md, TESTING_MONSOON.md, CREDITS.md and the two licence files -> both addon roots (they ship with the addon)
  docs/WORKSHOP_DESCRIPTION.txt -> <content addon>\\mg_monsoon STEAM DESCRIPTION.txt

Rules (docs/reference/file-safety.md, tools/safepath.py)
  - Only files whose bytes differ are written (size + sha256). An unchanged file is not touched, so its date stays and neither
    Hammer nor the compiler sees a change.
  - Nothing is ever deleted. Files that exist only in the destination are counted and left alone.
  - A file is backed up and the backup checked before it is replaced; new bytes go through a temp file. A .vmap is backed up
    next to itself as <map>.vmap.bak_<stamp>, everything else under out/deploy/backups/<stamp>/.
  - No write goes through a link below the addon folder.
  - HELD (exit 3, nothing written) while a cs2.exe runs with -tools and the addon's name: tools mode reloads every changed
    file and restarts the map script. Close the map, or pass --allow-open when the person at the game said go.
  - HELD (exit 4) while out/build.lock exists (a generator is still writing out/addon). --ignore-lock overrides.
  - A destination .vmap that changed since the last deploy (edited in Hammer) is NOT replaced: regenerate from it
    (make_map.py <live vmap> ...) or pass --overwrite-map. Every other file still deploys.
  - soundevents_addon.vsndevts is merged, not copied: when the addon already has one, only the "mg_monsoon" block is replaced
    and every other event in it is kept (sndevents.merge).
  - When the addon does not exist it is created with what Hammer's addon_template gives a new addon and the generator does
    not write: postprocess/mg_monsoon.vpost (the template's xxx_mapname_xxx.vpost under the map's name),
    postprocess/basic_linear_post.vpost, and an empty game-side addoninfo.txt. These are only ever created, never replaced.
  - "<addon> STEAM DESCRIPTION.txt" is replaced only while it still holds what the last deploy wrote; a hand-edited copy is kept.

Record: out/deploy/mg_monsoon_deploy_<stamp>.json (every file: create / modify, sha256 before and after, its backup).
How far this is checked: the copy logic is run on real files (dry run on the PC, an apply into a temp folder). What it deploys is
generated and has never been compiled or loaded in CS2: the report says level "untested", manual_check_required true.

Exit codes: 0 ok, 2 a problem that stops the deploy (missing source, bad merge, description too long, not enough room),
3 held because CS2 tools mode is open on the addon (or the process list could not be read), 4 held by out/build.lock.
AI-generated (Claude) for skink52.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PROJECT))
if HERE not in sys.path:
    sys.path.insert(0, HERE)                                   # sndevents (python -I does not add the script's folder)
for _p in (os.path.join(REPO, 'tools'), r'C:\source1\cs2port\tools'):
    if os.path.isfile(os.path.join(_p, 'safepath.py')):
        sys.path.append(_p)                                    # appended: nothing there shadows this folder's modules
        break
import safepath       # noqa: E402
import sndevents      # noqa: E402

ADDON = 'mg_monsoon'
TAG = 'mg_monsoon'                                             # the block name sounds.py gives the events
DEF_CONTENT = r'C:\source1\links\content_addons'
DEF_GAME = r'C:\source1\links\game_addons'
SNDEVENTS = 'soundevents/soundevents_addon.vsndevts'
EXT_PREFIXES = ('models/mv/ext/', 'materials/models/mv/ext/')  # the GMod Workshop conversions (docs/WORKSHOP_COMPLIANCE.md)
SKIP = ('*.part', '*.copytmp', '*.bak_*', '*.pyc', '*.lock', 'Thumbs.db', 'desktop.ini')
SKIP_DIRS = ('__pycache__',)
STEAM_LIMIT = 8000
KV3_EMPTY = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} '
             'format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n{\n}\n').encode('ascii')
SHIP_DOCS = ('docs/README_MONSOON.md', 'docs/TESTING_MONSOON.md', 'docs/CREDITS.md', 'LICENSE', 'LICENSE-CC-BY-NC-4.0.txt')


def mb(n):
    return '%.1f MB' % (n / 1048576.0)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def skipped(rel):
    parts = rel.split('/')
    if any(d in SKIP_DIRS for d in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in SKIP)


def tools_open(addon):
    """-> (state, text). state: 'open' (a cs2.exe with -tools and the addon name), 'closed', or 'unknown' (cannot tell)."""
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name='cs2.exe'\" | "
           "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd], capture_output=True, text=True,
                           timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))   # no console, no focus taken
    except Exception as e:                                     # no PowerShell, timeout
        return 'unknown', 'could not list processes (%s)' % type(e).__name__
    if r.returncode != 0:
        return 'unknown', 'the process list failed (exit %d)' % r.returncode
    rows = [l.split('|', 1) for l in r.stdout.splitlines() if '|' in l]
    blind = [pid for pid, cl in rows if not cl.strip()]
    hits = [pid for pid, cl in rows if '-tools' in cl.lower() and addon.lower() in cl.lower()]
    if hits:
        return 'open', 'cs2.exe pid %s is running with -tools on %s' % (', '.join(hits), addon)
    if blind:
        return 'unknown', 'cs2.exe pid %s hides its command line (started elevated?)' % ', '.join(blind)
    other = [pid for pid, cl in rows if '-tools' in cl.lower()]
    return 'closed', '%d cs2.exe running, %s' % (len(rows), 'tools mode open on another addon' if other else 'none in tools mode')


def last_manifest(mandir):
    """dst (normalised) -> sha256 the last complete deploys wrote there; newest manifest wins."""
    seen = {}
    for path in sorted(glob.glob(os.path.join(mandir, '%s_deploy_*.json' % ADDON))):
        try:
            with open(path, encoding='utf-8') as f:
                man = json.load(f)
        except (OSError, ValueError):
            continue
        if man.get('dry_run'):
            continue
        for rec in list(man.get('files', [])) + list(man.get('generated', [])):
            if rec.get('after') and rec.get('dst'):
                seen[os.path.normcase(os.path.normpath(rec['dst']))] = rec['after']
    return seen


def free_bytes(path):
    p = os.path.abspath(path)
    while p and not os.path.exists(p):
        q = os.path.dirname(p)
        if q == p:
            break
        p = q
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None


def only_in_destination(root, rels):
    """files below root that the source does not have (never deleted: counted for the report)"""
    have = {r.lower() for r in rels}
    n = size = 0
    if not os.path.isdir(root):
        return 0, 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not safepath.is_link(os.path.join(dp, d))]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), root).replace('\\', '/')
            if rel.lower() not in have:
                n += 1
                try:
                    size += os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    pass
    return n, size


def vmap_ext_refs(vmap):
    """names of the GMod-converted models a .vmap references (read as bytes; the model paths are plain text in it)"""
    import re
    try:
        with open(vmap, 'rb') as f:
            data = f.read()
    except OSError:
        return None
    return sorted({m.decode('ascii') for m in re.findall(rb'models/mv/ext/[a-z0-9_/]+\.vmdl', data)})


def build(a):
    """Everything a deploy would do, read-only. -> dict(plan, generated, held, problems, notes, roots...)"""
    out = os.path.abspath(a.out or os.path.join(PROJECT, 'out'))
    cs2 = os.environ.get('CS2_ROOT')
    content_root = a.content or (os.path.join(cs2, 'content', 'csgo_addons') if cs2 else DEF_CONTENT)
    game_root = a.game or (os.path.join(cs2, 'game', 'csgo_addons') if cs2 else DEF_GAME)
    addon = safepath.addon_name(ADDON)
    content_dst = os.path.join(content_root, addon)
    game_dst = os.path.join(game_root, addon)
    template = a.template or os.path.join(content_root, 'addon_template')
    mandir = os.path.join(out, 'deploy')
    src_addon, src_game = os.path.join(out, 'addon'), os.path.join(out, 'game')
    problems, notes, held = [], [], []

    for label, root in (('content addons folder', content_root), ('game addons folder', game_root)):
        if not os.path.isdir(root):
            problems.append('%s not found: %s' % (label, root))
    if not os.path.isdir(src_addon):
        problems.append('nothing to deploy: %s is missing (run the build steps in docs/BUILD.md)' % src_addon)
    for label, d in (('content', content_dst), ('game', game_dst)):
        if safepath.is_link(d):
            notes.append('%s addon folder is a link to %s (allowed: it is the folder the tool was pointed at)'
                         % (label, safepath.link_target(d)))
    if problems:
        return dict(problems=problems, notes=notes, plan=[], generated=[], held=[], content_dst=content_dst, game_dst=game_dst,
                    mandir=mandir, out=out, new_addon=False, extras=[], ext_refs=None, source={})

    new_addon = not os.path.isdir(content_dst)
    prev = last_manifest(mandir)
    plan = []
    source = {}
    for side, src, dst in (('content', src_addon, content_dst), ('game', src_game, game_dst)):
        part = [p for p in safepath.plan_copy(src, dst) if not skipped(p['rel'])]
        if side == 'content':
            part = [p for p in part if p['rel'].lower() != SNDEVENTS]          # merged below, never copied over
            if a.skip_ext:
                part = [p for p in part if not p['rel'].lower().startswith(EXT_PREFIXES)]
        source[side] = {'files': len(part), 'bytes': sum(p['size'] for p in part), 'rels': [p['rel'] for p in part]}
        for p in part:
            p['side'] = side
            p['rel'] = side + '/' + p['rel']
        plan += part
    taken = {os.path.normcase(os.path.normpath(p['dst'])) for p in plan}

    # the addon_template files a new addon has and the generator does not write: created when missing, never replaced
    pairs = []
    for src_rel, dst_rel in (('postprocess/xxx_mapname_xxx.vpost', 'postprocess/%s.vpost' % addon),
                             ('postprocess/basic_linear_post.vpost', 'postprocess/basic_linear_post.vpost')):
        dst = os.path.join(content_dst, *dst_rel.split('/'))
        if os.path.normcase(os.path.normpath(dst)) in taken or os.path.exists(dst):
            continue
        src = os.path.join(template, *src_rel.split('/'))
        if not os.path.isfile(src):
            problems.append('addon_template file missing, cannot create %s: %s' % (dst_rel, src))
            continue
        pairs.append((src, dst, 'content', 'template'))
    # the docs that ship inside the addon (both roots: the game folder is what reaches the Workshop)
    if not a.no_docs:
        for rel in SHIP_DOCS:
            src = os.path.join(PROJECT, *rel.split('/'))
            if not os.path.isfile(src):
                notes.append('doc not written yet, not shipped: %s' % rel)
                continue
            for side, root in (('content', content_dst), ('game', game_dst)):
                dst = os.path.join(root, os.path.basename(rel))
                if os.path.normcase(os.path.normpath(dst)) not in taken:
                    pairs.append((src, dst, side, 'doc'))
    for side, root in (('content', content_dst), ('game', game_dst)):
        mine = [(s, d) for s, d, sd, _ in pairs if sd == side]
        kinds = {os.path.normcase(os.path.normpath(d)): k for s, d, sd, k in pairs if sd == side}
        for p in safepath.plan_pairs(mine, [root]):
            p['side'] = side
            p['kind'] = kinds.get(os.path.normcase(os.path.normpath(p['dst'])), '')
            p['rel'] = side + '/' + p['rel']
            plan.append(p)

    # a map edited in Hammer since the last deploy is not replaced
    for p in list(plan):
        if p['rel'].lower().endswith('.vmap') and p['op'] == 'modify':
            now = safepath.sha256_file(p['dst'])
            if prev.get(os.path.normcase(os.path.normpath(p['dst']))) != now and not a.overwrite_map:
                plan.remove(p)
                held.append({'rel': p['rel'], 'dst': p['dst'], 'why': 'changed in the addon since the last deploy (edited in Hammer?): '
                             'regenerate from it, or pass --overwrite-map (it would be backed up as .vmap.bak_<stamp>)'})

    generated = []

    def gen(side, root, rel, data, note):
        dst = os.path.join(root, *rel.split('/'))
        try:
            safepath.check_no_nested_links(root, dst)
        except ValueError as e:
            problems.append(str(e))
            return None
        if safepath.is_link(dst) or os.path.isdir(dst):
            problems.append('%s is a link or a folder; a file would be written there' % dst)
            return None
        old = None
        if os.path.isfile(dst):
            with open(dst, 'rb') as f:
                old = f.read()
        op = 'create' if old is None else ('same' if old == data else 'modify')
        g = {'rel': side + '/' + rel, 'side': side, 'root': root, 'dst': dst, 'data': data, 'op': op, 'size': len(data),
             'old_size': None if old is None else len(old), 'before': None if old is None else sha_bytes(old), 'note': note}
        generated.append(g)
        return g

    # sound events: keep whatever else the live file holds
    src_snd = os.path.join(src_addon, *SNDEVENTS.split('/'))
    dst_snd = os.path.join(content_dst, *SNDEVENTS.split('/'))
    if os.path.isfile(src_snd):
        with open(src_snd, encoding='utf-8', newline='') as f:
            ours = f.read()
        n_ours = len(sndevents.event_names(sndevents.body_of(ours, TAG)))
        if os.path.isfile(dst_snd):
            with open(dst_snd, encoding='utf-8', newline='') as f:
                live = f.read()
            try:
                text = sndevents.merge(live, ours, TAG)
                kept = len(sndevents.event_names(text)) - n_ours
                gen('content', content_dst, SNDEVENTS, text.encode('utf-8'),
                    'merged: %d %s events replace the block, %d other events in the addon file kept' % (n_ours, TAG, kept))
            except ValueError as e:
                problems.append('sound events merge refused: %s' % e)
        else:
            gen('content', content_dst, SNDEVENTS, ours.encode('utf-8'), 'new file: %d %s events on the template events' % (n_ours, TAG))
    else:
        notes.append('no %s in out/addon (run sounds.py): the addon gets no sound events' % SNDEVENTS)

    # game-side addoninfo.txt, only when the addon has none
    if not os.path.exists(os.path.join(game_dst, 'addoninfo.txt')):
        gen('game', game_dst, 'addoninfo.txt', KV3_EMPTY, 'empty addon info (as Hammer writes for a new addon)')

    # Steam description
    desc_src = os.path.join(PROJECT, 'docs', 'WORKSHOP_DESCRIPTION.txt')
    desc_rel = '%s STEAM DESCRIPTION.txt' % addon
    if os.path.isfile(desc_src):
        with open(desc_src, 'rb') as f:
            data = f.read()
        chars = len(data.decode('utf-8', errors='replace').replace('\r\n', '\n'))
        if chars > STEAM_LIMIT:
            problems.append('docs/WORKSHOP_DESCRIPTION.txt is %d characters; Steam takes %d' % (chars, STEAM_LIMIT))
        else:
            dst = os.path.join(content_dst, desc_rel)
            cur = None
            if os.path.isfile(dst):
                with open(dst, 'rb') as f:
                    cur = sha_bytes(f.read())
            wrote = prev.get(os.path.normcase(os.path.normpath(dst)))
            if cur is not None and cur != sha_bytes(data) and cur != wrote:
                held.append({'rel': 'content/' + desc_rel, 'dst': dst, 'why': 'edited by hand since the last deploy: kept as it is '
                             '(the new text is docs/WORKSHOP_DESCRIPTION.txt)'})
            else:
                gen('content', content_dst, desc_rel, data, 'Steam Workshop description, %d of %d characters' % (chars, STEAM_LIMIT))
    else:
        notes.append('docs/WORKSHOP_DESCRIPTION.txt not written yet: no STEAM DESCRIPTION file')

    extras = []
    for side, root in (('content', content_dst), ('game', game_dst)):
        rels = [p['rel'].split('/', 1)[1] for p in plan if p.get('side') == side] + \
               [g['rel'].split('/', 1)[1] for g in generated if g['side'] == side] + \
               [h['rel'].split('/', 1)[1] for h in held if h['rel'].startswith(side + '/')]
        n, size = only_in_destination(root, rels)
        extras.append({'side': side, 'files': n, 'bytes': size})

    main_vmap = os.path.join(src_addon, 'maps', '%s.vmap' % addon)
    return dict(problems=problems, notes=notes, plan=plan, generated=generated, held=held, content_dst=content_dst,
                game_dst=game_dst, mandir=mandir, out=out, new_addon=new_addon, extras=extras,
                ext_refs=vmap_ext_refs(main_vmap), source=source)


def report(b, a, state, state_text, lock):
    plan, generated = b['plan'], b['generated']
    print('%s deploy: %s' % (ADDON, 'APPLY' if a.apply else 'DRY RUN (nothing is written; --apply to deploy)'))
    print('  content -> %s%s' % (b['content_dst'], '   (does not exist: would be created)' if b['new_addon'] else ''))
    print('  game    -> %s%s' % (b['game_dst'], '' if os.path.isdir(b['game_dst']) else '   (does not exist: would be created)'))
    for side in ('content', 'game'):
        s = b['source'].get(side)
        if s:
            print('  source out/%s: %d files, %s' % ('addon' if side == 'content' else 'game', s['files'], mb(s['bytes'])))
    tops = {}
    for p in plan:
        parts = p['rel'].split('/')
        key = parts[0] + '/' + (parts[1] if len(parts) > 2 else '(root)')
        t = tops.setdefault(key, {'create': 0, 'modify': 0, 'same': 0, 'bytes': 0})
        t[p['op']] += 1
        if p['op'] != 'same':
            t['bytes'] += p['size']
    print('  %-24s %7s %7s %7s %12s' % ('folder', 'create', 'modify', 'same', 'to write'))
    for key in sorted(tops):
        t = tops[key]
        print('  %-24s %7d %7d %7d %12s' % (key, t['create'], t['modify'], t['same'], mb(t['bytes'])))
    summ = safepath.summarise(plan)
    gw = sum(g['size'] for g in generated if g['op'] != 'same')
    gcount = {op: sum(1 for g in generated if g['op'] == op) for op in ('create', 'modify', 'same')}
    print('  %-24s %7d %7d %7d %12s' % ('copied files, total', summ['create'], summ['modify'], summ['same'], mb(summ['bytes_written'])))
    print('  %-24s %7d %7d %7d %12s' % ('written files, total', gcount['create'], gcount['modify'], gcount['same'], mb(gw)))
    for g in generated:
        print('    %-6s %s  (%s)' % (g['op'], g['rel'], g['note']))
    tmpl = [p for p in plan if p.get('kind') == 'template']
    if tmpl:
        print('  from addon_template (created because the addon has none): %s' % ', '.join(p['rel'] for p in tmpl))
    need = summ['bytes_written'] + summ['bytes_backed_up'] + gw
    free = free_bytes(b['content_dst'])
    print('  to write %s, to back up first %s; free on the destination drive: %s'
          % (mb(summ['bytes_written'] + gw), mb(summ['bytes_backed_up']), 'unknown' if free is None else mb(free)))
    if free is not None and free < need:
        b['problems'].append('not enough room on the destination drive: %s needed, %s free' % (mb(need), mb(free)))
    for e in b['extras']:
        if e['files']:
            print('  only in the %s addon (left alone, never deleted): %d files, %s' % (e['side'], e['files'], mb(e['bytes'])))
    refs = b['ext_refs']
    if refs is None:
        print('  GMod conversions: out/addon/maps/%s.vmap not found, cannot say which the map uses' % ADDON)
    else:
        ext_n = sum(1 for p in plan if p['rel'].split('/', 1)[1].lower().startswith(EXT_PREFIXES))
        print('  GMod conversions (models/mv/ext): %d files in this deploy%s; the map references %d of the models%s'
              % (ext_n, ' (left out: --skip-ext)' if a.skip_ext else '', len(refs),
                 (': ' + ', '.join(os.path.basename(r)[:-5] for r in refs)) if refs else ''))
        if a.skip_ext and refs:
            print('  WARNING: --skip-ext leaves out models the map uses; they would show as errors in game')
    for h in b['held']:
        print('  KEPT   %s: %s' % (h['rel'], h['why']))
    for n in b['notes']:
        print('  note: %s' % n)
    print('  CS2 tools mode: %s (%s)' % (state, state_text))
    if lock:
        print('  out/build.lock exists: a generator may still be writing out/addon')
    if a.list:
        for p in plan:
            if p['op'] != 'same':
                print('    %-6s %s  %s' % (p['op'], p['rel'], mb(p['size'])))
    for pr in b['problems']:
        print('  PROBLEM: %s' % pr)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Deploy the generated mg_monsoon addon (dry run unless --apply).')
    ap.add_argument('--apply', action='store_true', help='write the files (default: dry run)')
    ap.add_argument('--list', action='store_true', help='print every file that would be created or replaced')
    ap.add_argument('--skip-ext', action='store_true', help='leave out the GMod Workshop conversions (models/mv/ext)')
    ap.add_argument('--no-docs', action='store_true', help='do not ship README / TESTING / CREDITS / licence files')
    ap.add_argument('--overwrite-map', action='store_true', help='replace a .vmap that changed in the addon since the last deploy')
    ap.add_argument('--allow-open', action='store_true', help='deploy although CS2 tools mode is open on the addon (the person at the game said go)')
    ap.add_argument('--ignore-lock', action='store_true', help='deploy although out/build.lock exists')
    ap.add_argument('--json', help='also write the report as JSON to this file (dry run: the only file written)')
    ap.add_argument('--rollback', metavar='MANIFEST', help='undo a deploy from its manifest (dry run unless --apply)')
    ap.add_argument('--out', help='the project out folder (default: ../out)')
    ap.add_argument('--content', help='content addons folder (default %s, or CS2_ROOT\\content\\csgo_addons)' % DEF_CONTENT)
    ap.add_argument('--game', help='game addons folder (default %s, or CS2_ROOT\\game\\csgo_addons)' % DEF_GAME)
    ap.add_argument('--template', help='addon_template content folder (default: <content addons>\\addon_template)')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')

    state, state_text = tools_open(ADDON)
    if a.rollback:
        if a.apply and state != 'closed' and not a.allow_open:
            print('HELD: %s. Nothing was changed.' % state_text)
            return 3
        res = safepath.rollback(a.rollback, dry_run=not a.apply)
        print('rollback%s: %d restored, %d removed, %d left alone' % ('' if a.apply else ' (dry run)', len(res['restored']),
                                                                    len(res['removed']), len(res['skipped'])))
        for s in res['skipped']:
            print('  left: %s (%s)' % (s['dst'], s['why']))
        return 0

    b = build(a)
    lock = os.path.exists(os.path.join(b['out'], 'build.lock'))
    report(b, a, state, state_text, lock)
    summ = safepath.summarise(b['plan'])
    result = {'addon': ADDON, 'dry_run': not a.apply, 'level': 'untested', 'manual_check_required': True,
              'content': b['content_dst'], 'game': b['game_dst'], 'summary': {k: summ[k] for k in ('create', 'modify', 'same', 'bytes_written', 'bytes_backed_up')},
              'generated': [{k: g[k] for k in ('rel', 'op', 'size', 'note')} for g in b['generated']],
              'held': b['held'], 'problems': b['problems'], 'notes': b['notes'], 'tools_mode': state, 'build_lock': lock,
              'source': {k: {'files': v['files'], 'bytes': v['bytes']} for k, v in b['source'].items()},
              'only_in_destination': b['extras'], 'gmod_models_in_map': b['ext_refs']}

    def finish(code):
        if a.json:
            with open(a.json, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=1)
        return code

    if b['problems']:
        print('STOPPED: %d problem(s) above. Nothing was changed.' % len(b['problems']))
        return finish(2)
    if not a.apply:
        if state == 'open':
            print('An --apply now would be HELD: %s.' % state_text)
        print('Dry run only. Nothing was written.')
        return finish(0)
    if state != 'closed' and not a.allow_open:
        print('HELD: %s. Close the map in CS2 / Hammer and deploy again, or pass --allow-open. Nothing was changed.' % state_text)
        return finish(3)
    if lock and not a.ignore_lock:
        print('HELD: out/build.lock exists (a generator is writing out/addon). Nothing was changed.')
        return finish(4)

    if not (summ['create'] or summ['modify'] or any(g['op'] != 'same' for g in b['generated'])):
        print('Nothing to deploy: every file in the addon already has these bytes. Nothing was written, no record made.')
        return finish(0)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    n = 1
    while os.path.exists(os.path.join(b['mandir'], '%s_deploy_%s.json' % (ADDON, stamp))):   # two deploys in one second
        n += 1
        stamp = stamp.split('-')[0] + '-%d' % n
    manifest = os.path.join(b['mandir'], '%s_deploy_%s.json' % (ADDON, stamp))
    backups = os.path.join(b['mandir'], 'backups', stamp)

    def backup_path(p):                                         # a map's backup sits next to it (pclocal's convention)
        return p['dst'] + '.bak_' + stamp if p['dst'].lower().endswith('.vmap') else None

    man = safepath.apply_plan(b['plan'], backups, manifest, label='%s deploy' % ADDON, stamp=stamp, backup_path=backup_path,
                              roots=[b['content_dst'], b['game_dst']])
    man['complete'] = False
    man['generated'] = []
    for g in b['generated']:
        res = safepath.write_atomic(g['dst'], g['data'], backup=os.path.join(backups, 'written'), stamp=stamp, root=g['root'])
        if res['op'] != 'same':
            man['generated'].append({'rel': g['rel'], 'op': res['op'], 'dst': g['dst'], 'size': g['size'], 'before': g['before'],
                                     'after': sha_bytes(g['data']), 'backup': res['backup'], 'note': g['note']})
    man.update({'addon': ADDON, 'level': 'untested', 'manual_check_required': True, 'held': b['held'], 'notes': b['notes'],
                'tools_mode': state, 'gmod_models_in_map': b['ext_refs'], 'complete': True})
    tmp = manifest + '.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1)
    os.replace(tmp, manifest)
    result['manifest'] = manifest
    print('deployed: %d created, %d replaced, %d unchanged; %d written files. Record: %s'
          % (summ['create'], summ['modify'], summ['same'], len(man['generated']), manifest))
    print('Next: compile (docs/BUILD.md step 9). Nothing here has been compiled or loaded in CS2.')
    return finish(0)


if __name__ == '__main__':
    sys.exit(main())
