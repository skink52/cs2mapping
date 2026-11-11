"""Tiered, compressed map backups with deduplicated snapshots of the files that build the map.

  python mapbackup.py save <map.vmap> [--store DIR] [--kind manual] [--pin LABEL] [--sources DIR ...]
  python mapbackup.py scan <content addon folder> [--store DIR] [--settle 120]       back up every maps/*.vmap changed since its newest copy
  python mapbackup.py list <map name | map.vmap> [--store DIR] [--json]
  python mapbackup.py restore <map name> <stamp | latest> [--to FILE] [--store DIR] [--force]
  python mapbackup.py pin|unpin <map name> <stamp> [--label TEXT] [--store DIR]
  python mapbackup.py trim [<map name>] [--store DIR] [--dry-run]
  python mapbackup.py sources <stamp> --to DIR [--store DIR]                         restore a sources snapshot into an empty folder
  python mapbackup.py verify [<map name>] [--store DIR]                              unpack every copy and compare it with its recorded sha256

Store (--store, else env CS2MAP_BACKUPS, else C:\\source1\\cs2port\\map_backups): best on another disk or a synced folder.
  maps/<map>/<stamp>.vmap.xz + <stamp>.json      {kind, size, sha256, packed, source path, mtime, sources snapshot, pin}
  sources/objects/<sha[:2]>/<sha>.xz             each source file's content, stored once however many snapshots use it
  sources/snapshots/<stamp>.json                 {roots: {label: folder}, files: {"label/rel": [sha, size, mtime_ns]}}
Tiers per map (trimmed after every save): the newest KEEP_LAST copies, the oldest copy of each of the last HOURLY hours, DAILY days and
WEEKLY weeks (the map as it was before that period's work), and pinned copies forever. A save whose bytes equal the newest copy is skipped.
A snapshot stays while a kept copy refers to it or it is among the newest SOURCE_KEEP; objects nothing refers to are removed.
Restoring over an existing map first saves that map (kind "before-restore"), so a restore can itself be undone; --to writes elsewhere.
Hammer must not have the map open with unsaved edits when you restore over it (Hammer would overwrite it on its next save).
Every copy is read back and unpacked right after it is written, and again before a restore: a copy whose bytes do not give the recorded
sha256 is an error (a failed save leaves no copy behind; a restore of a damaged copy changes nothing). `verify` checks the whole store.

Ported from backups.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): same tiers, pins and source snapshots, fresh code;
lzma instead of zstd (Python 3.13's standard library), no background worker (a save is synchronous, about 1 s per 30 MB).
"""
import argparse, datetime as dt, hashlib, json, lzma, os, shutil, sys, time

KEEP_LAST, HOURLY, DAILY, WEEKLY, SOURCE_KEEP = 3, 24, 14, 8, 5
STAMP = '%Y%m%d-%H%M%S-%f'
SKIP_DIRS = {'__pycache__', '.git', '.svn', 'node_modules'}
SKIP_EXT = ('.vmap', '.vmap_c', '.vpk', '.pyc', '.tmp', '.bak')
SOURCE_MAX = 256 * 1024 * 1024


def default_store():
    return os.environ.get('CS2MAP_BACKUPS') or r'C:\source1\cs2port\map_backups'


def _sha(data): return hashlib.sha256(data).hexdigest()


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.part'
    with open(tmp, 'wb') as f: f.write(data)
    os.replace(tmp, path)


def _json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f: return json.load(f)
    except (OSError, ValueError):
        return default


def _now(): return dt.datetime.now()
def _when(stamp): return dt.datetime.strptime(stamp, STAMP)
def map_name(p): return os.path.splitext(os.path.basename(p))[0] if p.lower().endswith('.vmap') else p


class Store:
    def __init__(s, root=None):
        s.root = os.path.abspath(root or default_store())

    def map_dir(s, name): return os.path.join(s.root, 'maps', map_name(name))

    # ---------------------------------------------------------------- map copies
    def entries(s, name):
        d = s.map_dir(name)
        if not os.path.isdir(d): return []
        out = []
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                meta = _json(os.path.join(d, f), {})
                meta['stamp'] = f[:-5]; meta['file'] = os.path.join(d, f[:-5] + '.vmap.xz')
                if os.path.exists(meta['file']): out.append(meta)
        return out                                  # oldest first (stamps sort by time)

    def read(s, entry, check=True):
        """the copy's bytes; with check, an OSError when they do not match the sha256 recorded at save time"""
        try:
            with open(entry['file'], 'rb') as f: data = lzma.decompress(f.read())
        except lzma.LZMAError as ex:
            raise OSError('backup %s is damaged (%s)' % (entry['file'], ex))
        if check and entry.get('sha256') and _sha(data) != entry['sha256']:
            raise OSError('backup %s does not match its recorded sha256' % entry['file'])
        return data

    def verify(s, name=None):
        """unpack every copy (of one map, or of all) and compare with its sha256 -> {'checked': n, 'bad': [{map, stamp, problem}]}"""
        out = {'checked': 0, 'bad': []}
        for m in ([map_name(name)] if name else s.maps()):
            for e in s.entries(m):
                out['checked'] += 1
                try: s.read(e)
                except OSError as ex: out['bad'].append({'map': m, 'stamp': e['stamp'], 'problem': str(ex)})
        return out

    def save(s, vmap, kind='manual', pin=None, sources=(), now=None):
        """-> the new entry, or None when the newest copy already has these bytes"""
        with open(vmap, 'rb') as f: data = f.read()
        sha = _sha(data)
        old = s.entries(vmap)
        if old and old[-1].get('sha256') == sha:
            if pin: s.pin(vmap, old[-1]['stamp'], pin)
            return None
        stamp = (now or _now()).strftime(STAMP)
        while os.path.exists(os.path.join(s.map_dir(vmap), stamp + '.json')):     # two saves in one microsecond (tests)
            stamp = (_when(stamp) + dt.timedelta(microseconds=1)).strftime(STAMP)
        packed = lzma.compress(data, preset=6)
        d = s.map_dir(vmap)
        xz = os.path.join(d, stamp + '.vmap.xz')
        _write(xz, packed)
        try: s.read({'file': xz, 'sha256': sha})           # read the copy back from disk before trusting it
        except OSError:
            try: os.remove(xz)
            except OSError: pass
            raise
        meta = {'kind': kind, 'size': len(data), 'packed': len(packed), 'sha256': sha, 'source': os.path.abspath(vmap),
                'mtime': os.path.getmtime(vmap), 'pin': pin, 'sources': s.snapshot(sources, now) if sources else None}
        _write(os.path.join(d, stamp + '.json'), json.dumps(meta, indent=1).encode())
        s.trim(vmap, now)
        meta['stamp'] = stamp
        return meta

    def find(s, name, stamp):
        es = s.entries(name)
        if not es: raise FileNotFoundError('no backups of %s in %s' % (map_name(name), s.root))
        if stamp in (None, 'latest'): return es[-1]
        hit = [e for e in es if e['stamp'].startswith(stamp)]
        if len(hit) != 1: raise KeyError('%d backups of %s match %r' % (len(hit), map_name(name), stamp))
        return hit[0]

    def restore(s, name, stamp='latest', to=None, force=False):
        e = s.find(name, stamp)
        dest = to or e['source']
        data = s.read(e)                                   # checked against its sha256 before anything is touched
        if os.path.exists(dest):
            if to and not force: raise FileExistsError('%s exists (use --force)' % dest)
            s.save(dest, kind='before-restore')            # the restore can be undone
        _write(dest, data)
        return {'restored': e['stamp'], 'to': dest, 'size': e['size']}

    def pin(s, name, stamp, label='pinned'):
        e = s.find(name, stamp)
        p = os.path.join(s.map_dir(name), e['stamp'] + '.json')
        meta = _json(p, {}); meta['pin'] = label
        _write(p, json.dumps(meta, indent=1).encode())

    def unpin(s, name, stamp):
        e = s.find(name, stamp)
        p = os.path.join(s.map_dir(name), e['stamp'] + '.json')
        meta = _json(p, {}); meta['pin'] = None
        _write(p, json.dumps(meta, indent=1).encode())

    # ---------------------------------------------------------------- tiers
    @staticmethod
    def keep_set(stamps, now, keep_last=KEEP_LAST, hourly=HOURLY, daily=DAILY, weekly=WEEKLY):
        """which stamps the tiers keep (pins are added by the caller)"""
        keep = set(stamps[-keep_last:]) if keep_last else set()
        for span, count, key in ((dt.timedelta(hours=1), hourly, lambda t: t.strftime('%Y%m%d%H')),
                                 (dt.timedelta(days=1), daily, lambda t: t.strftime('%Y%m%d')),
                                 (dt.timedelta(weeks=1), weekly, lambda t: t.strftime('%G%V'))):
            first = {}
            for st in stamps:                               # oldest first: the first seen in a bucket is its oldest
                t = _when(st)
                if now - t <= span * count: first.setdefault(key(t), st)
            keep |= set(first.values())
        return keep

    def trim(s, name, now=None, dry_run=False):
        es = s.entries(name)
        keep = s.keep_set([e['stamp'] for e in es], now or _now()) | {e['stamp'] for e in es if e.get('pin')}
        gone = [e for e in es if e['stamp'] not in keep]
        if not dry_run:
            for e in gone:
                for p in (e['file'], os.path.join(s.map_dir(name), e['stamp'] + '.json')):
                    try: os.remove(p)
                    except OSError: pass
            s.trim_sources()
        return [e['stamp'] for e in gone]

    def maps(s):
        d = os.path.join(s.root, 'maps')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    # ---------------------------------------------------------------- sources
    def snapshot(s, roots, now=None):
        """content-addressed snapshot of the given folders (map files and caches left out); -> its stamp"""
        files, labels = {}, {}
        for root in roots:
            root = os.path.abspath(root); label = os.path.basename(root.rstrip('\\/')) or 'root'
            while label in labels: label += '_'
            labels[label] = root
            for dp, dns, fns in os.walk(root):
                dns[:] = [d for d in dns if d not in SKIP_DIRS]
                for fn in fns:
                    p = os.path.join(dp, fn)
                    if fn.lower().endswith(SKIP_EXT) or os.path.getsize(p) > SOURCE_MAX: continue
                    with open(p, 'rb') as f: data = f.read()
                    sha = _sha(data)
                    obj = os.path.join(s.root, 'sources', 'objects', sha[:2], sha + '.xz')
                    if not os.path.exists(obj): _write(obj, lzma.compress(data, preset=3))
                    files[label + '/' + os.path.relpath(p, root).replace('\\', '/')] = [sha, len(data), os.stat(p).st_mtime_ns]
        stamp = (now or _now()).strftime(STAMP)
        _write(os.path.join(s.root, 'sources', 'snapshots', stamp + '.json'), json.dumps({'roots': labels, 'files': files}, indent=0).encode())
        return stamp

    def snapshots(s):
        d = os.path.join(s.root, 'sources', 'snapshots')
        return sorted(f[:-5] for f in os.listdir(d) if f.endswith('.json')) if os.path.isdir(d) else []

    def restore_sources(s, stamp, dest):
        snap = _json(os.path.join(s.root, 'sources', 'snapshots', stamp + '.json'))
        if snap is None: raise FileNotFoundError('no sources snapshot %s' % stamp)
        if os.path.isdir(dest) and os.listdir(dest): raise FileExistsError('%s is not empty' % dest)
        for rel, (sha, size, _) in snap['files'].items():
            with open(os.path.join(s.root, 'sources', 'objects', sha[:2], sha + '.xz'), 'rb') as f:
                _write(os.path.join(dest, *rel.split('/')), lzma.decompress(f.read()))
        return {'files': len(snap['files']), 'to': dest}

    def trim_sources(s):
        snaps = s.snapshots()
        used = {e.get('sources') for m in s.maps() for e in s.entries(m)} | set(snaps[-SOURCE_KEEP:])
        for st in snaps:
            if st not in used: os.remove(os.path.join(s.root, 'sources', 'snapshots', st + '.json'))
        live = set()
        for st in s.snapshots():
            snap = _json(os.path.join(s.root, 'sources', 'snapshots', st + '.json'), {'files': {}})
            live |= {v[0] for v in snap['files'].values()}
        od = os.path.join(s.root, 'sources', 'objects')
        if os.path.isdir(od):
            for sub in os.listdir(od):
                for f in os.listdir(os.path.join(od, sub)):
                    if f[:-3] not in live: os.remove(os.path.join(od, sub, f))

    # ---------------------------------------------------------------- whole addon
    def scan(s, addon_content, settle=120.0, sources=True, now=None):
        """copy every maps/*.vmap (one level) whose bytes changed since its newest backup and that was last written settle s ago"""
        done = []
        maps_dir = os.path.join(addon_content, 'maps')
        if not os.path.isdir(maps_dir): return done
        snap = None
        for f in sorted(os.listdir(maps_dir)):
            p = os.path.join(maps_dir, f)
            if not f.lower().endswith('.vmap') or time.time() - os.path.getmtime(p) < settle: continue
            es = s.entries(p)
            if es and es[-1].get('mtime') == os.path.getmtime(p): continue
            if sources and snap is None: snap = s.snapshot([addon_content], now)
            e = s.save(p, kind='scan', now=now)
            if e:
                if snap:
                    jp = os.path.join(s.map_dir(p), e['stamp'] + '.json'); meta = _json(jp, {}); meta['sources'] = snap
                    _write(jp, json.dumps(meta, indent=1).encode())
                done.append({'map': f, 'stamp': e['stamp'], 'size': e['size'], 'packed': e['packed']})
        return done


def main(argv=None):
    ap = argparse.ArgumentParser(description='Tiered map backups')
    ap.add_argument('cmd', choices=['save', 'scan', 'list', 'restore', 'pin', 'unpin', 'trim', 'sources', 'verify'])
    ap.add_argument('args', nargs='*'); ap.add_argument('--store'); ap.add_argument('--kind', default='manual'); ap.add_argument('--pin')
    ap.add_argument('--label', default='pinned'); ap.add_argument('--sources', nargs='*', default=[]); ap.add_argument('--to')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--json', action='store_true')
    ap.add_argument('--settle', type=float, default=120.0)
    a = ap.parse_args(argv)
    st = Store(a.store)
    try:
        if a.cmd == 'save': out = st.save(a.args[0], a.kind, a.pin, a.sources) or {'skipped': 'same bytes as the newest copy'}
        elif a.cmd == 'scan': out = st.scan(a.args[0], a.settle)
        elif a.cmd == 'list': out = st.entries(a.args[0])
        elif a.cmd == 'restore': out = st.restore(a.args[0], a.args[1] if len(a.args) > 1 else 'latest', a.to, a.force)
        elif a.cmd == 'pin': st.pin(a.args[0], a.args[1], a.label); out = {'pinned': a.args[1]}
        elif a.cmd == 'unpin': st.unpin(a.args[0], a.args[1]); out = {'unpinned': a.args[1]}
        elif a.cmd == 'verify': out = st.verify(a.args[0] if a.args else None)
        elif a.cmd == 'trim':
            out = {m: st.trim(m, dry_run=a.dry_run) for m in ([a.args[0]] if a.args else st.maps())}
        else:
            if not a.to: raise ValueError('sources needs --to DIR')
            out = st.restore_sources(a.args[0], a.to)
    except (OSError, KeyError, ValueError, IndexError) as ex:
        print('mapbackup: %s' % ex, file=sys.stderr); return 2
    if a.cmd == 'verify':
        print(json.dumps(out, indent=1)); return 1 if out['bad'] else 0
    if a.json or a.cmd != 'list': print(json.dumps(out, indent=1, default=str))
    else:
        for e in out: print('%s  %-14s %8.1f MB -> %6.1f MB%s' % (e['stamp'], e['kind'], e['size'] / 1e6, e['packed'] / 1e6, ('  [pin: %s]' % e['pin']) if e.get('pin') else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
