import tkinter as tk
from tkinter import ttk

from main import C, ORDER, SHORT, VITALS, card, derived, g, kind, label, num, sc, status


def p_dashboard(app, body):
	rows = app.db.readings(app.uid)
	latest = rows[-1] if rows else {}
	app.header(body, f"Hello, {(app.user['name'] or app.user['username']).split()[0]}",
			   f"Latest reading: {latest['day']}" if rows else 'No readings yet')
	page = app.scrollable(body)

	if not rows:
		c = card(page, 'Get started')
		c.pack(fill='x', padx=22, pady=6)
		label(c, 'Add your first reading to see vitals, trends and analysis.',
			  10, C['dim']).pack(fill='x', padx=14, pady=(0, 12))
		from main import button
		button(c, 'Add Reading', lambda: app.show_main('Add Reading')).pack(
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

	d = derived(app.user, latest, rows)
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
