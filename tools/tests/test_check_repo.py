"""ci/check_repo.py text checks: control characters, invalid UTF-8, binary data, and a tab inside a Windows path in a document.

  python -m unittest discover -s tools/tests -p "test_check_repo.py" -v
"""
import os, sys, unittest
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'ci'))
import check_repo as C


class TextProblems(unittest.TestCase):
    def test_ordinary_text_passes(self):
        ok = [('a.md', 'Plain text.\r\n\tIndented with a tab.\nA table:\t| a | b |\n'.encode()),
              ('a.md', 'Unicode is fine: caf\u00e9, 1536\u00b2, \u2192, \u65e5\u672c\u8a9e, \U0001F600\n'.encode()),
              ('a.md', b'\xef\xbb\xbfWith a byte order mark\n'),
              ('a.md', b'Run it from `C:\\source1\\cs2port\\tools`, then `C:\\source1\\archive\\x`.\n'),
              ('a.py', b'x = {\n\t"C:\\\\tools":\t1}\n'),
              ('a.md', b'| `C:\\source1` |\tthe working folder |\n'),             # a tab after a path, not inside one
              ('a.md', b'')]
        for name, data in ok:
            self.assertEqual(C.text_problems(name, data), [], data)

    def test_lost_escape_in_a_windows_path(self):
        """the 11 Nov 2026 finds: "cs2port\\tools" had become cs2port<TAB>ools, and "source1\\archive" source1<BEL>rchive"""
        p = C.text_problems('CLAUDE.md', b'line one\nruns on the PC from `C:\\source1\\cs2port\tools`, through autoport\n')
        self.assertEqual(len(p), 1); self.assertIn('CLAUDE.md:2: a tab inside a Windows path', p[0]); self.assertIn('<TAB>ools', p[0])
        p = C.text_problems('CHANGELOG.md', b'moved to `C:\\source1\x07rchive\\cs2port_workers`\n')
        self.assertEqual(len(p), 1); self.assertIn('control character 0x07', p[0]); self.assertIn('CHANGELOG.md:1', p[0])
        for ch in (b'\x08', b'\x0b', b'\x0c', b'\x1b', b'\x7f'):
            self.assertEqual(len(C.text_problems('a.md', b'ab' + ch + b'cd\n')), 1, ch)
        self.assertEqual(C.text_problems('a.py', b'p = "C:\\source1\\cs2port\tools"\n'), [])     # code may hold what it likes after a path

    def test_invalid_utf8(self):
        p = C.text_problems('DESIGN.md', b'first\nlobby 1536\xb2, 12 vaults\n')            # Latin-1 superscript two
        self.assertEqual(len(p), 1); self.assertIn('DESIGN.md:2: byte 0xb2 is not valid UTF-8', p[0])
        self.assertEqual(len(C.text_problems('a.json', b'{"a": "\xff\xfe"}')), 1)
        self.assertEqual(len(C.text_problems('a.md', b'cut in the middle \xe2\x82')), 1)

    def test_binary_data_in_a_text_file(self):
        p = C.text_problems('notes.md', b'# Notes\n\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00')
        self.assertEqual(len(p), 1); self.assertIn('NUL byte', p[0]); self.assertIn('binary data', p[0])
        self.assertIn('UTF-16', 'UTF-16 text is caught the same way'); self.assertEqual(len(C.text_problems('a.md', 'hello'.encode('utf-16'))), 1)

    def test_the_repo_passes(self):
        n, probs, _ = C.check_control(C.tracked())
        self.assertGreater(n, 500); self.assertEqual(probs, [])


if __name__ == '__main__':
    unittest.main()
