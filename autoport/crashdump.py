"""Why did CS2 die? Find the newest minidump CS2 wrote and read the essentials from it. Stdlib only, no symbols.

  python crashdump.py                 the newest dump: exception, module + offset, process id and start, console tail
  python crashdump.py --since 600     only a dump written in the last 600 s (exit 1 if none)
  python crashdump.py <file.mdmp>     a given dump

CS2 writes `cs2_<yyyy>_<mmdd>_<hhmmss>_<n>_{crash,error,accessviolation}.mdmp` into game\\bin\\win64. Read from
Microsoft's MINIDUMP layout: the header (MDMP, stream count at 8, directory at 12), the module list (stream 4), the
exception (stream 6) and MiscInfo (stream 15: process id and start time, so a dump can be matched to the CS2 that a
check was watching). The console tail is the readable runs in the dump that look like errors, the same triage idea as
Rmgs123/cs2-map-mcp (MIT, src/cs2map/crashdump.py and gametest.py), re-written here.

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import struct
import sys
import time

CS2 = os.environ.get('CS2_ROOT') or r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
GAME_BIN = os.path.join(CS2, 'game', 'bin', 'win64')
PATTERNS = ('cs2_*_crash.mdmp', 'cs2_*_error.mdmp', 'cs2_*_accessviolation.mdmp', 'cs2_*.mdmp')
STREAM_MODULES, STREAM_EXCEPTION, STREAM_MISC = 4, 6, 15

EXCEPTIONS = {
    0xC0000005: 'ACCESS_VIOLATION', 0xC00000FD: 'STACK_OVERFLOW', 0xC0000094: 'INT_DIVIDE_BY_ZERO',
    0xC000001D: 'ILLEGAL_INSTRUCTION', 0xC0000409: 'STACK_BUFFER_OVERRUN (fast fail)', 0x80000003: 'BREAKPOINT (assert or fatal error)',
    0xC0000374: 'HEAP_CORRUPTION', 0xE06D7363: 'C++ exception', 0xC0000017: 'NO_MEMORY', 0x40000015: 'FATAL_APP_EXIT',
    0xC0000420: 'ASSERTION_FAILURE', 0xC000041D: 'FATAL_USER_CALLBACK_EXCEPTION',
}
# (exception, module or None) -> one line of advice
HINTS = {
    ('STACK_OVERFLOW', 'server.dll'): 'stack overflow in the game server: a map script or an entity I/O loop recursed',
    ('ACCESS_VIOLATION', 'server.dll'): 'access violation in the game server: an entity input or script call it could not handle',
    ('ACCESS_VIOLATION', 'client.dll'): 'access violation in the client: often a bad model, particle or material reference',
    ('ACCESS_VIOLATION', 'rendersystemvulkan.dll'): 'crash in the renderer: GPU driver, a broken texture or shader',
    ('ACCESS_VIOLATION', 'rendersystemdx11.dll'): 'crash in the renderer: GPU driver, a broken texture or shader',
    ('BREAKPOINT (assert or fatal error)', None): 'the engine stopped on a fatal error: read the FATAL ERROR line in the console tail',
    ('NO_MEMORY', None): 'out of memory: a huge map or too many things open at once (Hammer plus the game)',
}

_RUN = re.compile(rb'[ -~]{20,400}')
_SIGNAL = re.compile(rb'FATAL ERROR|Error loading|Failed to load|Uncaught|Exception|Script error|[Aa]ssert|Host_Error|'
                     rb'Missing|missing|ERROR|Error:|failed')
_NOISE = re.compile(rb'Cause the engine|Show entity|hltv memory|jpeg_screenshot|C_Network|CNetwork|client!|Annotation|'
                    rb'FrameSync|userlocal|SFUI_|AppID|cuda|mat_assert|\.mdmp|prototype|%[sdif]|\bconvar\b|FCVAR_|'
                    rb'Usage:|usage:|Break in debugger|^Format:')
_STAMP = re.compile(r'^\s*(\d+)\((\d+\.\d+)\):\s*')


def dumps(folder: str | None = None) -> list[str]:
    """CS2 minidumps in the folder (default GAME_BIN), newest first."""
    folder = folder or GAME_BIN
    found = {p for pat in PATTERNS for p in glob.glob(os.path.join(folder, pat))}
    return sorted(found, key=os.path.getmtime, reverse=True)


def newest(folder: str | None = None, since: float | None = None) -> str | None:
    """The newest dump, or None; with `since` (a time.time()), only one written at or after it."""
    found = dumps(folder)
    if not found:
        return None
    if since is not None and os.path.getmtime(found[0]) < since - 1:
        return None
    return found[0]


def _utf16(data: bytes, rva: int) -> str:
    n = struct.unpack_from('<I', data, rva)[0]
    return data[rva + 4:rva + 4 + n].decode('utf-16-le', 'replace')


def parse(path: str) -> dict:
    """{file, exception: {code, name, address, thread}, module: {name, offset}, modules, pid, process_start}"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'MDMP':
        raise ValueError('not a minidump: ' + path)
    count, directory = struct.unpack_from('<II', data, 8)
    streams = {}
    for i in range(count):
        kind, size, rva = struct.unpack_from('<III', data, directory + i * 12)
        streams.setdefault(kind, (size, rva))
    out = {'file': os.path.basename(path), 'exception': None, 'module': None, 'modules': 0, 'pid': None, 'process_start': None}
    modules = []
    if STREAM_MODULES in streams:
        rva = streams[STREAM_MODULES][1]
        n = struct.unpack_from('<I', data, rva)[0]
        for i in range(n):
            base, size, _, _, name_rva = struct.unpack_from('<QIIII', data, rva + 4 + i * 108)   # MINIDUMP_MODULE is 108 bytes
            modules.append((base, size, _utf16(data, name_rva)))
        out['modules'] = n
    if STREAM_EXCEPTION in streams:
        rva = streams[STREAM_EXCEPTION][1]
        thread = struct.unpack_from('<I', data, rva)[0]
        code, flags, record, address = struct.unpack_from('<IIQQ', data, rva + 8)
        out['exception'] = {'code': '0x%08X' % code, 'name': EXCEPTIONS.get(code, 'unknown'), 'address': '0x%X' % address, 'thread': thread}
        for base, size, name in modules:
            if base <= address < base + size:
                out['module'] = {'name': os.path.basename(name.replace('/', '\\')), 'offset': '0x%X' % (address - base)}
                break
    if STREAM_MISC in streams:
        size, rva = streams[STREAM_MISC]
        if size >= 16:
            _, flags1, pid, created = struct.unpack_from('<IIII', data, rva)
            if flags1 & 1:
                out['pid'] = pid
            if flags1 & 2:
                out['process_start'] = created
    return out


def console_tail(path: str, lines: int = 40) -> list[str]:
    """Readable runs in the dump that look like console errors, oldest first ("<frame>(<seconds>):" stamps sort them)."""
    with open(path, 'rb') as f:
        data = f.read()
    seen, stamped, other = set(), [], []
    for m in _RUN.finditer(data):
        raw = m.group(0)
        if _NOISE.search(raw) or not _SIGNAL.search(raw):
            continue
        text = raw.decode('ascii', 'replace').strip()
        if text in seen:
            continue
        seen.add(text)
        hit = _STAMP.match(text)
        if hit:
            stamped.append((float(hit.group(2)), text[hit.end():]))
        else:
            other.append(text)
    stamped.sort(key=lambda x: x[0])
    tail = ['%.1fs %s' % x for x in stamped]
    return (tail[-max(lines - len(other[-6:]), 1):] + other[-6:])[-lines:]


def report(path: str, lines: int = 40) -> dict:
    info = parse(path)
    exc = info['exception'] or {}
    module = (info['module'] or {}).get('name')
    mtime = os.path.getmtime(path)
    hint = HINTS.get((exc.get('name'), (module or '').lower())) or HINTS.get((exc.get('name'), None))
    return {**info, 'path': path, 'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime)),
            'age_seconds': round(time.time() - mtime), 'summary': '%s %s in %s' % (
                exc.get('name', 'no exception record'), exc.get('code', ''),
                '%s+%s' % (module, info['module']['offset']) if module else 'an unknown module'),
            'hint': hint, 'console_tail': console_tail(path, lines)}


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dump', nargs='?')
    ap.add_argument('--folder', default=GAME_BIN)
    ap.add_argument('--since', type=float, help='only a dump written in the last N seconds')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    path = a.dump or newest(a.folder, time.time() - a.since if a.since else None)
    if not path:
        print('No CS2 minidump%s in %s.' % (' from the last %g s' % a.since if a.since else '', a.folder)); return 1
    r = report(path)
    if a.json:
        print(json.dumps(r, indent=1)); return 0
    print('%s  (%s, %d min ago, pid %s)' % (r['file'], r['time'], r['age_seconds'] // 60, r['pid']))
    print('  ' + r['summary'])
    if r['hint']:
        print('  hint: ' + r['hint'])
    for line in r['console_tail'][-12:]:
        print('  | ' + line[:160])
    return 0


if __name__ == '__main__':
    sys.exit(main())
