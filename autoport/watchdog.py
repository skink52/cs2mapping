"""Hang watchdog for the unattended port pipeline: a plain local process, no AI and no human needed.

  python watchdog.py [options] -- <command> [args...]    run a command and watch it (the whole process tree)
  python watchdog.py [options] --attach <text>           watch a running cmd.exe whose command line contains <text>

A tree counts as active while it uses CPU, writes to disk or pipes, starts a process, or a --watch file changes. No activity for --stall
seconds = hung. Running past --max seconds = runaway (catches a process spinning forever, which never looks idle). Either way the tree is
killed and the reason goes to --report as one JSON line. With --attach the root stays alive and only its children are killed, so a batch
file's loop carries on with its next map.

--expect and --heartbeat are for any long command a Claude session runs on this PC: say how long it should take, and get a progress line every
N seconds (elapsed against expected, CPU used, MB written, idle time, last log line). For example:
  python C:\\source1\\cs2port\\autoport\\watchdog.py --label "vis test" --expect 480 --heartbeat 60 --stall 300 --max 1800 --log out.log -- python test.py

Exit code: the command's own (or 0 when an attached root ends), 124 hung, 125 runaway, 126 --attach found nothing to watch, 127 --slow-phase over budget.
"""
import argparse, json, os, subprocess, sys, time

SNAPSHOT = ('Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine,KernelModeTime,UserModeTime,WriteTransferCount'
            ' | ConvertTo-Json -Compress')

def snapshot():
    r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', SNAPSHOT], capture_output=True, text=True, encoding='utf-8', errors='replace')
    try: return json.loads(r.stdout)
    except ValueError: return []

def tree(procs, root):
    kids = {}
    for p in procs: kids.setdefault(p['ParentProcessId'], []).append(p)
    out, todo, seen = [], [root], set()
    while todo:
        pid = todo.pop()
        if pid in seen: continue
        seen.add(pid)
        out += [p for p in procs if p['ProcessId'] == pid]
        todo += [k['ProcessId'] for k in kids.get(pid, [])]
    return out

def file_state(paths):
    state = []
    for p in paths:
        try: s = os.stat(p); state.append((p, s.st_size, s.st_mtime))
        except OSError: state.append((p, None, None))
    return state

def tail(path, n=20):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2); f.seek(max(0, f.tell() - 8192))
            return f.read().decode('utf-8', 'replace').splitlines()[-n:]
    except OSError: return []

def kill(procs, root, keep_root):
    pids = [p['ProcessId'] for p in procs if p['ParentProcessId'] == root] if keep_root else [root]
    for pid in pids:
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)

def report(path, entry):
    if not path: return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f: f.write(json.dumps(entry) + '\n')

def phase_over_budget(a):
    """--slow-phase START END SECONDS: true once the log has had an unfinished START (more STARTs than ENDs) for over SECONDS."""
    try: text = open(a.log, 'rb').read().decode('utf-8', 'replace')
    except OSError: return False
    if text.count(a.slow_phase[0]) <= text.count(a.slow_phase[1]):
        a.phase_since = None; return False
    a.phase_since = a.phase_since or time.time()
    return time.time() - a.phase_since > float(a.slow_phase[2])

def fmt(s):
    s = int(s); return '%d:%02d:%02d' % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else '%d:%02d' % (s // 60, s % 60)

def watch(root, is_alive, a):
    start = last = beat = time.time(); keep_root = bool(a.attach)
    base_cpu = base_write = first = None; pids = set(); files = file_state(a.watch); warned = False
    while is_alive():
        time.sleep(a.poll)
        procs = tree(snapshot(), root)
        if not procs:
            if is_alive(): continue
            break
        cpu = sum(p['KernelModeTime'] + p['UserModeTime'] for p in procs) / 1e7   # 100 ns units
        write = sum(p['WriteTransferCount'] for p in procs)
        first = first or (cpu, write)
        now_pids = {p['ProcessId'] for p in procs}; now_files = file_state(a.watch)
        if base_cpu is None or cpu - base_cpu >= a.min_cpu or write - base_write >= 4096 or now_pids - pids or now_files != files:
            base_cpu, base_write, last = cpu, write, time.time()
        pids, files = now_pids, now_files
        now = time.time()
        if a.heartbeat and now - beat >= a.heartbeat:   # progress a session can read from this script's own output
            beat = now; lt = [l for w in a.watch for l in tail(w, 3) if l.strip()][-1:]
            print('watchdog: %s elapsed %s%s, CPU %.0f s, wrote %.1f MB, idle %s of %s%s' % (
                a.label or 'run', fmt(now - start), ' of ~%s expected' % fmt(a.expect) if a.expect else '', cpu - first[0],
                (write - first[1]) / 1e6, fmt(now - last), fmt(a.stall), ' | ' + lt[0].strip()[:120] if lt else ''), flush=True)
        if a.expect and not warned and now - start > 2 * a.expect:
            warned = True; print('watchdog: %s has run %s, over twice the ~%s expected (still active, not killed)' % (a.label or 'run', fmt(now - start), fmt(a.expect)), flush=True)
        reason = None
        if time.time() - last > a.stall: reason, code = 'hung', 124
        elif time.time() - start > a.max: reason, code = 'runaway', 125
        elif a.slow_phase and a.log and phase_over_budget(a): reason, code = 'slow phase', 127
        if reason:
            report(a.report, {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'label': a.label, 'reason': reason, 'elapsed_s': round(time.time() - start),
                              'idle_s': round(time.time() - last), 'processes': [[p['Name'], p['CommandLine']] for p in procs],
                              'log_tail': sum((tail(w) for w in a.watch), [])})
            print('watchdog: %s after %d s, killing: %s' % (reason, time.time() - start, ', '.join(p['Name'] for p in procs)), flush=True)
            kill(procs, root, keep_root)
            if not keep_root: return code
            start = last = time.time(); base_cpu = None; a.result = code   # attached: the batch file moves on, keep watching it
    return None

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stall', type=float, default=600, help='seconds with no activity before the tree counts as hung')
    ap.add_argument('--max', type=float, default=4 * 3600, help='hard limit in seconds')
    ap.add_argument('--poll', type=float, default=15)
    ap.add_argument('--min-cpu', type=float, default=1.0, help='CPU seconds that count as activity')
    ap.add_argument('--watch', action='append', default=[], help='file whose change counts as activity (repeatable)')
    ap.add_argument('--report', help='append one JSON line per kill here')
    ap.add_argument('--label', default='')
    ap.add_argument('--log', help='send the command output here')
    ap.add_argument('--slow-phase', nargs=3, metavar=('START', 'END', 'SECONDS'), help='kill if the --log shows START with no END for this long')
    ap.add_argument('--expect', type=float, help='how long the command should take, in seconds: shown in progress lines, one warning past twice it')
    ap.add_argument('--heartbeat', type=float, help='print a progress line this often, in seconds')
    ap.add_argument('--attach')
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    a = ap.parse_args(); a.result = 0; a.phase_since = None
    if a.cmd[:1] == ['--']: a.cmd = a.cmd[1:]
    if a.expect or a.heartbeat:
        print('watchdog: %s started%s; hung after %s with no CPU, disk or log activity, killed after %s' % (
            a.label or 'run', ', expected ~%s' % fmt(a.expect) if a.expect else '', fmt(a.stall), fmt(a.max)), flush=True)
    if a.attach:
        me = os.getpid()
        roots = [p for p in snapshot() if p['Name'].lower() == 'cmd.exe' and a.attach.lower() in (p['CommandLine'] or '').lower() and p['ProcessId'] != me]
        if not roots: print('watchdog: nothing running matches', a.attach); return 126
        root = roots[0]['ProcessId']
        print('watchdog: watching cmd.exe pid', root, flush=True)
        def alive(): return any(p['ProcessId'] == root for p in snapshot())
        watch(root, alive, a)
        return a.result
    if not a.cmd: ap.error('no command given')
    out = open(a.log, 'ab') if a.log else None
    if a.log: a.watch.append(a.log)
    child = subprocess.Popen(a.cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT if out else None)
    code = watch(child.pid, lambda: child.poll() is None, a)
    return code if code is not None else child.wait()

if __name__ == '__main__':
    sys.exit(main())
