#!/usr/bin/env python3
"""deploy_tw.py: the mg_trenchwarfare delivery (remaster step 9). Rebuilds the final map from the user's vmap through the guarded patch
chain, merges the step deploy lists, runs the offline gate, then hands the list to the neutral create/deploy_addon.py.
Dry run unless --apply. Replaces the numbered zips + C:\\source1\\cs2port\\unpack_mg_trenchwarfare.bat route (docs/BUILD.md "Old route").

usage (from the project folder):
  python -u tools/deploy_tw.py --chain                                          rebuild out/step9/chain/*.vmap, then the dry run
  python -u tools/deploy_tw.py                                                  merge + gate + deploy dry run on the last chain
  python -u tools/deploy_tw.py --apply                                          the same, then copy (held while Hammer / cs2 -tools is open)
  options: --show (every file), --no-gate (dry run only), --force-vmap (replace an addon map that is not the base: backed up first)
           --no-user-m2 / --no-user-w5 (leave those out of the chain; they are on by default, see "Opt-in flags" below)

(a) chain   out/step9/chain/0_user.vmap (a copy of content\\...\\maps\\mg_trenchwarfare.vmap) -> 1_world_1 (patch_world_1, step 5)
            -> 2_models (patch_models, step 6) -> 3_terrain (patch_terrain, step 7) -> 4_seams (patch_seams: siding-top caps, sheet
            lips, sap mouths; docs/REVIEW_WORLD_2.md "Seams") -> 5_world_3 (patch_world_3: CT air-lane poplars, pit_t_2's shell rack,
            the pool poplar, crater pool rims; docs/REVIEW_WORLD_3.md) -> 6_sounds (patch_sounds, step 8: the sound entities; skipped
            with a note while tools/patch_sounds.py does not exist) -> 7_nav (patch_nav, step 4, reading the staged models in out/addon
            like the gate: the rebuilt shelter of step 13) = the final map.
            Then the radar is re-made from the final map (tools/make_radar.py --vmap <final>, tools/check_radar.py; outputs are
            step 8's staging in out/addon + out/game, their hashes recorded so a later re-make is noticed).
            Before stage 1 the user's map must be the recorded BASE (CRC32 2e3f90d0, the tw34 delivery the patches' target tables were
            read from). After a Hammer save it is not: the chain stops and says so; the patches' target tables then have to be re-read
            from the new map's digest (ids change on a save) and BASE updated here. Every later stage checks that its input is the
            byte-exact output of the stage before; every stage's output goes through tools/patch_guard.py --strict (only declared
            changes). With no opt-in flags the outputs are compared with the earlier steps' own outputs (out/mg_trenchwarfare_*.vmap).
            The patch tools also rewrite their step's records (out/step5..7 deploy lists, targets, report); the chain keeps the copies
            from this run in out/step9/chain/side/ and puts the step folders back as they were.
            The user's opt-ins, passed to patch_world_1 only (a deploy refuses flags that differ from the chain's):
              --user-m2 (ON by default): delete the duplicate info_map_parameters id 7 (Hammer defaults, buying 0; tw_params keeps
                        buying 3 = nobody, the map's no-buy design; the script also sets mp_buytime 0).
              --user-w5 (ON by default): delete tl_bench 72, the exact copy of bench 71 1 u above it (z-fight; REVIEW_WORLD_2 W5).
              --user-h1 unlock|remove (OFF; do not use on this map): the 24 sap benches are the user's seam bridges, kept as placed.
            Decided by the user 12 Nov 2026: sap tunnels "do what's best for gameplay", duplicate info_map_parameters deleted if safe,
            then the correction that the benches are bridges (keep them; drop only the exact duplicate).
(b) list    out/step5..8/deploy_files.txt (5-7 from this chain run's side copies; 8 when present), out/step10/deploy_files.txt
            (release docs: CREDITS, licences, Steam description; when present), out/step11/deploy_files.txt (weapon replacements,
            staged by the weapons work), out/step12/deploy_files.txt (licence-replacement assets) and out/step13/deploy_files.txt (the
            rebuilt shelter: walkable dressing stations, docs/REVIEW_WORLD_3.md W2) (each when present; a later step wins), merged
            into out/step9/deploy_files.txt
            (one line per file, last step wins, map = the chain's final vmap) + a model -> material check (a material a deployed model
            names must be in the list, in the addon or in the game's pak01: the "stock.ensure" gotcha).
(c) gate    on the final map: check_world, check_play (no failure that the step 7 baseline did not have), check_seams --no-sight
            (0 open seams in the generated geometry; user-owned ones are listed, not counted), check_contract --vmap --stage (exit 0), and the script gate of docs/SCRIPT.md without perf: api.py --strict --check, tscheck, mock 32 300, mock 16 300
            fill=1 humans=4, mock scenario=all. Logs in out/step9/gate/, result out/step9/gate.json. A new failure refuses --apply.
(d) deploy  python -I create/deploy_addon.py --addon mg_trenchwarfare --list out/step9/deploy_files.txt --record-dir out/step9/deploy
            --vmap-base <BASE sha256> --vmap-base 2e3f90d0 --strict-vmap [--apply]. The addon's map is replaced only while it is still
            BASE (or what the last deploy wrote), and is backed up to content\\...\\mg_trenchwarfare\\backups\\deploy_<stamp>\\ first.
Also reports whether the old unpack bat is inert (every zip in cs2port\\assets\\tw is in its applied list).
Exit: 0 ok; 1 chain / guard failure; 2 list problem; 6 gate refused; otherwise deploy_addon's code. Level: the chain and checks are
offline ("simulated"); nothing is compiled. AI-generated (Claude) for skink52.
"""
import argparse, datetime, glob, hashlib, json, os, pickle, re, shutil, subprocess, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
STEP9 = os.path.join(OUT, 'step9')
CHAIN = os.path.join(STEP9, 'chain')
SIDE = os.path.join(CHAIN, 'side')
GATE = os.path.join(STEP9, 'gate')
ADDON = 'mg_trenchwarfare'
CONTENT = r'C:\source1\links\content_addons\mg_trenchwarfare'
USER_VMAP = os.path.join(CONTENT, 'maps', 'mg_trenchwarfare.vmap')
MAP_REL = 'maps/mg_trenchwarfare.vmap'
# the map every patch's target table was read from: the user's save = the tw34 delivery (docs/research/TW_STATE.md section 0)
BASE = dict(crc32='2e3f90d0', size=67206918, sha256='9fb68e43ff31e7f87b129909489b0c1a594c2e83e66eaa07440ed6da0da5f73f')
# earlier steps' own outputs (default flags), for the determinism comparison
REFS = {'1_world_1': 'mg_trenchwarfare_patched.vmap', '2_models': 'mg_trenchwarfare_models.vmap', '3_terrain': 'mg_trenchwarfare_terrain.vmap'}
STEP_LISTS = (5, 6, 7, 8, 10, 11, 12, 13)   # 8, 10-13 optional (a note when missing); 10 = release docs (CREDITS, licences, Steam description), 11 = weapons, 12 = licence-replacement assets, 13 = the rebuilt shelter
PY = sys.executable
OLD_BAT_LOG = r'C:\source1\cs2port\logs\mg_trenchwarfare_applied.txt'
OLD_ZIPS = r'C:\source1\cs2port\assets\tw'
VPK_INDEX = os.path.join(OUT, 'review', 'cache', 'pak01_index.pkl')       # check_world's cache of the game's pak01 file names


def rel(p):
    return os.path.relpath(p, PROJ).replace('\\', '/')


def deploy_map_entries():
    """(record, map entry) of every deploy record that wrote the map, newest first"""
    out = []
    for rp in sorted(glob.glob(os.path.join(STEP9, 'deploy', 'mg_trenchwarfare_deploy_*.json')), reverse=True):
        try:
            with open(rp, encoding='utf-8') as f: recd = json.load(f)
        except (OSError, ValueError): continue
        out += [(os.path.basename(rp), e) for e in recd.get('files', []) if e.get('rel', '').endswith(MAP_REL)]
    return out


def last_deployed_map(sha):
    """the newest deploy's map entry when the addon map is still exactly what it wrote, else None"""
    ents = deploy_map_entries()
    return ents[0] if ents and ents[0][1].get('after') == sha else None


def base_backup():
    """a deploy backup of the base map (the chain checks its hash), or None"""
    for _, e in deploy_map_entries():
        if e.get('before') == BASE['sha256'] and os.path.isfile(e.get('backup', '')): return e['backup']
    return None


def hashes(path, chunk=1 << 20):
    h, c, n = hashlib.sha256(), 0, 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b); c = zlib.crc32(b, c); n += len(b)
    return dict(sha256=h.hexdigest(), crc32='%08x' % (c & 0xffffffff), size=n)


def run(cmd, log, cwd=PROJ, timeout=1800):
    """run a command, tee its output into log; -> (exit code, output text, seconds)"""
    t0 = time.time()
    os.makedirs(os.path.dirname(log), exist_ok=True)
    print('  $ %s' % ' '.join(('"%s"' % c) if ' ' in c else c for c in cmd), flush=True)
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        code, text = r.returncode, (r.stdout or '') + (('\n[stderr]\n' + r.stderr) if r.stderr.strip() else '')
    except subprocess.TimeoutExpired as e:
        code, text = 124, ((e.stdout or b'').decode('utf-8', 'replace') if isinstance(e.stdout, bytes) else (e.stdout or '')) + '\nTIMEOUT after %d s' % timeout
    with open(log, 'w', encoding='utf-8', newline='\n') as f:
        f.write('$ %s\n%s\nexit %d\n' % (' '.join(cmd), text, code))
    return code, text, time.time() - t0


def last_line(text, pat):
    hit = [l for l in text.splitlines() if re.search(pat, l)]
    return hit[-1].strip() if hit else ''


# ---------------------------------------------------------------- (a) the chain
SIDE_FILES = {   # what each patch tool writes into an earlier step's folder besides its map (kept as side copies, then put back)
    '1_world_1': ['step5/deploy_files.txt', 'step5/deploy_files_optin.txt'],
    '2_models': ['step6/patch_models.targets.json', 'step6/user_owned.txt', 'step6/deploy_files.txt'],
    '3_terrain': ['step7/patch_terrain.report.json', 'step7/terrain_layers.npz', 'step7/deploy_files.txt'],
    '4_seams': [],
    '5_world_3': [],
    '6_sounds': [],
    '7_nav': [],
}
SOUNDS_TOOL = os.path.join(HERE, 'patch_sounds.py')
# step 8's radar is drawn from the map: re-made from the final chained map (its outputs are step 8's staging: out/addon, out/game)
RADAR_FILES = ['panorama/images/overheadmaps/mg_trenchwarfare_radar_psd.png', 'panorama/images/overheadmaps/mg_trenchwarfare_radar_psd.vtex',
               'game:resource/overviews/mg_trenchwarfare.txt']


def find_targets(outp, before):
    """patch_sounds' target list: <out>.targets.json, else the newest *patch_sounds*targets*.json under out/ written by this run"""
    cand = [os.path.splitext(outp)[0] + '.targets.json']
    cand += sorted(glob.glob(os.path.join(OUT, '**', '*sounds*targets*.json'), recursive=True), key=os.path.getmtime, reverse=True)
    for c in cand:
        if os.path.isfile(c) and os.path.getmtime(c) >= before - 1:
            return c
    return None


def radar(final, rec):
    """make_radar.py --vmap <final> then check_radar.py; -> (ok, summary)"""
    fin = os.path.join(PROJ, *final.split('/'))
    code, text, secs = run([PY, '-u', 'tools/make_radar.py', '--vmap', fin], os.path.join(CHAIN, 'radar_make.log'))
    r = dict(make_exit=code, make_seconds=round(secs, 1), make_last=(text.strip().splitlines() or [''])[-1][:200])
    if code == 0:
        code2, text2, secs2 = run([PY, '-u', 'tools/check_radar.py'], os.path.join(CHAIN, 'radar_check.log'))
        r.update(check_exit=code2, check_seconds=round(secs2, 1), check_last=(text2.strip().splitlines() or [''])[-1][:200])
    r['files'] = {}
    for f in RADAR_FILES:
        side, rr = ('game', f[5:]) if f.startswith('game:') else ('content', f)
        p = os.path.join(OUT, 'game' if side == 'game' else 'addon', *rr.split('/'))
        r['files'][f] = hashes(p)['sha256'] if os.path.isfile(p) else None
    rec['radar'] = r
    ok = code == 0 and r.get('check_exit') == 0
    return ok, 'make_radar exit %d (%s); check_radar %s' % (code, r['make_last'], ('exit %d (%s)' % (r['check_exit'], r['check_last'])) if 'check_exit' in r else 'not run')


def snapshot(stage):
    snap = {}
    for r in SIDE_FILES[stage]:
        p = os.path.join(OUT, *r.split('/'))
        snap[r] = open(p, 'rb').read() if os.path.isfile(p) else None
    return snap


def restore(stage, snap):
    """keep this run's version under chain/side/, put the step folder back as it was"""
    kept = []
    for r, old in snap.items():
        p = os.path.join(OUT, *r.split('/'))
        if not os.path.isfile(p):
            continue
        new = open(p, 'rb').read()
        if new == old:
            side = os.path.join(SIDE, r.replace('/', '_'))
            shutil.copyfile(p, side); kept.append((r, 'unchanged'))
            continue
        side = os.path.join(SIDE, r.replace('/', '_'))
        shutil.copyfile(p, side)
        if old is None:
            os.remove(p)                                        # it did not exist before this run: the side copy is the record
            kept.append((r, 'new (moved to side/)'))
        else:
            tmp = p + '.part'
            open(tmp, 'wb').write(old); os.replace(tmp, p)
            kept.append((r, 'differed (step folder restored; this run in side/)'))
    return kept


def chain(a):
    os.makedirs(SIDE, exist_ok=True)
    rec = dict(started=datetime.datetime.now().isoformat(timespec='seconds'), base=BASE,
               flags=dict(user_h1=a.user_h1, user_m2=bool(a.user_m2), user_w5=bool(a.user_w5)), stages=[], ok=False)
    out_json = os.path.join(STEP9, 'chain.json')

    def save():
        tmp = out_json + '.part'
        json.dump(rec, open(tmp, 'w', encoding='utf-8'), indent=1); os.replace(tmp, out_json)

    def stop(msg):
        rec['stopped'] = msg; save()
        print('CHAIN STOPPED: %s' % msg)
        return 1

    print('chain: base check on %s' % USER_VMAP)
    if not os.path.isfile(USER_VMAP):
        return stop('the user\'s vmap is missing: %s' % USER_VMAP)
    src = os.path.join(CHAIN, '0_user.vmap')
    tmp = src + '.part'
    base_from = USER_VMAP
    # the addon map is exactly what the last deploy wrote (the chain output, not a Hammer save): the base is read from a deploy backup
    cur = hashes(USER_VMAP)
    if cur['sha256'] != BASE['sha256'] and last_deployed_map(cur['sha256']):
        bk = base_backup()
        if bk:
            base_from = bk
            print('  the addon map is the last deploy\'s output (CRC32 %s); base read from its backup %s' % (cur['crc32'], bk))
    shutil.copyfile(base_from, tmp)
    h0 = hashes(tmp)
    if h0['sha256'] != BASE['sha256']:
        os.remove(tmp)
        return stop('the user\'s map is not the recorded base: CRC32 %s, %d bytes (base %s, %d bytes). It was saved in Hammer (or '
                    'replaced) since the patches were written. Nothing was patched. Re-read the patches\' target tables from the new '
                    'map\'s digest, then update BASE in tools/deploy_tw.py.' % (h0['crc32'], h0['size'], BASE['crc32'], BASE['size']))
    os.replace(tmp, src)
    rec['input'] = dict(path=base_from, copy=rel(src), **h0)
    print('  user map = base (CRC32 %s, %d bytes); copied to %s' % (h0['crc32'], h0['size'], rel(src)))
    flags = []
    if a.user_h1: flags += ['--user-h1', a.user_h1]
    if a.user_m2: flags += ['--user-m2']
    if a.user_w5: flags += ['--user-w5']
    stages = [
        ('1_world_1', [PY, '-u', 'tools/patch_world_1.py', '--targets', os.path.join(CHAIN, '1_world_1.targets.json')] + flags, '1_world_1.targets.json'),
        ('2_models', [PY, '-u', 'tools/patch_models.py', '--no-guard'], None),
        ('3_terrain', [PY, '-u', 'tools/patch_terrain.py', '--targets', os.path.join(CHAIN, '3_terrain.targets.json')], '3_terrain.targets.json'),
        ('4_seams', [PY, '-u', 'tools/patch_seams.py', '--no-guard', '--targets', os.path.join(CHAIN, '4_seams.targets.json'),
                     '--report', os.path.join(CHAIN, '4_seams.report.json')], '4_seams.targets.json'),
        ('5_world_3', [PY, '-u', 'tools/patch_world_3.py', '--no-guard', '--targets', os.path.join(CHAIN, '5_world_3.targets.json'),
                       '--report', os.path.join(CHAIN, '5_world_3.report.json')], '5_world_3.targets.json'),
        ('6_sounds', [PY, '-u', 'tools/patch_sounds.py'], None),
        ('7_nav', [PY, '-u', 'tools/patch_nav.py', '--estimate', '--stage', os.path.join(OUT, 'addon'), '--targets', os.path.join(CHAIN, '7_nav.targets.json'),
                   '--report', os.path.join(CHAIN, '7_nav.report.json')], '7_nav.targets.json'),
    ]
    prev = dict(path=src, **h0)
    for name, cmd, tfile in stages:
        print('chain %s:' % name, flush=True)
        if name == '6_sounds':
            if not os.path.isfile(SOUNDS_TOOL):
                note = 'skipped: tools/patch_sounds.py does not exist yet (the 3 new sound entities are not in this map)'
                rec['stages'].append(dict(stage=name, skipped=note)); save()
                print('  ' + note)
                continue
            if '--targets' in open(SOUNDS_TOOL, encoding='utf-8', errors='replace').read():
                cmd = cmd + ['--targets', os.path.join(CHAIN, '6_sounds.targets.json')]
                tfile = '6_sounds.targets.json'
        t_start = time.time()
        now = hashes(prev['path'])
        if now['sha256'] != prev['sha256']:
            return stop('%s: the input %s changed after the stage before wrote it (sha256 %s, expected %s)'
                        % (name, rel(prev['path']), now['sha256'][:12], prev['sha256'][:12]))
        outp = os.path.join(CHAIN, name + '.vmap')
        if os.path.exists(outp): os.remove(outp)
        snap = snapshot(name)
        code, text, secs = run(cmd + ['--in', prev['path'], '--out', outp], os.path.join(CHAIN, name + '.log'))
        side = restore(name, snap)
        if name == '2_models':                                  # its targets file has no option: take this run's copy
            shutil.copyfile(os.path.join(SIDE, 'step6_patch_models.targets.json'), os.path.join(CHAIN, '2_models.targets.json'))
            tfile = '2_models.targets.json'
        if name == '6_sounds' and tfile is None:
            found = find_targets(outp, t_start)
            if found:
                shutil.copyfile(found, os.path.join(CHAIN, '6_sounds.targets.json')); tfile = '6_sounds.targets.json'
            else:
                rec['stages'].append(dict(stage=name, exit=code)); save()
                return stop('6_sounds: no target list found for the guard (<out>.targets.json or out/**/*sounds*targets*.json)')
        st = dict(stage=name, cmd=' '.join(cmd), input=rel(prev['path']), input_sha256=prev['sha256'], input_crc32=prev['crc32'],
                  exit=code, seconds=round(secs, 1), side=side, summary=last_line(text, r'patched map|patch_nav: \d+ NONAV|wrote '))
        rec['stages'].append(st); save()
        if code != 0 or not os.path.isfile(outp):
            return stop('%s exited %d (log out/step9/chain/%s.log): %s' % (name, code, name, (text.strip().splitlines() or [''])[-1][:300]))
        ho = hashes(outp)
        st.update(output=rel(outp), output_sha256=ho['sha256'], output_crc32=ho['crc32'], output_bytes=ho['size'])
        tpath = os.path.join(CHAIN, tfile)
        tj = json.load(open(tpath, encoding='utf-8'))
        if tj.get('input_crc32') != prev['crc32']:
            return stop('%s: its targets file says input CRC32 %s, the chain fed %s' % (name, tj.get('input_crc32'), prev['crc32']))
        gcode, gtext, gsecs = run([PY, '-u', 'tools/patch_guard.py', prev['path'], outp, tpath, '--strict', '--report',
                                   os.path.join(CHAIN, name + '.guard.json')], os.path.join(CHAIN, name + '.guard.log'))
        st['guard'] = last_line(gtext, r'^RESULT') or 'exit %d' % gcode
        st['guard_exit'] = gcode
        ref = REFS.get(name)
        if ref and not (a.user_h1 or a.user_m2 or a.user_w5) and os.path.isfile(os.path.join(OUT, ref)):
            hr = hashes(os.path.join(OUT, ref))
            st['reference'] = dict(path='out/' + ref, crc32=hr['crc32'], same=hr['sha256'] == ho['sha256'])
        save()
        print('  %s -> %s CRC32 %s, %.1f MB, %.0f s; guard: %s%s' % (rel(prev['path']), rel(outp), ho['crc32'], ho['size'] / 1048576.0, secs,
              st['guard'], ('; same bytes as ' + st['reference']['path']) if st.get('reference', {}).get('same') else
              ('; DIFFERS from ' + st['reference']['path'] + ' (CRC32 ' + st['reference']['crc32'] + ')') if st.get('reference') else ''), flush=True)
        if gcode != 0:
            return stop('%s: patch_guard FAILED (out/step9/chain/%s.guard.json)' % (name, name))
        prev = dict(path=outp, **ho)
    rec['final'] = dict(path=rel(prev['path']), sha256=prev['sha256'], crc32=prev['crc32'], size=prev['size'])
    print('chain: final map %s CRC32 %s (%d bytes)' % (rel(prev['path']), prev['crc32'], prev['size']))
    print('chain radar (step 8 staging, from the final map):', flush=True)
    ok, summ = radar(rec['final']['path'], rec)
    print('  ' + summ)
    if not ok:
        return stop('radar: %s (logs out/step9/chain/radar_*.log)' % summ)
    rec.update(ok=True, finished=datetime.datetime.now().isoformat(timespec='seconds'))
    save()
    return 0


# ---------------------------------------------------------------- (b) the merged list
def parse_list(path):
    """a step's deploy list: 'rel', 'rel   <- src (comment)', 'rel   <- "src with spaces"', 'game:rel'; a '# GAME addon' comment
    switches the lines after it to the game addon (source out/game/<rel>). A BOM is ignored."""
    rows, section = [], 'content'
    for n, raw in enumerate(open(path, encoding='utf-8-sig'), 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith('#'):
            if re.match(r'#\s*GAME addon', s, re.I):
                section = 'game'
            continue
        side = section
        if s.lower().startswith('game:'):
            side, s = 'game', s[5:].strip()
        if '<-' in s:
            r, src = (x.strip() for x in s.split('<-', 1))
            if src.startswith('"') and '"' in src[1:]:
                src = src[1:].split('"', 1)[0].replace('\\', '/')      # a quoted path may hold spaces (step 10's Steam description)
            else:
                src = src.split()[0].replace('\\', '/') if src else None   # "src (same bytes as ...)": the first word is the path
        else:
            r, src = s, None
        rows.append(dict(side=side, rel=r.replace('\\', '/'), src=src, line=n))
    return rows


def merge_lists(ch):
    final = ch['final']['path']
    rows, used, problems, notes = {}, [], [], []
    flags = ch.get('flags', {})
    optin = bool(flags.get('user_h1') or flags.get('user_m2') or flags.get('user_w5'))
    for k in STEP_LISTS:
        cands = []
        if k == 5:
            cands = [os.path.join(SIDE, 'step5_deploy_files%s.txt' % ('_optin' if optin else ''))]
        elif k in (6, 7):
            cands = [os.path.join(SIDE, 'step%d_deploy_files.txt' % k)]
        cands.append(os.path.join(OUT, 'step%d' % k, 'deploy_files%s.txt' % ('_optin' if (k == 5 and optin) else '')))
        path = next((c for c in cands if os.path.isfile(c)), None)
        if not path:
            (notes if k in (8, 10, 11, 12, 13) else problems).append('step %d deploy list not found (%s)' % (k, ', '.join(rel(c) for c in cands)))
            continue
        used.append(dict(step=k, path=rel(path)))
        for r in parse_list(path):
            if r['side'] == 'content' and r['rel'].lower() == MAP_REL:
                continue                                         # every step's map line is superseded by the chain's final map
            src = r['src'] or ('out/game/' if r['side'] == 'game' else 'out/addon/') + r['rel']
            key = (r['side'], r['rel'].lower())
            if key in rows and rows[key]['src'] != src:
                notes.append('%s: step %d (%s) replaces step %d (%s)' % (r['rel'], k, src, rows[key]['step'], rows[key]['src']))
            rows[key] = dict(side=r['side'], rel=r['rel'], src=src, step=k)
    for f, sha in (ch.get('radar', {}).get('files') or {}).items():   # the radar the chain re-made from the final map
        side, rr = ('game', f[5:]) if f.startswith('game:') else ('content', f)
        src = ('out/game/' if side == 'game' else 'out/addon/') + rr
        p = os.path.join(PROJ, *src.split('/'))
        if (side, rr.lower()) not in rows:
            rows[(side, rr.lower())] = dict(side=side, rel=rr, src=src, step=8)
            notes.append('radar file added to the list (step 8 list lacks it): %s' % f)
        if os.path.isfile(p) and sha and hashes(p)['sha256'] != sha:
            notes.append('radar file changed since the chain drew it from the final map (re-made by step 8?): %s - run --chain again' % f)
    out =[dict(side='content', rel=MAP_REL, src=final, step=9)] + sorted(rows.values(), key=lambda r: (r['side'], r['rel']))
    for r in out:
        p = os.path.join(PROJ, *r['src'].split('/'))
        r['size'] = os.path.getsize(p) if os.path.isfile(p) else None
        if r['size'] is None:
            problems.append('source missing for %s: %s' % (r['rel'], r['src']))
    return out, used, problems, notes


def write_list(rows, used, ch):
    path = os.path.join(STEP9, 'deploy_files.txt')
    lines = ['# remaster step 9: the merged deploy list (tools/deploy_tw.py), addon-relative, into content\\csgo_addons\\mg_trenchwarfare\\.',
             '# Sources relative to projects/trenchwarfare-cs2. Map = the chain\'s final vmap (base CRC32 %s -> %s, flags %s).'
             % (ch['input']['crc32'], ch['final']['crc32'], json.dumps(ch.get('flags'))),
             '# Merged from: %s' % ', '.join('step %d %s' % (u['step'], u['path']) for u in used),
             '# Never deploy this by hand: python -u tools/deploy_tw.py [--apply] (Hammer / cs2 -tools closed; it keeps a Hammer-edited map).']
    step = None
    for r in rows:
        if r['step'] != step:
            step = r['step']; lines.append('# step %d' % step)
        lines.append('%s%s   <- %s' % ('game:' if r['side'] == 'game' else '', r['rel'], r['src']))
    data = ('\n'.join(lines) + '\n').encode('utf-8')
    tmp = path + '.part'
    open(tmp, 'wb').write(data); os.replace(tmp, path)
    json.dump(dict(rows=rows, used=used), open(os.path.join(STEP9, 'deploy_files.json'), 'w', encoding='utf-8'), indent=1)
    return path


def material_check(rows):
    """every .vmat a deployed .vmdl names: in the list, in the content addon, or stock (pak01). -> (problems, notes)"""
    problems, notes = [], []
    listed = {r['rel'].lower() for r in rows}
    stock = None
    if os.path.isfile(VPK_INDEX):
        try:
            stock = pickle.load(open(VPK_INDEX, 'rb'))
        except Exception:
            stock = None
    if stock is None:
        notes.append('no pak01 index (%s; check_world writes it): stock materials not checked' % rel(VPK_INDEX))
    n = 0
    for r in rows:
        if not r['rel'].lower().endswith(('.vmdl', '.vmat')) or r['size'] is None:
            continue
        text = open(os.path.join(PROJ, *r['src'].split('/')), encoding='utf-8', errors='replace').read()
        if r['rel'].lower().endswith('.vmdl'):
            refs = sorted({m.lower() for m in re.findall(r'"(materials/[^"]+\.vmat)"', text)})
        else:
            refs = sorted({m.lower() for m in re.findall(r'"(materials/[^"]+\.(?:png|tga|psd|jpg))"', text)
                           if not m.lower().startswith('materials/default/')})
        for m in refs:
            n += 1
            if m in listed or os.path.isfile(os.path.join(CONTENT, *m.split('/'))):
                continue
            if m.endswith('.vmat') and stock is not None and (m + '_c') in stock:
                continue
            staged = os.path.isfile(os.path.join(OUT, 'addon', *m.split('/')))
            if m.endswith('.vmat') and stock is None and not staged:
                continue
            problems.append('%s names %s: %s' % (r['rel'], m, 'staged in out/addon but not in any deploy list' if staged else 'not in the list, the addon or the game'))
    return problems, notes, n


# ---------------------------------------------------------------- (c) the gate
def split_fails(s):
    """'a, b [1, 2], c' -> ['a', 'b [1, 2]', 'c'] (commas inside brackets kept)"""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '[(':
            depth += 1
        elif ch in '])':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def result_fails(text):
    line = last_line(text, r'^RESULT:')
    m = re.match(r'RESULT:\s*(clean|FAILED:\s*(.*?))\s*\(\d+(?:\.\d+)?\s*s\)\s*$', line)
    if not m:
        return None, line
    return ([] if m.group(1) == 'clean' else split_fails(m.group(2))), line


def baseline():
    """the failures accepted at step 7 (its 'after' logs), frozen into out/step9/gate_baseline.json on first use"""
    path = os.path.join(STEP9, 'gate_baseline.json')
    if os.path.isfile(path):
        return json.load(open(path, encoding='utf-8'))
    b = dict(note='failures already present after step 7 (out/step7/check_*_after.log); the deploy refuses only new ones', made=datetime.date.today().isoformat())
    for k, f in (('check_world', 'step7/check_world_after.log'), ('check_play', 'step7/check_play_after.log')):
        fails, line = result_fails(open(os.path.join(OUT, *f.split('/')), encoding='utf-8', errors='replace').read())
        b[k] = dict(source='out/' + f, result=line, fails=fails or [])
    json.dump(b, open(path, 'w', encoding='utf-8'), indent=1)
    return b


def bash():
    for p in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files\Git\usr\bin\bash.exe'):
        if os.path.isfile(p):
            return p
    return shutil.which('sh')


def gate(final):
    os.makedirs(GATE, exist_ok=True)
    base = baseline()
    fin = os.path.join(PROJ, *final.split('/'))
    stage = os.path.join(OUT, 'addon')
    js = os.path.join(PROJ, 'src', 'mg_trenchwarfare.js')
    res = dict(map=final, started=datetime.datetime.now().isoformat(timespec='seconds'), checks=[])
    for name, cmd, cwd in (
            ('check_world', [PY, '-u', 'tools/check_world.py', fin, '--stage', stage, '--json', os.path.join(GATE, 'check_world.json')], PROJ),
            ('check_play', [PY, '-u', 'tools/check_play.py', fin, '--stage', stage, '--json', os.path.join(GATE, 'check_play.json')], PROJ),
            ('check_seams', [PY, '-u', 'tools/check_seams.py', fin, '--stage', stage, '--no-sight', '--json', os.path.join(GATE, 'check_seams.json')], PROJ),
            ('check_contract', [PY, '-u', 'tools/check_contract.py', '--vmap', fin, '--stage', stage], PROJ),
            ('api_strict', [PY, 'create/test/api.py', '--strict', '--check', js], REPO),
            ('tscheck', [bash() or 'sh', 'create/test/tscheck.sh', js.replace('\\', '/')], REPO),
            ('mock_32', ['node', 'test/mock.mjs', '32', '300'], PROJ),
            ('mock_bots', ['node', 'test/mock.mjs', '16', '300', 'fill=1', 'humans=4'], PROJ),
            ('mock_scenarios', ['node', 'test/mock.mjs', '32', '150', 'scenario=all'], PROJ)):
        print('gate %s:' % name, flush=True)
        code, text, secs = run(cmd, os.path.join(GATE, name + '.log'), cwd=cwd)
        c = dict(check=name, exit=code, seconds=round(secs, 1), log='out/step9/gate/%s.log' % name)
        if name in ('check_world', 'check_play'):
            fails, line = result_fails(text)
            c['result'] = line
            if fails is None:
                c.update(ok=False, why='no RESULT line (exit %d)' % code)
            else:
                known = set(base[name]['fails'])
                new = [f for f in fails if f not in known]
                c.update(fails=fails, new=new, fixed=sorted(known - set(fails)), ok=not new)
                if new: c['why'] = 'new failures: %s' % ', '.join(new)
        elif name == 'check_seams':
            c['result'] = last_line(text, r'^RESULT')
            c['ok'] = code == 0 and c['result'].startswith('RESULT: clean')
        elif name == 'check_contract':
            c['result'] = last_line(text, r'(?i)missing|result|ok') or (text.strip().splitlines() or [''])[-1]
            c['ok'] = code == 0
        elif name == 'api_strict':
            c['result'] = last_line(text, r'problems'); c['ok'] = code == 0
        elif name == 'tscheck':
            c['result'] = last_line(text, r'tscheck|error'); c['ok'] = code == 0 and 'tscheck: OK' in text
        elif name == 'mock_scenarios':
            c['result'] = last_line(text, r'^scenarios:')
            m = re.search(r'scenarios:\s*(\d+)\s*/\s*(\d+)', c['result'])
            c['ok'] = code == 0 and bool(m) and m.group(1) == m.group(2)
        else:
            c['result'] = last_line(text, r'^RESULT'); c['ok'] = code == 0 and c['result'].startswith('RESULT: ok')
        if not c['ok'] and 'why' not in c:
            c['why'] = '%s (exit %d)' % (c.get('result') or 'no result line', code)
        res['checks'].append(c)
        print('  %s %s  %s (%.0f s)' % ('ok  ' if c['ok'] else 'FAIL', name, c.get('result', ''), secs), flush=True)
    res['ok'] = all(c['ok'] for c in res['checks'])
    res['finished'] = datetime.datetime.now().isoformat(timespec='seconds')
    json.dump(res, open(os.path.join(STEP9, 'gate.json'), 'w', encoding='utf-8'), indent=1)
    return res


# ---------------------------------------------------------------- the old route
def old_route():
    """the unpack bat applies every twN_* zip in assets\\tw that is not in its applied list: inert only while every zip is listed"""
    if not os.path.isfile(OLD_BAT_LOG):
        return 'old unpack bat: no applied list at %s (a run would extract EVERY zip in %s over the addon)' % (OLD_BAT_LOG, OLD_ZIPS)
    done = {l.strip().lower() for l in open(OLD_BAT_LOG, encoding='utf-8', errors='replace') if l.strip()}
    zips = sorted(os.path.basename(z) for z in glob.glob(os.path.join(OLD_ZIPS, 'tw*_*.zip')))
    pending = [z for z in zips if z.lower() not in done]
    if pending:
        return 'old unpack bat NOT inert: %s would be extracted over the addon by unpack_mg_trenchwarfare.bat' % ', '.join(pending)
    return 'old unpack bat inert: all %d zips in assets\\tw are in its applied list (keep that list; never add a twN zip there)' % len(zips)


def main(argv=None):
    ap = argparse.ArgumentParser(description='mg_trenchwarfare delivery: chain, merged list, gate, deploy (dry run unless --apply)')
    ap.add_argument('--chain', action='store_true', help='rebuild the final map through the patch chain first')
    # the user's decisions of 12 Nov 2026 (docstring "Opt-in flags"): --user-m2 and --user-w5 on by default, --user-h1 never
    ap.add_argument('--user-h1', choices=('unlock', 'remove'), help='NOT for this map: the sap benches are the user seam bridges (patch_world_1)')
    ap.add_argument('--user-m2', action=argparse.BooleanOptionalAction, default=True, help='delete the duplicate info_map_parameters id 7 (default on)')
    ap.add_argument('--user-w5', action=argparse.BooleanOptionalAction, default=True, help='delete bench 72, the exact copy of 71 (default on)')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--no-gate', action='store_true', help='skip the gate (dry run only)')
    ap.add_argument('--force-vmap', action='store_true', help='replace an addon map that is not the base (backed up first)')
    ap.add_argument('--allow-open', action='store_true', help='passed to deploy_addon: the person at the game said go')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    if a.apply and a.no_gate:
        print('--no-gate is for dry runs only'); return 2
    os.makedirs(STEP9, exist_ok=True)
    t0 = time.time()
    if a.chain:
        rc = chain(a)
        if rc:
            return rc
    cj = os.path.join(STEP9, 'chain.json')
    if not os.path.isfile(cj):
        print('no chain yet: run with --chain first'); return 1
    ch = json.load(open(cj, encoding='utf-8'))
    if not ch.get('ok'):
        print('the last chain did not finish (%s): run --chain again' % ch.get('stopped')); return 1
    want = dict(user_h1=a.user_h1, user_m2=bool(a.user_m2), user_w5=bool(a.user_w5))
    if not a.chain and want != ch.get('flags'):
        print('the chain was built with flags %s, this run asks for %s: run --chain with the flags' % (ch.get('flags'), want)); return 1
    fin = os.path.join(PROJ, *ch['final']['path'].split('/'))
    if not os.path.isfile(fin) or hashes(fin)['sha256'] != ch['final']['sha256']:
        print('the chain\'s final map is missing or changed since the chain ran: run --chain again'); return 1
    cur = hashes(USER_VMAP) if os.path.isfile(USER_VMAP) else None
    if cur and cur['sha256'] not in (BASE['sha256'], ch['final']['sha256']) and not last_deployed_map(cur['sha256']):
        print('the addon\'s map changed since the chain ran (CRC32 %s; base %s, chain output %s): saved in Hammer? Nothing deployed.'
              % (cur['crc32'], BASE['crc32'], ch['final']['crc32']))
        return 1
    print('chain: base CRC32 %s -> final %s (%s, %.1f MB), flags %s; addon map now: %s'
          % (ch['input']['crc32'], ch['final']['crc32'], ch['final']['path'], ch['final']['size'] / 1048576.0, ch['flags'],
             'base' if cur and cur['sha256'] == BASE['sha256'] else 'the chain output (already deployed)' if cur and cur['sha256'] == ch['final']['sha256']
             else 'the last deploy\'s output (%s)' % last_deployed_map(cur['sha256'])[0] if cur else 'missing'))
    for st in ch['stages']:
        if st.get('skipped'):
            print('  %-10s %s' % (st['stage'], st['skipped']))
            continue
        print('  %-10s %s -> CRC32 %s  guard: %s%s' % (st['stage'], st['input_crc32'], st.get('output_crc32'), st.get('guard'),
              ('  (= %s)' % st['reference']['path']) if st.get('reference', {}).get('same') else ''))

    rows, used, problems, notes = merge_lists(ch)
    lp = write_list(rows, used, ch)
    mprob, mnotes, nref = material_check(rows)
    problems += mprob; notes += mnotes
    total = sum(r['size'] or 0 for r in rows)
    print('list: %s, %d files, %.1f MB (merged from %s); %d material / texture references checked'
          % (rel(lp), len(rows), total / 1048576.0, ', '.join('step %d' % u['step'] for u in used), nref))
    for n in notes:
        print('  note: %s' % n)
    print('  %s' % old_route())
    for p in problems:
        print('  PROBLEM: %s' % p)
    if problems:
        print('STOPPED: the list has problems; nothing deployed.'); return 2

    if a.no_gate:
        print('gate: skipped (--no-gate, dry run)')
        g = None
    else:
        g = gate(ch['final']['path'])
        print('gate: %s (out/step9/gate.json)' % ('PASS' if g['ok'] else 'REFUSED: ' + '; '.join('%s: %s' % (c['check'], c.get('why')) for c in g['checks'] if not c['ok'])))
        if not g['ok'] and a.apply:
            print('Nothing deployed: the gate has new failures.'); return 6

    cmd = [PY, '-I', os.path.join(REPO, 'create', 'deploy_addon.py'), '--addon', ADDON, '--list', lp, '--list-root', PROJ,
           '--src-root', os.path.join(OUT, 'addon'), '--record-dir', os.path.join(STEP9, 'deploy'),
           '--vmap-base', BASE['sha256'], '--vmap-base', BASE['crc32'], '--strict-vmap',
           '--json', os.path.join(STEP9, 'deploy_%s.json' % ('apply' if a.apply else 'dryrun')),
           '--label', 'trench chain %s flags %s' % (ch['final']['crc32'], json.dumps(ch['flags']))]
    for flag in ('apply', 'show', 'force_vmap', 'allow_open'):
        if getattr(a, flag): cmd.append('--' + flag.replace('_', '-'))
    print('deploy: %s' % ' '.join(cmd[2:4] + cmd[4:6]), flush=True)
    r = subprocess.run(cmd, cwd=PROJ)
    if g is not None and not g['ok']:
        print('NOTE: the gate has new failures: an --apply would be refused.')
    print('deploy_tw: %.0f s' % (time.time() - t0))
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
