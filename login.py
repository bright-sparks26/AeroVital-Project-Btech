import tkinter as tk
from tkinter import messagebox

from main import App, DB, C, FONT, button, card, field, label, num, set_theme


class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('AeroVital - Login')
        self.geometry('520x620')
        self.db = DB()
        self.container = tk.Frame(self)
        self.container.pack(fill='both', expand=True)
        self.apply_theme('dark')
        self.show_auth()

    def apply_theme(self, name):
        set_theme(name)
        self.configure(bg=C['bg'])
        self.container.configure(bg=C['bg'])

    def clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_auth(self, mode='login'):
        self.clear()
        wrap = tk.Frame(self.container, bg=C['bg'])
        wrap.place(relx=0.5, rely=0.5, anchor='center')
        c = card(wrap)
        c.pack()
        inner = tk.Frame(c, bg=C['panel'])
        inner.pack(padx=34, pady=28)

        label(inner, 'AeroVital', 22, C['fg'], True, anchor='center').pack(fill='x')
        label(inner, 'Your vitals, tracked against your own history.',
              9, C['dim'], anchor='center').pack(fill='x', pady=(2, 14))

        tabs = tk.Frame(inner, bg=C['panel'])
        tabs.pack(fill='x', pady=(0, 4))
        for tab_mode, text in (('login', 'Log In'), ('signup', 'Sign Up')):
            selected = tab_mode == mode
            tk.Button(tabs, text=text,
                      command=lambda selected_mode=tab_mode: self.show_auth(selected_mode),
                      bg=C['blue'] if selected else C['panel2'],
                      fg=C['on_accent'] if selected else C['dim'],
                      font=(FONT, 10, 'bold'), relief='flat', bd=0, pady=7,
                      cursor='hand2',
                      activebackground=C['blue'] if selected else C['panel2']
                      ).pack(side='left', expand=True, fill='x')

        username = field(inner, 'Username')
        password = field(inner, 'Password', show='\u2022')
        fields = {}
        if mode == 'signup':
            label(inner, 'YOUR PROFILE', 9, C['dim'], True).pack(fill='x', pady=(14, 0))
            label(inner, 'Used for BMI and to label your data.', 8, C['dim']).pack(fill='x')
            fields['name'] = field(inner, 'Full name')
            grid = tk.Frame(inner, bg=C['panel'])
            grid.pack(fill='x')
            for index, (key, field_label) in enumerate(
                    (('age', 'Age'), ('gender', 'Gender'),
                     ('weight', 'Weight (kg)'), ('height', 'Height (cm)'))):
                cell = tk.Frame(grid, bg=C['panel'])
                cell.grid(row=index // 2, column=index % 2, sticky='ew', padx=(0, 8))
                grid.columnconfigure(index % 2, weight=1)
                fields[key] = field(cell, field_label)

        def submit():
            try:
                if mode == 'signup':
                    values = {key: widget.get().strip() for key, widget in fields.items()}
                    uid = self.db.signup(
                        username.get().strip(), password.get(), name=values['name'],
                        age=num(values['age']), gender=values['gender'],
                        weight=num(values['weight']), height=num(values['height']))
                else:
                    user = self.db.login(username.get().strip(), password.get())
                    if not user:
                        messagebox.showerror('Login failed', 'Wrong username or password.')
                        return
                    uid = user['id']

                self.destroy()
                App(self.db, uid).mainloop()
            except ValueError as error:
                messagebox.showerror('Could not continue', str(error))

        tk.Frame(inner, bg=C['panel'], height=10).pack()
        button(inner, 'Log In' if mode == 'login' else 'Create Account', submit).pack(fill='x')
        password.bind('<Return>', lambda event: submit())
        username.focus_set()


if __name__ == '__main__':
    LoginApp().mainloop()
    