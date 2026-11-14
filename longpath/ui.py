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
from .report import write_report

BG, CARD, FG, MUTED = '#111214', '#1b1d21', '#eef0f3', '#989da8'
EDGE, ACCENT = '#30343b', '#92b9ff'
SETTINGS = Path(os.environ.get('APPDATA', str(Path.home()))) / 'LongPath' / 'settings.json'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry('980x740')
        self.minsize(800, 660)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.export_busy = False
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
        style.configure('.', background=BG, foreground=FG, fieldbackground=CARD,
                        font=('Segoe UI', 10), bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE)
        style.configure('TEntry', padding=(10, 8), borderwidth=1, relief='flat',
                        insertcolor=FG, selectbackground='#354e74', selectforeground=FG)
        style.map('TEntry', bordercolor=[('focus', '#698bbe')],
                  fieldbackground=[('disabled', '#202226'), ('readonly', '#17191d')],
                  foreground=[('disabled', '#6e7480'), ('readonly', MUTED)])
        style.configure('TButton', padding=(13, 8), background='#292d34', foreground=FG,
                        borderwidth=0, relief='flat', focusthickness=0)
        style.map('TButton', background=[('disabled', '#202226'), ('pressed', '#373e48'),
                                        ('active', '#343a43')],
                  foreground=[('disabled', '#626873')], bordercolor=[('focus', '#698bbe')])
        style.configure('Primary.TButton', background=ACCENT, foreground='#101a2a',
                        font=('Segoe UI Semibold', 10))
        style.map('Primary.TButton', background=[('disabled', '#283346'), ('pressed', '#739cdd'),
                                                ('active', '#aecbff')],
                  foreground=[('disabled', '#6c7c94'), ('!disabled', '#101a2a')])
        style.configure('Treeview', background=CARD, fieldbackground=CARD,
                        foreground=FG, rowheight=34, borderwidth=0, relief='flat')
        style.configure('Treeview.Heading', background='#252930', foreground=MUTED,
                        font=('Segoe UI Semibold', 9), padding=(10, 9), borderwidth=0, relief='flat')
        style.map('Treeview.Heading', background=[('active', '#2b3038')])
        style.map('Treeview', background=[('selected', '#30486b')], foreground=[('selected', '#ffffff')])
        for orient in ('Vertical', 'Horizontal'):
            name = orient + '.TScrollbar'
            style.configure(name, background='#383d46', troughcolor=CARD, arrowcolor=MUTED,
                            borderwidth=0, arrowsize=12, gripcount=0, relief='flat')
            style.map(name, background=[('active', '#505967'), ('pressed', '#637083')])
        style.configure('Scan.Horizontal.TProgressbar', background=ACCENT, troughcolor=BG,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT, thickness=3)
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill='both', expand=True, padx=24, pady=20)
        header = tk.Frame(frame, bg=BG)
        header.pack(fill='x')
        tk.Label(header, text='LongPath', bg=BG, fg=FG, font=('Segoe UI Semibold', 24)).pack(side='left')
        tk.Label(header, text='ТОЛЬКО ЧТЕНИЕ', bg='#1e2930', fg='#9abac3',
                 font=('Segoe UI Semibold', 8), padx=10, pady=5).pack(side='right')
        tk.Label(frame, text='Найдите пути, которые мешают копированию и работе старых программ.',
                 bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', pady=(3,18))
        panel = tk.Frame(frame, bg=CARD, padx=16, pady=14)
        panel.pack(fill='x')
        tk.Label(panel, text='ПАПКА ДЛЯ ПРОВЕРКИ', bg=CARD, fg=MUTED,
                 font=('Segoe UI Semibold', 8)).pack(anchor='w', pady=(0,7))
        line = tk.Frame(panel, bg=CARD)
        line.pack(fill='x')
        self.folder = tk.StringVar(value=str(saved.get('folder', '')))
        self.path_entry = ttk.Entry(line, textvariable=self.folder)
        self.path_entry.pack(side='left', fill='x', expand=True)
        self.browse = ttk.Button(line, text='Выбрать…', command=self.choose, cursor='hand2')
        self.browse.pack(side='left', padx=(8,0))
        options = tk.Frame(panel, bg=CARD)
        options.pack(fill='x', pady=(12,0))
        tk.Label(options, text='Длина от', bg=CARD, fg=MUTED).pack(side='left')
        threshold = str(saved.get('threshold', '260'))
        self.threshold = tk.StringVar(value=threshold if threshold.isdigit() else '260')
        self.threshold_entry = ttk.Entry(options, textvariable=self.threshold, width=6)
        self.threshold_entry.pack(side='left', padx=6)
        tk.Label(options, text='Пропускать папки', bg=CARD, fg=MUTED).pack(side='left', padx=(10,4))
        self.exclusions = tk.StringVar(value=str(saved.get('exclusions', '.git;node_modules;.venv')))
        self.exclude_entry = ttk.Entry(options, textvariable=self.exclusions)
        self.exclude_entry.pack(side='left', fill='x', expand=True, padx=6)
        command_line = tk.Frame(panel, bg=CARD)
        command_line.pack(fill='x', pady=(12,0))
        self.start_button = ttk.Button(command_line, text='Найти длинные пути', command=self.start,
                                       style='Primary.TButton', cursor='hand2')
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(command_line, text='Остановить', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=(8,0))
        tk.Label(command_line, text='Порог — риск совместимости', bg=CARD, fg=MUTED,
                 font=('Segoe UI', 9)).pack(side='right')
        progress_track = tk.Frame(frame, bg=BG, height=3)
        progress_track.pack(fill='x', pady=(0,12))
        progress_track.pack_propagate(False)
        self.progress = ttk.Progressbar(progress_track, mode='determinate',
                                       style='Scan.Horizontal.TProgressbar', value=0)
        self.progress.pack(fill='both', expand=True)
        self.status = tk.StringVar(value='Готов к проверке')
        self.status_label = tk.Label(frame, textvariable=self.status, bg=BG, fg=MUTED,
                                    anchor='w', justify='left', wraplength=850)
        self.status_label.pack(fill='x', pady=(0,8))
        frame.bind('<Configure>', lambda event: self.status_label.configure(wraplength=max(200, event.width)))
        search_line = tk.Frame(frame, bg=BG)
        search_line.pack(fill='x', pady=(0,8))
        tk.Label(search_line, text='Результаты', bg=BG, fg=FG,
                 font=('Segoe UI Semibold', 11)).pack(side='left')
        self.count = tk.StringVar(value='0')
        tk.Label(search_line, textvariable=self.count, bg='#242933', fg=ACCENT,
                 font=('Segoe UI Semibold', 9), padx=8, pady=3).pack(side='left', padx=8)
        tk.Label(search_line, text='Фильтр по пути', bg=BG, fg=MUTED).pack(side='left', padx=(12,6))
        self.query = tk.StringVar()
        ttk.Entry(search_line, textvariable=self.query).pack(side='left', fill='x', expand=True)
        self.query.trace_add('write', self.filter_changed)
        table = tk.Frame(frame, bg=EDGE, padx=1, pady=1)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('length','kind','path'), show='headings', selectmode='browse')
        for name, label, width in [('length','Длина ↓',90), ('kind','Тип',85), ('path','Путь от выбранной папки',620)]:
            self.tree.heading(name, text=label, anchor='w')
            self.tree.column(name, width=width, minwidth=60, stretch=name=='path', anchor='w')
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.tag_configure('risk', foreground='#fde68a')
        self.tree.tag_configure('even', background='#1e2126')
        self.tree.bind('<<TreeviewSelect>>', self.selected)
        self.empty = tk.Label(self.tree, text='Здесь появятся длинные пути\n\nВыберите папку и начните проверку',
                              bg=CARD, fg=MUTED, font=('Segoe UI', 11), justify='center')
        self.empty.place(relx=.5, rely=.52, anchor='center')
        self.detail = tk.StringVar()
        detail_entry = ttk.Entry(frame, textvariable=self.detail, state='readonly')
        detail_entry.pack(fill='x', pady=8)
        actions = tk.Frame(frame, bg=BG)
        actions.pack(fill='x')
        ttk.Button(actions, text='Копировать путь', command=self.copy_path, cursor='hand2').pack(side='left')
        ttk.Button(actions, text='Открыть папку', command=self.open_folder, cursor='hand2').pack(side='left', padx=8)
        self.export_button = ttk.Button(actions, text='Сохранить TXT', command=self.export)
        self.export_button.pack(side='right')
        ttk.Button(actions, text='Ошибки обхода', command=self.show_errors).pack(side='left', padx=8)
        footer = tk.Frame(frame, bg=BG)
        tk.Label(footer, text='День 83 / 365 · неделя «Файлы»', bg=BG, fg=MUTED,
                 font=('Segoe UI', 8)).pack(side='left')
        tk.Label(footer, text='v1.0.0 · darkshade', bg=BG, fg=MUTED,
                 font=('Segoe UI', 8)).pack(side='right')
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
        if busy:
            self.progress.configure(mode='indeterminate')
            self.progress.start(12)
            self.empty.configure(text='Проверяю длину путей…')
        else:
            self.progress.stop()
            self.progress.configure(mode='determinate', value=0)

    def poll(self):
        for _ in range(50):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in ('export_done', 'export_error'):
                self.export_busy = False
                self.export_button.configure(state='normal')
                if kind == 'export_error':
                    messagebox.showerror('TXT', data, parent=self)
                else:
                    messagebox.showinfo('TXT', 'Отчёт сохранён.', parent=self)
            elif kind == 'progress':
                self.status.set(f'Проверено: {data[0]} · найдено: {data[1]}')
            else:
                self.busy = False
                self.lock(False)
                if kind == 'error':
                    self.status.set('Ошибка: ' + data)
                    self.empty.configure(text='Не удалось прочитать папку\n\nПроверьте путь и доступ')
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
        self.count.set('0')
        self.empty.place(relx=.5, rely=.52, anchor='center')

    def refilter(self):
        if self.render_job is not None:
            self.after_cancel(self.render_job)
        self.render_job = None
        if self.result is None:
            return
        self.clear_table()
        needle = self.query.get().casefold()
        self.pending = [entry for entry in self.result.entries if needle in entry.path.casefold()]
        self.count.set(str(len(self.pending)))
        if self.pending:
            self.empty.place_forget()
        else:
            self.empty.configure(text='Нет совпадений с фильтром' if needle else
                                 'В проверенной части совпадений нет' if self.result.cancelled or self.result.errors else
                                 'Путей от выбранного порога не найдено')
        r = self.result
        state = 'Остановлено' if r.cancelled else 'Готово'
        self.status.set(f'{state} · проверено: {r.visited} · найдено: {len(r.entries)} · видно: {len(self.pending)}'
                        f' · ошибки: {r.errors} · ссылки: {r.skipped} · исключено: {r.excluded}')
        self.insert_batch(self.render_generation, self.pending, 0)

    def insert_batch(self, generation, entries, offset):
        if generation != self.render_generation:
            return
        for index, entry in enumerate(entries[offset:offset+250], start=offset):
            tags = (('even',) if index % 2 == 0 else ()) + (('risk',) if entry.length >= 260 else ())
            key = self.tree.insert('', 'end', values=(entry.length, entry.kind, entry.relative),
                                   tags=tags)
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
        if self.result is None or self.export_busy:
            return
        # A native file dialog runs a nested event loop; scan completion can replace self.result.
        result = self.result
        needle = self.query.get().casefold()
        entries = tuple(entry for entry in result.entries if needle in entry.path.casefold())
        state = 'Остановлено · частичный результат' if result.cancelled else 'Завершено'
        if result.errors:
            state += ' · обход неполный: есть ошибки'
        header = (f'LongPath · {state}\nПапка: {result.root}\nПорог: {result.threshold} UTF-16'
                  f'\nФильтр: {self.query.get()}\nСтрок: {len(entries)}'
                  f'\nПроверено: {result.visited} · ошибки: {result.errors}'
                  f' · ссылки: {result.skipped} · исключено: {result.excluded}')
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.txt', filetypes=[('Текст', '*.txt')])
        if path:
            self.export_busy = True
            self.export_button.configure(state='disabled')
            def work():
                try:
                    write_report(path, entries, header)
                except Exception as exc:
                    self.events.put(('export_error', str(exc)))
                else:
                    self.events.put(('export_done', None))
            # Finish an explicitly requested save even if the window closes meanwhile.
            threading.Thread(target=work, daemon=False).start()

    def show_errors(self):
        if self.result:
            text = '\n'.join(self.result.error_paths) or 'Ошибок обхода нет.'
            if self.result.errors > len(self.result.error_paths):
                text += '\nПоказаны первые 100 путей.'
            messagebox.showinfo('Ошибки обхода', text, parent=self)

    def close(self):
        self.stop.set()
        if self.render_job is not None:
            self.after_cancel(self.render_job)
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
