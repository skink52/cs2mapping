"""copy_changed.py: copy a folder tree, writing only the files whose bytes differ from what is already there.

Why (11 Nov 2026): deploy.sh used `cp -r`, which gives every file a new date on every deploy. CS2 in tools mode (Hammer) watches the
addon's files: skink52 was playing Dunes there when a deploy ran, the game reloaded about 900 materials, models, particles and sounds
one by one (1-2 fps for half a minute) and restarted the script. A new date on the content also made every compiled file look stale,
so 289 files went through the compiler and the test server copy (tools/server_copy.py) re-copied 900 MB each time.
A file that did not change is now not touched at all.

usage:  python -I tools/copy_changed.py <src dir> <dst dir> [--glob "*.js"] [--flat]
        --glob: only files whose name matches; --flat: no subfolders (the files directly in src)
prints one line: N copied, M the same. Never deletes anything in dst.
"""
import fnmatch, os, shutil, sys


def same(a, b):
    try:
        if os.path.getsize(a) != os.path.getsize(b): return False
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            while True:
                x = fa.read(1 << 20)
                if x != fb.read(1 << 20): return False
                if not x: return True
    except OSError:
        return False


def main():
    args, glob, flat, av = [], None, False, sys.argv[1:]
    i = 0
    while i < len(av):
        if av[i] == '--glob' and i + 1 < len(av): glob = av[i + 1]; i += 2; continue
        if av[i] == '--flat': flat = True
        elif not av[i].startswith('--'): args.append(av[i])
        i += 1
    if len(args) != 2: sys.exit(__doc__)
    src, dst = args
    if not os.path.isdir(src): print('copy_changed: no %s (nothing to copy)' % src); return
    copied = kept = 0
    for root, dirs, files in os.walk(src):
        if flat: dirs[:] = []
        for f in files:
            if glob and not fnmatch.fnmatch(f, glob): continue
            s = os.path.join(root, f); t = os.path.join(dst, os.path.relpath(s, src))
            if os.path.isfile(t) and same(s, t): kept += 1; continue
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.copyfile(s, t); copied += 1
    print('copy_changed %s -> %s: %d copied, %d the same' % (src, dst, copied, kept))


if __name__ == '__main__':
    main()
