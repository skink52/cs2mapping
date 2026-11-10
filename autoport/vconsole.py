"""A client for CS2's console over TCP: send console commands to a running CS2 and read what it prints. Stdlib only.

  python vconsole.py ping                         is the console there, and does it answer? (one echo round trip)
  python vconsole.py send "status" [--wait 1.5]   run commands (one per line or separated by ;;) and print their output
  python vconsole.py tail [--seconds 30] [--grep REGEX] [--backlog]   print console lines as they arrive
  python vconsole.py wait REGEX [--timeout 60] [--send CMD]           exit 0 when a line matches, 1 on timeout
  common options: --port 29000 (VConsole2) or --netcon PORT (plain text, a client started with -netconport PORT)

Two transports:
- VConsole2 (default, TCP 29000): opened by CS2 Workshop Tools (`-tools`), the channel Valve's VConsole2 window uses.
  CS2 serves one console client at a time: a second connection is accepted but never answered, so close the
  VConsole2 window (or another tool holding the port) first, and don't keep the connection open between jobs.
- netcon (`-netconport N` on any client or server): plain text lines both ways; colour codes are stripped and nothing
  is replayed on connect (docs/reference/cs2-gotchas.md, slime-mg-gm 6 Nov 2026).

Map script output (`Instance.Msg`, `echo` from a map) reaches a live console client even though it is missing from
console.log (-condebug), so this is how autoport reads it.

VConsole2 framing, learned from Rmgs123/cs2-map-mcp (MIT, src/cs2map/vconsole.py, commit 07e8ca3) and re-written here:
every packet is a 12-byte big-endian header -- 4-byte ASCII type, uint32 version (0x00D40000), uint16 total length
(header included), uint16 handle -- then the payload. Commands go out as CMND with the UTF-8 command and a NUL. Printed
lines come in as PRNT: the payload's first 28 bytes are a fixed header (bytes 16-20: milliseconds since the game
started; bytes 0-4 look like a channel id, unverified) and the text follows, NUL-terminated. Other types (AINF, CHAN,
ADON, CVRS...) are skipped. On connect CS2 replays its console buffer (several MB, ~2 s), so command output is framed
between two unique `echo` markers rather than by waiting for quiet: CS2 runs commands in order, so everything the
commands print lies between the markers. Server-side output (status, script messages) can land a frame after the end
marker: wait for its own text (run_until) or give `wait` seconds.

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import struct
import sys
import threading
import time
import uuid

PORT = 29000
VERSION = 0x00D40000
HEADER = struct.Struct('>4sIHH')
PRNT_TEXT = 28            # PRNT payload bytes before the text
MAX_PACKET = 0xFFFF       # the length field is 16 bits


class ConsoleError(RuntimeError):
    pass


# ------------------------------------------------------------------ framing
def packet(kind: bytes, payload: bytes, version: int = VERSION, handle: int = 0) -> bytes:
    if len(kind) != 4:
        raise ValueError('packet type must be 4 bytes')
    if HEADER.size + len(payload) > MAX_PACKET:
        raise ValueError('packet too long for the 16-bit length field (%d bytes)' % (HEADER.size + len(payload)))
    return HEADER.pack(kind, version, HEADER.size + len(payload), handle) + payload


def command_packet(cmd: str) -> bytes:
    return packet(b'CMND', cmd.encode('utf-8') + b'\0')


def prnt_packet(text: str, ms: int = 0, channel: int = 0) -> bytes:
    """What CS2 sends for a printed line (used by the tests' fake server)."""
    head = struct.pack('>I12xI8x', channel, ms)
    return packet(b'PRNT', head + text.encode('utf-8') + b'\0')


def _plausible_type(t: bytes) -> bool:
    return len(t) == 4 and all(65 <= c <= 90 or 48 <= c <= 57 for c in t)


class Line:
    """One printed line: text, ms since the game started (VConsole2 only), channel id and its name (from CHAN)."""
    __slots__ = ('text', 'ms', 'channel', 'chan', 'received')

    def __init__(self, text, ms=0, channel=0, received=None, chan=''):
        self.text, self.ms, self.channel, self.chan = text, ms, channel, chan
        self.received = time.time() if received is None else received

    def __repr__(self):
        return 'Line(%r, ms=%d)' % (self.text, self.ms)


class Parser:
    """Turns a byte stream into packets. A packet split across reads waits for the rest.

    Only headers carrying VERSION are trusted. CS2's CVRB packet (the cvar list it sends on connect) has another
    version (0x0002000B) and is bigger than 64 KB, so its 16-bit length wraps (seen 10 Nov 2026: field 34292, real size
    34292 + 11 x 65536). After such a packet, or any bytes that aren't a header, the parser skips to the next
    VERSION header. `types` counts the packets seen, `skipped` the bytes passed over."""

    VER = struct.pack('>I', VERSION)

    def __init__(self):
        self.buf = bytearray()
        self.types: dict[str, int] = {}
        self.skipped = 0

    def feed(self, data: bytes) -> list[tuple[bytes, int, bytes]]:
        self.buf += data
        out, pos, n = [], 0, len(self.buf)
        while n - pos >= HEADER.size:
            kind, ver, length, handle = HEADER.unpack_from(self.buf, pos)
            if not _plausible_type(kind) or length < HEADER.size or ver != VERSION:
                if _plausible_type(kind) and length >= HEADER.size:
                    k = kind.decode('ascii')
                    self.types[k] = self.types.get(k, 0) + 1
                nxt = self._resync(pos + 1)
                self.skipped += nxt - pos
                pos = nxt
                continue
            if n - pos < length:
                break
            out.append((kind, ver, bytes(self.buf[pos + HEADER.size:pos + length])))
            k = kind.decode('ascii')
            self.types[k] = self.types.get(k, 0) + 1
            pos += length
        del self.buf[:pos]
        return out

    def _resync(self, start: int) -> int:
        """Position of the next header with VERSION after `start`; at the end, keep a tail that may hold a split one."""
        i = self.buf.find(self.VER, start + 4)
        while i >= 0:
            if _plausible_type(self.buf[i - 4:i]):
                return i - 4
            i = self.buf.find(self.VER, i + 1)
        return max(start, len(self.buf) - (HEADER.size - 1))


def chan_names(payload: bytes) -> dict[int, str]:
    """CHAN: uint16 count, then 58-byte entries -- uint32 channel id at 0, NUL-padded name at 24..56 (decoded from a
    live CS2 Workshop Tools session 10 Nov 2026: 209 channels such as General, Console, Server, Entity System)."""
    if len(payload) < 2:
        return {}
    count = struct.unpack_from('>H', payload, 0)[0]
    out = {}
    for k in range(count):
        e = payload[2 + 58 * k:2 + 58 * (k + 1)]
        if len(e) < 58:
            break
        out[struct.unpack_from('>I', e, 0)[0]] = e[24:56].split(b'\0', 1)[0].decode('utf-8', 'replace')
    return out


def prnt_lines(payload: bytes, channels: dict | None = None) -> list[Line]:
    """The non-empty lines of one PRNT payload. Header (verified live 10 Nov 2026): uint32 channel id, 4 zero bytes,
    uint32 level (2 seen), RGBA colour, uint32 ms since start, 8 more bytes; text from byte 28, NUL-terminated."""
    if len(payload) < PRNT_TEXT:
        return []
    channel = struct.unpack_from('>I', payload, 0)[0]
    ms = struct.unpack_from('>I', payload, 16)[0]
    chan = (channels or {}).get(channel, '')
    text = payload[PRNT_TEXT:].split(b'\0', 1)[0].decode('utf-8', 'replace')
    now = time.time()
    return [Line(t.rstrip(), ms, channel, now, chan) for t in text.splitlines() if t.strip()]


# ------------------------------------------------------------------ transports
class _VConsoleWire:
    name = 'vconsole'

    def __init__(self):
        self.parser = Parser()
        self.channels: dict[int, str] = {}
        self.addon = None             # ADON: the addon the session runs (uint16, uint16 length, name)

    def encode(self, cmd):
        return command_packet(cmd)

    def decode(self, data):
        lines = []
        for kind, _, payload in self.parser.feed(data):
            if kind == b'PRNT':
                lines += prnt_lines(payload, self.channels)
            elif kind == b'CHAN':
                self.channels.update(chan_names(payload))
            elif kind == b'ADON' and len(payload) > 4:
                self.addon = payload[4:].split(b'\0', 1)[0].decode('utf-8', 'replace')
        return lines


class _NetconWire:
    name = 'netcon'

    def __init__(self):
        self.rest = b''

    def encode(self, cmd):
        return cmd.encode('utf-8') + b'\n'

    def decode(self, data):
        self.rest += data
        *full, self.rest = self.rest.split(b'\n')
        now = time.time()
        return [Line(t.decode('utf-8', 'replace').rstrip('\r'), 0, 0, now) for t in full if t.strip()]


# ------------------------------------------------------------------ the client
class Console:
    """One connection with a reader thread. Every received line is kept (bounded) so callers can read from a cursor:

        with Console() as c:
            out = c.run(['status'])                       # what the commands printed
            at = c.cursor(); c.send('map_workshop a b')   # start reading from here
            hit = c.wait_for(r'CSGO_GAME_UI_STATE_INGAME', 120, since=at)
    """
    KEEP = 200_000

    def __init__(self, host='127.0.0.1', port=PORT, netcon=False, timeout=5.0):
        self.host, self.port, self.netcon, self.timeout = host, port, netcon, timeout
        self.wire = _NetconWire() if netcon else _VConsoleWire()
        self.lines: list[Line] = []
        self.dropped = 0              # lines trimmed off the front (cursors are absolute)
        self.cv = threading.Condition()
        self.alive = False
        self.sock = None
        self.thread = None
        self._last_send: dict[str, float] = {}

    # connection
    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise ConsoleError('CS2 console on %s:%d is not reachable (%s). Start CS2 with %s.'
                               % (self.host, self.port, e, '-netconport %d' % self.port if self.netcon else
                                  '-tools (Workshop Tools opens VConsole2 on 29000)')) from None
        self.sock.settimeout(0.5)
        self.alive = True
        self.thread = threading.Thread(target=self._reader, name='vconsole-reader', daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.alive = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(2)
        with self.cv:
            self.cv.notify_all()

    def __enter__(self):
        return self.connect() if self.sock is None else self

    def __exit__(self, *exc):
        self.close()

    def _reader(self):
        try:
            while self.alive:
                try:
                    data = self.sock.recv(1 << 20)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not data:
                    break
                new = self.wire.decode(data)
                if new:
                    with self.cv:
                        self.lines += new
                        if len(self.lines) > self.KEEP:
                            cut = len(self.lines) - self.KEEP
                            del self.lines[:cut]
                            self.dropped += cut
                        self.cv.notify_all()
        finally:
            self.alive = False
            with self.cv:
                self.cv.notify_all()

    # reading
    def cursor(self) -> int:
        with self.cv:
            return self.dropped + len(self.lines)

    def since(self, cursor: int) -> list[Line]:
        with self.cv:
            return self.lines[max(0, cursor - self.dropped):]

    def texts(self, cursor: int = 0) -> list[str]:
        return [l.text for l in self.since(cursor)]

    def wait_for(self, pattern, timeout: float = 30.0, since: int | None = None):
        """The first line from `since` (default: now) matching the regex or callable, or None after `timeout`.
        Raises ConsoleError if the game closes the connection first."""
        test = pattern if callable(pattern) else re.compile(pattern).search
        pos = self.cursor() if since is None else since
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                start = max(0, pos - self.dropped)
                for i in range(start, len(self.lines)):
                    if test(self.lines[i].text):
                        return self.lines[i]
                pos = self.dropped + len(self.lines)
                left = deadline - time.monotonic()
                if not self.alive:
                    raise ConsoleError('CS2 closed the console connection (did the game crash or quit?)')
                if left <= 0:
                    return None
                self.cv.wait(min(left, 0.5))

    # writing
    def send(self, commands):
        """One command per string; a string with newlines is several. CS2 silently drops a server command repeated within
        a few milliseconds (cs2-map-mcp game.py:590-608), so an identical command is spaced 0.25 s from its last send
        (our unique echo markers never repeat)."""
        if isinstance(commands, str):
            commands = [commands]
        if not self.alive:
            raise ConsoleError('not connected to the CS2 console')
        for block in commands:
            for cmd in (c.strip() for c in block.splitlines()):
                if not cmd:
                    continue
                key = cmd
                gap = time.monotonic() - self._last_send.get(key, -1.0)
                if gap < 0.25:
                    time.sleep(0.25 - gap)
                if len(cmd.encode('utf-8')) + HEADER.size + 1 > MAX_PACKET:
                    raise ValueError('command too long for one CMND packet')
                try:
                    self.sock.sendall(self.wire.encode(cmd))
                except OSError as e:
                    self.alive = False
                    raise ConsoleError('CS2 closed the console connection (did the game crash?): %s' % e) from None
                self._last_send[key] = time.monotonic()

    def _framed(self, commands, until, timeout, linger):
        """Send begin marker, commands, end marker; return (answered, lines between the markers)."""
        token = uuid.uuid4().hex[:12]
        begin, end = 'autoport_b_' + token, 'autoport_e_' + token
        is_begin = lambda t: t.strip().endswith(begin) and 'echo' not in t
        is_end = lambda t: t.strip().endswith(end) and 'echo' not in t
        echoed = {'] ' + c.strip() for c in commands}      # a console that echoes typed commands (unverified for CS2)
        at = self.cursor()
        self.send(['echo ' + begin] + list(commands) + ['echo ' + end])
        deadline = time.monotonic() + timeout
        if self.wait_for(is_begin, timeout, since=at) is None:
            return False, []
        done_at = None
        while True:
            got = self.texts(at)
            try:
                i = next(k for k, t in enumerate(got) if is_begin(t))
            except StopIteration:
                i = -1
            body = [t for t in got[i + 1:] if begin not in t and end not in t and t.strip() not in echoed]
            ended = any(is_end(t) for t in got[i + 1:])
            now = time.monotonic()
            if done_at is None and until(body, ended):
                done_at = now + linger
            if done_at is not None and now >= done_at:
                return True, body
            if now >= deadline:
                return done_at is not None, body
            if not self.alive:
                raise ConsoleError('CS2 closed the console connection (did the game crash?)')
            with self.cv:
                self.cv.wait(min(0.1, max(0.0, (done_at or deadline) - now)))

    def run(self, commands, wait: float = 1.5, timeout: float = 20.0) -> list[str]:
        """Send commands and return what they printed: everything up to the end marker plus `wait` seconds."""
        if isinstance(commands, str):
            commands = [commands]
        return self._framed(commands, lambda body, ended: ended, timeout + wait, max(0.0, wait))[1]

    def run_until(self, commands, pattern, timeout: float = 30.0):
        """Send commands and read until a line matches `pattern` (a regex, or a callable taking the lines so far):
        (found, lines)."""
        if isinstance(commands, str):
            commands = [commands]
        if callable(pattern):
            return self._framed(commands, lambda body, ended: pattern(body), timeout, 0.0)
        rx = re.compile(pattern)
        return self._framed(commands, lambda body, ended: any(rx.search(t) for t in body), timeout, 0.0)

    def ping(self, timeout: float = 10.0) -> float | None:
        """Seconds for an echo round trip, or None when the console doesn't answer (busy or loading)."""
        t0 = time.monotonic()
        ok, _ = self._framed([], lambda body, ended: ended, timeout, 0.0)
        return round(time.monotonic() - t0, 3) if ok else None


# ------------------------------------------------------------------ helpers
def reachable(host='127.0.0.1', port=PORT, timeout=1.0) -> bool:
    """Is something listening? (A connect that's closed at once; it doesn't take the console slot.)"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def holders(port=PORT) -> list[str]:
    """Local processes with an established connection to the console port (pids; netstat, no extra modules)."""
    import subprocess
    try:
        out = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True, errors='replace', timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == 'ESTABLISHED' and parts[2].endswith(':%d' % port) and parts[4] != str(os.getpid()):
            pids.add(parts[4])
    return sorted(pids)


def _commands(args):
    out = []
    for a in args:
        out += [c for c in re.split(r';;|\n', a) if c.strip()]
    return out


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=PORT)
    ap.add_argument('--netcon', type=int, metavar='PORT', help='plain-text netcon port instead of VConsole2')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('ping')
    p = sub.add_parser('send'); p.add_argument('commands', nargs='+'); p.add_argument('--wait', type=float, default=1.5)
    p = sub.add_parser('tail'); p.add_argument('--seconds', type=float, default=0, help='0 = until Ctrl+C')
    p.add_argument('--grep'); p.add_argument('--backlog', action='store_true', help='also print what CS2 replays on connect')
    p.add_argument('--channels', action='store_true', help='prefix each line with its console channel')
    p = sub.add_parser('wait'); p.add_argument('regex'); p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--send', action='append', default=[], help='command to send once listening (repeatable)')
    a = ap.parse_args(argv)
    con = Console(a.host, a.netcon or a.port, netcon=bool(a.netcon))
    try:
        con.connect()
    except ConsoleError as e:
        print(e, file=sys.stderr); return 2
    try:
        if a.cmd == 'ping':
            took = con.ping()
            if took is None:
                held = holders(con.port)
                print('Connected, but the console did not answer in 10 s%s.' % (
                    ' (also connected: pid %s; CS2 answers one client only)' % ', '.join(held) if held else ''))
                return 1
            types = getattr(con.wire, 'parser', None)
            print('Console answered in %.3f s via %s.%s%s' % (took, con.wire.name,
                  ' Addon: %s.' % con.wire.addon if getattr(con.wire, 'addon', None) else '',
                  ' Packet types seen: %s; %d channels; %d bytes skipped.' % (
                      ', '.join('%s %d' % kv for kv in sorted(types.types.items())), len(con.wire.channels), types.skipped)
                  if types else ''))
            return 0
        if a.cmd == 'send':
            for line in con.run(_commands(a.commands), wait=a.wait):
                print(line)
            return 0
        if a.cmd == 'tail':
            rx = re.compile(a.grep) if a.grep else None
            pos = 0 if a.backlog else None
            if pos is None:
                con.ping(5)                  # the replayed backlog ends before our marker comes back
                pos = con.cursor()
            end = time.monotonic() + a.seconds if a.seconds else None
            try:
                while con.alive and (end is None or time.monotonic() < end):
                    con.wait_for(lambda t: True, 0.5 if end is None else max(0.05, min(0.5, end - time.monotonic())), since=pos)
                    for l in con.since(pos):
                        if rx is None or rx.search(l.text):
                            print(('[%s] ' % (l.chan or l.channel) if a.channels else '') + l.text, flush=True)
                    pos = con.cursor()
            except ConsoleError as e:
                print(e, file=sys.stderr); return 2
            except KeyboardInterrupt:
                pass
            return 0
        if a.cmd == 'wait':
            con.ping(5)
            at = con.cursor()
            if a.send:
                con.send(_commands(a.send))
            try:
                hit = con.wait_for(a.regex, a.timeout, since=at)
            except ConsoleError as e:
                print(e, file=sys.stderr); return 2
            if hit is None:
                print('No line matched %r in %g s.' % (a.regex, a.timeout)); return 1
            print(hit.text); return 0
    finally:
        con.close()


if __name__ == '__main__':
    sys.exit(main())
