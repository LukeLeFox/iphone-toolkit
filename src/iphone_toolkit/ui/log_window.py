from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from iphone_toolkit.core.syslog_service import (
    build_syslog_command,
    create_syslog_log_path,
    get_log_dir,
)


class LogWindow(tk.Toplevel):
    def __init__(self, master, get_udid_callback, initial_app_log: list[str] | None = None):
        super().__init__(master)

        self.title("iPhone Toolkit - Log Center")
        self.geometry("1100x720")
        self.minsize(900, 560)

        self.get_udid_callback = get_udid_callback

        self.syslog_process: subprocess.Popen | None = None
        self.syslog_thread: threading.Thread | None = None
        self.syslog_queue: queue.Queue[str] = queue.Queue()
        self.syslog_lines: list[str] = []
        self.app_lines: list[str] = list(initial_app_log or [])

        self.autoscroll_var = tk.BooleanVar(value=True)
        self.syslog_status_var = tk.StringVar(value="Syslog fermo")

        self._build_ui()
        self._load_initial_app_log()

        self.after(100, self._poll_syslog_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(
            header,
            text="Log Center",
            font=("Arial", 20, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="Console applicazione e syslog live iOS in una finestra separata.",
        ).pack(anchor="w", pady=(3, 0))

        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(toolbar, text="Avvia Syslog", command=self.start_syslog).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Ferma Syslog", command=self.stop_syslog).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Salva Console App", command=self.save_app_console).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Salva Syslog", command=self.save_syslog).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Pulisci Console App", command=self.clear_app_console).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Pulisci Syslog", command=self.clear_syslog).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Apri cartella log", command=self.open_log_folder).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(toolbar, text="Autoscroll", variable=self.autoscroll_var).pack(side="left", padx=(8, 0))

        ttk.Label(toolbar, textvariable=self.syslog_status_var).pack(side="right")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.app_tab = ttk.Frame(self.notebook, padding=8)
        self.syslog_tab = ttk.Frame(self.notebook, padding=8)

        self.notebook.add(self.app_tab, text="Console App")
        self.notebook.add(self.syslog_tab, text="Syslog Live")

        self.app_console = scrolledtext.ScrolledText(
            self.app_tab,
            wrap="word",
            font=("Monospace", 10),
        )
        self.app_console.pack(fill="both", expand=True)

        self.syslog_console = scrolledtext.ScrolledText(
            self.syslog_tab,
            wrap="word",
            font=("Monospace", 10),
        )
        self.syslog_console.pack(fill="both", expand=True)

    # ---------------- App console mirror ----------------

    def _load_initial_app_log(self):
        if not self.app_lines:
            return

        self.app_console.insert("end", "\n".join(self.app_lines) + "\n")
        self.app_console.see("end")

    def append_app_log(self, line: str):
        self.app_lines.append(line)
        self.app_console.insert("end", line + "\n")

        if self.autoscroll_var.get():
            self.app_console.see("end")

    # ---------------- Syslog ----------------

    def append_syslog(self, line: str):
        self.syslog_lines.append(line)
        self.syslog_console.insert("end", line + "\n")

        if self.autoscroll_var.get():
            self.syslog_console.see("end")

    def start_syslog(self):
        if shutil.which("idevicesyslog") is None:
            messagebox.showerror(
                "idevicesyslog mancante",
                "Il comando idevicesyslog non è installato.\n\n"
                "Su Kubuntu prova:\n"
                "sudo apt install libimobiledevice-utils",
            )
            return

        if self.syslog_process and self.syslog_process.poll() is None:
            messagebox.showinfo("Syslog già attivo", "Il syslog live è già in esecuzione.")
            return

        udid = self.get_udid_callback()

        if not udid:
            messagebox.showwarning(
                "Device non valido",
                "Per idevicesyslog serve un iPhone in Normal Mode, collegato, sbloccato e autorizzato.",
            )
            return

        log_path = create_syslog_log_path()
        command = build_syslog_command(udid)

        self.append_syslog("")
        self.append_syslog("=== AVVIO SYSLOG LIVE ===")
        self.append_syslog("$ " + " ".join(command))
        self.append_syslog(f"Log file: {log_path}")
        self.append_syslog("")

        self.syslog_status_var.set("Syslog attivo")
        self.notebook.select(self.syslog_tab)

        def worker():
            log_file = None

            try:
                log_file = Path(log_path).open("w", encoding="utf-8")

                self.syslog_process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                assert self.syslog_process.stdout is not None

                for line in self.syslog_process.stdout:
                    clean_line = line.rstrip()
                    self.syslog_queue.put(clean_line)
                    log_file.write(clean_line + "\n")
                    log_file.flush()

                returncode = self.syslog_process.wait()
                self.syslog_queue.put(f"[syslog exit code] {returncode}")

            except Exception as exc:
                self.syslog_queue.put(f"Errore syslog: {exc}")

            finally:
                if log_file is not None:
                    log_file.close()

                self.syslog_queue.put("=== SYSLOG LIVE TERMINATO ===")
                self.after(0, self.syslog_status_var.set, "Syslog fermo")

        self.syslog_thread = threading.Thread(target=worker, daemon=True)
        self.syslog_thread.start()

    def stop_syslog(self):
        if self.syslog_process and self.syslog_process.poll() is None:
            try:
                self.syslog_process.terminate()
                self.append_syslog("Richiesta stop syslog inviata.")
                self.syslog_status_var.set("Stop richiesto")
            except Exception as exc:
                self.append_syslog(f"Errore stop syslog: {exc}")
        else:
            self.append_syslog("Nessun syslog attivo.")

    def _poll_syslog_queue(self):
        while True:
            try:
                line = self.syslog_queue.get_nowait()
            except queue.Empty:
                break

            self.append_syslog(line)

        self.after(100, self._poll_syslog_queue)

    # ---------------- Save / clear ----------------

    def save_app_console(self):
        path = filedialog.asksaveasfilename(
            title="Salva Console App",
            defaultextension=".log",
            filetypes=[
                ("Log", "*.log"),
                ("Text", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        Path(path).write_text(self.app_console.get("1.0", "end-1c"), encoding="utf-8")
        self.append_app_log(f"Console app salvata in: {path}")

    def save_syslog(self):
        path = filedialog.asksaveasfilename(
            title="Salva Syslog",
            defaultextension=".log",
            filetypes=[
                ("Log", "*.log"),
                ("Text", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        Path(path).write_text(self.syslog_console.get("1.0", "end-1c"), encoding="utf-8")
        self.append_syslog(f"Syslog salvato in: {path}")

    def clear_app_console(self):
        self.app_console.delete("1.0", "end")
        self.app_lines.clear()
        self.append_app_log("Console app pulita.")

    def open_log_folder(self):
        log_dir = get_log_dir()
        system = platform.system()

        try:
            if system == "Darwin":
                subprocess.run(["open", str(log_dir)], check=False)
            elif system == "Windows":
                os.startfile(str(log_dir))
            else:
                subprocess.run(["xdg-open", str(log_dir)], check=False)

            self.append_app_log(f"Cartella log aperta: {log_dir}")

        except Exception as exc:
            self.append_app_log(f"Errore apertura cartella log: {exc}")

    def clear_syslog(self):
        self.syslog_console.delete("1.0", "end")
        self.syslog_lines.clear()

    # ---------------- Close ----------------

    def on_close(self):
        if self.syslog_process and self.syslog_process.poll() is None:
            if messagebox.askyesno(
                "Syslog attivo",
                "Il syslog live è ancora attivo.\n\nVuoi fermarlo e chiudere la finestra?",
            ):
                self.stop_syslog()
            else:
                return

        self.destroy()
