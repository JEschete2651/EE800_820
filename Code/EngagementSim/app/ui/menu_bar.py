"""Menu bar - File, Simulation, Assets, View menus."""

import tkinter as tk
from tkinter import messagebox


class MenuBar(tk.Menu):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._callbacks: dict = {}

        # ---- File menu ----
        file_menu = tk.Menu(self, tearoff=0)
        file_menu.add_command(label="Save Scenario...",
                              command=lambda: self._fire("save"))
        file_menu.add_command(label="Load Scenario...",
                              command=lambda: self._fire("load"))
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV...",
                              command=lambda: self._fire("export_csv"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit",
                              command=lambda: self._fire("exit"))
        self.add_cascade(label="File", menu=file_menu)

        # ---- Simulation menu ----
        sim_menu = tk.Menu(self, tearoff=0)
        sim_menu.add_command(label="Start", command=lambda: self._fire("start"))
        sim_menu.add_command(label="Stop", command=lambda: self._fire("stop"))
        sim_menu.add_command(label="Reset", command=lambda: self._fire("reset"))
        sim_menu.add_separator()
        sim_menu.add_command(label="Pause / Resume",
                             command=lambda: self._fire("toggle_pause"))
        sim_menu.add_command(label="Step", command=lambda: self._fire("step"))
        sim_menu.add_separator()
        sim_menu.add_command(label="Global Settings...",
                             command=lambda: self._fire("global_config"))
        self.add_cascade(label="Simulation", menu=sim_menu)

        # ---- Assets menu (add/remove) ----
        self.assets_menu = tk.Menu(self, tearoff=0)
        self.assets_menu.add_command(label="Add Target...",
                                     command=lambda: self._fire("add_target"))
        self.assets_menu.add_command(label="Add Threat...",
                                     command=lambda: self._fire("add_threat"))
        self.assets_menu.add_separator()
        self._asset_start_index = self.assets_menu.index(tk.END) + 1
        self.add_cascade(label="Assets", menu=self.assets_menu)

        # ---- View menu ----
        view_menu = tk.Menu(self, tearoff=0)
        view_menu.add_command(label="Clear Logs",
                              command=lambda: self._fire("clear_logs"))
        self.add_cascade(label="View", menu=view_menu)

    def set_callback(self, name: str, func):
        self._callbacks[name] = func

    def _fire(self, name: str, *args):
        cb = self._callbacks.get(name)
        if cb:
            cb(*args)

    def rebuild_asset_entries(self, asset_names: list[tuple[str, str]]):
        """Rebuild per-asset Remove entries under Assets menu."""
        end = self.assets_menu.index(tk.END)
        if end is not None:
            while end >= self._asset_start_index:
                self.assets_menu.delete(end)
                end = self.assets_menu.index(tk.END)
                if end is None:
                    break

        for name, atype in asset_names:
            label = f"{'[T]' if atype == 'target' else '[X]'} Remove {name}"
            self.assets_menu.add_command(
                label=label,
                command=lambda n=name: self._confirm_remove(n))

    def _confirm_remove(self, name: str):
        if messagebox.askyesno("Remove Asset",
                               f"Remove '{name}' from the simulation?"):
            self._fire("remove_asset", name)
