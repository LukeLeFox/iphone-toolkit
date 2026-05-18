from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from iphone_toolkit.core.appledb_service import get_appledb_device_link
from iphone_toolkit.core.device_service import (
    check_dependencies,
    check_optional_dependencies,
    enter_recovery,
    exit_recovery,
    get_connection_state,
    get_device_info,
    has_command,
    list_devices,
    parse_device_info,
    reboot_device,
)
from iphone_toolkit.core.firmware_service import (
    create_restore_log_path,
    get_log_dir,
    run_erase_restore_stream,
    run_update_restore_stream,
    validate_ipsw,
)
from iphone_toolkit.core.preflight_service import (
    run_preflight_checks,
    summarize_preflight,
)
from iphone_toolkit.ui.log_window import LogWindow
from iphone_toolkit.ui.preflight_window import PreflightWindow


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("iPhone Toolkit")
        self.geometry("1200x610")
        self.minsize(980, 540)

        self.udid_var = tk.StringVar(value="Nessun device rilevato")
        self.name_var = tk.StringVar(value="-")
        self.model_var = tk.StringVar(value="-")
        self.ios_var = tk.StringVar(value="-")
        self.connection_state_var = tk.StringVar(value="Sconosciuto")
        self.status_var = tk.StringVar(value="Pronto")
        self.phone_state_detail_var = tk.StringVar(value="Telefono non ancora rilevato.")
        self.preflight_status_var = tk.StringVar(value="Pre-flight non eseguito.")
        self.ipsw_var = tk.StringVar(value="")

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.restore_running = False
        self.current_product_type: str | None = None

        self.app_console_history: list[str] = []
        self.log_window: LogWindow | None = None

        self._build_ui()
        self._check_dependencies()
        self.after(100, self._poll_output_queue)

    # ---------------- UI ----------------

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 14))

        ttk.Label(
            header,
            text="iPhone Toolkit",
            font=("Arial", 24, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="Recovery Mode + dirty flash / erase restore IPSW workflow",
        ).pack(anchor="w", pady=(4, 0))

        cards = ttk.Frame(root)
        cards.pack(fill="x", pady=(0, 14))

        self._card(cards, "UDID", self.udid_var, 360).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._card(cards, "Nome", self.name_var, 150).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._card(cards, "Modello", self.model_var, 150).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._card(cards, "iOS", self.ios_var, 150).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._card(cards, "Stato", self.connection_state_var, 170).pack(
            side="left", fill="x", expand=True
        )

        actions = ttk.LabelFrame(root, text="Azioni device", padding=10)
        actions.pack(fill="x", pady=(0, 14))

        ttk.Button(actions, text="Rileva stato", command=self.detect_state).pack(side="left", padx=4)
        ttk.Button(actions, text="Rileva device", command=self.detect_device).pack(side="left", padx=4)
        ttk.Button(actions, text="Info device", command=self.device_info).pack(side="left", padx=4)
        ttk.Button(actions, text="AppleDB IPSW", command=self.open_appledb_for_device).pack(side="left", padx=4)
        ttk.Button(actions, text="Pre-flight Check", command=self.run_preflight_check).pack(side="left", padx=4)
        ttk.Button(actions, text="Riavvia", command=self.confirm_reboot).pack(side="left", padx=4)
        ttk.Button(actions, text="Entra in Recovery", command=self.confirm_recovery).pack(side="left", padx=4)
        ttk.Button(actions, text="Esci da Recovery", command=self.confirm_exit_recovery).pack(side="left", padx=4)
        ttk.Button(actions, text="Log Center", command=self.open_log_center).pack(side="left", padx=4)

        firmware = ttk.LabelFrame(root, text="Firmware IPSW", padding=10)
        firmware.pack(fill="x", pady=(0, 14))

        ttk.Label(firmware, text="IPSW:").pack(side="left")

        ttk.Entry(
            firmware,
            textvariable=self.ipsw_var,
        ).pack(side="left", fill="x", expand=True, padx=8)

        ttk.Button(
            firmware,
            text="Scegli IPSW",
            command=self.choose_ipsw,
        ).pack(side="left", padx=4)

        ttk.Button(
            firmware,
            text="Dirty Flash / Update",
            command=self.confirm_dirty_flash,
        ).pack(side="left", padx=4)

        ttk.Button(
            firmware,
            text="Erase Restore",
            command=self.confirm_erase_restore,
        ).pack(side="left", padx=4)

        warning = ttk.LabelFrame(root, text="Nota sicurezza", padding=10)
        warning.pack(fill="x", pady=(0, 14))

        ttk.Label(
            warning,
            text=(
                "Dirty Flash / Update usa idevicerestore senza --erase e tenta di preservare dati e impostazioni. "
                "Erase Restore usa invece --erase e cancella completamente il dispositivo. "
                "Prima di qualunque operazione firmware è fortemente consigliato un backup e un Pre-flight Check."
            ),
            wraplength=1100,
            justify="left",
        ).pack(anchor="w")

        status_box = ttk.LabelFrame(root, text="Stato operativo", padding=10)
        status_box.pack(fill="x", pady=(0, 10))

        ttk.Label(
            status_box,
            text="Stato telefono:",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            status_box,
            textvariable=self.phone_state_detail_var,
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(3, 8))

        ttk.Label(
            status_box,
            text="Pre-flight:",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            status_box,
            textvariable=self.preflight_status_var,
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(3, 8))

        ttk.Label(
            status_box,
            text="Operazione corrente:",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            status_box,
            textvariable=self.status_var,
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

    def _card(self, parent, title: str, variable: tk.StringVar, width: int) -> ttk.Frame:
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.configure(width=width)
        frame.pack_propagate(False)

        ttk.Label(
            frame,
            textvariable=variable,
            font=("Arial", 11),
        ).pack(anchor="w")

        return frame

    # ---------------- Helpers ----------------

    def log(self, text: str):
        self.app_console_history.append(text)

        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.append_app_log(text)

    def set_status(self, text: str):
        self.status_var.set(text)

    def log_command_result(self, result):
        self.log("$ " + " ".join(result.command))

        if result.stdout:
            self.log(result.stdout)

        if result.stderr:
            self.log("[stderr] " + result.stderr)

        self.log(f"[exit code] {result.returncode}")

    def run_background(self, status: str, worker, callback=None):
        self.set_status(status)

        def task():
            result = worker()
            self.after(0, self._background_done, result, callback)

        threading.Thread(target=task, daemon=True).start()

    def _background_done(self, result, callback):
        if callback:
            callback(result)
        self.set_status("Pronto")

    def _poll_output_queue(self):
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break

            self.log(line)

        self.after(100, self._poll_output_queue)

    def get_current_udid(self) -> str | None:
        udid = self.udid_var.get().strip()

        if not udid or udid in {"Nessun device rilevato", "Recovery/DFU mode"}:
            return None

        return udid

    def require_current_udid(self) -> str | None:
        udid = self.get_current_udid()

        if not udid:
            messagebox.showwarning(
                "Device non rilevato in Normal Mode",
                "Per questa azione serve un iPhone rilevato in modalità normale.\n\n"
                "Collega l'iPhone, sbloccalo, autorizza il computer e premi 'Rileva device'.",
            )
            return None

        return udid

    # ---------------- Dependency check ----------------

    def _check_dependencies(self):
        missing = check_dependencies()

        if shutil.which("idevicerestore") is None:
            missing.append("idevicerestore")

        optional_missing = check_optional_dependencies()

        if shutil.which("idevicesyslog") is None:
            optional_missing.append("idevicesyslog")

        if missing:
            self.log("Dipendenze mancanti: " + ", ".join(missing))
            self.log(
                "Su Kubuntu/Ubuntu prova: sudo apt install python3 python-is-python3 "
                "python3-tk libimobiledevice-utils usbmuxd ideviceinstaller idevicerestore"
            )
            self.set_status("Dipendenze mancanti")
        else:
            self.log("Dipendenze principali OK.")
            self.set_status("Toolkit pronto")

        if optional_missing:
            self.log("Dipendenze opzionali mancanti: " + ", ".join(optional_missing))
            self.log("Per Recovery/DFU e syslog: sudo apt install libirecovery-utils libimobiledevice-utils")

    # ---------------- Device actions ----------------

    def detect_state(self):
        def worker():
            return get_connection_state()

        def callback(state_data):
            state, detail = state_data

            if state == "normal":
                self.connection_state_var.set("Normal Mode")
                self.udid_var.set(detail)
                self.phone_state_detail_var.set(f"Normal Mode - UDID: {detail}")
                self.log(f"Stato: Normal Mode - UDID {detail}")
                self.device_info()

            elif state == "recovery":
                self.connection_state_var.set(detail)
                self.phone_state_detail_var.set(
                    f"{detail} - device rilevato tramite irecovery. "
                    "Dirty flash/update disponibile; syslog live non disponibile."
                )
                self.udid_var.set("Recovery/DFU mode")
                self.name_var.set("-")
                self.model_var.set("-")
                self.ios_var.set("-")
                self.log(f"Stato: {detail}")
                self.log("Device rilevato tramite irecovery.")

            elif state == "missing-irecovery":
                self.connection_state_var.set("Sconosciuto")
                self.phone_state_detail_var.set(
                    "Stato non determinabile: irecovery non è installato."
                )
                self.log("irecovery non installato: impossibile rilevare Recovery/DFU.")
                self.log("Installa con: sudo apt install libirecovery-utils")

            else:
                self.connection_state_var.set("Non rilevato")
                self.phone_state_detail_var.set(
                    "Nessun iPhone rilevato in Normal Mode, Recovery o DFU."
                )
                self.udid_var.set("Nessun device rilevato")
                self.name_var.set("-")
                self.model_var.set("-")
                self.ios_var.set("-")
                self.log("Nessun device rilevato né in Normal Mode né in Recovery/DFU.")

        self.run_background("Rilevamento stato...", worker, callback)

    def detect_device(self):
        def worker():
            return list_devices()

        def callback(devices):
            if not devices:
                self.udid_var.set("Nessun device rilevato")
                self.name_var.set("-")
                self.model_var.set("-")
                self.ios_var.set("-")
                self.connection_state_var.set("Non rilevato")
                self.phone_state_detail_var.set("Nessun device rilevato in Normal Mode.")
                self.log("Nessun device rilevato in Normal Mode.")
                return

            udid = devices[0]
            self.udid_var.set(udid)
            self.connection_state_var.set("Normal Mode")
            self.phone_state_detail_var.set(f"Normal Mode - UDID: {udid}")
            self.log(f"Device rilevato: {udid}")
            self.device_info()

        self.run_background("Rilevamento device...", worker, callback)

    def device_info(self):
        udid = self.require_current_udid()
        if not udid:
            return

        def worker():
            return get_device_info(udid)

        def callback(result):
            self.log_command_result(result)

            if not result.ok:
                return

            info = parse_device_info(result.stdout)

            device_name = info.get("DeviceName", "-")
            product_type = info.get("ProductType", "-")
            product_version = info.get("ProductVersion", "-")
            build_version = info.get("BuildVersion", "-")

            self.name_var.set(device_name)
            self.model_var.set(product_type)

            if product_type != "-":
                self.current_product_type = product_type

            if product_version != "-" and build_version != "-":
                self.ios_var.set(f"{product_version} ({build_version})")
            else:
                self.ios_var.set(product_version)

            self.phone_state_detail_var.set(
                f"Normal Mode - {device_name} / {product_type} / iOS {self.ios_var.get()}"
            )

        self.run_background("Lettura info device...", worker, callback)

    def confirm_reboot(self):
        udid = self.require_current_udid()
        if not udid:
            return

        if not messagebox.askyesno("Conferma riavvio", "Vuoi riavviare l'iPhone?"):
            return

        def worker():
            return reboot_device()

        def callback(result):
            self.log_command_result(result)

        self.run_background("Invio comando reboot...", worker, callback)

    def confirm_recovery(self):
        udid = self.require_current_udid()
        if not udid:
            return

        if not messagebox.askyesno(
            "Conferma Recovery Mode",
            "Vuoi mandare l'iPhone in Recovery Mode?\n\n"
            "Vedrai la schermata con cavo/computer. Non è DFU.",
        ):
            return

        def worker():
            return enter_recovery(udid)

        def callback(result):
            self.log_command_result(result)

            if result.ok:
                self.log("Recovery richiesta. Se tutto è ok, l'iPhone mostrerà la schermata cavo/computer.")
                self.connection_state_var.set("Recovery richiesta")
                self.phone_state_detail_var.set(
                    "Recovery richiesta: attendi schermata cavo/computer, poi premi Rileva stato."
                )
                self.udid_var.set("Recovery/DFU mode")

        self.run_background("Invio comando recovery...", worker, callback)

    def confirm_exit_recovery(self):
        if not has_command("irecovery"):
            messagebox.showerror(
                "irecovery mancante",
                "Il comando irecovery non è installato.\n\n"
                "Su Kubuntu prova:\n"
                "sudo apt install libirecovery-utils",
            )
            return

        if not messagebox.askyesno(
            "Conferma uscita Recovery",
            "Vuoi inviare il comando di uscita da Recovery?\n\n"
            "Equivale a: irecovery -n",
        ):
            return

        def worker():
            return exit_recovery()

        def callback(result):
            self.log_command_result(result)

            if result.ok:
                self.log("Comando uscita Recovery inviato. Il device dovrebbe riavviarsi.")
                self.connection_state_var.set("Riavvio richiesto")
                self.phone_state_detail_var.set(
                    "Uscita da Recovery richiesta: il device dovrebbe riavviarsi in Normal Mode."
                )

        self.run_background("Uscita da Recovery...", worker, callback)

    # ---------------- AppleDB ----------------

    def open_appledb_for_device(self):
        product_type = self.current_product_type or self.model_var.get().strip()

        if not product_type or product_type == "-":
            messagebox.showwarning(
                "Modello non rilevato",
                "Prima premi 'Rileva stato' o 'Info device' per recuperare il ProductType del dispositivo.",
            )
            return

        self.set_status("Ricerca pagina AppleDB...")
        self.log(f"Ricerca AppleDB per ProductType: {product_type}")

        def worker():
            return get_appledb_device_link(product_type)

        def callback(link):
            self.set_status("Pronto")

            if link is None:
                messagebox.showwarning(
                    "AppleDB non trovato",
                    f"Non sono riuscito a trovare una pagina AppleDB per {product_type}.\n\n"
                    "Controlla la connessione internet oppure apri manualmente appledb.dev.",
                )
                self.log(f"AppleDB: nessun link trovato per {product_type}")
                return

            self.log(f"AppleDB: {link.name} -> {link.url}")

            system = platform.system()

            try:
                if system == "Darwin":
                    subprocess.run(["open", link.url], check=False)
                elif system == "Windows":
                    os.startfile(link.url)
                else:
                    subprocess.run(["xdg-open", link.url], check=False)

                self.phone_state_detail_var.set(
                    f"AppleDB aperto per {link.name} ({link.identifier})"
                )

            except Exception as exc:
                messagebox.showerror(
                    "Errore apertura browser",
                    f"Link trovato ma non sono riuscito ad aprire il browser:\n\n{link.url}\n\n{exc}",
                )
                self.log(f"Errore apertura AppleDB: {exc}")

        self.run_background("Ricerca AppleDB...", worker, callback)

    # ---------------- Pre-flight ----------------

    def run_preflight_check(self):
        product_type = self.current_product_type or self.model_var.get().strip()
        connection_state = self.connection_state_var.get().strip()
        ipsw_path = self.ipsw_var.get().strip()

        checks = run_preflight_checks(
            ipsw_path=ipsw_path,
            product_type=product_type,
            connection_state=connection_state,
        )

        headline, details = summarize_preflight(checks)

        self.preflight_status_var.set(headline)
        self.log("=== PRE-FLIGHT CHECK ===")
        self.log(headline)
        self.log(details)

        PreflightWindow(
            master=self,
            headline=headline,
            checks=checks,
            open_log_callback=self.open_log_center,
        )

    # ---------------- Log Center ----------------

    def open_log_center(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.focus_force()
            return

        self.log_window = LogWindow(
            master=self,
            get_udid_callback=self.get_current_udid,
            initial_app_log=self.app_console_history,
        )
        self.log("Log Center aperto.")

    # ---------------- Firmware actions ----------------

    def choose_ipsw(self):
        path = filedialog.askopenfilename(
            title="Seleziona firmware IPSW",
            filetypes=[
                ("Apple firmware IPSW", "*.ipsw"),
                ("Tutti i file", "*.*"),
            ],
        )

        if path:
            self.ipsw_var.set(path)
            self.log(f"IPSW selezionato: {path}")

    def confirm_dirty_flash(self):
        self._start_restore_operation(mode="update")

    def confirm_erase_restore(self):
        self._start_restore_operation(mode="erase")

    def _confirm_restore_operation(self, mode: str) -> bool:
        if mode == "erase":
            first_confirm = messagebox.askyesno(
                "Conferma ERASE RESTORE",
                (
                    "ATTENZIONE: questa operazione cancellerà completamente l'iPhone.\n\n"
                    "Verrà usato idevicerestore con --erase.\n"
                    "Dati, app e impostazioni verranno rimossi.\n\n"
                    "Continuare?"
                ),
            )

            if not first_confirm:
                return False

            typed = simpledialog.askstring(
                "Conferma finale",
                "Per confermare il ripristino distruttivo scrivi esattamente:\n\nERASE",
                parent=self,
            )

            if typed != "ERASE":
                messagebox.showinfo(
                    "Operazione annullata",
                    "Conferma non valida. Erase Restore annullato.",
                )
                return False

            return True

        return messagebox.askyesno(
            "Conferma dirty flash / update",
            (
                "Vuoi avviare il dirty flash IPSW?\n\n"
                "Il tool userà idevicerestore in modalità UPDATE, senza --erase.\n"
                "L'obiettivo è preservare dati e impostazioni.\n\n"
                "Backup fortemente consigliato prima di procedere.\n\n"
                "Continuare?"
            ),
        )

    def _start_restore_operation(self, mode: str):
        if self.restore_running:
            messagebox.showinfo(
                "Operazione in corso",
                "Un'operazione idevicerestore è già in corso.",
            )
            return

        valid, message = validate_ipsw(self.ipsw_var.get().strip())

        if not valid:
            messagebox.showwarning("IPSW non valido", message)
            return

        if shutil.which("idevicerestore") is None:
            messagebox.showerror(
                "idevicerestore mancante",
                "Il comando idevicerestore non è installato.\n\n"
                "Su Kubuntu prova:\n"
                "sudo apt install idevicerestore",
            )
            return

        current_state = self.connection_state_var.get().strip().lower()

        if "recovery" not in current_state and "dfu" not in current_state:
            continue_anyway = messagebox.askyesno(
                "Recovery/DFU non confermata",
                (
                    "Lo stato attuale non risulta Recovery o DFU.\n\n"
                    "Consigliato:\n"
                    "1. Premi 'Pre-flight Check'\n"
                    "2. Premi 'Rileva stato'\n"
                    "3. Entra in Recovery Mode\n"
                    "4. Avvia l'operazione firmware\n\n"
                    "Vuoi continuare comunque?"
                ),
            )

            if not continue_anyway:
                return

        if not self._confirm_restore_operation(mode):
            return

        self.restore_running = True

        if mode == "erase":
            operation_title = "ERASE RESTORE"
            operation_status = "Erase Restore in corso..."
            operation_mode = "erase / factory restore"
            erase_label = "ABILITATO"
            runner = run_erase_restore_stream
        else:
            operation_title = "DIRTY FLASH / UPDATE IPSW"
            operation_status = "Dirty flash IPSW in corso..."
            operation_mode = "update / preserve data"
            erase_label = "DISABILITATO"
            runner = run_update_restore_stream

        self.set_status(operation_status)
        self.phone_state_detail_var.set(
            f"{operation_title} in corso: modalità {operation_mode}, erase {erase_label}."
        )

        ipsw_path = message
        log_path = create_restore_log_path(mode=mode)

        self.log(f"=== AVVIO {operation_title} ===")
        self.log(f"Modalità: {operation_mode}")
        self.log(f"Erase: {erase_label}")
        self.log(f"IPSW: {ipsw_path}")
        self.log(f"Log file: {log_path}")

        def on_line(line: str):
            self.output_queue.put(line)

        def on_done(returncode: int):
            if returncode == 0:
                if mode == "erase":
                    self.output_queue.put("Erase Restore completato correttamente.")
                    self.after(0, self.set_status, "Erase Restore completato")
                    self.after(
                        0,
                        self.phone_state_detail_var.set,
                        "Erase Restore completato: il device dovrebbe riavviarsi alla configurazione iniziale.",
                    )
                else:
                    self.output_queue.put("Dirty flash completato correttamente.")
                    self.after(0, self.set_status, "Dirty flash completato")
                    self.after(
                        0,
                        self.phone_state_detail_var.set,
                        "Dirty flash completato: il device dovrebbe riavviarsi automaticamente.",
                    )
            else:
                self.output_queue.put("Operazione firmware terminata con errore. Controlla il Log Center.")
                self.after(0, self.set_status, "Operazione firmware fallita")
                self.after(
                    0,
                    self.phone_state_detail_var.set,
                    "Operazione firmware fallita: controlla il Log Center e lo stato del device.",
                )

            self.restore_running = False

        def worker():
            try:
                runner(
                    ipsw_path=ipsw_path,
                    on_line=on_line,
                    on_done=on_done,
                    log_path=log_path,
                )
            except Exception as exc:
                self.output_queue.put(f"Errore idevicerestore: {exc}")
                self.restore_running = False
                self.after(0, self.set_status, "Errore operazione firmware")

        threading.Thread(target=worker, daemon=True).start()

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

            self.log(f"Cartella log: {log_dir}")

        except Exception as exc:
            self.log(f"Errore apertura cartella log: {exc}")

    def clear_console(self):
        self.app_console_history.clear()

        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.app_console.delete("1.0", "end")
            self.log_window.app_lines.clear()

        self.set_status("Log pulito")
