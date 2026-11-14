"""Russian dark tkinter UI, read-only filesystem operations."""
import ctypes
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .instance import TITLE
from .scan import scan

BG, CARD, FG, MUTED = '#111111', '#1c1c1c', '#eeeeee', '#999999'
SETTINGS = Path(os.environ.get('APPDATA', str(Path.home()))) / 'LongPath' / 'settings.json'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry('900x620')
        self.minsize(720, 480)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.result = None
        self.rows = {}
        self.pending = []
        self.render_job = None
        self.render_generation = 0
        try:
            saved = json.loads(SETTINGS.read_text(encoding='utf-8'))
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=FG, fieldbackground=CARD)
        style.configure('Treeview', background=CARD, fieldbackground=CARD,
                        foreground=FG, rowheight=28, borderwidth=0)
        style.configure('Treeview.Heading', background='#303030', foreground=FG)
        style.map('Treeview', background=[('selected', '#334862')], foreground=[('selected', '#ffffff')])
        style.map('TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', FG)])
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill='both', expand=True, padx=20, pady=16)
        tk.Label(frame, text='LongPath', bg=BG, fg=FG, font=('Segoe UI Semibold', 21)).pack(anchor='w')
        tk.Label(frame, text='Длинные пути · порог — риск совместимости, а не гарантия ошибки',
                 bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', pady=(0,12))
        line = tk.Frame(frame, bg=BG)
        line.pack(fill='x')
        self.folder = tk.StringVar(value=str(saved.get('folder', '')))
        self.path_entry = ttk.Entry(line, textvariable=self.folder)
        self.path_entry.pack(side='left', fill='x', expand=True)
        self.browse = ttk.Button(line, text='Папка…', command=self.choose)
        self.browse.pack(side='left', padx=(8,0))
        options = tk.Frame(frame, bg=BG)
        options.pack(fill='x', pady=10)
        tk.Label(options, text='Длина от', bg=BG, fg=FG).pack(side='left')
        threshold = str(saved.get('threshold', '260'))
        self.threshold = tk.StringVar(value=threshold if threshold.isdigit() else '260')
        self.threshold_entry = ttk.Entry(options, textvariable=self.threshold, width=6)
        self.threshold_entry.pack(side='left', padx=6)
        tk.Label(options, text='UTF-16 · исключения', bg=BG, fg=MUTED).pack(side='left')
        self.exclusions = tk.StringVar(value=str(saved.get('exclusions', '.git;node_modules;.venv')))
        self.exclude_entry = ttk.Entry(options, textvariable=self.exclusions)
        self.exclude_entry.pack(side='left', fill='x', expand=True, padx=6)
        self.start_button = ttk.Button(options, text='Найти', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(options, text='Стоп', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=(6,0))
        self.status = tk.StringVar(value='Выберите папку. Файлы и папки остаются на месте.')
        tk.Label(frame, textvariable=self.status, bg=BG, fg=MUTED, anchor='w').pack(fill='x')
        search_line = tk.Frame(frame, bg=BG)
        search_line.pack(fill='x', pady=8)
        tk.Label(search_line, text='Фильтр', bg=BG, fg=MUTED).pack(side='left')
        self.query = tk.StringVar()
        ttk.Entry(search_line, textvariable=self.query).pack(side='left', fill='x', expand=True, padx=8)
        self.query.trace_add('write', self.filter_changed)
        table = tk.Frame(frame, bg=BG)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('length','kind','path'), show='headings', selectmode='browse')
        for name, label, width in [('length','Длина',75), ('kind','Тип',80), ('path','Путь от выбранной папки',620)]:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=60, stretch=name=='path')
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.tag_configure('risk', foreground='#fde68a')
        self.tree.bind('<<TreeviewSelect>>', self.selected)
        self.detail = tk.StringVar()
        detail_entry = ttk.Entry(frame, textvariable=self.detail, state='readonly')
        detail_entry.pack(fill='x', pady=8)
        actions = tk.Frame(frame, bg=BG)
        actions.pack(fill='x')
        ttk.Button(actions, text='Копировать путь', command=self.copy_path).pack(side='left')
        ttk.Button(actions, text='Открыть папку', command=self.open_folder).pack(side='left', padx=8)
        ttk.Button(actions, text='Сохранить TXT', command=self.export).pack(side='left')
        ttk.Button(actions, text='Ошибки обхода', command=self.show_errors).pack(side='left', padx=8)
        footer = tk.Label(frame, text='неделя 12 · день 83                                         v1.0.0 · darkshade',
                          bg=BG, fg=MUTED, anchor='w')
        footer.pack(fill='x', pady=(12,0))
        # Allocate controls before the expanding table, including on high-DPI screens.
        footer.pack_configure(side='bottom', before=table)
        actions.pack_configure(side='bottom', before=table)
        detail_entry.pack_configure(side='bottom', before=table)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(80, self.poll)

    def choose(self):
        path = filedialog.askdirectory(parent=self)
        if path:
            self.folder.set(path)

    def start(self):
        if self.busy:
            return
        try:
            threshold = int(self.threshold.get())
            if not 1 <= threshold <= 32767:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Порог', 'Введите целое число от 1 до 32767.', parent=self)
            return
        root = self.folder.get().strip()
        if not root:
            return
        self.busy = True
        self.result = None
        self.stop.clear()
        self.clear_table()
        self.lock(True)
        self.status.set('Обход…')
        exclusions = {x.strip() for x in self.exclusions.get().split(';') if x.strip()}
        def work():
            try:
                result = scan(root, threshold, exclusions, self.stop,
                              lambda seen, found: self.events.put(('progress', (seen, found))))
                self.events.put(('done', result))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def lock(self, busy):
        for widget in (self.start_button, self.browse, self.path_entry, self.threshold_entry, self.exclude_entry):
            widget.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')

    def poll(self):
        for _ in range(50):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self.status.set(f'Проверено: {data[0]} · найдено: {data[1]}')
            else:
                self.busy = False
                self.lock(False)
                if kind == 'error':
                    self.status.set('Ошибка: ' + data)
                else:
                    self.result = data
                    self.refilter()
        self.after(80, self.poll)

    def filter_changed(self, *_):
        if self.render_job:
            self.after_cancel(self.render_job)
        self.render_job = self.after(180, self.refilter)

    def clear_table(self):
        self.render_generation += 1
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.detail.set('')

    def refilter(self):
        self.render_job = None
        if self.result is None:
            return
        self.clear_table()
        needle = self.query.get().casefold()
        self.pending = [entry for entry in self.result.entries if needle in entry.path.casefold()]
        r = self.result
        state = 'Остановлено' if r.cancelled else 'Готово'
        self.status.set(f'{state} · проверено: {r.visited} · найдено: {len(r.entries)} · видно: {len(self.pending)}'
                        f' · ошибки: {r.errors} · ссылки: {r.skipped} · исключено: {r.excluded}')
        self.insert_batch(self.render_generation, self.pending, 0)

    def insert_batch(self, generation, entries, offset):
        if generation != self.render_generation:
            return
        for entry in entries[offset:offset+250]:
            key = self.tree.insert('', 'end', values=(entry.length, entry.kind, entry.relative),
                                   tags=('risk',) if entry.length >= 260 else ())
            self.rows[key] = entry
        if offset+250 < len(entries):
            self.after(1, self.insert_batch, generation, entries, offset+250)

    def selected(self, _event=None):
        chosen = self.tree.selection()
        entry = self.rows.get(chosen[0]) if chosen else None
        self.detail.set(entry.path if entry else '')
        return entry

    def copy_path(self):
        entry = self.selected()
        if entry:
            self.clipboard_clear()
            self.clipboard_append(entry.path)

    def open_folder(self):
        entry = self.selected()
        if entry:
            try:
                os.startfile(entry.path if entry.kind == 'Папка' else os.path.dirname(entry.path))
            except OSError as exc:
                messagebox.showerror('Проводник', str(exc), parent=self)

    def export(self):
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.txt', filetypes=[('Текст', '*.txt')])
        if path:
            try:
                needle = self.query.get().casefold()
                with open(path, 'w', encoding='utf-8') as handle:
                    for entry in self.result.entries:
                        if needle in entry.path.casefold():
                            handle.write(f'{entry.length}\t{entry.kind}\t{entry.path}\n')
            except OSError as exc:
                messagebox.showerror('TXT', str(exc), parent=self)

    def show_errors(self):
        if self.result:
            text = '\n'.join(self.result.error_paths) or 'Ошибок обхода нет.'
            if self.result.errors > len(self.result.error_paths):
                text += '\nПоказаны первые 100 путей.'
            messagebox.showinfo('Ошибки обхода', text, parent=self)

    def close(self):
        self.stop.set()
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS.write_text(json.dumps({'folder':self.folder.get(), 'threshold':self.threshold.get(),
                                           'exclusions':self.exclusions.get()}, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass
        self.destroy()


def run():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except OSError:
        pass
    App().mainloop()
