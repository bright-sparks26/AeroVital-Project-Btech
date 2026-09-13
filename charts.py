import tkinter as tk

from main import C, ORDER, VITALS, card, derived, kind, label, num, sc, status


class Chart(tk.Canvas):
	"""Line chart with a shaded normal band."""

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
		pts = [(day, value) for day, value in pts if value is not None]
		if not pts:
			self.create_text(w / 2, h / 2, text='No data yet', fill=C['dim'], font=('DejaVu Sans', 10))
			return

		vals = [value for _, value in pts]
		anchors = vals + ([lo, min(hi, max(vals) * 1.1)] if banded else [])
		vmin, vmax = min(anchors), max(anchors)
		span = (vmax - vmin) or 1
		vmin, vmax = vmin - span * 0.15, vmax + span * 0.15
		pl, pr, pt, pb = 48, 14, 14, 24

		def x_coord(index):
			return pl + (w - pl - pr) * (index / max(1, len(pts) - 1))

		def y_coord(value):
			return pt + (h - pt - pb) * (1 - (value - vmin) / (vmax - vmin))

		if banded:
			self.create_rectangle(pl, y_coord(min(hi, vmax)), w - pr, y_coord(max(lo, vmin)),
								  fill=C['band'], outline='')
		for grid_value in (vmin, (vmin + vmax) / 2, vmax):
			self.create_line(pl, y_coord(grid_value), w - pr, y_coord(grid_value), fill=C['line'])
			self.create_text(pl - 6, y_coord(grid_value), text=f'{grid_value:,.0f}',
							 fill=C['dim'], font=('DejaVu Sans', 8), anchor='e')

		coords = []
		for index, (_, value) in enumerate(pts):
			coords += [x_coord(index), y_coord(value)]
		if len(coords) >= 4:
			self.create_line(*coords, fill=C['blue'], width=2)
		for index, (_, value) in enumerate(pts):
			self.create_oval(x_coord(index) - 3.5, y_coord(value) - 3.5,
							 x_coord(index) + 3.5, y_coord(value) + 3.5,
							 fill=sc(status(self.key, value)), outline='')
		self.create_text(pl, h - 8, text=pts[0][0][5:], fill=C['dim'],
						 font=('DejaVu Sans', 8), anchor='w')
		self.create_text(w - pr, h - 8, text=pts[-1][0][5:], fill=C['dim'],
						 font=('DejaVu Sans', 8), anchor='e')


def p_analysis(app, body):
	rows = app.db.readings(app.uid)
	app.header(body, 'Analysis',
			   'Shaded band = normal range. Each dot is coloured by its own status.')
	page = app.scrollable(body)
	if len(rows) < 2:
		c = card(page)
		c.pack(fill='x', padx=22, pady=6)
		label(c, 'Log at least two days to draw trends.', 10,
			  C['dim']).pack(padx=14, pady=14)
		return

	recent = rows[-30:]
	grid = tk.Frame(page, bg=C['bg'])
	grid.pack(fill='both', expand=True, padx=22, pady=6)
	shown = [key for key in ORDER
			 if any(num(row.get(key)) is not None for row in recent)]
	for index, key in enumerate(shown):
		lab, unit = VITALS[key][:2]
		c = card(grid, f'{lab} ({unit})')
		c.grid(row=index // 2, column=index % 2, sticky='nsew', padx=4, pady=4)
		grid.columnconfigure(index % 2, weight=1)
		chart = Chart(c, key)
		chart.pack(fill='both', expand=True, padx=12, pady=(0, 12))
		chart.set_data(recent)
		values = [num(row.get(key)) for row in recent if num(row.get(key)) is not None]
		if values:
			label(c, f'avg {sum(values)/len(values):,.1f}   min {min(values):,g}   max {max(values):,g}',
				  9, C['dim']).pack(fill='x', padx=14, pady=(0, 10))

	d = derived(app.user, rows[-1], rows)
	if d:
		c = card(page, 'Derived from your latest reading')
		c.pack(fill='x', padx=22, pady=(6, 22))
		for key, (value, unit) in d.items():
			label(c, f'{key}: {value} {unit}', 10, C['fg']).pack(fill='x', padx=14, pady=1)
		tk.Frame(c, bg=C['panel'], height=10).pack()
