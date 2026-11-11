"""Run the pipeline in a local workspace on the PC instead of the cloud one (Claude Code on the PC).

  python pclocal.py deliver <manifest.json> [...] [--force] [--dry-run]   copy prep.py's (staged, PC path) pairs to the PC paths
  python pclocal.py root <addon> [<root>]                     build the stage C working root for an addon
  python pclocal.py apply <addon> [<root>] [--dry-run]        copy stage C's output back to the addon (only changed files, each backed up first)
  python pclocal.py rollback <addon> [<root>] [--dry-run]     undo the newest apply of that addon from its manifest (or: rollback <manifest.json>,
                                                              which is also how a deliver is undone: rollback <root>\\out\\deliver_<stamp>.json)

apply backs up every file it overwrites before touching it and checks the copy (size and sha256): a .vmap as <map>.vmap.bak_<stamp> next to
it (as before), anything else under <root>\\apply_backups\\<addon>\\<stamp>\\. It records the run in <root>\\out\\<addon>_apply_<stamp>.json (each
file's sha256 before and after, and its backup). --dry-run lists what would be created and overwritten, the folders touched and the bytes
needed, and changes nothing. rollback restores the overwritten files and removes the created ones, but leaves any file that was edited
after the apply (it says which). The addon name must be a plain folder name.

<root> defaults to C:\\source1\\cs2port\\work. Layout: content\\<addon> (a junction to the real addon: remove it with rmdir, never delete through it),
source1\\maps\\<addon>.vmf, vpk\\cs2_pak01_dir.vpk + csgo_pak01_dir.vpk, embedded\\<addon> (unpacked from maps\\<addon>_embedded*.zip), out\\.
"""
import datetime, filecmp, glob, json, os, shutil, subprocess, sys, zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import safepath

CS2 = os.environ.get('CS2_ROOT') or r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
S1 = os.environ.get('CS2MAP_SOURCE1') or r'C:\source1'
DEFAULT_ROOT = os.path.join(S1, 'cs2port', 'work')

def deliver(manifests, force, dry_run=False, root=None):
    """Copy prep.py's (staged, PC path) pairs. Nothing is copied unless every pair is valid: each destination must be inside the CS2
    install or the Source 1 workspace (CS2_ROOT / CS2MAP_SOURCE1), each source must exist. Files that already exist and differ stop
    the run unless force; with force each is backed up (checked by sha256) under <root>\\deliver_backups\\<stamp>\\ first. Every copy
    goes through a temp file and is checked against the source's sha256. The run is recorded in <root>\\out\\deliver_<stamp>.json,
    which `pclocal.py rollback <that file>` undoes. -> the manifest dict"""
    root = root or DEFAULT_ROOT
    pairs = []
    for m in manifests:
        try:
            with open(m, encoding='utf-8') as f: got = json.load(f)
        except (OSError, ValueError) as ex: sys.exit('nothing copied: cannot read manifest %s (%s)' % (m, ex))
        if not isinstance(got, list): sys.exit('nothing copied: %s is not a list of [staged, PC path] pairs' % m)
        pairs += got
    try: plan = safepath.plan_pairs(pairs, [CS2, S1])
    except (ValueError, OSError) as ex: sys.exit('nothing copied: %s' % ex)
    clash = [p['dst'] for p in plan if p['op'] == 'modify']
    if clash and not force and not dry_run:
        sys.exit('nothing copied: these already exist and differ (--force to overwrite):\n  ' + '\n  '.join(clash))
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); n = 1
    manifest = os.path.join(root, 'out', 'deliver_%s.json' % stamp)
    while os.path.exists(manifest):
        n += 1; manifest = os.path.join(root, 'out', 'deliver_%s_%d.json' % (stamp, n))
    if not any(p['op'] != 'same' for p in plan): manifest = None
    try:
        man = safepath.apply_plan(plan, os.path.join(root, 'deliver_backups', stamp + ('_%d' % n if n > 1 else '')), manifest,
                                  dry_run=dry_run, label='pclocal deliver', stamp=stamp)
    except OSError as ex:
        sys.exit('delivery stopped: %s%s' % (ex, ('\n  undo what was copied: python pclocal.py rollback "%s"' % manifest) if manifest and os.path.exists(manifest) else ''))
    sm = man['summary']
    if dry_run:
        print('DRY RUN, nothing changed. deliver would create %d and overwrite %d files (%d already identical): %.1f MB to write, %.1f MB of backups%s'
              % (sm['create'], sm['modify'], sm['same'], sm['bytes_written'] / 1e6, sm['bytes_backed_up'] / 1e6,
                 '' if force or not clash else '\n  %d existing files differ: the real run stops unless --force' % len(clash)))
        for f in man['files']: print('  %-6s %s' % (f['op'], f['dst']))
    else:
        print('%d files delivered' % len(pairs))
    return man

def copy_if_changed(src, dst):
    if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst) and os.path.getmtime(src) <= os.path.getmtime(dst): return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)

def root(addon, r):
    link = os.path.join(r, 'content', addon); real = os.path.join(CS2, 'content', 'csgo_addons', addon)
    if not os.path.isdir(real): sys.exit('no addon content at ' + real)
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if not os.path.exists(link):
        subprocess.run(['cmd', '/c', 'mklink', '/J', link, real], check=True, stdout=subprocess.DEVNULL)
    copy_if_changed(os.path.join(S1, 'maps', addon + '.vmf'), os.path.join(r, 'source1', 'maps', addon + '.vmf'))
    copy_if_changed(os.path.join(CS2, 'game', 'csgo', 'pak01_dir.vpk'), os.path.join(r, 'vpk', 'cs2_pak01_dir.vpk'))
    copy_if_changed(os.path.join(S1, 'pak01_dir.vpk'), os.path.join(r, 'vpk', 'csgo_pak01_dir.vpk'))
    emb = os.path.join(r, 'embedded', addon); n = 0
    for z in glob.glob(os.path.join(S1, 'maps', addon + '_embedded*.zip')):
        with zipfile.ZipFile(z) as f:
            f.extractall(emb); n += len(f.namelist())
    # the importer turns spaces in material paths into underscores, so the vmap asks for names the BSP never packed
    # (mg_arcs_multigames: 49 of 52 "missing" textures were packed as "materials/MISC/128x128 arena screenie.vmt"): add underscore copies
    alias = 0
    for dp, _, fs in os.walk(emb):
        for fn in fs:
            rel = os.path.relpath(os.path.join(dp, fn), emb)
            if ' ' not in rel: continue
            dst = os.path.join(emb, rel.replace(' ', '_'))
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(os.path.join(dp, fn), dst); alias += 1
    print('root %s ready for %s (%d embedded files%s)' % (r, addon, n, ', %d underscore copies of names with spaces' % alias if alias else ''))

def _sides(addon, r):
    return (('content', os.path.join(r, 'out', addon), os.path.join(CS2, 'content', 'csgo_addons', addon)),
            ('game', os.path.join(r, 'out', addon + '_game'), os.path.join(CS2, 'game', 'csgo_addons', addon)))

def apply(addon, r, dry_run=False):
    """-> the manifest dict (see safepath.apply_plan); prints one summary line, or the full list on a dry run"""
    addon = safepath.addon_name(addon)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    plan = []
    for side, src_root, dst_root in _sides(addon, r):
        for p in safepath.plan_copy(src_root, dst_root):
            p['rel'] = side + '/' + p['rel']; plan.append(p)
    vmap_bak = lambda p: p['dst'] + '.bak_' + stamp if p['dst'].lower().endswith('.vmap') else None
    manifest = os.path.join(r, 'out', '%s_apply_%s.json' % (addon, stamp)); n = 1
    while os.path.exists(manifest):                    # two applies in one second: never replace an earlier run's record
        n += 1; manifest = os.path.join(r, 'out', '%s_apply_%s_%d.json' % (addon, stamp, n))
    if not any(p['op'] != 'same' for p in plan): manifest = None      # nothing to copy: nothing to record
    man = safepath.apply_plan(plan, os.path.join(r, 'apply_backups', addon, stamp + ('_%d' % n if n > 1 else '')), manifest,
                              dry_run=dry_run, label='pclocal apply ' + addon, stamp=stamp, backup_path=vmap_bak)
    sm = man['summary']
    if dry_run:
        print('DRY RUN, nothing changed. apply %s would create %d and overwrite %d files (%d unchanged): %.1f MB to write, %.1f MB of backups'
              % (addon, sm['create'], sm['modify'], sm['same'], sm['bytes_written'] / 1e6, sm['bytes_backed_up'] / 1e6))
        for f in man['files']: print('  %-6s %s' % (f['op'], f['dst']))
        for d in sm['folders']: print('  folder %s' % d)
    else:
        print('%d changed files copied back for %s' % (sm['create'] + sm['modify'], addon))
    return man

def rollback(target, r, dry_run=False):
    """target: an addon name (its newest apply manifest under <root>\\out) or a manifest path"""
    if target.lower().endswith('.json') and os.path.isfile(target): path = target
    else:
        found = sorted(glob.glob(os.path.join(r, 'out', safepath.addon_name(target) + '_apply_*.json')))
        if not found: sys.exit('no apply manifest for %s under %s' % (target, os.path.join(r, 'out')))
        path = found[-1]
    out = safepath.rollback(path, dry_run=dry_run)
    print('%srollback of %s: %d restored, %d created files removed, %d left alone'
          % ('DRY RUN, nothing changed. ' if dry_run else '', os.path.basename(path), len(out['restored']), len(out['removed']), len(out['skipped'])))
    for sk in out['skipped']: print('  left: %s (%s)' % (sk['dst'], sk['why']))
    return out

if __name__ == '__main__':
    args = sys.argv[1:]; force = '--force' in args; dry = '--dry-run' in args; args = [a for a in args if a not in ('--force', '--dry-run')]
    if len(args) < 2: sys.exit(__doc__)
    cmd = args[0]
    if cmd == 'deliver': deliver(args[1:], force, dry_run=dry)
    elif cmd == 'root': root(args[1], args[2] if len(args) > 2 else DEFAULT_ROOT)
    elif cmd == 'apply': apply(args[1], args[2] if len(args) > 2 else DEFAULT_ROOT, dry_run=dry)
    elif cmd == 'rollback': rollback(args[1], args[2] if len(args) > 2 else DEFAULT_ROOT, dry_run=dry)
    else: sys.exit(__doc__)
