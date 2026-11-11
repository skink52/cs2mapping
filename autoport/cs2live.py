"""The running CS2, for in-game checks: find it, (only when asked) launch it, load a map, read the player, reset,
take screenshots, notice a hang, stop a CS2 we started. Stdlib only. Everything talks through vconsole.Console.

Mirrors the live-game half of Rmgs123/cs2-map-mcp (MIT; src/cs2map/game.py, system.py, gametest.py at commit 07e8ca3),
re-written for autoport with skink52's rules:
- Never steal focus. cs2-map-mcp brings the game window to the front for screenshots and real input (game.py
  views/focused, system.focus); here that only happens with focus=True, and never while someone is using the PC
  (idle_seconds() under IDLE_NEEDED). The default screenshot is the console's own `jpeg_screenshot`, no window needed.
- Never launch unless asked (launch() is only called by --launch), and then minimised and not activated.
- Never kill a CS2 we didn't start, and never one whose Hammer has unsaved edits (title ends in '*').

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)   # appended: inside tools/mcp_server.py, tools/ modules keep priority
import vconsole  # noqa: E402

CS2 = os.environ.get('CS2_ROOT') or r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
GAME_BIN = os.path.join(CS2, 'game', 'bin', 'win64')
CS2_EXE = os.path.join(GAME_BIN, 'cs2.exe')
STATE_DIR = os.environ.get('AUTOPORT_LIVE_STATE', os.path.join(os.environ.get('CS2PORT', r'C:\source1\cs2port'), 'work', 'cs2live'))
LAUNCHED = 'launched.json'
LOCK = 'cs2.lock'
LOCK_STALE = 15 * 60
IDLE_NEEDED = 30           # seconds without keyboard/mouse before focus may be taken (only with focus=True)
EYE = 64.0                 # getpos gives the eye; setpos takes the feet

# cs2-map-mcp game.py:296-297 starts Workshop Tools with exactly these (cwd game\bin\win64, DETACHED_PROCESS):
MCP_FLAGS = ['-tools', '-steam', '-retail', '-gpuraytracing', '-novid', '+sv_steamauth_enforce', '0']
# Ours on top, none tested by autoport yet: no Asset Browser window (cs2-gotchas.md Hammer line), a window instead of
# fullscreen, keep rendering and running while unfocused.
OUR_FLAGS = ['-noassetbrowser', '-windowed', '-w', '1280', '-h', '720', '+engine_no_focus_sleep', '0']

INGAME = r'CSGO_GAME_UI_STATE_INGAME'          # game.py:637 waits for "-> CSGO_GAME_UI_STATE_INGAME"
LOAD_FAILED = r"invalid map|can't find map|couldn't find map|failed to load map|map load failed|Host_Error|missing map|no such map"
TEAM_MENU = ('choose a team', 'select a team', 'team select', 'press 1 for', 'press 2 for', 'all teams are full')
FAST_START = ('mp_freezetime 0', 'mp_team_intro_time 0')   # game.py:665: 25.8 s -> 6.0 s from load to a live player
RELEASE_KEYS = ('-attack', '-attack2', '-use', '-forward', '-back', '-left', '-right', '-turnleft', '-turnright',
                '-jump', '-duck', '-reload', '-sprint')    # gametest.py:81
RESET_CVARS = ('weapon_accuracy_nospread 0', 'weapon_recoil_scale 2', 'bot_stop 0', 'bot_dont_shoot 0', 'cl_drawhud 1',
               'r_drawviewmodel 1', 'mat_fullbright 0')
_SETPOS = re.compile(r'setpos\s+([-+\d.e]+)\s+([-+\d.e]+)\s+([-+\d.e]+)\s*;\s*setang\s+([-+\d.e]+)\s+([-+\d.e]+)(?:\s+([-+\d.e]+))?', re.I)


class GameError(RuntimeError):
    pass


def _state(name):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, name)


# ------------------------------------------------------------------ processes and windows
def pid_alive(pid: int) -> bool:
    out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'], capture_output=True, text=True, errors='replace').stdout
    return str(pid) in out


def cs2_processes() -> list[dict]:
    """Every cs2.exe: pid, start, command line, mode (tools / insecure / game / unknown when Windows hides the command
    line, as it does for a CS2 started from Steam with more rights) and addon."""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'cs2.exe\'" | Select-Object ProcessId,CommandLine,'
          '@{n="Start";e={$_.CreationDate.ToString("o")}} | ConvertTo-Json -Compress')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=60)
        rows = json.loads(r.stdout) if r.stdout.strip() else []
    except (OSError, ValueError, subprocess.SubprocessError):
        rows = []
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    titles = {}
    for w in windows():
        titles.setdefault(w['pid'], []).append(w['title'])
    for p in rows:
        cmd = p.get('CommandLine') or ''
        low = cmd.lower().split()
        if '-tools' in low:
            mode = 'tools'
        elif cmd:
            mode = 'insecure' if '-insecure' in low else ('dedicated' if '-dedicated' in low else 'game')
        else:
            t = ' '.join(titles.get(p['ProcessId'], [])).lower()
            mode = 'tools' if ('hammer' in t or 'asset browser' in t or 'workshop tools' in t) else 'unknown'
        addon = None
        if '-addon' in low and low.index('-addon') + 1 < len(low):
            addon = cmd.split()[low.index('-addon') + 1]
        out.append({'pid': p['ProcessId'], 'start': p.get('Start'), 'cmdline': cmd[:300], 'mode': mode, 'addon': addon,
                    'titles': titles.get(p['ProcessId'], [])})
    return out


def _user32():
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM), wt.LPARAM]
    u.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    u.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
    u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    return u


def windows(names=('cs2.exe',)) -> list[dict]:
    """Visible titled windows of processes with these exe names: hwnd, pid, exe, title, rect, minimized."""
    if os.name != 'nt':
        return []
    import ctypes
    import ctypes.wintypes as wt
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, errors='replace').stdout
    pids = {}
    for row in out.splitlines():
        cells = [c.strip('"') for c in row.split('","')]
        if len(cells) > 1 and cells[0].lower() in names:
            pids[int(cells[1])] = cells[0].lower()
    u = _user32()
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            n = u.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, buf, n + 1)
            r = wt.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            if buf.value:
                found.append({'hwnd': int(hwnd), 'pid': pid.value, 'exe': pids[pid.value], 'title': buf.value,
                              'rect': (r.left, r.top, r.right, r.bottom), 'minimized': bool(u.IsIconic(hwnd))})
        return True

    u.EnumWindows(cb, 0)
    return found


def hammer_dirty(pid: int | None = None) -> str | None:
    """Title of a Hammer window with unsaved edits ('*'), or None. Such a CS2 is never killed or restarted."""
    for w in windows():
        t = w['title']
        if (pid is None or w['pid'] == pid) and t.rstrip().endswith('*') and ('hammer' in t.lower() or '.vmap' in t.lower()):
            return t
    return None


def hung(pid: int, probe_ms: int = 3000) -> bool:
    """Windows flags a window of the process "Not responding", or it doesn't answer a WM_NULL in probe_ms (catches a
    frozen thread Windows doesn't flag; system.py:123-143 in cs2-map-mcp)."""
    if os.name != 'nt':
        return False
    import ctypes
    u = _user32()
    hwnds = [w['hwnd'] for w in windows() if w['pid'] == pid]
    if any(u.IsWindow(h) and u.IsHungAppWindow(h) for h in hwnds):
        return True
    if not hwnds:
        return False
    res = ctypes.c_size_t()
    sent = u.SendMessageTimeoutW(hwnds[0], 0, 0, 0, 0x0002, probe_ms, ctypes.byref(res))   # WM_NULL, SMTO_ABORTIFHUNG
    return not sent and bool(u.IsWindow(hwnds[0]))


def idle_seconds() -> float | None:
    """Seconds since the last keyboard or mouse input anywhere (GetLastInputInfo)."""
    if os.name != 'nt':
        return None
    import ctypes
    import ctypes.wintypes as wt

    class LII(ctypes.Structure):
        _fields_ = [('cbSize', wt.UINT), ('dwTime', wt.DWORD)]
    info = LII(ctypes.sizeof(LII), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def foreground() -> int:
    import ctypes
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


def focus(hwnd: int, allowed: bool = False) -> bool:
    """Bring a window to the front: only with allowed=True and only when nobody has touched the PC for IDLE_NEEDED s."""
    if not allowed:
        raise GameError('refusing to take focus: pass focus=True (and only when nobody is using the PC)')
    idle = idle_seconds()
    if idle is not None and idle < IDLE_NEEDED:
        raise GameError('refusing to take focus: the keyboard or mouse was used %.0f s ago' % idle)
    import ctypes
    u = ctypes.windll.user32
    u.ShowWindow(hwnd, 4)                          # SW_SHOWNOACTIVATE, then ask for the front
    u.keybd_event(0x12, 0, 0, 0)                   # the Alt trick lets a background process switch focus
    ok = bool(u.SetForegroundWindow(hwnd))
    u.keybd_event(0x12, 0, 2, 0)
    return ok


@contextlib.contextmanager
def focused(hwnd: int, allowed: bool = False):
    """Game window in front for the block, the previous window back afterwards (cs2-map-mcp game.py:782-792)."""
    before = foreground()
    focus(hwnd, allowed)
    try:
        yield
    finally:
        if before:
            with contextlib.suppress(Exception):
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(before)


def close_vconsole_windows(confirm: bool = False) -> list[str]:
    """Valve's VConsole2 window takes CS2's only console slot. With confirm=True, ask it to close (WM_CLOSE, as its X
    button does; cs2-map-mcp vconsole.py:126-156). Never terminates anything."""
    found = [w for w in windows(('vconsole2.exe',))]
    if confirm:
        import ctypes
        for w in found:
            ctypes.windll.user32.PostMessageW(w['hwnd'], 0x0010, 0, 0)
        if found:
            time.sleep(0.5)
    return ['%s (pid %d)' % (w['title'], w['pid']) for w in found]


# ------------------------------------------------------------------ the shared lock and launched pids
@contextlib.contextmanager
def exclusive(owner: str = 'autoport', wait: float = 600):
    """One user of the game at a time across processes (cs2-map-mcp game.py:180-234). Stale when its pid is gone or it
    is older than 15 min."""
    path = _state(LOCK)
    deadline = time.monotonic() + wait
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump({'pid': os.getpid(), 'owner': owner, 'time': time.time()}, f)
            break
        except FileExistsError:
            try:
                with open(path, encoding='utf-8') as f:
                    info = json.load(f)
                stale = not pid_alive(int(info.get('pid', -1))) or time.time() - info.get('time', 0) > LOCK_STALE
            except (OSError, ValueError):
                info = {}
                try:
                    stale = time.time() - os.path.getmtime(path) > 5
                except OSError:
                    continue
            if stale:
                with contextlib.suppress(OSError):
                    os.remove(path)
                continue
            if time.monotonic() > deadline:
                raise GameError('CS2 is in use by %s; try again later' % info.get('owner'))
            time.sleep(1)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


def launched_pids() -> set[int]:
    try:
        with open(_state(LAUNCHED), encoding='utf-8') as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def _remember(pid: int):
    pids = {p for p in launched_pids() if pid_alive(p)} | {pid}
    with open(_state(LAUNCHED), 'w', encoding='utf-8') as f:
        json.dump(sorted(pids), f)


# ------------------------------------------------------------------ launching (only on request)
def launch_command(addon: str, hammer_map: str | None = None, netcon: int | None = None, windowed: bool = True,
                   width: int = 1280, height: int = 720, extra=()) -> list[str]:
    """The cs2.exe argv: cs2-map-mcp's Workshop Tools flags, then ours. `hammer_map` also opens it in Hammer
    (game.py:298-299: -tool hammer -asset maps/<map>.vmap); `netcon` adds the plain-text console port."""
    argv = [CS2_EXE, '-addon', addon] + MCP_FLAGS
    if hammer_map:
        argv += ['-tool', 'hammer', '-asset', 'maps/%s.vmap' % hammer_map]
    ours = list(OUR_FLAGS)
    if not windowed:
        ours = [f for f in ours if f not in ('-windowed', '-w', '1280', '-h', '720')]
    else:
        ours[ours.index('-w') + 1], ours[ours.index('-h') + 1] = str(width), str(height)
    argv += ours
    if netcon:
        argv += ['-netconport', str(netcon)]
    return argv + list(extra)


def launch(addon: str, wait: float = 150, port: int = vconsole.PORT, **kw) -> dict:
    """Start CS2 Workshop Tools with the addon, minimised and not activated, and wait for its console port.
    Refuses while any CS2 runs (it never takes over the user's game). Only called for an explicit --launch."""
    running = cs2_processes()
    if running:
        r = running[0]
        raise GameError('CS2 is already running (pid %d, %s mode%s): close it or use it as it is; autoport never closes '
                        'a CS2 it did not start' % (r['pid'], r['mode'], ', addon ' + r['addon'] if r['addon'] else ''))
    argv = launch_command(addon, **kw)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7                                  # SW_SHOWMINNOACTIVE: minimised, never activated (skink52)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(argv, cwd=GAME_BIN, startupinfo=si, creationflags=flags,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _remember(proc.pid)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise GameError('CS2 exited during startup (code %s)' % proc.returncode)
        if vconsole.reachable(port=port):
            time.sleep(5)                               # let the tools finish starting before the first command
            return {'state': 'started', 'pid': proc.pid, 'argv': argv}
        time.sleep(2)
    return {'state': 'started, console not reachable yet', 'pid': proc.pid, 'argv': argv}


def stop(pid: int) -> str:
    """Kill a CS2 this tool launched, unless Hammer has unsaved edits. Any other CS2 is left alone."""
    if pid not in launched_pids():
        return 'left running: pid %d was not started by autoport' % pid
    dirty = hammer_dirty(pid)
    if dirty:
        return 'left running: Hammer has unsaved edits (%s)' % dirty
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
    return 'stopped pid %d' % pid


# ------------------------------------------------------------------ images (stdlib)
def write_png(path: str, width: int, height: int, rgb: bytes):
    """A plain 8-bit RGB PNG."""
    raw = b''.join(b'\0' + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def frame_check(width: int, height: int, bgra: bytes, previous: str | None = None) -> dict:
    """Is a captured frame a real view? Same tests as cs2-map-mcp game.py:121-177 (uniform, mostly black, flat around
    the median colour, unchanged since the last view) on a sampled grid, without numpy."""
    reasons = []
    if width < 320 or height < 180:
        reasons.append('capture is smaller than a game frame')
    sx, sy = max(1, width // 160), max(1, height // 90)
    px = []
    for y in range(0, height, sy):
        row = y * width * 4
        for x in range(0, width, sx):
            i = row + x * 4
            px.append((bgra[i + 2], bgra[i + 1], bgra[i]))
    n = max(1, len(px))
    mean = sum(sum(p) for p in px) / (3 * n)
    var = 0.0
    for c in range(3):
        m = sum(p[c] for p in px) / n
        var += sum((p[c] - m) ** 2 for p in px) / n
    var /= 3
    black = sum(1 for p in px if max(p) <= 4) / n
    med = [sorted(p[c] for p in px)[n // 2] for c in range(3)]
    flat = sum(1 for p in px if all(abs(p[c] - med[c]) <= 16 for c in range(3))) / n
    sig = hashlib.sha256(bytes(v for p in px for v in p)).hexdigest()[:16]
    if var < 0.5:
        reasons.append('frame is uniform (loading or blank)')
    elif flat > 0.95:
        reasons.append('frame is nearly one colour (camera inside geometry, or loading)')
    elif black > 0.985 and mean < 5:
        reasons.append('frame is almost entirely black (loading)')
    if previous and sig == previous:
        reasons.append('frame did not change after the camera move')
    return {'ok': not reasons, 'reasons': reasons, 'mean': round(mean, 2), 'variance': round(var, 2),
            'black': round(black, 4), 'flat': round(flat, 4), 'signature': sig}


def capture_window(hwnd: int) -> tuple[int, int, bytes]:
    """The window's client area via PrintWindow(PW_CLIENTONLY | PW_RENDERFULLCONTENT): works for a covered DirectX/Vulkan
    window without bringing it forward (system.py:202-240). A minimised window has no client area."""
    import ctypes
    import ctypes.wintypes as wt
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wt.RECT()
    u.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise GameError('the CS2 window has no client area (minimised?): restore it, or use the console screenshot')
    hdc = u.GetDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    old = g.SelectObject(mem, bmp)
    try:
        if not u.PrintWindow(hwnd, mem, 3):
            raise GameError('PrintWindow failed')

        class BIH(ctypes.Structure):
            _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD),
                        ('biBitCount', wt.WORD), ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                        ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]
        bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
        return w, h, buf.raw
    finally:
        g.SelectObject(mem, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mem)
        u.ReleaseDC(hwnd, hdc)


def bgra_to_rgb(bgra: bytes) -> bytes:
    out = bytearray(len(bgra) // 4 * 3)
    out[0::3], out[1::3], out[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    return bytes(out)


# ------------------------------------------------------------------ parsing
def parse_getpos(lines) -> tuple | None:
    """(x, y, z, pitch, yaw, roll) of the eye from getpos's "setpos x y z;setang p y r"."""
    for line in lines:
        m = _SETPOS.search(line)
        if m:
            return tuple(float(v) if v is not None else 0.0 for v in m.groups())
    return None


def status_map(lines) -> str | None:
    """The loaded map from status ("loaded spawngroup(  1)  : SV:  [1: mg_x | main lump | mapload]")."""
    for line in lines:
        m = re.search(r'loaded spawngroup\(\s*\d+\)\s*:\s*SV:\s*\[\d+:\s*([^|\]]+?)\s*\|[^\]]*\bmapload\]', line, re.I)
        if m:
            name = m.group(1).strip()
            return None if name == '<empty>' else name
        m = re.search(r'^\s*map\s*[:=]\s*(\S+)', line, re.I)
        if m:
            return m.group(1)
    return None


def status_has_map(lines, name: str) -> bool:
    got = status_map(lines)
    return bool(got) and (got.lower() == name.lower() or got.lower().endswith('/' + name.lower()))


def cvar_values(lines, names) -> dict:
    """"name = value" lines, as CS2 prints a cvar read."""
    out = {}
    for n in names:
        for line in lines:
            m = re.match(r'\s*%s\s*=\s*(\S+)' % re.escape(n), line)
            if m:
                out[n] = m.group(1)
    return out


def look_at(eye, target) -> list[float]:
    """Source angles (pitch down positive, yaw) from eye to target."""
    dx, dy, dz = (target[i] - eye[i] for i in range(3))
    return [round(-math.degrees(math.atan2(dz, math.hypot(dx, dy))), 2), round(math.degrees(math.atan2(dy, dx)) % 360, 2), 0.0]


# ------------------------------------------------------------------ the game session
class Game:
    """Commands with their output, map loading, the player, screenshots, reset. Use under exclusive() when other tools
    may use the same CS2."""

    def __init__(self, console: vconsole.Console, addon: str | None = None, pid: int | None = None):
        self.c, self.addon, self.pid = console, addon, pid

    # console
    def command(self, cmd, wait: float = 1.0) -> list[str]:
        self.alive()
        return self.c.run([x for x in (cmd.splitlines() if isinstance(cmd, str) else cmd) if x.strip()], wait=wait)

    def query(self, cmd, pattern, timeout: float = 5.0, retries: int = 1) -> list[str]:
        """A command and its own output (`pattern`), re-sent after a timeout."""
        lines = []
        for _ in range(retries + 1):
            self.alive()
            ok, lines = self.c.run_until(cmd.splitlines() if isinstance(cmd, str) else cmd, pattern, timeout)
            if ok:
                return lines
        return lines

    def alive(self, wait: float = 30):
        """A hung game window gets `wait` s to recover (a map load freezes it for a while), then GameError."""
        if not self.pid:
            return
        since = time.monotonic()
        while hung(self.pid):
            if time.monotonic() - since > wait:
                raise GameError('CS2 (pid %d) has not responded for %d s' % (self.pid, wait))
            time.sleep(1)

    def status(self) -> list[str]:
        return self.query('status', r'#end|loaded spawngroup|mapload', timeout=3.0, retries=1)

    def getpos(self):
        return parse_getpos(self.query('getpos', r'setpos', timeout=3.0, retries=1))

    def cvars(self, names) -> dict:
        """Current values of these cvars (CS2 prints "name = value" for a bare cvar)."""
        names = list(names)
        found = {}
        for _ in range(2):
            self.alive()
            _, lines = self.c.run_until(names, lambda body: len(cvar_values(body, names)) == len(names), timeout=3.0)
            found = cvar_values(lines, names)
            if len(found) == len(names):
                break
        return found

    # map
    def load_map(self, name: str, addon: str | None = None, plain: bool = False, timeout: float = 120) -> dict:
        """Load an addon map and wait until a player is in game. `map <name>` loads without addons ("invalid map name"
        for an addon map, game.py:630), so addon maps go through `map_workshop <addon> <map>` as Hammer's Run does;
        plain=True sends `map <name>` (stock maps, or a session started with -addon if that works there).
        Returns {ok, reason, seconds, lines (all console lines printed during the load)}."""
        addon = addon or self.addon
        if not plain and not addon:
            raise GameError('an addon map needs the addon name (map_workshop <addon> <map>)')
        cmd = 'map %s' % name if plain else 'map_workshop %s %s' % (addon, name)
        t0 = time.monotonic()
        at = self.c.cursor()
        self.c.send(cmd)
        out = {'ok': False, 'reason': None, 'command': cmd}
        try:
            hit = self.c.wait_for(r'(?i)%s|%s' % (INGAME, LOAD_FAILED), timeout, since=at)
        except vconsole.ConsoleError as e:
            out.update(reason='console closed during the load: %s' % e, seconds=round(time.monotonic() - t0, 1),
                       lines=self.c.texts(at), crashed=True)
            return out
        try:
            if hit is None or not re.search(INGAME, hit.text):
                out.update(reason=('load failed: ' + hit.text) if hit else 'no in-game state after %g s' % timeout)
            else:
                left = max(5.0, timeout - (time.monotonic() - t0))
                deadline = time.monotonic() + left
                st = []
                while time.monotonic() < deadline:
                    st = self.status()
                    if status_has_map(st, name):
                        out['ok'] = True
                        break
                    time.sleep(0.5)
                if not out['ok']:
                    out['reason'] = 'in game, but status does not name %s: %s' % (name, ' | '.join(st[-3:]))
            if out['ok']:
                out['freezetime'] = self.fast_start()
                out['player'] = self.wait_for_player(max(5.0, timeout - (time.monotonic() - t0)))
        except vconsole.ConsoleError as e:              # the game went away after reaching the in-game state
            out.update(ok=False, reason='console closed after the load: %s' % e, crashed=True)
        out.update(seconds=round(time.monotonic() - t0, 1), lines=self.c.texts(at))
        return out

    def fast_start(self):
        """No freeze time or team intro on the loaded map (game.py:661-679); returns mp_freezetime read back."""
        self.command(list(FAST_START), wait=0.2)
        return self.cvars(['mp_freezetime']).get('mp_freezetime')

    def wait_for_player(self, timeout: float = 45) -> bool:
        """The UI says in game before the loading screen is gone: wait until getpos answers and no team menu shows,
        joining a team if needed (game.py:693-705)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            lines = self.query('getpos', r'setpos', timeout=3.0, retries=0)
            text = '\n'.join(lines).lower()
            if parse_getpos(lines) and not any(m in text for m in TEAM_MENU):
                return True
            self.command(['engine_no_focus_sleep 0', 'sv_cheats 1', 'jointeam 2 1'], wait=0.4)
            time.sleep(1.0)
        return False

    # scenario hygiene
    def release_keys(self):
        self.command(['sv_cheats 1'] + list(RELEASE_KEYS), wait=0.2)

    def reset(self) -> dict:
        """Undo what tests change, in one call (gametest.py:96-129): keys released, noclip off, HUD and viewmodel on,
        default accuracy and recoil, no bots, round restarted, then wait for a live player."""
        self.release_keys()
        self.command(['noclip 0', 'bot_kick', 'bot_quota 0'] + list(RESET_CVARS) + ['mp_restartgame 1'], wait=0.5)
        time.sleep(3.5)
        return {'ok': self.wait_for_player(40), 'done': ['keys released', 'noclip off', 'bots removed', 'cvars default', 'mp_restartgame 1']}

    # screenshots
    def console_screenshot(self, name: str = 'autoport', quality: int = 90, timeout: float = 15) -> str | None:
        """`jpeg_screenshot <name> <quality>`: CS2 writes the frame itself and prints "Screenshot written to: <path>"
        a frame later (cs2-map-mcp marks.py:9-10; Workshop Tools writes into <game addon>/screenshots/). No focus
        needed; whether an unfocused game renders a fresh frame depends on engine_no_focus_sleep 0 (untested here)."""
        at = self.c.cursor()
        self.c.send('jpeg_screenshot %s %d' % (name, quality))
        hit = self.c.wait_for(r'Screenshot written to:\s*(.+)', timeout, since=at)
        if not hit:
            return None
        path = re.search(r'Screenshot written to:\s*(.+)', hit.text).group(1).strip().strip('"')
        if not os.path.isabs(path) and self.addon:
            path = os.path.join(CS2, 'game', 'csgo_addons', self.addon, path)
        return path

    def game_window(self) -> dict:
        wins = [w for w in windows() if (self.pid is None or w['pid'] == self.pid) and w['title'].startswith('Counter-Strike 2')]
        if not wins:
            raise GameError('no "Counter-Strike 2" game window')
        return wins[0]

    def window_screenshot(self, path: str, previous: str | None = None, allow_focus: bool = False) -> dict:
        """PNG of the game window via PrintWindow, checked with frame_check. Focus is taken only with allow_focus."""
        w = self.game_window()
        if allow_focus:
            with focused(w['hwnd'], True):
                time.sleep(0.5)
                width, height, bgra = capture_window(w['hwnd'])
        else:
            width, height, bgra = capture_window(w['hwnd'])
        check = frame_check(width, height, bgra, previous)
        write_png(path, width, height, bgra_to_rgb(bgra))
        return {'path': path, 'size': [width, height], 'check': check}

    def place(self, pos=None, ang=None, settle: float = 0.6, tries: int = 3) -> tuple:
        """noclip camera at pos (feet) looking along ang, repeated until getpos confirms within 2 units / 2 degrees
        (game.py:814-839: enabling noclip in the same tick as setpos lets the camera fall)."""
        self.command(['sv_cheats 1', 'noclip 1'], wait=0.1)
        time.sleep(0.4)
        got = None
        for _ in range(tries):
            cmds = []
            if pos is not None:
                cmds.append('setpos %g %g %g' % tuple(float(v) for v in pos[:3]))
            if ang is not None:
                cmds.append('setang %g %g %g' % tuple(float(v) for v in (list(ang) + [0, 0, 0])[:3]))
            if cmds:
                self.command(cmds, wait=0.3)
            time.sleep(settle)
            got = self.getpos()
            if not got:
                raise GameError('getpos returned nothing after setpos/setang')
            okp = pos is None or all(abs(got[i] - (pos[i] + (EYE if i == 2 else 0))) <= 2 for i in range(3))
            oka = ang is None or all(abs((got[3 + i] - float(ang[i]) + 180) % 360 - 180) <= 2 for i in range(2))
            if okp and oka:
                return got
        raise GameError('camera did not reach %s / %s: eye at %s' % (pos, ang, got and got[:5]))

    def views(self, shots: list[dict], folder: str, method: str = 'console', hide_hud: bool = True,
              allow_focus: bool = False) -> dict:
        """For each {name, pos?, ang?, cmd?, wait?}: move the noclip camera, run cmd, wait, capture. method 'console'
        (jpeg_screenshot, no focus) or 'window' (PrintWindow PNG with a freshness challenge: a frame at yaw+17 first,
        so an unchanged picture proves a stale capture, game.py:961-1017)."""
        done, rejected = [], []
        base = ['engine_no_focus_sleep 0', 'sv_cheats 1'] + (['cl_drawhud 0', 'r_drawviewmodel 0'] if hide_hud else [])
        self.command(base, wait=0.3)
        try:
            for i, v in enumerate(shots):
                name = re.sub(r'[^\w.-]', '_', str(v.get('name') or 'view%d' % (i + 1)))
                if v.get('pos') is not None or v.get('ang') is not None:
                    self.place(v.get('pos'), v.get('ang'))
                printed = self.command(v['cmd'], wait=float(v.get('wait', 1.0))) if v.get('cmd') else None
                if not v.get('cmd') and v.get('wait'):
                    time.sleep(float(v['wait']))
                if method == 'console':
                    path = self.console_screenshot('autoport_' + name)
                    if path:
                        done.append({'name': name, 'path': path, **({'console': printed[-8:]} if printed else {})})
                    else:
                        rejected.append({'name': name, 'reasons': ['no "Screenshot written to" line from jpeg_screenshot']})
                    continue
                ang = v.get('ang')
                previous = None
                if ang is not None:
                    self.command('setang %g %g %g' % (float(ang[0]), float(ang[1]) + 17, 0), wait=0.3)
                    previous = self.window_screenshot(os.path.join(folder, '_fresh.png'), allow_focus=allow_focus)['check']['signature']
                    self.place(None, ang)
                shot = None
                for _ in range(4):
                    shot = self.window_screenshot(os.path.join(folder, name + '.png'), previous, allow_focus)
                    if shot['check']['ok']:
                        break
                    time.sleep(1.0)
                entry = {'name': name, **shot, **({'console': printed[-8:]} if printed else {})}
                (done if shot['check']['ok'] else rejected).append(entry)
        finally:
            if hide_hud:
                with contextlib.suppress(Exception):
                    self.command(['cl_drawhud 1', 'r_drawviewmodel 1'], wait=0.1)
            with contextlib.suppress(OSError):
                os.remove(os.path.join(folder, '_fresh.png'))
        return {'shots': done, 'rejected': rejected}


def connect(port: int = vconsole.PORT, netcon: int | None = None, addon: str | None = None) -> Game:
    """A Game on a fresh console connection; pid from the one CS2 running, if there is exactly one."""
    con = vconsole.Console(port=netcon or port, netcon=bool(netcon)).connect()
    if con.ping(15) is None:                            # also lets the replayed backlog (and ADON) arrive first
        held = vconsole.holders(con.port)
        con.close()
        raise GameError('connected to the console, but CS2 did not answer in 15 s%s' % (
            ': another client holds it (pid %s; close the VConsole2 window or that tool)' % ', '.join(held) if held else
            ' (a map load or a hang?)'))
    procs = cs2_processes() if os.name == 'nt' else []
    g = Game(con, addon or getattr(con.wire, 'addon', None), procs[0]['pid'] if len(procs) == 1 else None)
    return g
