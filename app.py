"""TypeForge Studio — local-first desktop typing assistant for Windows 10/11."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import os
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from core import (Profile, PRESETS, choose_typo, estimate_seconds, expand_template,
                  format_duration, keystroke_delay, parse_variables, prepare_text)
from storage import (ROOT, append_history, load_history, load_profile,
                     load_snippets, save_profile, save_snippets)
from windows_input import WindowsInput

C = {
    'bg': '#0b1020', 'surface': '#121a2d', 'surface2': '#19233a',
    'border': '#273650', 'text': '#e7edf9', 'muted': '#92a4c5',
    'accent': '#52b5ff', 'bright': '#78d9df', 'green': '#65dcb0',
    'danger': '#ff8297', 'amber': '#ffc978'
}
FONT = 'Segoe UI'

class TypeForge:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('TypeForge Studio  ·  v1.0')
        root.geometry('1120x745')
        root.minsize(970, 650)
        root.configure(bg=C['bg'])
        self.api = WindowsInput() if os.name == 'nt' else None
        self.events = queue.Queue()
        self.prefs = load_profile()
        self.library = load_snippets()
        self.pending = []
        self.session_text = ''
        self.session_kind = ''
        self.current_profile = self.prefs
        self.target = 0
        self.progress = 0
        self.started_at = 0.0
        self.session_elapsed = 0.0
        self.planned_duration = 0.0
        self.stop_signal = threading.Event()
        self.pause_signal = threading.Event()
        self.worker = None
        self.state = 'idle'
        self.last_f8 = self.last_f9 = self.last_mouse = False
        self.job_token = 0
        self._style()
        self._draw()
        self._load_controls(self.prefs)
        self._refresh_library()
        self._refresh_history()
        self._change_metrics()
        self.root.after(50, self._poll)
        self.root.protocol('WM_DELETE_WINDOW', self._close)

    def _style(self):
        sty = ttk.Style()
        sty.theme_use('clam')
        sty.configure('.', background=C['bg'], foreground=C['text'], font=(FONT, 10))
        sty.configure('TFrame', background=C['bg'])
        sty.configure('Panel.TFrame', background=C['surface'])
        sty.configure('TLabel', background=C['bg'], foreground=C['text'])
        sty.configure('Panel.TLabel', background=C['surface'], foreground=C['text'])
        sty.configure('Muted.TLabel', background=C['surface'], foreground=C['muted'])
        sty.configure('TButton', background=C['surface2'], foreground=C['text'],
                      borderwidth=0, padding=(13, 9), focuscolor=C['surface2'])
        sty.map('TButton', background=[('active', '#283952'), ('disabled', '#182239')],
                foreground=[('disabled', C['muted'])])
        sty.configure('Accent.TButton', background=C['accent'], foreground='#0b1020',
                      font=(FONT, 10, 'bold'), padding=(15, 10))
        sty.map('Accent.TButton', background=[('active', '#89cfff')])
        sty.configure('Warn.TButton', background='#492a3a', foreground=C['danger'])
        sty.map('Warn.TButton', background=[('active', '#5c3444')])
        sty.configure('TEntry', fieldbackground=C['surface2'], foreground=C['text'],
                      bordercolor=C['border'], padding=8)
        sty.configure('TCombobox', fieldbackground=C['surface2'], foreground=C['text'],
                      bordercolor=C['border'], padding=6, arrowcolor=C['accent'])
        sty.map('TCombobox', fieldbackground=[('readonly', C['surface2'])],
                foreground=[('readonly', C['text'])])
        sty.configure('TSpinbox', fieldbackground=C['surface2'], foreground=C['text'],
                      arrowcolor=C['accent'], bordercolor=C['border'], padding=5)
        sty.configure('TCheckbutton', background=C['surface'], foreground=C['text'])
        sty.map('TCheckbutton', background=[('active', C['surface'])])
        sty.configure('TNotebook', background=C['bg'], borderwidth=0)
        sty.configure('TNotebook.Tab', background=C['surface'], foreground=C['muted'], padding=(19, 11), borderwidth=0)
        sty.map('TNotebook.Tab', background=[('selected', C['surface2'])],
                foreground=[('selected', C['accent'])])
        sty.configure('Accent.Horizontal.TProgressbar', troughcolor=C['surface2'],
                      background=C['bright'], bordercolor=C['surface2'], thickness=10)

    def _label(self, parent, text, *, color=None, size=10, weight='normal', bg=None, **kwargs):
        return tk.Label(parent, text=text, bg=bg or C['surface'], fg=color or C['text'],
                        font=(FONT, size, weight), **kwargs)

    def _panel(self, parent, **pack):
        fr = tk.Frame(parent, bg=C['surface'], highlightthickness=1,
                      highlightbackground=C['border'])
        fr.pack(**pack)
        return fr

    def _draw(self):
        head = tk.Frame(self.root, bg=C['bg'])
        head.pack(fill='x', padx=26, pady=(21, 17))
        tk.Label(head, text='⌨', fg=C['bright'], bg=C['bg'], font=(FONT, 26)).pack(side='left', padx=(0, 11))
        titleframe = tk.Frame(head, bg=C['bg'])
        titleframe.pack(side='left')
        tk.Label(titleframe, text='TYPEFORGE', fg=C['text'], bg=C['bg'],
                 font=(FONT, 21, 'bold')).pack(anchor='w')
        tk.Label(titleframe, text='STUDIO  /  Precision typing workstation',
                 fg=C['muted'], bg=C['bg'], font=(FONT, 9)).pack(anchor='w')
        tk.Label(head, text='LOCAL ONLY  •  WINDOWS 10/11', fg=C['green'], bg=C['bg'],
                 font=(FONT, 9, 'bold')).pack(side='right', anchor='n', pady=10)

        body = tk.Frame(self.root, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=24, pady=(0, 8))
        left = tk.Frame(body, bg=C['bg'])
        left.pack(side='left', fill='both', expand=True)
        right = tk.Frame(body, bg=C['bg'], width=302)
        right.pack(side='right', fill='y', padx=(15, 0))
        right.pack_propagate(False)

        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill='both', expand=True)
        editor = tk.Frame(self.tabs, bg=C['surface'])
        library_tab = tk.Frame(self.tabs, bg=C['surface'])
        settings_tab = tk.Frame(self.tabs, bg=C['surface'])
        self.tabs.add(editor, text='  Editor  ')
        self.tabs.add(library_tab, text='  Library & Queue  ')
        self.tabs.add(settings_tab, text='  Preferences  ')
        self._draw_editor(editor)
        self._draw_library(library_tab)
        self._draw_settings(settings_tab)
        self._draw_dashboard(right)

        foot = tk.Frame(self.root, bg=C['bg'])
        foot.pack(fill='x', padx=27, pady=(0, 15))
        self.footer = tk.Label(foot, text='Ready. Click Start, then focus your destination window.',
                               fg=C['muted'], bg=C['bg'], anchor='w', font=(FONT, 9))
        self.footer.pack(side='left')
        tk.Label(foot, text='F8  Pause / resume    •    F9  Stop', bg=C['bg'],
                 fg=C['muted'], font=(FONT, 9)).pack(side='right')

    def _draw_editor(self, frame):
        top = tk.Frame(frame, bg=C['surface'])
        top.pack(fill='x', padx=18, pady=(18, 10))
        self._label(top, 'COMPOSE YOUR TEXT', color=C['muted'], size=9, weight='bold').pack(side='left')
        ttk.Button(top, text='Import .txt / .md', command=self._import_text).pack(side='right')
        ttk.Button(top, text='Paste', command=self._paste).pack(side='right', padx=8)
        box = tk.Frame(frame, bg=C['border'], padx=1, pady=1)
        box.pack(fill='both', expand=True, padx=18)
        self.editor = tk.Text(box, wrap='word', undo=True, bg=C['surface2'], fg=C['text'],
                              insertbackground=C['accent'], selectbackground='#245c82',
                              font=('Consolas', 11), relief='flat', padx=15, pady=15,
                              borderwidth=0, spacing2=3)
        self.editor.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(box, command=self.editor.yview)
        scrollbar.pack(side='right', fill='y')
        self.editor.configure(yscrollcommand=scrollbar.set)
        self.editor.insert('1.0', 'Welcome to TypeForge Studio!\n\nType or paste your text here.\nArabic: أهلاً وسهلاً 👋\n\nUse {{date}} and custom variables to personalize templates.')
        self.editor.bind('<<Modified>>', self._editor_changed)
        self.editor.bind('<Control-Return>', lambda _: self.start())

        bottom = tk.Frame(frame, bg=C['surface'])
        bottom.pack(fill='x', padx=18, pady=12)
        self.selection_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text='Type selection only', variable=self.selection_only).pack(side='left')
        ttk.Button(bottom, text='Save to Library', command=self._save_as_snippet).pack(side='right')
        ttk.Button(bottom, text='Preview', command=self._preview).pack(side='right', padx=8)
        self._label(frame, 'TEMPLATE VARIABLES  •  one per line (name=value)',
                    size=9, color=C['muted'], weight='bold').pack(anchor='w', padx=18, pady=(1, 6))
        self.vars_text = tk.Text(frame, height=3, bg=C['surface2'], fg=C['text'],
                                 insertbackground=C['accent'], font=('Consolas', 10),
                                 relief='flat', padx=12, pady=7)
        self.vars_text.pack(fill='x', padx=18, pady=(0, 17))
        self.vars_text.insert('1.0', 'name=Your Name')

    def _draw_library(self, frame):
        self._label(frame, 'SAVED SNIPPETS', size=14, weight='bold').pack(anchor='w', padx=18, pady=(18, 7))
        self._label(frame, 'Snippets are stored locally. Editor content is NOT autosaved.', color=C['muted'], size=9).pack(anchor='w', padx=18)
        wrap = tk.Frame(frame, bg=C['surface'])
        wrap.pack(fill='both', expand=True, padx=18, pady=13)
        self.saved = tk.Listbox(wrap, bg=C['surface2'], fg=C['text'], selectbackground='#244f6d',
                                relief='flat', highlightthickness=0, activestyle='none',
                                font=(FONT, 10), height=8)
        self.saved.pack(side='left', fill='both', expand=True)
        buttons = tk.Frame(wrap, bg=C['surface'])
        buttons.pack(side='right', fill='y', padx=(10, 0))
        for text, cmd in [('Load into Editor', self._load_snippet), ('Add to Queue', self._enqueue),
                          ('Delete Snippet', self._delete_snippet), ('Export Library', self._export_library),
                          ('Import Library', self._import_library)]:
            ttk.Button(buttons, text=text, command=cmd).pack(fill='x', pady=(0, 7))
        self._label(frame, 'BATCH QUEUE', size=14, weight='bold').pack(anchor='w', padx=18, pady=(0, 7))
        self.queue_list = tk.Listbox(frame, height=6, bg=C['surface2'], fg=C['text'],
                                     selectbackground='#244f6d', relief='flat',
                                     highlightthickness=0, font=(FONT, 10), activestyle='none')
        self.queue_list.pack(fill='x', padx=18)
        actions = tk.Frame(frame, bg=C['surface'])
        actions.pack(fill='x', padx=18, pady=12)
        ttk.Button(actions, text='Move Up', command=lambda: self._move_queue(-1)).pack(side='left', padx=(0, 7))
        ttk.Button(actions, text='Move Down', command=lambda: self._move_queue(1)).pack(side='left')
        ttk.Button(actions, text='Remove', command=self._remove_queue).pack(side='left', padx=7)
        ttk.Button(actions, text='Run Queue', style='Accent.TButton', command=lambda: self.start(batch=True)).pack(side='right')

    def _draw_settings(self, frame):
        self._label(frame, 'TYPING ENGINE', size=14, weight='bold').pack(anchor='w', padx=22, pady=(21, 16))
        inner = tk.Frame(frame, bg=C['surface'])
        inner.pack(fill='x', padx=22)
        self.profile_name = tk.StringVar(value=self.prefs.name)
        ttk.Label(inner, text='Preset profile', style='Panel.TLabel').grid(row=0, column=0, sticky='w', pady=8)
        profile_box = ttk.Combobox(inner, textvariable=self.profile_name, state='readonly', values=list(PRESETS))
        profile_box.grid(row=0, column=1, sticky='ew', padx=(22, 0))
        profile_box.bind('<<ComboboxSelected>>', lambda _: self._load_controls(PRESETS[self.profile_name.get()]))

        self.wpm = tk.IntVar(); self.jitter = tk.IntVar(); self.typo = tk.DoubleVar()
        self.punctuation = tk.IntVar(); self.paragraph = tk.IntVar(); self.countdown = tk.IntVar()
        fields = [('Target WPM', self.wpm, 10, 220, 5),
                  ('Rhythm variation (%)', self.jitter, 0, 65, 1),
                  ('Typo correction (%)', self.typo, 0, 6, .1),
                  ('Pause after punctuation (ms)', self.punctuation, 0, 3000, 20),
                  ('Pause after paragraphs (ms)', self.paragraph, 0, 5000, 20),
                  ('Focus countdown (seconds)', self.countdown, 2, 15, 1)]
        for idx, (label, variable, low, hi, step) in enumerate(fields, 1):
            ttk.Label(inner, text=label, style='Panel.TLabel').grid(row=idx, column=0, sticky='w', pady=9)
            ttk.Spinbox(inner, textvariable=variable, from_=low, to=hi, increment=step, width=18).grid(
                row=idx, column=1, sticky='ew', padx=(22, 0), pady=5)
        inner.columnconfigure(1, weight=1)
        self.shift_enter = tk.BooleanVar(); self.tabs_as_spaces = tk.BooleanVar()
        self.focus_loss = tk.BooleanVar()
        for label, variable in [('Use Shift+Enter instead of Enter for new lines (chat-safe)', self.shift_enter),
                                 ('Convert tabs to four spaces', self.tabs_as_spaces),
                                 ('Immediately pause if destination window loses focus', self.focus_loss)]:
            ttk.Checkbutton(frame, text=label, variable=variable).pack(anchor='w', padx=22, pady=6)
        ttk.Button(frame, text='Save Preferences', style='Accent.TButton', command=self._save_preferences).pack(
            anchor='w', padx=22, pady=14)
        self._label(frame, 'Safety: no remote server, no stealth mode. Use only where automated input is allowed.',
                    color=C['muted'], size=9, wraplength=590, justify='left').pack(anchor='w', padx=22, pady=(3, 12))

    def _draw_dashboard(self, container):
        panel = self._panel(container, fill='x', pady=(0, 13))
        self._label(panel, 'LIVE SESSION', color=C['muted'], size=9, weight='bold').pack(anchor='w', padx=16, pady=(16, 11))
        self.status_label = self._label(panel, '●  READY', color=C['green'], size=15, weight='bold')
        self.status_label.pack(anchor='w', padx=16)
        self.target_label = self._label(panel, 'Destination: not selected', color=C['muted'],
                                        size=9, wraplength=265, justify='left')
        self.target_label.pack(anchor='w', padx=16, pady=(10, 12))
        self.progressbar = ttk.Progressbar(panel, mode='determinate', maximum=100,
                                            style='Accent.Horizontal.TProgressbar')
        self.progressbar.pack(fill='x', padx=16)
        self.progress_label = self._label(panel, '0 / 0 characters', color=C['muted'], size=9)
        self.progress_label.pack(anchor='w', padx=16, pady=(6, 10))
        stats = tk.Frame(panel, bg=C['surface'])
        stats.pack(fill='x', padx=16, pady=(4, 13))
        self.stats_labels = {}
        for row, (key, title, init) in enumerate([
            ('wpm','TARGET WPM','65'),('eta','TIME LEFT','—'),('chars','TOTAL CHARS','0'),('words','WORDS','0')]):
            r, c = divmod(row, 2)
            tile = tk.Frame(stats, bg=C['surface2'], padx=11, pady=9)
            tile.grid(row=r, column=c, sticky='nsew', padx=(0, 5) if c == 0 else (5, 0), pady=5)
            self._label(tile, title, bg=C['surface2'], color=C['muted'], size=8).pack(anchor='w')
            lbl = self._label(tile, init, bg=C['surface2'], size=16, weight='bold')
            lbl.pack(anchor='w', pady=(2, 0))
            self.stats_labels[key] = lbl
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)

        controls = self._panel(container, fill='x', pady=(0, 13))
        self._label(controls, 'QUICK CONTROLS', color=C['muted'], size=9, weight='bold').pack(anchor='w', padx=16, pady=(15, 9))
        self.start_button = ttk.Button(controls, text='▶   START TYPING', style='Accent.TButton', command=self.start)
        self.start_button.pack(fill='x', padx=16, pady=4)
        self.pause_button = ttk.Button(controls, text='Ⅱ   PAUSE / RESUME', command=self.toggle_pause)
        self.pause_button.pack(fill='x', padx=16, pady=4)
        self.stop_button = ttk.Button(controls, text='■   STOP SESSION', style='Warn.TButton', command=self.stop)
        self.stop_button.pack(fill='x', padx=16, pady=(4, 16))

        activity = self._panel(container, fill='both', expand=True)
        self._label(activity, 'RECENT ACTIVITY', color=C['muted'], size=9, weight='bold').pack(anchor='w', padx=16, pady=(14, 8))
        self.history_box = tk.Listbox(activity, bg=C['surface'], fg=C['muted'], font=(FONT, 9),
                                      relief='flat', borderwidth=0, highlightthickness=0,
                                      selectbackground=C['surface2'], activestyle='none')
        self.history_box.pack(fill='both', expand=True, padx=13, pady=(0, 14))

    def _editor_changed(self, event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            if self.state == 'idle':
                self._change_metrics()

    def _load_controls(self, p):
        self.profile_name.set(p.name if p.name in PRESETS else 'Balanced')
        for var, value in [(self.wpm, p.wpm), (self.jitter, p.jitter), (self.typo, p.typo_percent),
                           (self.punctuation, p.punctuation_pause_ms), (self.paragraph, p.paragraph_pause_ms),
                           (self.countdown, p.countdown), (self.shift_enter, p.shift_enter),
                           (self.tabs_as_spaces, p.tabs_as_spaces), (self.focus_loss, p.stop_on_focus_loss)]:
            var.set(value)
        self._change_metrics()

    def _get_profile(self):
        try:
            return Profile(self.profile_name.get(), int(self.wpm.get()), int(self.jitter.get()),
                           float(self.typo.get()), int(self.punctuation.get()), int(self.paragraph.get()),
                           int(self.countdown.get()), bool(self.shift_enter.get()),
                           bool(self.tabs_as_spaces.get()), bool(self.focus_loss.get())).clean()
        except (TypeError, ValueError, tk.TclError):
            raise ValueError('Please enter valid numeric settings under Preferences.')

    def _save_preferences(self):
        try:
            self.prefs = self._get_profile()
            save_profile(self.prefs)
            self._status('Preferences saved locally.')
            self._change_metrics()
        except ValueError as err:
            messagebox.showerror('Settings', str(err))

    def _raw_text(self):
        if self.selection_only.get():
            try:
                return self.editor.get('sel.first', 'sel.last')
            except tk.TclError:
                raise ValueError('Select text in the editor first, or uncheck selection only.')
        return self.editor.get('1.0', 'end-1c')

    def _resolve(self, text, p):
        vars = parse_variables(self.vars_text.get('1.0', 'end-1c'))
        clip = None
        if '{{clipboard}}' in text or '{{ clipboard }}' in text:
            try:
                clip = self.root.clipboard_get()
            except tk.TclError:
                raise ValueError('The clipboard variable is used but clipboard text is unavailable.')
        return prepare_text(expand_template(text, vars, clipboard=clip), tabs_as_spaces=p.tabs_as_spaces)

    def _change_metrics(self):
        try:
            p = self._get_profile()
            src = self._raw_text() if not self.selection_only.get() else self.editor.get('1.0', 'end-1c')
            # Do not expand variables here: preview/start do exact validation.
            self.stats_labels['chars'].config(text=str(len(src)))
            self.stats_labels['words'].config(text=str(len(src.split())))
            self.stats_labels['wpm'].config(text=str(p.wpm))
            if self.state == 'idle':
                self.stats_labels['eta'].config(text=format_duration(estimate_seconds(src, p)))
        except (ValueError, tk.TclError):
            pass

    def _preview(self):
        try:
            p = self._get_profile()
            text = self._resolve(self._raw_text(), p)
            if not text.strip():
                raise ValueError('Your text is empty.')
        except ValueError as err:
            messagebox.showerror('Preview error', str(err))
            return
        win = tk.Toplevel(self.root)
        win.title('TypeForge — exact output preview')
        win.geometry('680x520')
        win.configure(bg=C['bg'])
        self._label(win, f'PREVIEW  ·  {len(text)} characters  ·  ~{format_duration(estimate_seconds(text, p))}',
                    bg=C['bg'], size=11, weight='bold', color=C['accent']).pack(anchor='w', padx=18, pady=14)
        preview = tk.Text(win, wrap='word', bg=C['surface2'], fg=C['text'], relief='flat',
                          insertbackground=C['accent'], padx=15, pady=15, font=('Consolas', 11))
        preview.pack(fill='both', expand=True, padx=18, pady=(0, 18))
        preview.insert('1.0', text)
        preview.config(state='disabled')

    def _import_text(self):
        path = filedialog.askopenfilename(filetypes=[('Text files', '*.txt *.md *.csv *.log'), ('All files', '*.*')])
        if not path:
            return
        try:
            data = Path(path).read_text(encoding='utf-8-sig')
            if len(data) > 600_000:
                raise ValueError('File is too large (maximum 600,000 characters).')
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', data)
            self.tabs.select(0)
        except (UnicodeError, OSError, ValueError) as err:
            messagebox.showerror('Import failed', str(err))

    def _paste(self):
        try:
            self.editor.insert('insert', self.root.clipboard_get())
        except tk.TclError:
            messagebox.showwarning('Clipboard', 'No text is available in your clipboard.')

    def _save_as_snippet(self):
        try:
            text = self._raw_text()
        except ValueError as err:
            messagebox.showerror('Library', str(err)); return
        if not text.strip():
            messagebox.showwarning('Library', 'Write some text first.'); return
        title = simpledialog.askstring('Save snippet', 'Snippet name:', parent=self.root)
        if not title or not title.strip():
            return
        self.library.append({'name': title.strip()[:120], 'text': text})
        save_snippets(self.library)
        self._refresh_library()
        self._status('Saved to local snippet library.')

    def _refresh_library(self):
        self.saved.delete(0, 'end')
        for it in self.library:
            self.saved.insert('end', f"  {it['name']}   ·   {len(it['text'])} chars")
        self._refresh_queue()

    def _selected_saved(self):
        sel = self.saved.curselection()
        if not sel:
            messagebox.showinfo('Select a snippet', 'Select a saved snippet first.')
            return None
        return sel[0]

    def _load_snippet(self):
        idx = self._selected_saved()
        if idx is None: return
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', self.library[idx]['text'])
        self.tabs.select(0)
        self._change_metrics()

    def _delete_snippet(self):
        idx = self._selected_saved()
        if idx is None: return
        if messagebox.askyesno('Delete snippet', f"Delete '{self.library[idx]['name']}' from the library?"):
            del self.library[idx]
            save_snippets(self.library)
            self._refresh_library()

    def _enqueue(self):
        idx = self._selected_saved()
        if idx is None: return
        self.pending.append(dict(self.library[idx]))
        self._refresh_queue()

    def _refresh_queue(self):
        if not hasattr(self, 'queue_list'): return
        self.queue_list.delete(0, 'end')
        for i, it in enumerate(self.pending, 1):
            self.queue_list.insert('end', f"{i:02d}   {it['name']}  ·  {len(it['text'])} chars")

    def _remove_queue(self):
        sel = self.queue_list.curselection()
        if sel:
            del self.pending[sel[0]]
            self._refresh_queue()

    def _move_queue(self, direction):
        sel = self.queue_list.curselection()
        if not sel: return
        i = sel[0]; j = i + direction
        if 0 <= j < len(self.pending):
            self.pending[i], self.pending[j] = self.pending[j], self.pending[i]
            self._refresh_queue()
            self.queue_list.selection_set(j)

    def _export_library(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                Path(path).write_text(json.dumps(self.library, indent=2, ensure_ascii=False), encoding='utf-8')
            except OSError as err:
                messagebox.showerror('Export failed', str(err))

    def _import_library(self):
        path = filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if not isinstance(data, list) or len(data) > 1000:
                raise ValueError('Expected a list of up to 1000 snippets.')
            items = []
            for it in data:
                if not isinstance(it, dict) or not isinstance(it.get('text'), str) or not isinstance(it.get('name'), str):
                    raise ValueError('One or more snippets have an invalid format.')
                if len(it['text']) > 600_000:
                    raise ValueError('A snippet is too large.')
                items.append({'name': it['name'][:120], 'text': it['text']})
            self.library.extend(items)
            save_snippets(self.library)
            self._refresh_library()
        except (ValueError, UnicodeError, OSError) as err:
            messagebox.showerror('Import failed', str(err))

    def _refresh_history(self):
        self.history_box.delete(0, 'end')
        for it in reversed(load_history()[-12:]):
            self.history_box.insert('end', f"{it.get('date', '?')}   {it.get('chars', 0)} chars  ·  {it.get('result', '?')}")

    def _status(self, msg, mode=None):
        self.footer.config(text=msg)
        if mode:
            display = {'idle': ('●  READY', C['green']), 'arming': ('◉  ARMING', C['amber']),
                       'typing': ('▶  TYPING', C['green']), 'paused': ('Ⅱ  PAUSED', C['amber'])}
            title, color = display.get(mode, display['idle'])
            self.status_label.config(text=title, fg=color)

    def start(self, batch=False):
        if self.state != 'idle':
            messagebox.showinfo('Session active', 'Stop your current session before starting another.')
            return
        if not self.api:
            messagebox.showinfo('Windows required', 'Keyboard injection is available only on Windows 10/11.'); return
        try:
            p = self._get_profile()
            if batch:
                if not self.pending:
                    raise ValueError('Add saved snippets to your batch queue first.')
                # Intentional separator. Shift+Enter default prevents chat submission.
                raw = '\n\n'.join(it['text'] for it in self.pending)
            else:
                raw = self._raw_text()
            text = self._resolve(raw, p)
            if not text.strip(): raise ValueError('Nothing to type.')
            if len(text) > 600_000: raise ValueError('Text is too long (600,000 characters maximum).')
        except ValueError as err:
            messagebox.showerror('Cannot start', str(err))
            return
        if not p.shift_enter and '\n' in text:
            if not messagebox.askyesno('Enter may submit a form',
                    'Normal Enter is enabled. In chat or form apps it could SEND messages or SUBMIT forms. Continue?'):
                return
        self.current_profile = p
        self.planned_duration = estimate_seconds(text, p)
        save_profile(p)
        self.session_kind = 'Batch' if batch else 'Editor'
        self.session_text = text
        self.progress = 0
        self.target = 0
        self.started_at = time.monotonic()
        self.session_elapsed = 0
        self.stop_signal = threading.Event()
        self.pause_signal = threading.Event()
        self._change_metrics()
        self._arm(p.countdown, resume=False)

    def _arm(self, seconds, resume):
        self.job_token += 1
        token = self.job_token
        self.state = 'arming'
        self._status(f'Click the destination text box. Capturing target in {seconds}s…', 'arming')
        self.start_button.state(['disabled'])

        def tick(left):
            if token != self.job_token or self.state != 'arming': return
            if left > 0:
                self._status(f'Focus the destination window now — {left}s remaining.', 'arming')
                self.root.after(1000, lambda: tick(left - 1))
                return
            hwnd = self.api.foreground()
            if not hwnd or not self.api.valid_target(hwnd):
                self._arm_failed('No valid destination was focused. Try again.')
                return
            if resume and hwnd != self.target:
                self._arm_failed('Resume canceled: select the ORIGINAL destination window, then retry.', paused=True)
                return
            if not resume:
                self.target = hwnd
                self.target_label.config(text='Destination: ' + self.api.title(hwnd)[:80])
                self._start_worker()
            else:
                self.pause_signal.clear()
            self.state = 'typing'
            self._status('Typing in ' + self.api.title(hwnd)[:65], 'typing')
        tick(seconds)

    def _arm_failed(self, msg, paused=False):
        self.state = 'paused' if paused else 'idle'
        self._status(msg, self.state)
        if not paused:
            self.start_button.state(['!disabled'])

    def _start_worker(self):
        self.worker = threading.Thread(target=self._run_typing, daemon=True, name='TypeForgeTyping')
        self.worker.start()

    def _wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.stop_signal.is_set(): return False
            if self.pause_signal.is_set():
                return False
            time.sleep(min(.02, max(0, end - time.monotonic())))
        return True

    def _run_typing(self):
        text = self.session_text
        p = self.current_profile
        rng = random.Random()
        prev = ''
        pos = 0
        try:
            while pos < len(text) and not self.stop_signal.is_set():
                if self.pause_signal.is_set():
                    time.sleep(.04); continue
                if not self.api.is_window(self.target):
                    self.pause_signal.set()
                    self.events.put(('paused', 'Destination was closed. Stop the session.'))
                    continue
                if p.stop_on_focus_loss and self.api.foreground() != self.target:
                    self.pause_signal.set()
                    self.events.put(('paused', 'Destination changed. Click Resume to return to the original window.'))
                    continue
                if self.api.modifiers_pressed():
                    time.sleep(.04)
                    continue
                ch = text[pos]
                delay = keystroke_delay(ch, prev, p, rng)
                if not self._wait(delay): continue
                if self.stop_signal.is_set() or self.pause_signal.is_set() or self.api.modifiers_pressed(): continue
                if p.stop_on_focus_loss and self.api.foreground() != self.target:
                    self.pause_signal.set()
                    self.events.put(('paused', 'Typing paused because focus changed.'))
                    continue
                wrong = choose_typo(ch, p, rng)
                if wrong:
                    # Wrong-character + backspace is one short, non-interruptible unit;
                    # resume always starts after the last correctly typed character.
                    self.api.type_char(wrong)
                    time.sleep(.08)
                    self.api.backspace()
                    time.sleep(.075)
                self.api.type_char(ch, shift_enter=p.shift_enter)
                pos += 1
                prev = ch
                if pos % 3 == 0 or pos == len(text):
                    self.events.put(('progress', pos))
            self.events.put(('finished', pos, bool(self.stop_signal.is_set())))
        except Exception as err:
            self.events.put(('failed', str(err), pos))

    def toggle_pause(self):
        if self.state == 'typing':
            self.pause_signal.set()
            self.state = 'paused'
            self._status('Paused. Press Resume, then refocus the same window.', 'paused')
        elif self.state == 'paused':
            if not self.api or not self.target or not self.api.is_window(self.target):
                messagebox.showerror('Cannot resume', 'The original destination is no longer available. Stop and restart.')
                return
            self._arm(3, resume=True)

    def stop(self):
        if self.state == 'idle': return
        self.job_token += 1
        self.stop_signal.set()
        self.pause_signal.clear()
        if self.worker and self.worker.is_alive():
            self._status('Stopping after current keystroke…')
        else:
            self._end(self.progress, stopped=True)

    def _end(self, count, stopped=False, error=None):
        if self.state == 'idle' and not self.session_text: return
        self.job_token += 1
        self.state = 'idle'
        self.progress = count
        self.start_button.state(['!disabled'])
        result = 'Failed' if error else ('Stopped' if stopped else 'Done')
        append_history({'date': datetime.now().strftime('%m/%d %H:%M'),
                        'chars': count, 'result': result})
        self._refresh_history()
        if not stopped and not error:
            self.progressbar['value'] = 100
            self._status(f'Done — {count} characters typed. Ready for a new session.', 'idle')
        elif error:
            self._status(f'Error: {error}', 'idle')
            messagebox.showerror('Typing failed', error)
        else:
            self._status(f'Stopped after {count} characters.', 'idle')
        self.session_text = ''
        self._change_metrics()

    def _poll(self):
        if self.api:
            # Key edge detection. F9 always stops; F8 pauses/arms resume.
            f8 = self.api.held(0x77)
            f9 = self.api.held(0x78)
            if f9 and not self.last_f9 and self.state != 'idle': self.stop()
            elif f8 and not self.last_f8 and self.state in ('typing', 'paused'): self.toggle_pause()
            self.last_f8, self.last_f9 = f8, f9
            mouse = self.api.held(0x01) or self.api.held(0x02)
            if mouse and not self.last_mouse and self.state == 'typing' and self.api.foreground() == self.target:
                self.toggle_pause()  # a click may reposition the caret within the target
            self.last_mouse = mouse
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'progress':
                    self.progress = event[1]
                    total = max(1, len(self.session_text))
                    self.progressbar['value'] = 100 * self.progress / total
                    self.progress_label.config(text=f'{self.progress:,} / {total:,} characters')
                    self.stats_labels['chars'].config(text=f'{total:,}')
                    self.stats_labels['words'].config(text=str(len(self.session_text.split())))
                    self.stats_labels['wpm'].config(text=str(self.current_profile.wpm))
                    self.stats_labels['eta'].config(text=format_duration(
                        self.planned_duration * max(0, 1 - self.progress / total)))
                elif kind == 'paused' and self.state != 'idle':
                    self.state = 'paused'; self._status(event[1], 'paused')
                elif kind == 'finished' and self.state != 'idle':
                    self._end(event[1], stopped=event[2])
                elif kind == 'failed' and self.state != 'idle':
                    self._end(event[2], error=event[1])
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def _close(self):
        self.job_token += 1
        self.stop_signal.set()
        self.pause_signal.clear()
        self.root.destroy()


def main():
    root = tk.Tk()
    TypeForge(root)
    root.mainloop()

if __name__ == '__main__':
    main()