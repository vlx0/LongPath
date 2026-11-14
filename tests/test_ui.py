import tempfile
from pathlib import Path
import queue
import unittest
from unittest.mock import patch

from longpath.ui import App
from longpath.scan import Entry, Result


class UiTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.withdraw()

    def tearDown(self):
        for callback in self.app.tk.call('after', 'info'):
            self.app.after_cancel(callback)
        self.app.destroy()

    def test_immediate_refilter_cancels_delayed_refilter(self):
        a = self.app
        a.result = Result(entries=[Entry('C:/x', 'x', 'Файл', 260)])
        a.query.set('x')
        pending = a.render_job
        self.assertIn(pending, a.tk.call('after', 'info'))
        a.refilter()
        self.assertNotIn(pending, a.tk.call('after', 'info'))
        self.assertEqual(len(a.rows), 1)

    def test_export_uses_snapshot_when_dialog_changes_result(self):
        a = self.app
        a.result = Result(entries=[Entry('C:/original.txt', 'original.txt', 'Файл', 260)],
                          cancelled=True, root='C:/', threshold=260)
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder, 'result.txt'))
            def dialog(**_):
                a.result = None
                return target
            with patch('longpath.ui.filedialog.asksaveasfilename', side_effect=dialog):
                a.export()
            # Worker completion event gives deterministic synchronization without driving UI.
            kind, message = a.events.get(timeout=5)
            self.assertEqual(kind, 'export_done', message)
            text = Path(target).read_text(encoding='utf-8')
            self.assertIn('original.txt', text)
            self.assertIn('частичный результат', text)
