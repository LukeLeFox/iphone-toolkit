from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class PreflightWindow(tk.Toplevel):
    def __init__(self, master, headline: str, checks, open_log_callback=None):
        super().__init__(master)

        self.title("iPhone Toolkit - Pre-flight Check")
        self.geometry("980x560")
        self.minsize(820, 440)

        self.headline = headline
        self.checks = checks
        self.open_log_callback = open_log_callback

        self._build_ui()
        self._populate()

        self.transient(master)
        self.lift()
        self.focus_force()

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(
            header,
            text="Pre-flight Check",
            font=("Arial", 20, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text=self.headline,
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", pady=(4, 0))

        table_frame = ttk.Frame(root)
        table_frame.pack(fill="both", expand=True)

        columns = ("status", "check", "message")

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=16,
        )

        self.tree.heading("status", text="Stato")
        self.tree.heading("check", text="Check")
        self.tree.heading("message", text="Dettaglio")

        self.tree.column("status", width=90, minwidth=80, anchor="center", stretch=False)
        self.tree.column("check", width=210, minwidth=160, anchor="w", stretch=False)
        self.tree.column("message", width=640, minwidth=320, anchor="w", stretch=True)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        self.tree.tag_configure("ok", foreground="#0a7f24")
        self.tree.tag_configure("warn", foreground="#a15c00")
        self.tree.tag_configure("fail", foreground="#b00020")

        summary_box = ttk.Frame(root)
        summary_box.pack(fill="x", pady=(10, 0))

        ok_count = sum(1 for check in self.checks if check.ok)
        warn_count = sum(1 for check in self.checks if check.warn)
        fail_count = sum(1 for check in self.checks if check.fail)

        ttk.Label(
            summary_box,
            text=f"✓ OK: {ok_count}    ! Warning: {warn_count}    ✗ Errori: {fail_count}",
        ).pack(anchor="w")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(12, 0))

        ttk.Button(
            buttons,
            text="Copia risultati",
            command=self.copy_results,
        ).pack(side="left")

        if self.open_log_callback is not None:
            ttk.Button(
                buttons,
                text="Apri Log Center",
                command=self.open_log_callback,
            ).pack(side="left", padx=(8, 0))

        ttk.Button(
            buttons,
            text="Chiudi",
            command=self.destroy,
        ).pack(side="right")

    def _populate(self):
        for check in self.checks:
            if check.ok:
                status_label = "✓ OK"
                tag = "ok"
            elif check.warn:
                status_label = "! WARN"
                tag = "warn"
            elif check.fail:
                status_label = "✗ FAIL"
                tag = "fail"
            else:
                status_label = "?"
                tag = "warn"

            self.tree.insert(
                "",
                "end",
                values=(status_label, check.name, check.message),
                tags=(tag,),
            )

    def copy_results(self):
        lines = [self.headline, ""]

        for check in self.checks:
            if check.ok:
                prefix = "✓"
            elif check.warn:
                prefix = "!"
            elif check.fail:
                prefix = "✗"
            else:
                prefix = "?"

            lines.append(f"{prefix} {check.name}: {check.message}")

        text = "\n".join(lines)

        self.clipboard_clear()
        self.clipboard_append(text)
