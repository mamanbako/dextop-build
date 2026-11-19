import threading

import customtkinter as ctk
from tkinter import messagebox

from dextop.config import Config
from dextop.orchestrator import (
    ConnectionConfig,
    DisplayConfig,
    ScrcpyOrchestrator,
    SessionState,
)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DeXtopApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config_store = Config()
        self.title("DeXtop")
        self.geometry("760x620")
        self.minsize(680, 540)
        self.orch = ScrcpyOrchestrator(
            on_state_change=self._on_state,
            on_log=self._on_log,
        )
        self._build_ui()
        self._refresh_devices()

    def _build_ui(self) -> None:
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(top, text="Appareil").pack(side="left", padx=(8, 6))
        self.device_var = ctk.StringVar(value="")
        self.device_menu = ctk.CTkOptionMenu(top, variable=self.device_var, values=["—"])
        self.device_menu.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(top, text="Actualiser", width=90, command=self._refresh_devices).pack(side="left", padx=8)

        params = ctk.CTkFrame(self)
        params.pack(fill="x", padx=12, pady=8)
        params.grid_columnconfigure((1, 3, 5), weight=1)

        ctk.CTkLabel(params, text="Largeur").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.width_entry = ctk.CTkEntry(params)
        self.width_entry.insert(0, str(self.config_store.get("width", 1920)))
        self.width_entry.grid(row=0, column=1, padx=4, sticky="ew")

        ctk.CTkLabel(params, text="Hauteur").grid(row=0, column=2, padx=8)
        self.height_entry = ctk.CTkEntry(params)
        self.height_entry.insert(0, str(self.config_store.get("height", 1080)))
        self.height_entry.grid(row=0, column=3, padx=4, sticky="ew")

        ctk.CTkLabel(params, text="DPI").grid(row=0, column=4, padx=8)
        self.dpi_entry = ctk.CTkEntry(params)
        self.dpi_entry.insert(0, str(self.config_store.get("dpi", 240)))
        self.dpi_entry.grid(row=0, column=5, padx=4, sticky="ew")

        ctk.CTkLabel(params, text="Application").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.app_entry = ctk.CTkEntry(params, placeholder_text="com.android.settings")
        self.app_entry.grid(row=1, column=1, columnspan=4, padx=4, pady=6, sticky="ew")
        ctk.CTkButton(params, text="Lister les apps", width=110, command=self._refresh_apps).grid(
            row=1, column=5, padx=4, pady=6, sticky="ew"
        )

        ctk.CTkLabel(params, text="Applications installées").grid(
            row=2, column=0, padx=8, pady=(2, 6), sticky="w"
        )
        self.app_menu = ctk.CTkOptionMenu(
            params,
            values=["—"],
            command=self._select_app,
        )
        self.app_menu.grid(row=2, column=1, columnspan=5, padx=4, pady=(2, 6), sticky="ew")

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=12, pady=8)
        self.start_btn = ctk.CTkButton(actions, text="Démarrer", command=self._start)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ctk.CTkButton(
            actions, text="Arrêter", command=self._stop,
            state="disabled", fg_color="#8b1e1e", hover_color="#a32626",
        )
        self.stop_btn.pack(side="left", padx=4)

        ctk.CTkLabel(self, text="Journal", anchor="w").pack(fill="x", padx=16)
        self.log_box = ctk.CTkTextbox(self, height=300)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def _refresh_devices(self) -> None:
        def refresh() -> None:
            try:
                devices = self.orch.list_devices()
                values = devices or ["—"]
                last_serial = self.config_store.get("last_serial")
                if last_serial in devices:
                    values = [last_serial] + [device for device in devices if device != last_serial]
            except Exception as exc:
                values = ["—"]
                self.after(0, lambda: self._on_log(f"[dextop] Erreur ADB : {exc}"))
            self.after(0, lambda: self._set_devices(values))

        threading.Thread(target=refresh, daemon=True).start()

    def _set_devices(self, values: list[str]) -> None:
        self.device_menu.configure(values=values)
        self.device_var.set(values[0])

    def _refresh_apps(self) -> None:
        serial = self.device_var.get()
        serial = serial if serial != "—" else None

        def refresh() -> None:
            try:
                result = self.orch.list_packages(serial=serial, third_party_only=True)
                values = result or ["—"]
            except Exception as exc:
                values = ["—"]
                self.after(0, lambda: self._on_log(f"[dextop] Erreur lors de la lecture des applications : {exc}"))
            self.after(0, lambda: self._set_apps(values))

        threading.Thread(target=refresh, daemon=True).start()

    def _set_apps(self, values: list[str]) -> None:
        self.app_menu.configure(values=values)
        self.app_menu.set(values[0])

    def _select_app(self, package: str) -> None:
        if package == "—":
            return
        self.app_entry.delete(0, "end")
        self.app_entry.insert(0, package)

    def _start(self) -> None:
        try:
            width = int(self.width_entry.get())
            height = int(self.height_entry.get())
            dpi = int(self.dpi_entry.get())
            if width < 320 or height < 320 or dpi < 120:
                raise ValueError("Une résolution valide utilise au moins 320 × 320 et 120 DPI.")

            serial = self.device_var.get()
            serial = serial if serial != "—" else None
            display = DisplayConfig(
                width=width, height=height, dpi=dpi,
                start_app=self.app_entry.get().strip() or None,
            )
            connection = ConnectionConfig(serial=serial)
            self.config_store.set("width", width)
            self.config_store.set("height", height)
            self.config_store.set("dpi", dpi)
            self.config_store.set("last_serial", serial)
            self.orch.start(display, connection)
        except Exception as exc:
            messagebox.showerror("Impossible de démarrer DeXtop", str(exc))

    def _stop(self) -> None:
        threading.Thread(target=self.orch.stop, daemon=True).start()

    def _on_state(self, state: SessionState) -> None:
        def update() -> None:
            running = state in (SessionState.RUNNING, SessionState.STARTING)
            self.start_btn.configure(state="disabled" if running else "normal")
            self.stop_btn.configure(state="normal" if running else "disabled")
            self.title(f"DeXtop — {state.value}")

        self.after(0, update)

    def _on_log(self, line: str) -> None:
        def update() -> None:
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")

        self.after(0, update)


def run() -> None:
    app = DeXtopApp()
    app.mainloop()


if __name__ == "__main__":
    run()
