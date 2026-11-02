"""Live view of an autoport run: python monitor.py [--once] [--every SECONDS]   (run_autoport.bat opens it in its own window)

Shows each map's steps, what is running right now, whether it is doing anything (CPU, disk, idle time against the watchdog's limit),
the newest log lines and any watchdog kills. It only reads, so closing the window doesn't affect the run.
"""
import argparse, glob, json, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import watchdog

PORT = os.environ.get('CS2PORT', r'C:\source1\cs2port')
WORK = os.path.join(PORT, 'work')
STEPS = ['prep', 'deliver', 'import', 'root', 'stage_c', 'fixups', 'passes', 'credit', 'build', 'report']

def tail(path, n):
    try:
        with open(path, 'rb') as f:
            bom = f.read(2); f.seek(0, 2); size = f.tell(); start = max(0, size - 16384)
            wide = bom in (b'\xff\xfe', b'\xfe\xff')
            f.seek(start - start % 2 if wide else start); raw = f.read()
        text = raw.decode('utf-16-le' if bom == b'\xff\xfe' else 'utf-16-be' if wide else 'utf-8', 'replace')
    except OSError: return []
    return [l for l in text.replace('\r', '\n').split('\n') if l.strip()][-n:]

def fmt(s):
    s = int(s)
    return '%d:%02d:%02d' % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else '%d:%02d' % (s // 60, s % 60)

class Activity:
    """The watchdog's own rule, so "idle" here means what it means there."""
    def __init__(s): s.seen = {}
    def update(s, key, cpu, write, pids):
        now = time.time(); o = s.seen.get(key)
        if o is None: o = s.seen[key] = dict(cpu=cpu, write=write, pids=pids, last=now, t=now, rate=0.0, wrate=0.0, pcpu=cpu, pwrite=write)
        dt = max(now - o['t'], 0.1)
        o['rate'] = max(cpu - o['pcpu'], 0) / dt; o['wrate'] = max(write - o['pwrite'], 0) / dt
        o['pcpu'], o['pwrite'], o['t'] = cpu, write, now
        if cpu - o['cpu'] >= 1.0 or write - o['write'] >= 4096 or pids - o['pids']:
            o.update(cpu=cpu, write=write, last=now)
        o['pids'] = pids
        return o

def latest_run():
    runs = sorted(glob.glob(os.path.join(WORK, 'autoport_runs', '*')))
    return runs[-1] if runs else None

def draw(act, cols):
    out = []; run = latest_run()
    if not run: return ['No autoport run found under ' + WORK]
    procs = watchdog.snapshot()
    active = [p for p in procs if p['Name'].lower().startswith('python') and 'autoport.py' in (p['CommandLine'] or '')]
    dogs = [p for p in procs if p['Name'].lower().startswith('python') and 'watchdog.py' in (p['CommandLine'] or '')]
    # py launchers show twice (a launcher and its python): keep the outermost
    pids = {p['ProcessId'] for p in dogs}; dogs = [p for p in dogs if p['ParentProcessId'] not in pids]
    out.append('AUTOPORT  %s   run %s   %s' % (time.strftime('%H:%M:%S'), os.path.basename(run), 'RUNNING' if active else 'NOT RUNNING (finished or stopped)'))
    out.append('')
    labels = [os.path.basename(f)[:-5] for f in sorted(glob.glob(os.path.join(WORK, 'autoport_state', '*.json')), key=os.path.getmtime)]
    names = sorted({re.sub(r'_(prep|import|stage_c|stage_d|disprestore|laserhurt|glowfix|skysplit|build|gibfix|fixrefs|visfit)\.log$', '', os.path.basename(f)) for f in glob.glob(os.path.join(run, '*.log'))})
    for name in [n for n in labels if n in names or dogs and any(n in (d['CommandLine'] or '') for d in dogs)]:
        st = json.load(open(os.path.join(WORK, 'autoport_state', name + '.json')))
        marks = []
        for s in STEPS:
            if s in st['done']: marks.append(s + ' ok')
            else:
                marks.append('>' + s + '<' if active and not any(s2 not in st['done'] for s2 in STEPS[:STEPS.index(s)]) else s)
        out.append('%-28s %s' % (name, '  '.join(marks)))
    out.append('')
    newest = None
    if not dogs:
        out.append('Nothing under the watchdog right now.' + (' Autoport is between steps.' if active else ''))
    for d in dogs:
        line = d['CommandLine'] or ''
        label = re.search(r'--label\s+"?([^"]*?)"?\s+--report', line); stall = re.search(r'--stall\s+(\S+)', line); limit = re.search(r'--max\s+(\S+)', line)
        log = re.search(r'--log\s+"?(.*?\.log)"?\s+--', line)
        kids = [p for p in watchdog.tree(procs, d['ProcessId']) if p['ProcessId'] != d['ProcessId']]
        cpu = sum(p['KernelModeTime'] + p['UserModeTime'] for p in kids) / 1e7; write = sum(p['WriteTransferCount'] for p in kids)
        o = act.update(d['ProcessId'], cpu, write, {p['ProcessId'] for p in kids})
        idle = time.time() - o['last']; lim = float(stall.group(1)) if stall else 600
        health = 'WORKING' if idle < 60 else 'QUIET' if idle < lim / 2 else 'POSSIBLY HUNG'
        out.append('NOW: %s   %s   idle %s of %s before the watchdog kills it' % (label.group(1) if label else '?', health, fmt(idle), fmt(lim)))
        out.append('     CPU %.0f%% of one core   writing %.1f MB/s   hard limit %s' % (o['rate'] * 100, o['wrate'] / 1e6, fmt(float(limit.group(1))) if limit else '?'))
        for p in kids:
            if p['Name'].lower() in ('conhost.exe', 'cmd.exe', 'py.exe'): continue
            out.append('       %-24s %s' % (p['Name'], ' '.join((p['CommandLine'] or '').split())[:cols - 34]))
        if log: newest = log.group(1)
    logs = glob.glob(os.path.join(run, '*.log')) + glob.glob(os.path.join(PORT, 'logs', '*.log'))
    if logs:
        recent = max(logs, key=os.path.getmtime)
        if newest is None or os.path.getmtime(recent) > os.path.getmtime(newest) if newest and os.path.exists(newest) else True: newest = recent
    if newest:
        out += ['', 'LOG %s  (updated %s ago)' % (newest, fmt(time.time() - os.path.getmtime(newest)))] + ['  ' + l for l in tail(newest, 14)]
    kills = tail(os.path.join(run, 'watchdog.jsonl'), 5)
    out.append('')
    if kills:
        out.append('WATCHDOG KILLS:')
        for k in kills:
            try: j = json.loads(k); out.append('  %s  %s  %s after %ss' % (j['time'], j['label'], j['reason'], j['elapsed_s']))
            except ValueError: pass
    else: out.append('Watchdog kills this run: none')
    lst = os.path.join(run, 'cleanup_list.md')
    if os.path.exists(lst): out.append('Cleanup list so far: ' + lst)
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--once', action='store_true'); ap.add_argument('--every', type=float, default=3); a = ap.parse_args()
    os.system('')   # turns on ANSI codes in a Windows console
    act = Activity()
    if a.once:
        draw(act, 150); time.sleep(a.every); print('\n'.join(l[:150] for l in draw(act, 150))); return
    while True:
        cols, rows = shutil.get_terminal_size((120, 40))
        lines = [l[:cols - 1] for l in draw(act, cols)][:rows - 1]
        sys.stdout.write('\x1b[H\x1b[2J' + '\n'.join(lines)); sys.stdout.flush()
        time.sleep(a.every)

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
