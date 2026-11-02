"""Paths, the step list and the dated log shared by autoport, its review commands and the monitor."""
import json, os, sys, time, traceback, uuid

PORT = os.environ.get('CS2PORT', r'C:\source1\cs2port')
TOOLS = os.path.join(PORT, 'tools')
WORK = os.path.join(PORT, 'work')
S1 = r'C:\source1'
REPO = os.environ.get('CS2MAPPING', r'C:\source1\cs2mapping')
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(WORK, 'autoport_state')
INBOX = os.path.join(STATE, 'inbox')
LOGS = os.path.join(PORT, 'logs', 'autoport')
LOCK = os.path.join(STATE, 'worker.lock')
CLEANUP = os.path.join(LOGS, 'cleanup_list.md')

PREP_STEPS = ['prep', 'deliver', 'import', 'root', 'stage_c', 'fixups', 'passes', 'profile', 'credit', 'audit']
BUILD_STEPS = ['build', 'report', 'description']
STEPS = PREP_STEPS + BUILD_STEPS

# error/missing/unknown/io hold a map back from the build until someone clears them; the rest only go on the list
HOLD_KINDS = ('error', 'missing', 'unknown', 'io')
ALL_KINDS = HOLD_KINDS + ('minor', 'review', 'playtest')
OLD_KINDS = {'blocker': 'error', 'agent': 'review'}

def read(path):
    try: raw = open(path, 'rb').read()
    except OSError: return ''
    return raw.decode('utf-16', 'replace') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')

def today_log(): return os.path.join(LOGS, time.strftime('%Y-%m-%d') + '.log')

def log(kind, addon, step, text):
    """One line in today's log. Anything missing, wrong or unknown ends up here, whichever map or step it came from."""
    os.makedirs(LOGS, exist_ok=True)
    with open(today_log(), 'a', encoding='utf-8') as f:
        f.write('%s %-8s %-28s %-8s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), kind.upper(), addon or '-', step or '-', text))

def install_excepthook():
    """A crash outside any map's steps still reaches the dated log."""
    def hook(typ, val, tb):
        log('error', None, 'crash', ''.join(traceback.format_exception(typ, val, tb)))
        sys.__excepthook__(typ, val, tb)
    sys.excepthook = hook

def state_path(addon): return os.path.join(STATE, addon + '.json')

def load_state(addon):
    st = json.load(open(state_path(addon), encoding='utf-8'))
    for i in st.get('issues', []):
        i['kind'] = OLD_KINDS.get(i['kind'], i['kind']); i.setdefault('step', ''); i.setdefault('cleared', '')
    st.setdefault('status', 'built' if 'build' in st.get('done', []) else 'held')
    st.setdefault('failed', None); st.setdefault('profile', ''); st.setdefault('force', False)
    return st

def all_addons():
    try: names = os.listdir(STATE)
    except OSError: return []
    return sorted(f[:-5] for f in names if f.endswith('.json'))

def open_issues(st, kinds=ALL_KINDS): return [i for i in st['issues'] if i['kind'] in kinds and not i['cleared']]

def pid_alive(pid):
    import subprocess
    out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'], capture_output=True, text=True, errors='replace').stdout
    return str(pid) in out

def worker_pid():
    """The running worker's pid, or None. A lock left by a dead process doesn't count."""
    try: pid = int(open(LOCK).read().strip())
    except (OSError, ValueError): return None
    return pid if pid_alive(pid) else None

def take_lock():
    """Only one worker at a time, even when two start in the same instant: creating the file is the atomic part."""
    os.makedirs(STATE, exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd); return
        except FileExistsError:
            time.sleep(1)   # the other one may not have written its pid yet
            other = worker_pid()
            if other: sys.exit('Another worker is already running (pid %d).' % other)
            try: os.remove(LOCK)   # left by a dead process, or the other worker just finished
            except FileNotFoundError: pass
    sys.exit('Could not take the worker lock: ' + LOCK)

def post_command(cmd):
    """Hand the worker a command. Only the worker writes map state, so nothing can overwrite it while a step is running."""
    os.makedirs(INBOX, exist_ok=True)
    name = '%d_%s.json' % (time.time() * 1000, uuid.uuid4().hex)   # several commands can land in the same millisecond
    tmp = os.path.join(INBOX, name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(cmd, f)
    os.replace(tmp, os.path.join(INBOX, name))

def start_worker():
    """Its own console, so closing anything else doesn't stop it, but minimised and never activated: it must not pull the user out of a
    fullscreen game (skink52)."""
    import subprocess
    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 7   # SW_SHOWMINNOACTIVE
    subprocess.Popen([sys.executable, os.path.join(HERE, 'autoport.py'), 'serve'], creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si, cwd=PORT)
