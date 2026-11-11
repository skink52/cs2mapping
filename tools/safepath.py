"""Path checks and change records shared by the tools that copy, overwrite or delete files in an addon.

  from safepath import addon_name, inside, is_link, sha256_file, plan_copy, apply_plan, rollback

  addon_name(name)            -> name, or ValueError: a single folder name (no separators, "..", drive, reserved Windows name)
  inside(root, path)          -> True when path is root or below it, compared as written (see "Junctions" below)
  is_link(path)               -> True for a symlink or an NTFS junction
  sha256_file(path)           -> hex digest
  write_atomic(path, data, backup=None)  -> write bytes through a temp file; untouched when the bytes are the same; optional checked backup
  plan_copy(src, dst)         -> [{rel, op: create|modify|same, src, dst, size, old_size}] for copying the tree src over dst
  plan_pairs(pairs, roots)    -> the same for explicit (source, destination) pairs, each destination inside one of roots
  apply_plan(plan, backup_dir, manifest, dry_run=False, keep=...)
                              -> the manifest dict; backs up every file it is about to overwrite, checks the backup, then copies
  rollback(manifest)          -> puts overwritten files back and removes created ones that have not changed since

Junctions: the pipeline's working root holds content\\<addon> as a junction to the real addon, which may be on another drive, so
`inside` compares the paths as written (normalised, case-insensitive on Windows) and never resolves links. A path that leaves its
root through ".." is outside; a path that passes through a junction is inside, because that is where the tool was told to work.
`plan_copy` does not descend into links in the *source* tree (a link there would copy something the tool did not make).

Stdlib only; Python 3.9+. Nothing here is specific to one PC.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import stat

_RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % i for i in range(1, 10)} | {'lpt%d' % i for i in range(1, 10)}
_BAD_CHARS = set('<>:"/\\|?*')


def addon_name(name):
    """A name safe to join onto an addons folder: exactly one path component, nothing that walks out of it."""
    if not isinstance(name, str) or not name:
        raise ValueError('empty addon name')
    if name in ('.', '..') or name != name.strip() or name.endswith('.'):
        raise ValueError('not a folder name: %r' % name)
    bad = sorted(c for c in set(name) if c in _BAD_CHARS or ord(c) < 32)
    if bad:
        raise ValueError('addon name %r has characters a folder name cannot have: %s' % (name, ' '.join(map(repr, bad))))
    if name.split('.')[0].lower() in _RESERVED:
        raise ValueError('addon name %r is a reserved Windows device name' % name)
    return name


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def inside(root, path):
    """path is root or below it, as written: '..' is folded away, links are not followed."""
    r, p = _norm(root), _norm(path)
    if r == p:
        return True
    try:
        return os.path.commonpath([r, p]) == r
    except ValueError:                      # different drives
        return False


def is_link(path):
    """symlink or NTFS junction (os.path.islink is False for a junction before Python 3.12's isjunction)"""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def write_atomic(path, data, backup=None, stamp=None):
    """Replace path with data (bytes) without ever leaving a half-written file under its name.

    -> {'op': 'same' | 'create' | 'modify', 'path', 'backup': path or None}. When the file already holds exactly these bytes it is
    not touched (its modification time stays, so nothing downstream recompiles). Otherwise the bytes go to <path>.part, are read
    back and compared, and replace the file in one step. backup='sibling' first copies an existing file to <path>.bak_<stamp>;
    backup=<folder> copies it there as <name>.bak_<stamp>; the copy is checked (sha256) before the original is replaced.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('write_atomic takes bytes')
    out = {'op': 'create', 'path': path, 'backup': None}
    if os.path.isdir(path):
        raise IsADirectoryError(path)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            old = f.read()
        if old == bytes(data):
            out['op'] = 'same'
            return out
        out['op'] = 'modify'
        if backup:
            stamp = stamp or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            bak = (path if backup == 'sibling' else os.path.join(backup, os.path.basename(path))) + '.bak_' + stamp
            n = 1
            while os.path.exists(bak):
                n += 1; bak = bak.rsplit('.bak_', 1)[0] + '.bak_%s_%d' % (stamp, n)
            os.makedirs(os.path.dirname(os.path.abspath(bak)), exist_ok=True)
            shutil.copy2(path, bak)
            if sha256_file(bak) != hashlib.sha256(old).hexdigest():
                raise OSError('backup of %s did not verify; it was not changed' % path)
            out['backup'] = bak
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.part'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    with open(tmp, 'rb') as f:
        ok = f.read() == bytes(data)
    if not ok:
        try: os.remove(tmp)
        except OSError: pass
        raise OSError('%s did not read back as written; %s was left as it was' % (tmp, path))
    os.replace(tmp, path)
    return out


def _same(a, b):
    return os.path.getsize(a) == os.path.getsize(b) and sha256_file(a) == sha256_file(b)


def plan_copy(src_root, dst_root):
    """What copying the tree src_root over dst_root would do. Reads only. Links inside src_root are not followed."""
    plan = []
    if not os.path.isdir(src_root):
        return plan
    for dp, dns, fns in os.walk(src_root):
        dns[:] = sorted(d for d in dns if not is_link(os.path.join(dp, d)))
        for fn in sorted(fns):
            src = os.path.join(dp, fn)
            if is_link(src):
                continue
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            if not inside(dst_root, dst):
                raise ValueError('%s would be written outside %s' % (rel, dst_root))
            size = os.path.getsize(src)
            if not os.path.exists(dst):
                op, old = 'create', None
            elif os.path.isdir(dst):
                raise ValueError('%s is a folder in the destination and a file in the source' % dst)
            else:
                old = os.path.getsize(dst)
                op = 'same' if _same(src, dst) else 'modify'
            plan.append({'rel': rel.replace('\\', '/'), 'op': op, 'src': src, 'dst': dst, 'size': size, 'old_size': old})
    return plan


def plan_pairs(pairs, allowed_roots):
    """The same kind of plan for explicit (source file, destination file) pairs, e.g. prep.py's manifest.json. Reads only.

    Every destination must be an absolute path inside one of allowed_roots (as written; see `inside`) and every source must be
    an existing file that is not a link: otherwise ValueError / FileNotFoundError before anything is planned, so a bad manifest
    changes nothing. Two pairs naming the same destination are an error.
    """
    plan, seen = [], set()
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or not all(isinstance(x, str) and x for x in pair):
            raise ValueError('not a [source, destination] pair: %r' % (pair,))
        src, dst = pair
        if not os.path.isabs(dst):
            raise ValueError('destination is not an absolute path: %s' % dst)
        root = next((r for r in allowed_roots if inside(r, dst) and _norm(r) != _norm(dst)), None)
        if root is None:
            raise ValueError('destination is outside the allowed folders (%s): %s' % (', '.join(allowed_roots), dst))
        if not os.path.isfile(src) or is_link(src):
            raise FileNotFoundError('source file is missing (or is a link): %s' % src)
        key = _norm(dst)
        if key in seen:
            raise ValueError('two files would be written to %s' % dst)
        seen.add(key)
        if os.path.isdir(dst):
            raise ValueError('%s is a folder; a file would be written there' % dst)
        size = os.path.getsize(src)
        if not os.path.exists(dst):
            op, old = 'create', None
        else:
            old = os.path.getsize(dst)
            op = 'same' if _same(src, dst) else 'modify'
        rel = os.path.relpath(os.path.abspath(dst), root).replace('\\', '/')
        plan.append({'rel': rel, 'op': op, 'src': src, 'dst': os.path.abspath(dst), 'size': size, 'old_size': old})
    return plan


def summarise(plan):
    """counts and byte totals for a dry-run report"""
    out = {'create': 0, 'modify': 0, 'same': 0, 'bytes_written': 0, 'bytes_backed_up': 0, 'folders': []}
    folders = set()
    for p in plan:
        out[p['op']] += 1
        if p['op'] != 'same':
            out['bytes_written'] += p['size']
            folders.add(os.path.dirname(p['dst']))
        if p['op'] == 'modify':
            out['bytes_backed_up'] += p['old_size']
    out['folders'] = sorted(folders)
    return out


def apply_plan(plan, backup_dir, manifest_path, dry_run=False, label='', stamp=None, backup_path=None):
    """Copy every create/modify entry of the plan, safely.

    Before a file is overwritten its current bytes are copied to backup_dir/<n>/<rel> and the copy is checked (size and
    sha256); only then is the new file written, through a temp file that replaces the old one. backup_path(entry) -> path
    or None lets a tool put some backups elsewhere (e.g. <map>.vmap.bak_<stamp> next to a map). The manifest (JSON, written
    after every file so a crash leaves a usable record) lists each file's before/after sha256 and its backup, which is what
    rollback() reads. dry_run changes nothing and writes nothing; the returned dict is what would be done.
    """
    stamp = stamp or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    man = {'label': label, 'stamp': stamp, 'dry_run': bool(dry_run), 'complete': False, 'backup_dir': backup_dir,
           'summary': summarise(plan), 'files': []}
    todo = [p for p in plan if p['op'] != 'same']
    if dry_run:
        man['files'] = [{'rel': p['rel'], 'op': p['op'], 'dst': p['dst'], 'size': p['size'], 'old_size': p['old_size']} for p in todo]
        return man
    need = man['summary']['bytes_written'] + man['summary']['bytes_backed_up']
    for d in {os.path.splitdrive(os.path.abspath(p['dst']))[0] for p in todo}:
        probe = d + os.sep if d else os.path.abspath(os.sep)
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            continue
        if free < need:
            raise OSError('not enough room on %s: %d MB needed, %d MB free' % (probe, need >> 20, free >> 20))

    def record():
        if manifest_path:
            os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
            tmp = manifest_path + '.part'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(man, f, indent=1)
            os.replace(tmp, manifest_path)

    for n, p in enumerate(todo):
        rec = {'rel': p['rel'], 'op': p['op'], 'dst': p['dst'], 'size': p['size'], 'before': None, 'after': None, 'backup': None}
        if p['op'] == 'modify':
            rec['before'] = sha256_file(p['dst'])
            bak = (backup_path(p) if backup_path else None) or os.path.join(backup_dir, '%04d' % n, *p['rel'].split('/'))
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(p['dst'], bak)
            if os.path.getsize(bak) != p['old_size'] or sha256_file(bak) != rec['before']:
                raise OSError('backup of %s did not verify; nothing was overwritten' % p['dst'])
            rec['backup'] = bak
        os.makedirs(os.path.dirname(p['dst']), exist_ok=True)
        tmp = p['dst'] + '.part'
        want = sha256_file(p['src'])
        shutil.copyfile(p['src'], tmp)
        rec['after'] = sha256_file(tmp)
        if rec['after'] != want or os.path.getsize(tmp) != p['size']:   # the copy on disk is not the source: leave the old file in place
            try: os.remove(tmp)
            except OSError: pass
            raise OSError('copy of %s did not verify (sha256 / size); %s was left as it was' % (p['src'], p['dst']))
        os.replace(tmp, p['dst'])
        man['files'].append(rec)
        record()
    man['complete'] = True
    record()
    return man


def rollback(manifest, dry_run=False):
    """Undo an apply_plan run from its manifest (a dict or a path).

    A modified file gets its backup back; a created file is removed. Either happens only while the file still has the
    bytes the run wrote ("after"): a file edited since is left alone and reported, because undoing it would lose that edit.
    -> {'restored': [...], 'removed': [...], 'skipped': [{'dst', 'why'}]}
    """
    if isinstance(manifest, str):
        with open(manifest, encoding='utf-8') as f:
            manifest = json.load(f)
    out = {'restored': [], 'removed': [], 'skipped': [], 'dry_run': bool(dry_run)}
    for rec in reversed(manifest.get('files', [])):
        dst = rec['dst']
        if rec.get('after') is None:
            out['skipped'].append({'dst': dst, 'why': 'the manifest has no record of what was written (dry run?)'})
            continue
        if not os.path.exists(dst):
            if rec['op'] == 'create':
                continue                                   # already gone
            now = None
        else:
            now = sha256_file(dst)
        if now is not None and now != rec['after']:
            out['skipped'].append({'dst': dst, 'why': 'changed since the run; left as it is'})
            continue
        if rec['op'] == 'create':
            if not dry_run:
                os.remove(dst)
            out['removed'].append(dst)
        else:
            bak = rec.get('backup')
            if not bak or not os.path.exists(bak):
                out['skipped'].append({'dst': dst, 'why': 'its backup is missing: %s' % bak})
                continue
            if sha256_file(bak) != rec['before']:
                out['skipped'].append({'dst': dst, 'why': 'its backup no longer matches the recorded hash'})
                continue
            if not dry_run:
                tmp = dst + '.part'
                shutil.copyfile(bak, tmp)
                os.replace(tmp, dst)
            out['restored'].append(dst)
    return out
