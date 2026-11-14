#!/usr/bin/env python3
"""deploy_addon.py: copy a project's staged files into a CS2 addon (content and game folders). Dry run unless --apply.
Project-neutral fork of projects/monsoon-cs2/tools/deploy_monsoon.py (create/libsync.json "forks").

  python -I create/deploy_addon.py --addon NAME --list FILE --record-dir DIR            dry run: counts, sizes, holds; writes nothing
  python -I create/deploy_addon.py --addon NAME --tree out/addon --game-tree out/game --record-dir DIR --show
  ... --apply                                                                           do it
  python -I create/deploy_addon.py --addon NAME --record-dir DIR --rollback DIR/NAME_deploy_<stamp>.json [--apply]

Sources (one or both)
  --tree DIR / --game-tree DIR  copy the tree DIR over <content addons>\\NAME / <game addons>\\NAME (monsoon's out/addon, out/game)
  --list FILE                   a deploy list, one file per line, '#' starts a comment:
                                    [game:]<addon-relative path>   [<- <source path>]
                                the source is relative to --list-root (default: the list's folder); a line with no '<-' takes
                                <--src-root>/<path> (default --src-root: <list-root>/out/addon). 'game:' sends it to the game addon.
Destinations: --content (default C:\\source1\\links\\content_addons, or CS2_ROOT\\content\\csgo_addons), --game likewise.

Rules (docs/reference/file-safety.md, tools/safepath.py)
  - Only files whose bytes differ are written (size + sha256); an unchanged file keeps its date, so Hammer and the compiler see nothing.
  - Nothing is deleted. A replaced file is backed up first and the backup checked (size + sha256); new bytes go through a temp file.
    Backups go to <record-dir>/backups/<stamp>/, except a .vmap: see below. No write goes through a link below an addon folder.
  - HELD (exit 3, nothing written) while CS2 tools mode (cs2.exe -tools, i.e. Hammer) has the addon open, while a cs2.exe -tools
    gives no -addon (cannot tell which addon), while a cs2.exe hides its command line, or while a resourcecompiler.exe is compiling
    something of this addon. A cs2.exe without -tools (the game, or the dedicated server in C:\\cs2server) is not a tools instance.
    --allow-open overrides, only when the person at the game said go.
  - HELD (exit 4) while --lock FILE exists (a generator is still writing the sources). --ignore-lock overrides.
  - A destination .vmap is the user's Hammer work. It is replaced only when its current bytes are an expected "base" (--vmap-base,
    sha256 or CRC32, repeatable: the map the patches were made from) or what the last applied deploy wrote there; otherwise it is
    KEPT and listed (the rest still deploys; --strict-vmap stops the whole deploy instead, exit 5). --force-vmap replaces it anyway.
    Every replaced .vmap is first copied to <content addon>\\backups\\deploy_<stamp>\\<path> (checked) - always, forced or not.
  - --merge-sndevents TAG: soundevents/soundevents_addon.vsndevts is merged, not copied: only the TAG block of the addon's live file
    is replaced, every other event in it is kept (create/sndevents.py merge). Without it the file is copied like any other.

Records (--record-dir): <NAME>_deploy_<stamp>.json after every file (create / modify, sha256 before and after, backup), a line per
apply in <NAME>_applied.txt, and on a dry run nothing at all unless --json. --rollback <manifest> --apply undoes a run
(safepath.rollback: only files that still hold what the run wrote).
How far this is checked: the copy logic is safepath's (unit tested); this wrapper was run as a dry run against the real addon folders.
What it copies is whatever the project staged: compiling and loading it in CS2 is still to do (level "untested").

Exit codes: 0 ok, 2 a problem that stops the deploy (missing source, bad list, bad merge, no room), 3 held (tools mode / compile /
process list unreadable), 4 held by --lock, 5 a .vmap kept with --strict-vmap.
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
import re
import shutil
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for _p in (os.path.join(REPO, 'tools'), r'C:\source1\cs2port\tools'):
    if os.path.isfile(os.path.join(_p, 'safepath.py')):
        sys.path.append(_p)                                    # appended: nothing there shadows create/
        break
import safepath       # noqa: E402

DEF_CONTENT = r'C:\source1\links\content_addons'
DEF_GAME = r'C:\source1\links\game_addons'
SNDEVENTS = 'soundevents/soundevents_addon.vsndevts'
SKIP = ('*.part', '*.copytmp', '*.bak_*', '*.pyc', '*.lock', 'Thumbs.db', 'desktop.ini')
SKIP_DIRS = ('__pycache__',)


def mb(n):
    return '%.1f MB' % (n / 1048576.0)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def crc32_file(path, chunk=1 << 20):
    c = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            c = zlib.crc32(b, c)
    return '%08x' % (c & 0xffffffff)


def norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def skipped(rel):
    parts = rel.split('/')
    if any(d in SKIP_DIRS for d in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in SKIP)


# ---------------------------------------------------------------- who has the addon open
def processes():
    """-> (rows, error). rows: [(pid, name, exe, cmdline)] for cs2.exe, resourcecompiler.exe and any *hammer* process."""
    cmd = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cs2.exe' -or $_.Name -eq 'resourcecompiler.exe' "
           "-or $_.Name -like '*hammer*' } | ForEach-Object { \"$($_.ProcessId)`t$($_.Name)`t$($_.ExecutablePath)`t$($_.CommandLine)\" }")
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd], capture_output=True, text=True,
                           timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))   # no console, no focus taken
    except Exception as e:                                     # no PowerShell, timeout
        return None, 'could not list processes (%s)' % type(e).__name__
    if r.returncode != 0:
        return None, 'the process list failed (exit %d)' % r.returncode
    rows = []
    for line in r.stdout.splitlines():
        f = line.split('\t', 3)
        if len(f) == 4:
            rows.append(tuple(x.strip() for x in f))
    return rows, None


def tools_state(addon, rows=None, err=None):
    """-> (state, text, notes). state 'open' | 'unknown' | 'closed'. Pure function of the process rows (testable)."""
    if rows is None and err is None:
        rows, err = processes()
    if rows is None:
        return 'unknown', err, []
    word = re.compile(r'(?<![a-z0-9_])%s(?![a-z0-9_])' % re.escape(addon.lower()))
    held, unknown, notes = [], [], []
    for pid, name, exe, cl in rows:
        low = cl.lower()
        lname = name.lower()
        if lname == 'cs2.exe':
            if not cl:
                unknown.append('cs2.exe pid %s hides its command line (started elevated?)' % pid)
            elif re.search(r'(^|\s)-tools(\s|$)', low):
                if word.search(low):
                    held.append('cs2.exe pid %s runs with -tools on %s (Hammer / tools mode)' % (pid, addon))
                elif '-addon' not in low:
                    unknown.append('cs2.exe pid %s runs with -tools and no -addon: cannot tell which addon it has' % pid)
                else:
                    notes.append('cs2.exe pid %s: tools mode on another addon' % pid)
            else:
                kind = 'dedicated server' if ('-dedicated' in low or 'cs2server' in (exe or low).lower()) else 'game'
                notes.append('cs2.exe pid %s: %s, not a tools instance' % (pid, kind))
        elif lname == 'resourcecompiler.exe':
            if word.search(low.replace('\\', '/')):
                held.append('resourcecompiler.exe pid %s is compiling %s' % (pid, addon))
            else:
                notes.append('resourcecompiler.exe pid %s compiles another addon' % pid)
        elif 'hammer' in lname:
            if word.search(low) or not cl:
                held.append('%s pid %s (%s)' % (name, pid, 'on ' + addon if cl else 'command line hidden'))
            else:
                notes.append('%s pid %s: another map' % (name, pid))
    if held:
        return 'open', '; '.join(held), notes
    if unknown:
        return 'unknown', '; '.join(unknown), notes
    return 'closed', 'no tools instance or compile on %s' % addon, notes


# ---------------------------------------------------------------- inputs
def read_list(path, list_root, src_root):
    """-> ([(side, rel, src, lineno)], problems)"""
    out, problems = [], []
    with open(path, encoding='utf-8-sig') as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            side = 'content'
            if line.lower().startswith('game:'):
                side, line = 'game', line[5:].strip()
            if '<-' in line:
                rel, src = (x.strip() for x in line.split('<-', 1))
                src = src.replace('\\', os.sep).replace('/', os.sep)
                src = src if os.path.isabs(src) else os.path.join(list_root, src)
            else:
                rel, src = line, None
            rel = rel.replace('\\', '/').strip('/')
            parts = rel.split('/')
            if not rel or os.path.isabs(rel) or ':' in rel or any(p in ('', '.', '..') for p in parts):
                problems.append('%s line %d: not an addon-relative path: %r' % (path, n, rel))
                continue
            if src is None:
                src = os.path.join(src_root, *parts)
            out.append((side, rel, os.path.normpath(src), n))
    return out, problems


def last_written(record_dir, addon):
    """dst (normalised) -> sha256 the last complete applied deploys wrote there; newest manifest wins."""
    seen = {}
    for path in sorted(glob.glob(os.path.join(record_dir, '%s_deploy_*.json' % addon))):
        try:
            with open(path, encoding='utf-8') as f:
                man = json.load(f)
        except (OSError, ValueError):
            continue
        if man.get('dry_run'):
            continue
        for rec in list(man.get('files', [])) + list(man.get('generated', [])):
            if rec.get('after') and rec.get('dst'):
                seen[norm(rec['dst'])] = rec['after']
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


def build(a):
    """Everything a deploy would do, read-only."""
    cs2 = os.environ.get('CS2_ROOT')
    content_root = a.content or (os.path.join(cs2, 'content', 'csgo_addons') if cs2 else DEF_CONTENT)
    game_root = a.game or (os.path.join(cs2, 'game', 'csgo_addons') if cs2 else DEF_GAME)
    addon = safepath.addon_name(a.addon)
    roots = {'content': os.path.join(content_root, addon), 'game': os.path.join(game_root, addon)}
    problems, notes, held = [], [], []
    for label, root in (('content addons folder', content_root), ('game addons folder', game_root)):
        if not os.path.isdir(root):
            problems.append('%s not found: %s' % (label, root))
    for side, d in roots.items():
        if safepath.is_link(d):
            notes.append('%s addon folder is a link to %s (allowed: it is the folder the tool was pointed at)' % (side, safepath.link_target(d)))
    b = dict(problems=problems, notes=notes, held=held, plan=[], generated=[], roots=roots, addon=addon,
             new_addon=not os.path.isdir(roots['content']), sources=[])
    if problems:
        return b

    plan = []
    for side, tree in (('content', a.tree), ('game', a.game_tree)):
        if not tree:
            continue
        if not os.path.isdir(tree):
            problems.append('--%s not found: %s' % ('tree' if side == 'content' else 'game-tree', tree))
            continue
        part = [p for p in safepath.plan_copy(tree, roots[side]) if not skipped(p['rel'])]
        for p in part:
            p['side'] = side
            p['from'] = 'tree'
        plan += part
        b['sources'].append({'kind': side + ' tree', 'path': os.path.abspath(tree), 'files': len(part)})
    if a.list:
        list_root = os.path.abspath(a.list_root or os.path.dirname(os.path.abspath(a.list)))
        src_root = os.path.abspath(a.src_root or os.path.join(list_root, 'out', 'addon'))
        entries, probs = read_list(a.list, list_root, src_root)
        problems += probs
        b['sources'].append({'kind': 'list', 'path': os.path.abspath(a.list), 'files': len(entries), 'list_root': list_root, 'src_root': src_root})
        firsts, pairs = {}, {'content': [], 'game': []}
        for side, rel, src, n in entries:
            dst = os.path.join(roots[side], *rel.split('/'))
            k = norm(dst)
            if k in firsts:
                if norm(firsts[k]) != norm(src):
                    problems.append('two sources for %s:%s: %s and %s' % (side, rel, firsts[k], src))
                continue
            firsts[k] = src
            if not os.path.isfile(src) or safepath.is_link(src):
                problems.append('source missing (or a link) for %s:%s: %s' % (side, rel, src))
                continue
            pairs[side].append((src, dst))
        for side in ('content', 'game'):
            if not pairs[side]:
                continue
            try:
                part = safepath.plan_pairs(pairs[side], [roots[side]])
            except (ValueError, OSError) as e:
                problems.append(str(e))
                continue
            for p in part:
                p['side'] = side
                p['from'] = 'list'
            plan += part
    seen = {}
    for p in plan:
        k = norm(p['dst'])
        if k in seen and norm(seen[k]) != norm(p['src']):
            problems.append('two sources for %s: %s and %s' % (p['dst'], seen[k], p['src']))
        seen[k] = p['src']
    for p in plan:
        p['rel'] = p['side'] + '/' + p['rel']

    # the user's map: replaced only from a known base, or over what the last deploy wrote
    bases = {h.lower() for h in (a.vmap_base or [])}
    prev = last_written(a.record_dir, addon)
    for p in list(plan):
        if not p['rel'].lower().endswith('.vmap') or p['op'] != 'modify':
            continue
        now_sha = safepath.sha256_file(p['dst'])
        now_crc = crc32_file(p['dst'])
        p['vmap_now'] = {'sha256': now_sha, 'crc32': now_crc}
        if now_sha in bases or now_crc in bases:
            p['vmap_rule'] = 'replaces the recorded base (%s)' % now_crc
        elif prev.get(norm(p['dst'])) == now_sha:
            p['vmap_rule'] = 'replaces what the last deploy wrote (%s)' % now_crc
        elif a.force_vmap:
            p['vmap_rule'] = 'FORCED over a map that is not the base (CRC32 %s)' % now_crc
        else:
            plan.remove(p)
            held.append({'rel': p['rel'], 'dst': p['dst'], 'crc32': now_crc, 'sha256': now_sha,
                         'why': 'the addon\'s map (CRC32 %s) is neither the recorded base%s nor what the last deploy wrote: saved in Hammer? '
                                'Re-run the patches from it, or pass --force-vmap (it is backed up first)'
                                % (now_crc, ' (%s)' % ', '.join(sorted(h[:8] for h in bases)) if bases else '')})
    for p in plan:
        if p['rel'].lower().endswith('.vmap') and p['op'] == 'modify':
            bak = os.path.join(roots['content'], 'backups', 'deploy_<stamp>', *p['rel'].split('/')[1:])
            try:
                safepath.check_no_nested_links(roots['content'], bak.replace('<stamp>', 'x'))
            except ValueError as e:
                problems.append('the map backup would go through a link: %s' % e)
            p['vmap_backup'] = bak

    # sound events: keep whatever else the live file holds
    snd = [p for p in plan if p['side'] == 'content' and p['rel'].split('/', 1)[1].lower() == SNDEVENTS]
    if snd and a.merge_sndevents:
        sys.path.insert(0, HERE)
        import sndevents                                       # create/sndevents.py
        p = snd[0]
        plan.remove(p)
        with open(p['src'], encoding='utf-8', newline='') as f:
            ours = f.read()
        tag = a.merge_sndevents
        n_ours = len(sndevents.event_names(sndevents.body_of(ours, tag)))
        if os.path.isfile(p['dst']):
            with open(p['dst'], encoding='utf-8', newline='') as f:
                live = f.read()
            try:
                text = sndevents.merge(live, ours, tag)
                note = 'merged: %d %s events replace the block, %d other events kept' % (n_ours, tag, len(sndevents.event_names(text)) - n_ours)
            except ValueError as e:
                problems.append('sound events merge refused: %s' % e)
                text = None
        else:
            text, note = ours, 'new file: %d %s events' % (n_ours, tag)
        if text is not None:
            data = text.encode('utf-8')
            old = open(p['dst'], 'rb').read() if os.path.isfile(p['dst']) else None
            b['generated'].append({'rel': p['rel'], 'side': 'content', 'root': roots['content'], 'dst': p['dst'], 'data': data,
                                   'op': 'create' if old is None else ('same' if old == data else 'modify'), 'size': len(data),
                                   'old_size': None if old is None else len(old), 'before': None if old is None else sha_bytes(old),
                                   'note': note})
    elif snd and snd[0]['op'] == 'modify':
        notes.append('%s replaces the whole live file (pass --merge-sndevents TAG to keep other events in it)' % SNDEVENTS)
    b['plan'] = plan
    return b


def report(b, a, state, state_text, pnotes, lock):
    plan, gen = b['plan'], b['generated']
    print('%s deploy: %s' % (b['addon'], 'APPLY' if a.apply else 'DRY RUN (nothing is written; --apply to deploy)'))
    for side in ('content', 'game'):
        print('  %-7s -> %s%s' % (side, b['roots'][side], '' if os.path.isdir(b['roots'][side]) else '   (does not exist: would be created)'))
    for s in b['sources']:
        print('  source %s: %s (%d files)' % (s['kind'], s['path'], s['files']))
    tops = {}
    for p in plan:
        parts = p['rel'].split('/')
        key = parts[0] + '/' + (parts[1] if len(parts) > 2 else '(root)')
        t = tops.setdefault(key, {'create': 0, 'modify': 0, 'same': 0, 'bytes': 0})
        t[p['op']] += 1
        if p['op'] != 'same':
            t['bytes'] += p['size']
    print('  %-28s %7s %7s %7s %12s' % ('folder', 'create', 'modify', 'same', 'to write'))
    for key in sorted(tops):
        t = tops[key]
        print('  %-28s %7d %7d %7d %12s' % (key, t['create'], t['modify'], t['same'], mb(t['bytes'])))
    summ = safepath.summarise(plan)
    gw = sum(g['size'] for g in gen if g['op'] != 'same')
    print('  %-28s %7d %7d %7d %12s' % ('total', summ['create'], summ['modify'], summ['same'], mb(summ['bytes_written'])))
    for g in gen:
        print('    %-6s %s  (%s)' % (g['op'], g['rel'], g['note']))
    for p in plan:
        if p.get('vmap_rule'):
            print('  MAP    %s %s: %s; backup first to %s' % (p['op'], p['rel'], p['vmap_rule'], p['vmap_backup']))
    need = summ['bytes_written'] + summ['bytes_backed_up'] + gw
    free = free_bytes(b['roots']['content'])
    print('  to write %s, to back up first %s; free on the destination drive: %s'
          % (mb(summ['bytes_written'] + gw), mb(summ['bytes_backed_up']), 'unknown' if free is None else mb(free)))
    if free is not None and free < need:
        b['problems'].append('not enough room on the destination drive: %s needed, %s free' % (mb(need), mb(free)))
    for h in b['held']:
        print('  KEPT   %s: %s' % (h['rel'], h['why']))
    for n in b['notes'] + pnotes:
        print('  note: %s' % n)
    print('  CS2 tools / compile: %s (%s)' % (state, state_text))
    if lock:
        print('  lock file exists: %s' % a.lock)
    if a.show:
        for p in plan:
            if p['op'] != 'same':
                print('    %-6s %s  %s' % (p['op'], p['rel'], mb(p['size'])))
    for pr in b['problems']:
        print('  PROBLEM: %s' % pr)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Deploy staged files into a CS2 addon (dry run unless --apply).')
    ap.add_argument('--addon', required=True, help='addon folder name (one plain name)')
    ap.add_argument('--tree', help='copy this tree over the content addon')
    ap.add_argument('--game-tree', help='copy this tree over the game addon')
    ap.add_argument('--list', help='deploy list file ([game:]rel [<- src] per line)')
    ap.add_argument('--list-root', help='folder the list\'s sources are relative to (default: the list\'s folder)')
    ap.add_argument('--src-root', help='where list lines without "<-" come from (default <list-root>/out/addon)')
    ap.add_argument('--record-dir', required=True, help='manifests, the applied list and non-map backups go here')
    ap.add_argument('--content', help='content addons folder (default %s, or CS2_ROOT\\content\\csgo_addons)' % DEF_CONTENT)
    ap.add_argument('--game', help='game addons folder (default %s, or CS2_ROOT\\game\\csgo_addons)' % DEF_GAME)
    ap.add_argument('--vmap-base', action='append', help='sha256 or CRC32 of a destination .vmap that may be replaced (repeatable)')
    ap.add_argument('--force-vmap', action='store_true', help='replace a .vmap that is not a base (it is backed up first)')
    ap.add_argument('--strict-vmap', action='store_true', help='a kept .vmap stops the whole deploy (exit 5)')
    ap.add_argument('--merge-sndevents', metavar='TAG', help='merge soundevents_addon.vsndevts: replace only the TAG block')
    ap.add_argument('--lock', help='hold while this file exists')
    ap.add_argument('--ignore-lock', action='store_true')
    ap.add_argument('--allow-open', action='store_true', help='deploy although CS2 tools mode / a compile has the addon (the person at the game said go)')
    ap.add_argument('--apply', action='store_true', help='write the files (default: dry run)')
    ap.add_argument('--show', action='store_true', help='print every file that would be created or replaced')
    ap.add_argument('--json', help='also write the report as JSON here (on a dry run, the only file written)')
    ap.add_argument('--label', default='', help='a note recorded in the manifest and the applied list')
    ap.add_argument('--rollback', metavar='MANIFEST', help='undo a deploy from its manifest (dry run unless --apply)')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    try:
        addon = safepath.addon_name(a.addon)
    except ValueError as e:
        print('PROBLEM: %s' % e)
        return 2

    state, state_text, pnotes = tools_state(addon)
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
    if not (a.tree or a.game_tree or a.list):
        print('PROBLEM: nothing to deploy: give --tree, --game-tree or --list')
        return 2

    b = build(a)
    lock = bool(a.lock and os.path.exists(a.lock))
    report(b, a, state, state_text, pnotes, lock)
    summ = safepath.summarise(b['plan'])
    result = {'addon': addon, 'dry_run': not a.apply, 'level': 'untested', 'label': a.label, 'roots': b['roots'],
              'summary': {k: summ[k] for k in ('create', 'modify', 'same', 'bytes_written', 'bytes_backed_up')},
              'files': [{'rel': p['rel'], 'op': p['op'], 'size': p['size'], 'src': p['src'], 'vmap_rule': p.get('vmap_rule')} for p in b['plan']],
              'generated': [{k: g[k] for k in ('rel', 'op', 'size', 'note')} for g in b['generated']],
              'held': b['held'], 'problems': b['problems'], 'notes': b['notes'] + pnotes, 'tools_state': state, 'tools_text': state_text,
              'lock': lock, 'sources': b['sources']}

    def finish(code):
        result['exit'] = code
        if a.json:
            os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
            with open(a.json, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=1)
        return code

    if b['problems']:
        print('STOPPED: %d problem(s) above. Nothing was changed.' % len(b['problems']))
        return finish(2)
    if b['held'] and a.strict_vmap:
        print('STOPPED: a map is kept (--strict-vmap). Nothing was changed.')
        return finish(5)
    if not a.apply:
        if state != 'closed':
            print('An --apply now would be HELD: %s.' % state_text)
        if lock:
            print('An --apply now would be HELD by the lock file.')
        print('Dry run only. Nothing was written.')
        return finish(0)
    if state != 'closed' and not a.allow_open:
        print('HELD: %s. Close the map in CS2 / Hammer (or wait for the compile) and deploy again. Nothing was changed.' % state_text)
        return finish(3)
    if lock and not a.ignore_lock:
        print('HELD: %s exists (a generator is writing the sources). Nothing was changed.' % a.lock)
        return finish(4)
    if not (summ['create'] or summ['modify'] or any(g['op'] != 'same' for g in b['generated'])):
        print('Nothing to deploy: every file in the addon already has these bytes. Nothing was written, no record made.')
        return finish(0)

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    n = 1
    while os.path.exists(os.path.join(a.record_dir, '%s_deploy_%s.json' % (addon, stamp))):
        n += 1
        stamp = stamp.split('-')[0] + '-%d' % n
    os.makedirs(a.record_dir, exist_ok=True)
    manifest = os.path.join(a.record_dir, '%s_deploy_%s.json' % (addon, stamp))
    backups = os.path.join(a.record_dir, 'backups', stamp)

    def backup_path(p):                                         # the user's map: into the addon's own backups folder
        if p['dst'].lower().endswith('.vmap'):
            bak = p['vmap_backup'].replace('<stamp>', stamp)
            safepath.check_no_nested_links(b['roots']['content'], bak)
            return bak
        return None

    man = safepath.apply_plan(b['plan'], backups, manifest, label='%s deploy %s' % (addon, a.label), stamp=stamp,
                              backup_path=backup_path, roots=[b['roots']['content'], b['roots']['game']])
    man['complete'] = False
    man['generated'] = []
    for g in b['generated']:
        res = safepath.write_atomic(g['dst'], g['data'], backup=os.path.join(backups, 'written'), stamp=stamp, root=g['root'])
        if res['op'] != 'same':
            man['generated'].append({'rel': g['rel'], 'op': res['op'], 'dst': g['dst'], 'size': g['size'], 'before': g['before'],
                                     'after': sha_bytes(g['data']), 'backup': res['backup'], 'note': g['note']})
    maps = [{'rel': p['rel'], 'rule': p['vmap_rule'], 'before': p['vmap_now'], 'backup': p['vmap_backup'].replace('<stamp>', stamp)}
            for p in b['plan'] if p.get('vmap_rule')]
    man.update({'addon': addon, 'level': 'untested', 'held': b['held'], 'notes': b['notes'] + pnotes, 'tools_state': state,
                'maps': maps, 'sources': b['sources'], 'complete': True})
    tmp = manifest + '.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1)
    os.replace(tmp, manifest)
    with open(os.path.join(a.record_dir, '%s_applied.txt' % addon), 'a', encoding='utf-8', newline='\n') as f:
        f.write('%s\t%d created\t%d replaced\t%d written\t%s\t%s\n' % (stamp, summ['create'], summ['modify'], len(man['generated']),
                                                                    os.path.basename(manifest), a.label))
    result['manifest'] = manifest
    print('deployed: %d created, %d replaced, %d unchanged; %d generated files. Record: %s'
          % (summ['create'], summ['modify'], summ['same'], len(man['generated']), manifest))
    for m in maps:
        print('  map %s backed up to %s' % (m['rel'], m['backup']))
    print('Next: compile (the project\'s docs/BUILD.md). Nothing here has been compiled or loaded in CS2.')
    return finish(0)


if __name__ == '__main__':
    sys.exit(main())
