"""Atomic UTF-8 report: failures leave an existing target unchanged."""
import os
import tempfile
from .scan import native


def write_report(path, entries, header):
    target = native(os.path.abspath(path))
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', errors='backslashreplace',
                                         dir=os.path.dirname(target), prefix='.longpath-',
                                         suffix='.tmp', delete=False) as handle:
            temp = handle.name
            handle.write(header + '\n\n')
            for entry in entries:
                handle.write(f'{entry.length}\t{entry.kind}\t{entry.path}\n')
        os.replace(temp, target)
        temp = None
    finally:
        if temp is not None:
            try:
                os.unlink(temp)
            except OSError:
                pass
