# Extrait de gui.py - ajout d'un panneau de gestion des fenêtres
def _build_multi_window_panel(self):
    panel = ctk.CTkFrame(self)
    panel.pack(fill="x", padx=12, pady=8)

    ctk.CTkLabel(panel, text="Applications :").pack(side="left", padx=8)
    self.app_selector = ctk.CTkOptionMenu(panel, values=["—"])
    self.app_selector.pack(side="left", fill="x", expand=True, padx=4)

    ctk.CTkButton(panel, text="Ouvrir dans une nouvelle fenêtre",
                  command=self._launch_app_window).pack(side="left", padx=4)

def _refresh_apps(self):
    """Liste les packages installés sur l'appareil."""
    # Utilise adb shell pm list packages -3 (apps tierces) ou sans -3 pour tout
    result = subprocess.run([self.orch.adb_path, "shell", "pm", "list", "packages", "-3"],
                            capture_output=True, text=True, timeout=15)
    packages = [line.replace("package:", "").strip() for line in result.stdout.splitlines()]
    self.app_selector.configure(values=packages or ["—"])

def _launch_app_window(self):
    app = self.app_selector.get()
    if app == "—": return
    display = DisplayConfig(  # Utilise les paramètres de l'UI
        width=int(self.width_entry.get()),
        height=int(self.height_entry.get()),
        dpi=int(self.dpi_entry.get()),
    )
    connection = ConnectionConfig(serial=self.device_var.get() or None)
    # Délègue au MultiSessionOrchestrator
    self.multi_orch.launch_app_window(app, display, connection)