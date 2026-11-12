"""Nav-only test compile of a map copy (Nav 2, 12 Nov 2026): the NAVGEN area count in minutes instead of the 50-min final.

usage: python -u tools/navtest.py <map.vmap> <tag> [--full] [--threads N]
  copies <map.vmap> to content\\csgo_addons\\mg_trenchwarfare\\maps\\_navtest\\<tag>.vmap (a new file of its own; the addon's maps are not touched),
  runs resourcecompiler -world -phys -nav with its own -outroot (out/nav2/outroot; never the game addon), from C:\\source1\\cs2port,
  log out/nav2/<tag>.log (utf-8). Without --full the compiler is stopped once NAVGEN's IslandRemoval line gives the area count (the
  "CSGO Compute AI Data" pass after it takes minutes per thousand areas). With --full it runs to the end and the .nav is extracted
  from the built vpk to out/nav2/<tag>.nav. The test vmap and the outroot are removed at the end.
Refuses while another resourcecompiler.exe runs (one compile at a time).
"""
import os, re, shutil, subprocess, sys, time, json
HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'nav2')  # outputs stay in out/nav2
os.makedirs(HERE, exist_ok=True)
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
RC = os.path.join(CS2, 'game', 'bin', 'win64', 'resourcecompiler.exe')
TESTDIR = os.path.join(CS2, 'content', 'csgo_addons', 'mg_trenchwarfare', 'maps', '_navtest')
OUTROOT = os.path.join(HERE, 'outroot')
RX = re.compile(r'IslandRemoval took [\d.]+ sec, produced (\d+) polys')


def others():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq resourcecompiler.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if 'resourcecompiler' in l.lower()]


def main():
    src, tag = sys.argv[1], sys.argv[2]
    full = '--full' in sys.argv
    th = sys.argv[sys.argv.index('--threads') + 1] if '--threads' in sys.argv else str(max(1, (os.cpu_count() or 4) - 2))
    if not re.fullmatch(r'[a-z0-9_]+', tag): sys.exit('tag: lower-case letters, digits, _')
    while others():
        print('navtest: another resourcecompiler is running; waiting 30 s', flush=True); time.sleep(30)
    os.makedirs(TESTDIR, exist_ok=True)
    vm = os.path.join(TESTDIR, tag + '.vmap')
    shutil.copyfile(src, vm)
    if os.path.isdir(OUTROOT): shutil.rmtree(OUTROOT)
    os.makedirs(OUTROOT)
    log = os.path.join(HERE, tag + '.log')
    argv = [RC, '-threads', th, '-fshallow', '-maxtextureres', '256', '-quiet', '-unbufferedio', '-i', vm.replace('\\', '/').lower(),
            '-noassert', '-world', '-phys', '-nav', '-breakpad', '-nop4', '-outroot', OUTROOT]
    t0 = time.time(); count = None; nav_done = None
    print('navtest: %s -> %s (%s)' % (src, vm, 'full' if full else 'stop at the area count'), flush=True)
    p = subprocess.Popen(argv, cwd=r'C:\source1\cs2port', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with open(log, 'w', encoding='utf-8') as f:
        for raw in p.stdout:
            line = raw.decode('utf-8', 'replace').rstrip()
            if '\x00' in line: line = raw.decode('utf-16-le', 'replace').rstrip()
            f.write(line + '\n'); f.flush()
            if 'NAVGEN' in line or 'Compute' in line or 'Building' in line or 'nav areas' in line:
                print('  %6.0f s  %s' % (time.time() - t0, line), flush=True)
            m = RX.search(line)
            if m:
                count = int(m.group(1)); nav_done = time.time() - t0
                if not full:
                    subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True); break
    p.wait()
    res = dict(tag=tag, src=os.path.abspath(src), areas=count, seconds_to_count=round(nav_done or 0), seconds=round(time.time() - t0), exit=p.returncode)
    if full and count is not None:
        sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', 'tools')))
        import vpk
        built = os.path.join(OUTROOT, 'csgo_addons', 'mg_trenchwarfare', 'maps', '_navtest', tag + '.vpk')
        if os.path.isfile(built):
            v = vpk.VPK(built)
            key = [k for k in v.files if k.endswith('.nav')]
            if key:
                open(os.path.join(HERE, tag + '.nav'), 'wb').write(v.read(key[0], {})); res['nav'] = os.path.join(HERE, tag + '.nav')
    # clean up: our test vmap (and its folder if empty) and the outroot
    try: os.remove(vm)
    except OSError as e: print('navtest: could not remove', vm, e)
    left = os.listdir(TESTDIR) if os.path.isdir(TESTDIR) else []
    res['testdir_left'] = left
    if not left: os.rmdir(TESTDIR)
    shutil.rmtree(OUTROOT, ignore_errors=True)
    print('navtest: %s' % json.dumps(res), flush=True)
    with open(os.path.join(HERE, 'results.jsonl'), 'a') as f: f.write(json.dumps(res) + '\n')
    return 0 if count is not None else 1


if __name__ == '__main__':
    sys.exit(main())
