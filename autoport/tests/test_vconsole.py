"""vconsole.py against a fake CS2 console on localhost. Run: python -m unittest discover -s autoport/tests -v"""
import contextlib
import io
import os
import struct
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vconsole as V  # noqa: E402
from fakecs2 import CHANNELS, FakeCS2, chan_packet, cvrb_packet  # noqa: E402


class Framing(unittest.TestCase):
    def test_command_packet_header(self):
        p = V.command_packet('status')
        kind, ver, length, handle = struct.unpack('>4sIHH', p[:12])
        self.assertEqual((kind, ver, length, handle), (b'CMND', 0x00D40000, 12 + 7, 0))
        self.assertEqual(p[12:], b'status\0')

    def test_prnt_fields(self):
        lines = V.prnt_lines(V.prnt_packet('one\ntwo\n', ms=1234, channel=0x22222222)[12:], CHANNELS)
        self.assertEqual([l.text for l in lines], ['one', 'two'])
        self.assertEqual((lines[0].ms, lines[0].chan), (1234, 'Entity System'))

    def test_split_reads_one_byte_at_a_time(self):
        data = V.prnt_packet('hello') + V.packet(b'AINF', b'x' * 30) + V.prnt_packet('world')
        p, got = V.Parser(), []
        for b in data:
            got += p.feed(bytes([b]))
        self.assertEqual([k for k, _, _ in got], [b'PRNT', b'AINF', b'PRNT'])
        self.assertEqual(p.skipped, 0)

    def test_wrapped_cvrb_length_resyncs(self):
        """CS2's cvar list is over 64 KB with another version: its length field wraps (seen live 10 Nov 2026)."""
        big = cvrb_packet(70000)
        data = V.prnt_packet('before') + big + V.prnt_packet('after')
        p = V.Parser()
        got = []
        for i in range(0, len(data), 4096):
            got += p.feed(data[i:i + 4096])
        texts = [l.text for k, _, pay in got if k == b'PRNT' for l in V.prnt_lines(pay)]
        self.assertEqual(texts, ['before', 'after'])
        self.assertEqual(p.skipped, len(big))
        self.assertEqual(p.types.get('CVRB'), 1)

    def test_garbage_between_packets(self):
        p = V.Parser()
        got = p.feed(b'\x01\x02garbage' + V.prnt_packet('ok'))
        self.assertEqual(len(got), 1)

    def test_chan_names(self):
        self.assertEqual(V.chan_names(chan_packet(CHANNELS)[12:]), CHANNELS)

    def test_too_long(self):
        with self.assertRaises(ValueError):
            V.packet(b'CMND', b'x' * 70000)


class Client(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCS2()
        self.c = V.Console(port=self.fake.port).connect()

    def tearDown(self):
        self.c.close()
        self.fake.close()

    def test_ping_reads_backlog_channels_and_addon(self):
        self.assertIsNotNone(self.c.ping())
        self.assertEqual(self.c.wire.addon, 'mg_test')
        self.assertIn('Entity System', self.c.wire.channels.values())
        self.assertIn('CVRB', self.c.wire.parser.types)

    def test_run_returns_only_its_own_output(self):
        out = self.c.run(['echo hello'], wait=0.1)
        self.assertEqual(out, ['hello'])                 # not the backlog, not the "] echo" lines, not the markers

    def test_run_wait_catches_late_server_output(self):
        self.fake.delayed['slowcmd'] = (0.3, ['late line'])
        self.assertNotIn('late line', self.c.run(['slowcmd'], wait=0))
        self.fake.delayed['slow2'] = (0.3, ['late line 2'])
        self.assertIn('late line 2', self.c.run(['slow2'], wait=0.8))

    def test_run_until_waits_for_pattern_after_end_marker(self):
        self.fake.map = 'mg_test'
        ok, lines = self.c.run_until('status', r'#end', timeout=5)
        self.assertTrue(ok)
        self.assertTrue(any('loaded spawngroup' in l for l in lines))

    def test_wait_for_times_out(self):
        t = time.monotonic()
        self.assertIsNone(self.c.wait_for(r'never', 0.4))
        self.assertLess(time.monotonic() - t, 2)

    def test_wait_for_raises_when_game_dies(self):
        self.c.ping()
        self.fake.crash()
        with self.assertRaises(V.ConsoleError):
            self.c.wait_for(r'never', 5)

    def test_identical_commands_are_spaced(self):
        self.c.send(['bot_kick', 'bot_kick'])
        time.sleep(0.3)
        times = [t for t, c in self.fake.received if c == 'bot_kick']
        self.assertEqual(len(times), 2)
        self.assertGreaterEqual(times[1] - times[0], 0.2)

    def test_channels_on_lines(self):
        self.c.ping()
        self.fake.say('Unknown input Foo', channel=0x22222222)
        hit = self.c.wait_for(r'Unknown input', 3, since=0)
        self.assertEqual(hit.chan, 'Entity System')


class ChunkedServer(unittest.TestCase):
    def test_tiny_tcp_chunks(self):
        fake = FakeCS2(chunk=7)
        try:
            with V.Console(port=fake.port) as c:
                self.assertEqual(c.run('echo split up', wait=0.1), ['split up'])
        finally:
            fake.close()


class Netcon(unittest.TestCase):
    def test_plain_text_transport(self):
        fake = FakeCS2(netcon=True)
        try:
            with V.Console(port=fake.port, netcon=True) as c:
                self.assertEqual(c.run('echo over netcon', wait=0.1), ['over netcon'])
            self.assertIn('echo over netcon', fake.commands())
        finally:
            fake.close()


class Cli(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCS2()

    def tearDown(self):
        self.fake.close()

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = V.main(['--port', str(self.fake.port)] + list(args))
        return code, out.getvalue()

    def test_send(self):
        code, out = self.run_cli('send', 'echo a;;echo b', '--wait', '0.1')
        self.assertEqual((code, out.split()), (0, ['a', 'b']))

    def test_wait_found_and_timeout(self):
        code, out = self.run_cli('wait', r'^marker \d+$', '--timeout', '5', '--send', 'echo marker 42')
        self.assertEqual((code, out.strip()), (0, 'marker 42'))
        code, _ = self.run_cli('wait', 'nothing', '--timeout', '0.5')
        self.assertEqual(code, 1)

    def test_tail_skips_backlog(self):
        self.fake.later(1.5, 'live line')
        code, out = self.run_cli('tail', '--seconds', '3')
        self.assertEqual(code, 0)
        self.assertIn('live line', out)
        self.assertNotIn('old line from before', out)

    def test_ping_and_unreachable(self):
        code, out = self.run_cli('ping')
        self.assertEqual(code, 0)
        self.assertIn('Addon: mg_test', out)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(V.main(['--port', '1', 'ping']), 2)
        self.assertIn('not reachable', err.getvalue())


if __name__ == '__main__':
    unittest.main()
