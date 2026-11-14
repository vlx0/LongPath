from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from longpath.report import write_report
from longpath.scan import Entry


class ReportTests(unittest.TestCase):
    def test_failed_replace_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, 'report.txt')
            target.write_text('old content')
            with patch('longpath.report.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    write_report(str(target), [Entry('C:/long.txt', 'long.txt', 'Файл', 260)], 'header')
            self.assertEqual(target.read_text(), 'old content')
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['report.txt'])

    def test_report_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, 'report.txt')
            write_report(str(target), [Entry('C:/😀.txt', '😀.txt', 'Файл', 260)], 'Частичный результат')
            text = target.read_text(encoding='utf-8')
            self.assertIn('Частичный результат', text)
            self.assertIn('😀.txt', text)
