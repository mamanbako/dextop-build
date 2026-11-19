# dextop/gui.py
import threading
import customtkinter as ctk
from tkinter import messagebox

from dextop.orchestrator import (
    ScrcpyOrchestrator, DisplayConfig, ConnectionConfig, SessionState,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DeXtopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DeXtop — Desktop mode via scrcpy")
        self.geometry("720x560")

        self.orch = ScrcpyOrchestrator(
            on_state_change=self._on_state,
            on_log=self._on_log,
        )
        self._build_ui()
        self._refresh_devices()

    # ---------- UI ----------

    def _build_ui(self):
        # Ligne appareil
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(top, text="Appareil :").pack(side="left", padx=(8, 4))
        self.device_var = ctk.StringVar(value="")
        self.device_menu = ctk.CTkOptionMenu(top, variable=self.device_var, values=["—"])
        self.device_menu.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(top, text="↻", width=36, command=self._refresh_devices).pack(side="left")

        # Paramètres écran
        params = ctk.CTkFrame(self)
        params.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(params, text="Résolution :").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.width_entry = ctk.CTkEntry(params, width=80)
        self.width_entry.insert(0, "1920")
        self.width_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(params, text="×").grid(row=0, column=2)
        self.height_entry = ctk.CTkEntry(params, width=80)
        self.height_entry.insert(0, "1080")
        self.height_entry.grid(row=0, column=3, padx=4)

        ctk.CTkLabel(params, text="DPI :").grid(row=0, column=4, padx=8)
        self.dpi_entry = ctk.CTkEntry(params, width=80)
        self.dpi_entry.insert(0, "240")
        self.dpi_entry.grid(row=0, column=5, padx=4)

        ctk.CTkLabel(params, text="App (optionnel) :").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.app_entry = ctk.CTkEntry(params, placeholder_text="com.android.settings")
        self.app_entry.grid(row=1, column=1, columnspan=5, sticky="ew", padx=4)

        # Boutons
        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=12, pady=8)
        self.start_btn = ctk.CTkButton(actions, text="▶ Démarrer", command=self._start)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ctk.CTkButton(
            actions, text="■ Arrêter", command=self._stop,
            state="disabled", fg_color="#8b1e1e",
        )
        self.stop_btn.pack(side="left", padx=4)

        # Logs
        self.log_box = ctk.CTkTextbox(self, height=240)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---------- Actions ----------

    def _refresh_devices(self):
        try:
            devices = self.orch.list_devices()
        except Exception as e:
            devices = [f"erreur: {e}"]
        values = devices or ["—"]
        self.device_menu.configure(values=values)
        self.device_var.set(values[0])

    def _start(self):
        try:
            display = DisplayConfig(
                width=int(self.width_entry.get()),
                height=int(self.height_entry.get()),
                dpi=int(self.dpi_entry.get()),
                start_app=self.app_entry.get().strip() or None,
            )
            serial = self.device_var.get()
            connection = ConnectionConfig(serial=serial if serial != "—" else None)
            self.orch.start(display, connection)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _stop(self):
        threading.Thread(target=self.orch.stop, daemon=True).start()

    # ---------- Callbacks (depuis scrcpy) ----------

    def _on_state(self, state: SessionState):
        def update():
            running = state in (SessionState.RUNNING, SessionState.STARTING)
            self.start_btn.configure(state="disabled" if running else "normal")
            self.stop_btn.configure(state="normal" if running else "disabled")
            self.title(f"DeXtop — {state.value}")
        self.after(0, update)

    def _on_log(self, line: str):
        def update():
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
        self.after(0, update)


def run():
    app = DeXtopApp()
    app.mainloop()


if __name__ == "__main__":
    run()