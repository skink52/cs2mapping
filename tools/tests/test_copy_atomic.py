"""safepath.copy_atomic: a copy decided by content (SHA-256), written through a temporary file, verified, then moved into place.
Real files in a temporary folder; nothing outside it is touched.

  python -m unittest discover -s tools/tests -p "test_copy_atomic.py" -v
"""
import os, shutil, stat, subprocess, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import safepath as S


def put(path, data=b'x', mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(data)
    if mtime is not None: os.utime(path, (mtime, mtime))


def get(path):
    with open(path, 'rb') as f: return f.read()


def junction(link, target):
    try:
        os.makedirs(os.path.dirname(link), exist_ok=True)
        if os.name == 'nt': subprocess.run(['cmd', '/c', 'mklink', '/J', link, target], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else: os.symlink(target, link, target_is_directory=True)
        return link
    except (OSError, subprocess.CalledProcessError):
        return None


class CopyAtomic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='copy_atomic_')
        self.src = os.path.join(self.tmp, 'in', 'a.vpk'); self.dst = os.path.join(self.tmp, 'out', 'a.vpk')

    def tearDown(self):
        for dp, dns, fs in os.walk(self.tmp):
            for d in list(dns):
                q = os.path.join(dp, d)
                if S.is_link(q):
                    os.rmdir(q) if os.name == 'nt' else os.unlink(q); dns.remove(d)
            for f in fs:
                try: os.chmod(os.path.join(dp, f), stat.S_IWRITE | stat.S_IREAD)
                except OSError: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def leftovers(self):
        return [f for _, _, fs in os.walk(self.tmp) for f in fs if f.endswith('.copytmp')]

    # ---- the decision is by content
    def test_same_size_different_content_is_replaced(self):
        """the bug this replaces: equal size (and a destination no older than the source) used to count as "already copied" """
        put(self.src, b'AAAA', mtime=1_700_000_000); put(self.dst, b'BBBB', mtime=1_700_000_000)
        self.assertEqual(os.path.getsize(self.src), os.path.getsize(self.dst))
        r = S.copy_atomic(self.src, self.dst)
        self.assertEqual(r['op'], 'modify'); self.assertEqual(get(self.dst), b'AAAA'); self.assertEqual(r['sha256'], S.sha256_file(self.src))

    def test_same_size_different_content_with_a_newer_destination_is_replaced(self):
        put(self.src, b'new data', mtime=1_600_000_000); put(self.dst, b'old data', mtime=1_900_000_000)
        self.assertEqual(S.copy_atomic(self.src, self.dst)['op'], 'modify')
        self.assertEqual(get(self.dst), b'new data')

    def test_identical_files_with_different_timestamps_are_left_alone(self):
        for src_time, dst_time in ((1_900_000_000, 1_600_000_000), (1_600_000_000, 1_900_000_000)):
            put(self.src, b'same bytes', mtime=src_time); put(self.dst, b'same bytes', mtime=dst_time)
            self.assertEqual(S.copy_atomic(self.src, self.dst)['op'], 'same')
            self.assertEqual(int(os.path.getmtime(self.dst)), dst_time)            # not rewritten
        self.assertEqual(self.leftovers(), [])

    def test_different_sizes(self):
        put(self.src, b'longer content'); put(self.dst, b'short')
        self.assertEqual(S.copy_atomic(self.src, self.dst)['op'], 'modify'); self.assertEqual(get(self.dst), b'longer content')

    def test_empty_source_and_a_file_larger_than_one_chunk(self):
        put(self.src, b''); put(self.dst, b'something')
        self.assertEqual(S.copy_atomic(self.src, self.dst)['op'], 'modify'); self.assertEqual(get(self.dst), b'')
        big = os.urandom(300_000); put(self.src, big)
        self.assertEqual(S.copy_atomic(self.src, self.dst, chunk=65536)['op'], 'modify'); self.assertEqual(get(self.dst), big)

    def test_missing_destination_folder_is_made(self):
        put(self.src, b'data'); deep = os.path.join(self.tmp, 'a', 'b', 'c', 'a.vpk')
        self.assertEqual(S.copy_atomic(self.src, deep)['op'], 'create'); self.assertEqual(get(deep), b'data')

    # ---- refusals: the destination is as it was
    def test_missing_source(self):
        put(self.dst, b'keep me')
        with self.assertRaises(S.CopyError) as cm: S.copy_atomic(self.src, self.dst)
        self.assertIn('source is missing', str(cm.exception)); self.assertEqual(get(self.dst), b'keep me')
        os.makedirs(self.src)                                                       # a folder is not a regular file either
        with self.assertRaises(S.CopyError): S.copy_atomic(self.src, self.dst)
        self.assertIsInstance(cm.exception, OSError)

    def test_destination_that_is_a_folder(self):
        put(self.src, b'data'); os.makedirs(self.dst)
        with self.assertRaises(S.CopyError): S.copy_atomic(self.src, self.dst)
        self.assertTrue(os.path.isdir(self.dst)); self.assertEqual(self.leftovers(), [])

    def test_destination_that_is_a_link_is_refused_not_followed(self):
        put(self.src, b'data'); real = os.path.join(self.tmp, 'elsewhere'); put(os.path.join(real, 'f.txt'), b'precious')
        if not junction(self.dst, real): self.skipTest('cannot make a junction / symlink here')
        with self.assertRaises(S.CopyError) as cm: S.copy_atomic(self.src, self.dst)
        self.assertIn('link', str(cm.exception))
        self.assertTrue(S.is_link(self.dst)); self.assertEqual(get(os.path.join(real, 'f.txt')), b'precious')

    def test_folder_above_the_destination_that_is_a_junction_is_written_through(self):
        """as before this change: copy_atomic does not police the folders above dst (callers that must, use check_no_nested_links)"""
        put(self.src, b'data'); real = os.path.join(self.tmp, 'real_out'); os.makedirs(real)
        if not junction(os.path.join(self.tmp, 'out'), real): self.skipTest('cannot make a junction / symlink here')
        self.assertEqual(S.copy_atomic(self.src, self.dst)['op'], 'create')
        self.assertEqual(get(os.path.join(real, 'a.vpk')), b'data')

    # ---- failures part way: old destination kept, temporary file gone
    def test_failed_replace_keeps_the_old_file_and_cleans_up(self):
        put(self.src, b'new'); put(self.dst, b'old')
        with mock.patch.object(S.os, 'replace', side_effect=PermissionError(13, 'in use by another process')):
            with self.assertRaises(PermissionError): S.copy_atomic(self.src, self.dst)
        self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])

    def test_hash_mismatch_after_copying(self):
        put(self.src, b'new'); put(self.dst, b'old'); real = S.sha256_file
        with mock.patch.object(S, 'sha256_file', side_effect=lambda p, *a: '0' * 64 if p.endswith('.copytmp') else real(p, *a)):
            with self.assertRaises(S.CopyError) as cm: S.copy_atomic(self.src, self.dst)
        self.assertIn('does not match its source', str(cm.exception))
        self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])

    def test_interrupted_copy(self):
        put(self.src, b'new'); put(self.dst, b'old')
        with mock.patch.object(S.os, 'fsync', side_effect=KeyboardInterrupt):       # Ctrl+C with the temporary file half done
            with self.assertRaises(KeyboardInterrupt): S.copy_atomic(self.src, self.dst)
        self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])
        with mock.patch.object(S.os, 'fsync', side_effect=OSError(28, 'No space left on device')):
            with self.assertRaises(OSError): S.copy_atomic(self.src, os.path.join(self.tmp, 'new', 'b.vpk'))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'new', 'b.vpk'))); self.assertEqual(self.leftovers(), [])

    def test_source_modified_while_copying(self):
        put(self.src, b'second version'); put(self.dst, b'old'); real = S.sha256_file; first = S.hashlib.sha256(b'first version!').hexdigest()
        with mock.patch.object(S, 'sha256_file', side_effect=lambda p, *a: first if p == self.src else real(p, *a)):   # the hash taken before the copy
            with self.assertRaises(S.CopyError) as cm: S.copy_atomic(self.src, self.dst)
        self.assertIn('changed while', str(cm.exception)); self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows refuses to replace a read-only file; POSIX replaces by folder permission')
    def test_read_only_destination_is_not_forced(self):
        put(self.src, b'new'); put(self.dst, b'old'); os.chmod(self.dst, stat.S_IREAD)
        with self.assertRaises(OSError): S.copy_atomic(self.src, self.dst)
        self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows file locking')
    def test_destination_open_in_another_program(self):
        put(self.src, b'new'); put(self.dst, b'old')
        with open(self.dst, 'rb'):                                                  # Python opens without delete sharing: replace is refused
            with self.assertRaises(OSError): S.copy_atomic(self.src, self.dst)
        self.assertEqual(get(self.dst), b'old'); self.assertEqual(self.leftovers(), [])


if __name__ == '__main__':
    unittest.main()
