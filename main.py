import os, sqlite3, hashlib, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usrdata.db')
FONT = 'Segoe UI' if os.name == 'nt' else 'DejaVu Sans'

# ---------------------------------------------------------------- themes
THEMES = {
    'dark': dict(bg='#0f1620', panel='#182231', panel2='#212d3f', fg='#e8edf3',
                 dim='#8fa0b5', line='#2c3a4d', green='#3ecf8e', amber='#f5a623',
                 red='#e5484d', blue='#4fa3ff', info='#7c8ba1', band='#14332a',
                 on_accent='#ffffff'),
    'light': dict(bg='#eef1f6', panel='#ffffff', panel2='#f4f6fa', fg='#16202e',
                  dim='#5f7086', line='#d5dde8', green='#12855a', amber='#a86200',
                  red='#c62828', blue='#1f6feb', info='#6b7a8f', band='#e3f5ec',
                  on_accent='#ffffff'),
}
C = dict(THEMES['dark'])          # live palette; widgets read this at build time


def set_theme(name):
    C.clear()
    C.update(THEMES.get(name, THEMES['dark']))


def sc(st):
    """Colour for a status key."""
    return {'ok': C['green'], 'warn': C['amber'], 'bad': C['red'],
            'info': C['info'], 'none': C['dim']}[st]


# ------------------------------------------------------------- parameters
# key: (label, unit, ok_lo, ok_hi, warn_lo, warn_hi, kind)
#   range -> medical range, can go amber or red
#   goal  -> a target you aim for; falling short is amber, never red
#   info  -> tracked and charted, never flagged (no universal normal)
VITALS = {
    'hr':      ('Resting HR', 'bpm', 60, 100, 50, 110, 'range'),
    'spo2':    ('SpO2', '%', 95, 100, 92, 100, 'range'),
    'sys':     ('BP systolic', 'mmHg', 90, 120, 85, 140, 'range'),
    'dia':     ('BP diastolic', 'mmHg', 60, 80, 55, 90, 'range'),
    'temp':    ('Temperature', 'C', 36.1, 37.2, 35.8, 37.8, 'range'),
    'glucose': ('Fasting glucose', 'mg/dL', 70, 99, 60, 125, 'range'),
    'sleep':   ('Sleep', 'h', 7, 9, 6, 10, 'range'),
    'steps':   ('Steps', 'steps', 7000, 99999, 4000, 99999, 'goal'),
    'water':   ('Water', 'L', 2.0, 6.0, 1.2, 6.0, 'goal'),
    'mood':    ('Mood / energy', '/5', 4, 5, 3, 5, 'goal'),
    'weight':  ('Weight', 'kg', 0, 0, 0, 0, 'info'),
}
ORDER = ['hr', 'spo2', 'sys', 'dia', 'temp', 'glucose',
         'sleep', 'steps', 'water', 'mood', 'weight']

# Short names for the trends table, which has 13 columns and no room for
# "BP diastolic" spelled out.
SHORT = {'hr': 'HR', 'spo2': 'SpO2', 'sys': 'Sys', 'dia': 'Dia', 'temp': 'Temp',
         'glucose': 'Gluc', 'sleep': 'Sleep', 'steps': 'Steps', 'water': 'Water',
         'mood': 'Mood', 'weight': 'Wt'}

# Shown under the entry field so the number means the right thing.
HINTS = {
    'glucose': 'measure fasting, before breakfast',
    'steps': 'daily total',
    'water': 'plain water, litres',
    'mood': '1 = drained, 5 = great',
    'weight': 'no normal range - tracked as a trend',
}


def kind(k):
    return VITALS[k][6]


def status(key, v):
    if v is None:
        return 'none'
    if kind(key) == 'info':
        return 'info'
    _, _, lo, hi, wlo, whi = VITALS[key][:6]
    if lo <= v <= hi:
        return 'ok'
    if wlo <= v <= whi:
        return 'warn'
    return 'warn' if kind(key) == 'goal' else 'bad'


def num(v):
    try:
        return None if v in (None, '') else float(v)
    except (TypeError, ValueError):
        return None


def g(v):
    return f'{v:g}' if v is not None else '--'


# sdatabase
class DB:
    def __init__(self, path=None):
        self.c = sqlite3.connect(path or DB_PATH)
        self.c.row_factory = sqlite3.Row
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, pw TEXT,
            name TEXT, age INTEGER, gender TEXT, weight REAL, height REAL,
            theme TEXT DEFAULT 'dark');
        CREATE TABLE IF NOT EXISTS readings(
            id INTEGER PRIMARY KEY, uid INTEGER, day TEXT, notes TEXT,
            UNIQUE(uid, day));
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY, uid INTEGER, day TEXT, kind TEXT, text TEXT);
        ''')
        self._migrate()
        self.c.commit()

    def _migrate(self):
        """Add any columns a older database file is missing, so upgrading
        the app never means losing your data."""
        for table, wanted in (('readings', [(k, 'REAL') for k in ORDER] + [('attachment','TEXT')]),
                              ('users', [('theme', "TEXT DEFAULT 'dark'")])):
            have = {r['name'] for r in self.c.execute(f'PRAGMA table_info({table})')}
            for col, decl in wanted:
                if col not in have:
                    self.c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {decl}')

    @staticmethod
    def _hash(pw, salt):
        return hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 100_000).hex()

    def signup(self, username, pw, **p):
        if not username or not pw:
            raise ValueError('Username and password are both required.')
        if len(pw) < 6:
            raise ValueError('Use a password of at least 6 characters.')
        if self.c.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            raise ValueError('That username is already taken.')
        salt = os.urandom(16).hex()
        cur = self.c.execute(
            'INSERT INTO users(username,salt,pw,name,age,gender,weight,height,theme) '
            'VALUES(?,?,?,?,?,?,?,?,?)',
            (username, salt, self._hash(pw, salt), p.get('name', ''), p.get('age'),
             p.get('gender', ''), p.get('weight'), p.get('height'), 'dark'))
        self.c.commit()
        return cur.lastrowid

    def login(self, username, pw):
        u = self.c.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not u or self._hash(pw, u['salt']) != u['pw']:
            return None
        return dict(u)

    def user(self, uid):
        return dict(self.c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())

    def update_profile(self, uid, **f):
        self.c.execute('UPDATE users SET name=?,age=?,gender=?,weight=?,height=? WHERE id=?',
                       (f['name'], f['age'], f['gender'], f['weight'], f['height'], uid))
        self.c.commit()

    def set_theme(self, uid, theme):
        self.c.execute('UPDATE users SET theme=? WHERE id=?', (theme, uid))
        self.c.commit()

    def readings(self, uid):
        return [dict(r) for r in self.c.execute(
            'SELECT * FROM readings WHERE uid=? ORDER BY day', (uid,))]

    def save_reading(self, uid, day, vals, notes='', attachment=''):
        cols = ','.join(ORDER)
        marks = ','.join('?' * len(ORDER))
        self.c.execute(
            f'INSERT INTO readings(uid,day,{cols},notes) VALUES(?,?,{marks},?) '
            f'ON CONFLICT(uid,day) DO UPDATE SET '
            + ','.join(f'{k}=excluded.{k}' for k in ORDER) + ',notes=excluded.notes,attachment=excluded.attachment',
            [uid, day] + [vals.get(k) for k in ORDER] + [notes,attachment])
        self.c.commit()

    def history(self, uid):
        return [dict(r) for r in self.c.execute(
            'SELECT * FROM history WHERE uid=? ORDER BY day DESC', (uid,))]

    def add_history(self, uid, day, kind_, text):
        self.c.execute('INSERT INTO history(uid,day,kind,text) VALUES(?,?,?,?)',
                       (uid, day, kind_, text))
        self.c.commit()

    def del_history(self, hid):
        self.c.execute('DELETE FROM history WHERE id=?', (hid,))
        self.c.commit()


# ---------------------------------------------------------------- analysis
def current_weight(user, readings):
    """Latest logged weight wins over the signup figure, so BMI stays current."""
    for r in reversed(readings):
        w = num(r.get('weight'))
        if w:
            return w
    return num(user.get('weight'))


def derived(user, r, readings=()):
    out = {}
    h, w = num(user.get('height')), current_weight(user, list(readings))
    if h and w and h > 0:
        out['BMI'] = (round(w / (h / 100) ** 2, 1), 'kg/m2')
    s, d = num(r.get('sys')), num(r.get('dia'))
    if s and d:
        out['Pulse pressure'] = (round(s - d), 'mmHg')
        out['Mean arterial pressure'] = (round(d + (s - d) / 3), 'mmHg')
    sl = num(r.get('sleep'))
    if sl is not None:
        out['Sleep debt vs 8h'] = (round(8 - sl, 1), 'h')
    st = num(r.get('steps'))
    if st is not None:
        out['Distance (approx)'] = (round(st * 0.762 / 1000, 1), 'km')
    return out


def anomalies(readings):
    out = []
    for r in readings:
        for k in ORDER:
            st = status(k, num(r.get(k)))
            if st in ('warn', 'bad'):
                label_, unit, lo, hi = VITALS[k][:4]
                target = (f'target {lo:g}+' if kind(k) == 'goal'
                          else f'normal {lo:g}-{hi:g}')
                out.append({'day': r['day'], 'status': st,
                            'text': f'{label_} {num(r[k]):g} {unit} ({target})'})
    return sorted(out, key=lambda a: a['day'], reverse=True)


def watch_list(readings, user):
    out = []
    recent = readings[-7:]
    if len(recent) < 3:
        return [('none', 'Log at least 3 days to start spotting patterns.')]
    n = len(recent)

    def avg(k):
        vs = [num(r.get(k)) for r in recent]
        vs = [v for v in vs if v is not None]
        return sum(vs) / len(vs) if vs else None

    s, d, hr, sl, sp = avg('sys'), avg('dia'), avg('hr'), avg('sleep'), avg('spo2')
    gl, stp, wt, md = avg('glucose'), avg('steps'), avg('water'), avg('mood')

    if (s and s >= 130) or (d and d >= 85):
        out.append(('bad', f'Blood pressure has averaged {s:.0f}/{d:.0f} over {n} days. '
                           'Sustained readings in this range are worth a doctor visit.'))
    elif s and s >= 120:
        out.append(('warn', f'Systolic has averaged {s:.0f} over {n} days, above the '
                            'under-120 optimal range.'))
    if gl:
        if gl >= 126:
            out.append(('bad', f'Fasting glucose has averaged {gl:.0f} mg/dL over {n} days. '
                               'Repeated fasting readings at 126+ should be confirmed with a '
                               'lab test, not a home meter.'))
        elif gl >= 100:
            out.append(('warn', f'Fasting glucose has averaged {gl:.0f} mg/dL over {n} days, '
                                'inside the 100-125 prediabetes band.'))
        elif gl < 70:
            out.append(('bad', f'Fasting glucose has averaged {gl:.0f} mg/dL over {n} days, '
                               'below the usual 70 floor.'))
    if hr and hr > 100:
        out.append(('warn', f'Resting heart rate has averaged {hr:.0f} bpm over {n} days, '
                            'above the usual 60-100 resting range.'))
    if sp and sp < 95:
        out.append(('bad', f'SpO2 has averaged {sp:.0f}% over {n} days. Readings under 95% '
                           'that persist should be checked, and finger clips misread easily.'))
    if sl and sl < 6.5:
        out.append(('warn', f'Sleep has averaged {sl:.1f}h over {n} days, under the '
                            '7-9h commonly recommended for adults.'))
    if stp and stp < 5000:
        out.append(('warn', f'Steps have averaged {stp:,.0f}/day over {n} days. '
                            'Lifestyle habit, not a medical reading.'))
    if wt and wt < 1.5:
        out.append(('warn', f'Water has averaged {wt:.1f}L/day over {n} days.'))
    if md and md <= 2.5:
        out.append(('warn', f'Mood/energy has averaged {md:.1f}/5 over {n} days. If low mood '
                            'persists for weeks, that is worth talking to someone about.'))

    b = derived(user, {}, readings).get('BMI')
    if b:
        v = b[0]
        if v >= 30:
            out.append(('warn', f'BMI {v} is in the obese range (30+).'))
        elif v >= 25:
            out.append(('warn', f'BMI {v} is in the overweight range (25-29.9).'))
        elif v < 18.5:
            out.append(('warn', f'BMI {v} is in the underweight range (under 18.5).'))
    if not out:
        out.append(('ok', f'Nothing sustained across your last {n} readings.'))
    return out


# ---------------------------------------------------------------- widgets
def label(parent, text, size=11, color=None, bold=False, **kw):
    return tk.Label(parent, text=text, bg=kw.pop('bg', C['panel']),
                    fg=color or C['fg'],
                    font=(FONT, size, 'bold' if bold else 'normal'),
                    anchor=kw.pop('anchor', 'w'), **kw)


def card(parent, title=None):
    f = tk.Frame(parent, bg=C['panel'], highlightbackground=C['line'], highlightthickness=1)
    if title:
        label(f, title.upper(), 9, C['dim'], True).pack(fill='x', padx=14, pady=(12, 6))
    return f


def button(parent, text, cmd, kind_='primary', **kw):
    bg = {'primary': C['blue'], 'ghost': C['panel2'], 'danger': C['red']}[kind_]
    fg = C['fg'] if kind_ == 'ghost' else C['on_accent']
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=(FONT, 10, 'bold'),
                     relief='flat', bd=0, padx=16, pady=8, cursor='hand2',
                     activebackground=bg, activeforeground=fg, **kw)


def entry(parent, show=None, width=22):
    return tk.Entry(parent, bg=C['panel2'], fg=C['fg'], insertbackground=C['blue'],
                    relief='flat', font=(FONT, 11), width=width, show=show,
                    highlightthickness=1, highlightbackground=C['line'],
                    highlightcolor=C['blue'])


def field(parent, text, show=None, value='', hint=''):
    label(parent, text, 9, C['dim'], True).pack(fill='x', pady=(8, 2))
    e = entry(parent, show=show)
    e.insert(0, '' if value in (None, '') else str(value))
    e.pack(fill='x', ipady=5)
    if hint:
        label(parent, hint, 8, C['dim']).pack(fill='x')
    return e


class Chart(tk.Canvas):
    """Line chart with a shaded normal band. No matplotlib needed."""

    def __init__(self, parent, key, height=170, **kw):
        super().__init__(parent, bg=C['panel2'], height=height, highlightthickness=0, **kw)
        self.key, self.rows = key, []
        self.bind('<Configure>', lambda e: self.draw())

    def set_data(self, rows):
        self.rows = rows
        self.draw()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or h < 60:
            return
        _, _, lo, hi = VITALS[self.key][:4]
        banded = kind(self.key) != 'info'
        pts = [(r['day'], num(r.get(self.key))) for r in self.rows]
        pts = [(d, v) for d, v in pts if v is not None]
        if not pts:
            self.create_text(w / 2, h / 2, text='No data yet', fill=C['dim'], font=(FONT, 10))
            return

        vals = [v for _, v in pts]
        anchors = vals + ([lo, min(hi, max(vals) * 1.1)] if banded else [])
        vmin, vmax = min(anchors), max(anchors)
        span = (vmax - vmin) or 1
        vmin, vmax = vmin - span * 0.15, vmax + span * 0.15
        pl, pr, pt, pb = 48, 14, 14, 24

        def X(i):
            return pl + (w - pl - pr) * (i / max(1, len(pts) - 1))

        def Y(v):
            return pt + (h - pt - pb) * (1 - (v - vmin) / (vmax - vmin))

        if banded:
            self.create_rectangle(pl, Y(min(hi, vmax)), w - pr, Y(max(lo, vmin)),
                                  fill=C['band'], outline='')
        for gv in (vmin, (vmin + vmax) / 2, vmax):
            self.create_line(pl, Y(gv), w - pr, Y(gv), fill=C['line'])
            self.create_text(pl - 6, Y(gv), text=f'{gv:,.0f}', fill=C['dim'],
                             font=(FONT, 8), anchor='e')

        coords = []
        for i, (_, v) in enumerate(pts):
            coords += [X(i), Y(v)]
        if len(coords) >= 4:
            self.create_line(*coords, fill=C['blue'], width=2)
        for i, (_, v) in enumerate(pts):
            self.create_oval(X(i) - 3.5, Y(v) - 3.5, X(i) + 3.5, Y(v) + 3.5,
                             fill=sc(status(self.key, v)), outline='')
        self.create_text(pl, h - 8, text=pts[0][0][5:], fill=C['dim'], font=(FONT, 8), anchor='w')
        self.create_text(w - pr, h - 8, text=pts[-1][0][5:], fill=C['dim'],
                         font=(FONT, 8), anchor='e')


# ---------------------------------------------------------------- app
class App(tk.Tk):
    def __init__(self, db, uid):
        super().__init__()
        self.title('AeroVital')
        self.geometry('1180x740')
        self.minsize(980, 640)
        self.db, self.uid = db, uid
        self.container = tk.Frame(self)
        self.container.pack(fill='both', expand=True)
        self.apply_theme(self.db.user(self.uid).get('theme') or 'dark')
        self.show_main()

    def apply_theme(self, name):
        set_theme(name)
        self.configure(bg=C['bg'])
        self.container.configure(bg=C['bg'])
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('T.Treeview', background=C['panel2'], fieldbackground=C['panel2'],
                    foreground=C['fg'], rowheight=27, borderwidth=0, font=(FONT, 10))
        s.configure('T.Treeview.Heading', background=C['panel'], foreground=C['dim'],
                    font=(FONT, 9, 'bold'), relief='flat')
        s.map('T.Treeview', background=[('selected', C['blue'])])
        s.configure('TCombobox', fieldbackground=C['panel2'], background=C['panel2'],
                    foreground=C['fg'], arrowcolor=C['dim'])

    def toggle_theme(self):
        new = 'light' if C is not None and C['bg'] == THEMES['dark']['bg'] else 'dark'
        self.apply_theme(new)
        if self.uid:
            self.db.set_theme(self.uid, new)
            self.show_main('Profile')

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()


    # ------------------------------------------------ shell
    def show_main(self, tab='Dashboard'):
        self.clear()
        self.container.configure(bg=C['bg'])
        self.user = self.db.user(self.uid)
        shell = tk.Frame(self.container, bg=C['bg'])
        shell.pack(fill='both', expand=True)

        side = tk.Frame(shell, bg=C['panel'], width=190)
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        label(side, 'AeroVital', 15, C['fg'], True).pack(fill='x', padx=18, pady=(20, 2))
        label(side, self.user['name'] or self.user['username'], 9,
              C['dim']).pack(fill='x', padx=18, pady=(0, 8))

        for t in ['Dashboard', 'Add Reading', 'Analysis', 'Medical Record', 'Profile']:
            on = t == tab
            tk.Button(side, text='  ' + t, command=lambda t=t: self.show_main(t),
                      bg=C['panel2'] if on else C['panel'],
                      fg=C['blue'] if on else C['dim'],
                      font=(FONT, 10, 'bold' if on else 'normal'), relief='flat', bd=0,
                      anchor='w', pady=10, cursor='hand2',
                      activebackground=C['panel2']).pack(fill='x', padx=10, pady=1)
        tk.Frame(side, bg=C['panel']).pack(fill='both', expand=True)
        for txt, cmd in (('  Switch theme', self.toggle_theme), ('  Log out', self.logout)):
            tk.Button(side, text=txt, command=cmd, bg=C['panel'], fg=C['dim'],
                      font=(FONT, 9), relief='flat', bd=0, anchor='w', pady=8,
                      cursor='hand2', activebackground=C['panel']).pack(fill='x', padx=10)
        tk.Frame(side, bg=C['panel'], height=10).pack()

        body = tk.Frame(shell, bg=C['bg'])
        body.pack(side='left', fill='both', expand=True)
        import dashboard
        import charts
        {'Dashboard': lambda parent: dashboard.p_dashboard(self, parent), 'Add Reading': self.p_add,
         'Analysis': lambda parent: charts.p_analysis(self, parent),
         'Medical Record': self.p_record, 'Profile': self.p_profile}[tab](body)

    def logout(self):
        self.destroy()
        from login import LoginApp
        LoginApp().mainloop()

    def header(self, parent, title, sub=''):
        h = tk.Frame(parent, bg=C['bg'])
        h.pack(fill='x', padx=22, pady=(20, 12))
        label(h, title, 18, C['fg'], True, bg=C['bg']).pack(fill='x')
        if sub:
            label(h, sub, 9, C['dim'], bg=C['bg']).pack(fill='x')

    def scrollable(self, parent):
        canvas = tk.Canvas(parent, bg=C['bg'], highlightthickness=0)
        bar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        inner = tk.Frame(canvas, bg=C['bg'])
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        win = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units'))
        canvas.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
        canvas.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))
        return inner

    # ------------------------------------------------ dashboard
    def p_dashboard(self, body):
        rows = self.db.readings(self.uid)
        latest = rows[-1] if rows else {}
        self.header(body, f"Hello, {(self.user['name'] or self.user['username']).split()[0]}",
                    f"Latest reading: {latest['day']}" if rows else 'No readings yet')
        page = self.scrollable(body)

        if not rows:
            c = card(page, 'Get started')
            c.pack(fill='x', padx=22, pady=6)
            label(c, 'Add your first reading to see vitals, trends and analysis.',
                  10, C['dim']).pack(fill='x', padx=14, pady=(0, 12))
            button(c, 'Add Reading', lambda: self.show_main('Add Reading')).pack(
                anchor='w', padx=14, pady=(0, 14))
            return

        c = card(page, 'Current vitals')
        c.pack(fill='x', padx=22, pady=6)
        grid = tk.Frame(c, bg=C['panel'])
        grid.pack(fill='x', padx=14, pady=(0, 14))
        for i, k in enumerate(ORDER):
            lab, unit, lo, hi = VITALS[k][:4]
            v = num(latest.get(k))
            col = sc(status(k, v))
            t = tk.Frame(grid, bg=C['panel2'], highlightbackground=col, highlightthickness=2)
            t.grid(row=i // 4, column=i % 4, sticky='ew', padx=4, pady=4, ipady=6)
            grid.columnconfigure(i % 4, weight=1)
            label(t, lab.upper(), 8, C['dim'], True, bg=C['panel2']).pack(fill='x', padx=10)
            shown = f'{v:,.0f} {unit}' if (v is not None and k == 'steps') else \
                    (f'{v:g} {unit}' if v is not None else '--')
            label(t, shown, 16, col, True, bg=C['panel2']).pack(fill='x', padx=10)
            sub = 'trend only' if kind(k) == 'info' else (
                f'target {lo:g}+' if kind(k) == 'goal' else f'normal {lo:g}-{hi:g}')
            label(t, sub, 8, C['dim'], bg=C['panel2']).pack(fill='x', padx=10)

        d = derived(self.user, latest, rows)
        if d:
            c2 = card(page, 'Derived values')
            c2.pack(fill='x', padx=22, pady=6)
            g2 = tk.Frame(c2, bg=C['panel'])
            g2.pack(fill='x', padx=14, pady=(0, 14))
            for i, (k, (v, unit)) in enumerate(d.items()):
                cell = tk.Frame(g2, bg=C['panel'])
                cell.grid(row=0, column=i, sticky='ew', padx=(0, 20))
                label(cell, k.upper(), 8, C['dim'], True).pack(fill='x')
                label(cell, f'{v} {unit}', 13, C['fg'], True).pack(fill='x')

        c3 = card(page, 'Past trends  (colour = worst reading that day)')
        c3.pack(fill='both', expand=True, padx=22, pady=(6, 22))
        cols = ['Date'] + [SHORT[k] for k in ORDER] + ['Flags']
        tv = ttk.Treeview(c3, columns=cols, show='headings', style='T.Treeview', height=12)
        widths = {'Date': 96, 'Flags': 184}
        for col in cols:
            tv.heading(col, text=col)
            tv.column(col, width=widths.get(col, 58), minwidth=44,
                      anchor='w' if col == 'Flags' else 'center')
        for tag, colr in (('ok', C['green']), ('warn', C['amber']), ('bad', C['red'])):
            tv.tag_configure(tag, foreground=colr)
        for r in reversed(rows[-30:]):
            sts = [status(k, num(r.get(k))) for k in ORDER]
            worst = 'bad' if 'bad' in sts else ('warn' if 'warn' in sts else 'ok')
            flagged = [SHORT[k] for k, s in zip(ORDER, sts) if s in ('warn', 'bad')]
            tv.insert('', 'end', tags=(worst,),
                      values=[r['day']] + [g(num(r.get(k))) for k in ORDER]
                             + [', '.join(flagged) or 'clear'])
        tv.pack(fill='both', expand=True, padx=14, pady=(0, 14))

    # ------------------------------------------------ add reading
    
    # ------------------------------------------------ analysis
    def p_analysis(self, body):
        rows = self.db.readings(self.uid)
        self.header(body, 'Analysis',
                    'Shaded band = normal range. Each dot is coloured by its own status.')
        page = self.scrollable(body)
        if len(rows) < 2:
            c = card(page)
            c.pack(fill='x', padx=22, pady=6)
            label(c, 'Log at least two days to draw trends.', 10,
                  C['dim']).pack(padx=14, pady=14)
            return

        recent = rows[-30:]
        grid = tk.Frame(page, bg=C['bg'])
        grid.pack(fill='both', expand=True, padx=22, pady=6)
        shown = [k for k in ORDER
                 if any(num(r.get(k)) is not None for r in recent)]
        for i, k in enumerate(shown):
            lab, unit = VITALS[k][:2]
            c = card(grid, f'{lab} ({unit})')
            c.grid(row=i // 2, column=i % 2, sticky='nsew', padx=4, pady=4)
            grid.columnconfigure(i % 2, weight=1)
            ch = Chart(c, k)
            ch.pack(fill='both', expand=True, padx=12, pady=(0, 12))
            ch.set_data(recent)
            vs = [num(r.get(k)) for r in recent if num(r.get(k)) is not None]
            if vs:
                label(c, f'avg {sum(vs)/len(vs):,.1f}   min {min(vs):,g}   max {max(vs):,g}',
                      9, C['dim']).pack(fill='x', padx=14, pady=(0, 10))

        d = derived(self.user, rows[-1], rows)
        if d:
            c = card(page, 'Derived from your latest reading')
            c.pack(fill='x', padx=22, pady=(6, 22))
            for k, (v, unit) in d.items():
                label(c, f'{k}: {v} {unit}', 10, C['fg']).pack(fill='x', padx=14, pady=1)
            tk.Frame(c, bg=C['panel'], height=10).pack()

    # ------------------------------------------------ medical record
    def p_record(self, body):
        rows = self.db.readings(self.uid)
        self.header(body, 'Medical Record',
                    'Not a diagnosis. These are patterns in your numbers to raise with a doctor.')
        page = self.scrollable(body)

        c1 = card(page, 'Watch list')
        c1.pack(fill='x', padx=22, pady=6)
        for st, text in watch_list(rows, self.user):
            r = tk.Frame(c1, bg=C['panel'])
            r.pack(fill='x', padx=14, pady=3)
            tk.Frame(r, bg=sc(st), width=4).pack(side='left', fill='y', padx=(0, 10))
            label(r, text, 10, C['fg'], wraplength=780, justify='left').pack(fill='x')
        tk.Frame(c1, bg=C['panel'], height=10).pack()

        c2 = card(page, 'Every time something was unusual')
        c2.pack(fill='x', padx=22, pady=6)
        an = anomalies(rows)
        if not an:
            label(c2, 'Nothing outside its usual range so far.', 10,
                  C['dim']).pack(fill='x', padx=14, pady=(0, 14))
        else:
            tv = ttk.Treeview(c2, columns=('Date', 'What'), show='headings',
                              style='T.Treeview', height=min(9, len(an)))
            tv.heading('Date', text='Date')
            tv.heading('What', text='What was unusual')
            tv.column('Date', width=110, anchor='center')
            tv.column('What', width=660, anchor='w')
            tv.tag_configure('warn', foreground=C['amber'])
            tv.tag_configure('bad', foreground=C['red'])
            for a in an[:80]:
                tv.insert('', 'end', values=(a['day'], a['text']), tags=(a['status'],))
            tv.pack(fill='x', padx=14, pady=(0, 14))

        c3 = card(page, 'Your medical history')
        c3.pack(fill='both', expand=True, padx=22, pady=(6, 22))
        hist = self.db.history(self.uid)
        box = tk.Frame(c3, bg=C['panel'])
        box.pack(fill='x', padx=14)
        if not hist:
            label(box, 'Nothing recorded. Add conditions, surgeries, allergies or '
                       'medications below.', 10, C['dim']).pack(fill='x', pady=(0, 6))
        for h in hist:
            r = tk.Frame(box, bg=C['panel2'])
            r.pack(fill='x', pady=2)
            label(r, f"{h['day']}   [{h['kind']}]   {h['text']}", 10, C['fg'],
                  bg=C['panel2']).pack(side='left', fill='x', expand=True, padx=10, pady=6)
            tk.Button(r, text='x', bg=C['panel2'], fg=C['dim'], relief='flat', bd=0,
                      cursor='hand2', font=(FONT, 10, 'bold'),
                      command=lambda i=h['id']: (self.db.del_history(i),
                                                 self.show_main('Medical Record'))
                      ).pack(side='right', padx=8)

        add = tk.Frame(c3, bg=C['panel'])
        add.pack(fill='x', padx=14, pady=12)
        kb = ttk.Combobox(add, values=['Condition', 'Surgery', 'Allergy', 'Medication', 'Other'],
                          state='readonly', width=12, font=(FONT, 10))
        kb.set('Condition')
        kb.pack(side='left', padx=(0, 8))
        txt = entry(add, width=52)
        txt.pack(side='left', fill='x', expand=True, ipady=4, padx=(0, 8))

        def add_h():
            if txt.get().strip():
                self.db.add_history(self.uid, date.today().isoformat(),
                                    kb.get(), txt.get().strip())
                self.show_main('Medical Record')
        button(add, 'Add', add_h).pack(side='left')

    # ------------------------------------------------ profile
    def p_profile(self, body):
        self.header(body, 'Profile', 'Height feeds BMI. Weight comes from your latest '
                                     'logged reading if you have one.')
        page = self.scrollable(body)
        c = card(page)
        c.pack(fill='x', padx=22, pady=6)
        inner = tk.Frame(c, bg=C['panel'])
        inner.pack(fill='x', padx=14, pady=14)
        u = self.user
        label(inner, f"Signed in as {u['username']}", 10, C['dim']).pack(fill='x')
        es = {k: field(inner, lab, value=u[k]) for k, lab in
              (('name', 'Full name'), ('age', 'Age'), ('gender', 'Gender'),
               ('weight', 'Starting weight (kg)'), ('height', 'Height (cm)'))}

        def save():
            self.db.update_profile(self.uid, name=es['name'].get().strip(),
                                   age=num(es['age'].get()), gender=es['gender'].get().strip(),
                                   weight=num(es['weight'].get()), height=num(es['height'].get()))
            messagebox.showinfo('Profile', 'Saved.')
            self.show_main('Profile')

        tk.Frame(inner, bg=C['panel'], height=8).pack()
        button(inner, 'Save Profile', save).pack(anchor='w')

        c2 = card(page, 'Appearance')
        c2.pack(fill='x', padx=22, pady=(6, 22))
        now = 'Dark' if C['bg'] == THEMES['dark']['bg'] else 'Light'
        label(c2, f'Current theme: {now}. Your choice is remembered next time you log in.',
              10, C['dim']).pack(fill='x', padx=14)
        button(c2, 'Switch theme', self.toggle_theme, 'ghost').pack(
            anchor='w', padx=14, pady=(8, 14))


if __name__ == '__main__':
    from login import LoginApp
    LoginApp().mainloop()
