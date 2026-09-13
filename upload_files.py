import os, sqlite3, hashlib, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from main import C, ORDER, VITALS, card, derived, kind, label, num, sc, status

def upload():
    file_path = filedialog.askopenfilename(filetypes=[("FIT files", "*.fit")])
    if not file_path:
        return

    try:
        fitfile = fitparse.FitFile(file_path)
        for record in fitfile.get_messages('record'):
            data = {}
            for field in record:
                data[field.name] = field.value
            # Here you can process the data as needed, e.g., save to database
            print(data)  # For demonstration purposes, print the data
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read FIT file: {e}")

class add_data(tk.Tk):
    def p_add(self, body):
            self.header(body, 'Add Reading', 'Leave anything blank that you did not measure. '
                                             'Saving twice for the same date updates that day.')
            page = self.scrollable(body)
            c = card(page)
            c.pack(fill='x', padx=22, pady=6)
            inner = tk.Frame(c, bg=C['panel'])
            inner.pack(fill='x', padx=14, pady=14)
    
            day_e = field(inner, 'Date (YYYY-MM-DD)', value=date.today().isoformat())
            existing = {r['day']: r for r in self.db.readings(self.uid)}.get(
                date.today().isoformat(), {})
    
            grid = tk.Frame(inner, bg=C['panel'])
            grid.pack(fill='x')
            es = {}
            for i, k in enumerate(ORDER):
                lab, unit, lo, hi = VITALS[k][:4]
                cell = tk.Frame(grid, bg=C['panel'])
                cell.grid(row=i // 3, column=i % 3, sticky='ew', padx=(0, 14))
                grid.columnconfigure(i % 3, weight=1)
                note = HINTS.get(k) or (f'target {lo:g}+' if kind(k) == 'goal'
                                        else f'normal {lo:g}-{hi:g}')
                es[k] = field(cell, f'{lab} ({unit})', value=existing.get(k, ''), hint=note)
            notes_e = field(inner, 'Notes (optional)', value=existing.get('notes', ''))
    
            def save():
                try:
                    day = datetime.strptime(day_e.get().strip(), '%Y-%m-%d').date()
                except ValueError:
                    messagebox.showerror('Bad date', 'Use YYYY-MM-DD, e.g. 2026-09-10.')
                    return
                if day > date.today():
                    messagebox.showerror('Bad date', "You can't log a reading in the future.")
                    return
                vals = {k: num(es[k].get()) for k in ORDER}
                if all(v is None for v in vals.values()):
                    messagebox.showwarning('Nothing to save', 'Fill in at least one reading.')
                    return
                self.db.save_reading(self.uid, day.isoformat(), vals, notes_e.get().strip(), attach_path.get())
                flagged = [VITALS[k][0] for k in ORDER if status(k, vals[k]) in ('warn', 'bad')]
                messagebox.showinfo('Reading saved', 'Saved.' + (
                    f"\n\nOutside its usual range: {', '.join(flagged)}." if flagged
                    else '\n\nEverything is inside its usual range.'))
                self.show_main('Dashboard')
    
            tk.Frame(inner, bg=C['panel'], height=8).pack()
            button(inner, 'Save Reading', save).pack(anchor='w')
    
            attach_path =tk.StringerVar(value=existing.get('attachment',''))
            file_row = tk.Frame(inner, bg=C['panel'])
            file_row.pack(fill='x',pady=(8,0))
    
            def pick_file():
                p = filedialog.askopenfilename(title='Attach a file')
                if p:
                    attach_path.set(p)
                    file_lbl.config(text=os.path.basename(p))
    
            button(file_row, 'Upload File', pick_file, 'ghost').pack(side='left')
            file_lbl = label(file_row, os.path.basename(attach_path.get()) or 'No File Chosen',9, C['dim'])
            file_lbl.pack(side='left', padx =10)