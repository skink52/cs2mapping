"""A fake CS2 console on localhost for the autoport live-check tests: VConsole2 framing (or plain netcon text), the
connect-time backlog CS2 sends (AINF, CHAN, ADON, an oversized CVRB whose 16-bit length wraps, buffered PRNT lines),
and enough of the game to answer what autoport sends: echo, status, getpos/setpos/setang, noclip, +forward/-forward
movement, map_workshop loads (with scripted console errors), cvars, jpeg_screenshot, bind, the probe commands.

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
import math
import os
import re
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vconsole as V  # noqa: E402

CHANNELS = {0x11111111: 'General', 0x22222222: 'Entity System', 0x33333333: 'Console'}


def chan_packet(channels):
    body = struct.pack('>H', len(channels))
    for cid, name in channels.items():
        body += struct.pack('>I20x', cid) + name.encode().ljust(32, b'\0') + b'\0\x01'
    return V.packet(b'CHAN', body)


def cvrb_packet(real_size=70000):
    """A cvar list bigger than 64 KB, framed like CS2 does it: another version, the length field wrapped."""
    body = (b'm_szName\0sv_cheats\0' * (real_size // 19 + 1))[:real_size - 12]
    return struct.pack('>4sIHH', b'CVRB', 0x0002000B, real_size & 0xFFFF, 0) + body


class FakeCS2:
    def __init__(self, netcon=False, addon='mg_test', backlog=True, chunk=None, echo_commands=True):
        self.netcon, self.addon, self.backlog, self.chunk, self.echo_commands = netcon, addon, backlog, chunk, echo_commands
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.received = []                 # (time, command)
        self.map = None
        self.pos = [0.0, 0.0, 64.0]          # eye
        self.ang = [0.0, 0.0, 0.0]
        self.noclip = False
        self.forward_since = None
        self.cvars = {'mp_freezetime': '15', 'game_type': '0', 'game_mode': '0', 'bot_quota': '0', 'sv_airaccelerate': '12'}
        self.maps = {}                     # name -> lines printed while it loads
        self.after_load = []               # lines printed a little after the in-game state
        self.crash_after_load = False
        self.invalid_maps = set()
        self.probe = False
        self.entities = {}
        self.binds = {'F8': ''}
        self.delayed = {}                  # command word -> (delay, lines) printed later
        self.shots = 0
        self.lock = threading.Lock()
        self.conn = None
        self.alive = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    # ---- wire
    def _send_raw(self, data):
        if self.conn is None:
            return
        try:
            if self.chunk:
                for i in range(0, len(data), self.chunk):
                    self.conn.sendall(data[i:i + self.chunk])
            else:
                self.conn.sendall(data)
        except OSError:
            pass

    def say(self, *lines, channel=0x11111111):
        with self.lock:
            for text in lines:
                if self.netcon:
                    self._send_raw(text.encode() + b'\n')
                else:
                    self._send_raw(V.prnt_packet(text + '\n', ms=int(time.monotonic() * 1000) & 0xFFFFFFFF, channel=channel))

    def later(self, delay, *lines, channel=0x11111111):
        threading.Timer(delay, lambda: self.say(*lines, channel=channel)).start()

    def _serve(self):
        while self.alive:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            self.lock.acquire()                # the backlog goes out before any line a test sends
            self.conn = conn
            if self.backlog and not self.netcon:
                self._send_raw(V.packet(b'AINF', b'\0' * 40 + b'cs2\0'))
                self._send_raw(chan_packet(CHANNELS))
                name = self.addon.encode() + b'\0'
                self._send_raw(V.packet(b'ADON', struct.pack('>HH', 1, len(name)) + name))
                self._send_raw(cvrb_packet())
                for text in ('old line from before: Error loading resource old.vmat', 'VConsole client connection from 127.0.0.1'):
                    self._send_raw(V.prnt_packet(text, channel=0x33333333))
            self.lock.release()
            buf = b''
            parser = V.Parser()
            while self.alive:
                try:
                    data = conn.recv(65536)
                except OSError:
                    break
                if not data:
                    break
                if self.netcon:
                    buf += data
                    *cmds, buf = buf.split(b'\n')
                    cmds = [c.decode() for c in cmds]
                else:
                    cmds = [p[2].rstrip(b'\0').decode() for p in parser.feed(data) if p[0] == b'CMND']
                for c in cmds:
                    self.received.append((time.monotonic(), c))
                    if self.echo_commands:
                        self.say('] ' + c)
                    self.handle(c)
            try:
                conn.close()
            except OSError:
                pass
            if self.conn is conn:
                self.conn = None

    def crash(self):
        """The game dies: the console connection drops."""
        c = self.conn
        self.conn = None
        if c:
            try:
                c.shutdown(socket.SHUT_RDWR)
                c.close()
            except OSError:
                pass

    def close(self):
        self.alive = False
        self.crash()
        self.srv.close()

    # ---- the game
    def eye(self):
        if self.forward_since is not None:
            dt = time.monotonic() - self.forward_since
            yaw = math.radians(self.ang[1])
            return [self.pos[0] + math.cos(yaw) * 250 * dt, self.pos[1] + math.sin(yaw) * 250 * dt, self.pos[2]]
        return list(self.pos)

    def commands(self):
        return [c for _, c in self.received]

    def handle(self, c):
        word, _, rest = c.partition(' ')
        if word in self.delayed:
            d, lines = self.delayed[word]
            self.later(d, *lines)
        if word == 'echo':
            self.say(rest)
        elif word == 'status':
            m = self.map or '<empty>'
            self.later(0.05, 'Server:  Running [0.0.0.0:27015]', '---------spawngroups----',
                       'loaded spawngroup(  1)  : SV:  [1: %s | main lump | mapload]' % m, '---------players--------',
                       '  id     time ping loss      state   rate adr name', "65535 [NoChan]    0    0 challenging      0unknown ''",
                       *["%4d      BOT    0    0     active      0 'Bot%d'" % (i, i) for i in range(int(self.cvars['bot_quota']))], '#end')
        elif word == 'getpos':
            if self.map:
                e = self.eye()
                self.later(0.02, 'setpos %.6f %.6f %.6f;setang %.6f %.6f %.6f' % (*e, *self.ang))
        elif word == 'setpos':
            x, y, z = (float(v) for v in rest.split()[:3])
            self.pos = [x, y, z + 64]
        elif word == 'setang':
            if self.forward_since is not None:
                self.pos, self.forward_since = self.eye(), time.monotonic()
            self.ang = [float(v) for v in rest.split()[:3]]
        elif word == 'noclip':
            self.noclip = rest.strip() != '0'
        elif word == '+forward':
            if self.forward_since is None:
                self.forward_since = time.monotonic()
        elif word == '-forward':
            if self.forward_since is not None:
                self.pos, self.forward_since = self.eye(), None
        elif word in ('map_workshop', 'map'):
            name = rest.split()[-1]
            if name in self.invalid_maps:
                self.later(0.1, 'Invalid map name: %s' % name)
                return
            self.say('Loading custom game %s with map %s' % (self.addon, name))
            self.later(0.2, *self.maps.get(name, []), channel=0x22222222)
            self.later(0.4, 'ChangeGameUIState: CSGO_GAME_UI_STATE_LOADINGSCREEN -> CSGO_GAME_UI_STATE_INGAME')
            self.map = name

            def after():
                self.say(*self.after_load)
                if self.crash_after_load:
                    time.sleep(0.1)
                    self.crash()
            threading.Timer(0.6, after).start()
        elif word in self.cvars:
            if rest.strip():
                self.cvars[word] = rest.strip()
            else:
                self.later(0.02, '%s = %s' % (word, self.cvars[word]))
        elif word == 'jpeg_screenshot':
            self.shots += 1
            name = rest.split()[0]
            self.later(0.1, 'Screenshot written to: screenshots/%s_%04d.jpg' % (name, self.shots))
        elif word == 'bind':
            key, _, val = rest.partition(' ')
            if val:
                self.binds[key] = val.strip('"')
            else:
                self.say('"%s" = "%s"' % (key, self.binds.get(key, '')))
        elif word == 'bot_add_t' or word == 'bot_add_ct':
            self.cvars['bot_quota'] = str(int(self.cvars['bot_quota']) + 1)
        elif word == 'bot_kick':
            self.cvars['bot_quota'] = '0'
        elif word == 'ap_probe_entities' and self.probe:
            token, *names = rest.split()
            for n in names:
                ent = self.entities.get(n)
                self.say('AP_ENTITY %s {"name": "%s", "count": %d, "entity": %s}' % (
                    token, n, 1 if ent else 0, '{"classname": "%s", "origin": [1, 2, 3], "health": 50, "alive": true}' % ent if ent else 'null'))
            self.say('AP_ENTITIES_END %s {"map": "%s"}' % (token, self.map))
        elif word == 'ent_create' and 'autoport_probe' in rest:
            self.probe = True
        elif word.startswith('ap_probe') or word in ('respawn_player',):
            self.say("Unknown command '%s'!" % word)
