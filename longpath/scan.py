"""Read-only, cancellable path scan. Never follows reparse points."""
from dataclasses import dataclass, field
import os
import stat
import threading


def units(text: str) -> int:
    return len(text.encode('utf-16-le', errors='surrogatepass')) // 2


def native(path: str) -> str:
    if os.name != 'nt' or path.startswith('\\\\?\\'):
        return path
    if path.startswith('\\\\'):
        return '\\\\?\\UNC\\' + path[2:]
    return '\\\\?\\' + path


def display(path: str) -> str:
    if path.startswith('\\\\?\\UNC\\'):
        return '\\\\' + path[8:]
    if path.startswith('\\\\?\\'):
        return path[4:]
    return path


@dataclass(frozen=True)
class Entry:
    path: str
    relative: str
    kind: str
    length: int


@dataclass
class Result:
    entries: list[Entry] = field(default_factory=list)
    visited: int = 0
    skipped: int = 0
    excluded: int = 0
    errors: int = 0
    error_paths: list[str] = field(default_factory=list)
    cancelled: bool = False


def scan(root: str, threshold: int, exclusions: set[str], stop: threading.Event,
         progress=None) -> Result:
    if threshold < 1:
        raise ValueError('Порог должен быть положительным.')
    root = os.path.abspath(display(root))
    fsroot = native(root)
    info = os.lstat(fsroot)
    if not stat.S_ISDIR(info.st_mode):
        raise NotADirectoryError(root)
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Выберите обычную папку, а не ссылку или junction.')
    result = Result()
    excluded = {name.casefold() for name in exclusions}
    stack = [root]

    def fail(path):
        result.errors += 1
        if len(result.error_paths) < 100:
            result.error_paths.append(path)

    while stack and not stop.is_set():
        current = stack.pop()
        try:
            with os.scandir(native(current)) as children:
                for item in children:
                    if stop.is_set():
                        break
                    path = os.path.join(current, item.name)
                    result.visited += 1
                    try:
                        meta = item.stat(follow_symlinks=False)
                        if stat.S_ISLNK(meta.st_mode) or getattr(meta, 'st_file_attributes', 0) & 0x400:
                            result.skipped += 1
                            continue
                        directory = stat.S_ISDIR(meta.st_mode)
                        if directory and item.name.casefold() in excluded:
                            result.excluded += 1
                            continue
                        length = units(path)
                        if length >= threshold:
                            result.entries.append(Entry(path, os.path.relpath(path, root),
                                                        'Папка' if directory else 'Файл', length))
                        if directory:
                            stack.append(path)
                    except OSError:
                        fail(path)
                    if progress and result.visited % 250 == 0:
                        progress(result.visited, len(result.entries))
        except OSError:
            fail(current)
    result.cancelled = stop.is_set()
    result.entries.sort(key=lambda entry: (-entry.length, entry.path.casefold()))
    return result
