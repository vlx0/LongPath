import os
from pathlib import Path
import tempfile
import threading
import unittest

from longpath.scan import scan, units, native, display


class ScanTests(unittest.TestCase):
    def test_utf16_and_prefix(self):
        self.assertEqual(units('a😀'), 3)
        for path in [r'C:\folder\name', r'\\server\share\folder']:
            self.assertEqual(display(native(path)), path)

    def test_scan_threshold_exclusions_and_cancel(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root, 'child')
            folder.mkdir()
            file = folder / 'file.txt'
            file.write_text('hello')
            ignored = Path(root, '.GIT')
            ignored.mkdir()
            (ignored / 'hidden').write_text('x')
            result = scan(root, units(str(file)), {'.git'}, threading.Event())
            self.assertEqual([e.path for e in result.entries], [str(file)])
            self.assertEqual(result.excluded, 1)
            stop = threading.Event()
            stop.set()
            self.assertTrue(scan(root, 1, set(), stop).cancelled)

    def test_long_tree(self):
        with tempfile.TemporaryDirectory() as root:
            path = root
            for _ in range(5):
                path = os.path.join(path, 'a' * 55)
                os.mkdir(native(path))
            file = os.path.join(path, '😀.txt')
            with open(native(file), 'w') as handle:
                handle.write('x')
            result = scan(root, 260, set(), threading.Event())
            self.assertIn(file, [e.path for e in result.entries])
            self.assertEqual(result.errors, 0)
            self.assertEqual(result.entries[0].length, units(file))


if __name__ == '__main__':
    unittest.main()
