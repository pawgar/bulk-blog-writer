"""Główne okno aplikacji z zakładkami."""

import customtkinter as ctk

from config_manager import load_config, save_config
from ui.tab_generate import GenerateTab
from ui.tab_history import HistoryTab
from ui.tab_settings import SettingsTab
from ui.components import ACCENT_GREEN


class MainWindow(ctk.CTk):
    """Główne okno Bulk Blog Writer."""

    def __init__(self):
        super().__init__()
        self.title("Bulk Blog Writer — SemTree")
        self.geometry("1100x750")
        self.minsize(900, 600)

        self.config_data = load_config()

        # Motyw
        ctk.set_appearance_mode(self.config_data.get("appearance_mode", "dark"))
        ctk.set_default_color_theme("green")

        self._build_ui()

    def _build_ui(self):
        # Tabview
        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=ACCENT_GREEN,
            segmented_button_selected_hover_color="#25C466",
            segmented_button_unselected_color="gray20",
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Zakładki
        self.tabview.add("Generuj")
        self.tabview.add("Historia")
        self.tabview.add("Ustawienia")

        # Zakładka Ustawienia (tworzymy pierwszą bo inne mogą potrzebować konfiguracji)
        self.settings_tab = SettingsTab(
            self.tabview.tab("Ustawienia"),
            config=self.config_data,
            save_callback=self._on_save_config,
        )
        self.settings_tab.pack(fill="both", expand=True)

        # Zakładka Generuj
        self.generate_tab = GenerateTab(
            self.tabview.tab("Generuj"),
            config=self.config_data,
            get_config_callback=self._get_current_config,
        )
        self.generate_tab.pack(fill="both", expand=True)

        # Zakładka Historia
        self.history_tab = HistoryTab(self.tabview.tab("Historia"))
        self.history_tab.pack(fill="both", expand=True)

        # Domyślna zakładka
        self.tabview.set("Generuj")

        # Odświeżaj historię przy przejściu na zakładkę
        self.tabview.configure(command=self._on_tab_changed)

    def _on_tab_changed(self):
        """Callback przy zmianie zakładki."""
        current = self.tabview.get()
        if current == "Historia":
            self.history_tab.refresh()

    def _on_save_config(self, config: dict):
        """Callback po zapisaniu ustawień."""
        self.config_data = config
        save_config(config)

    def _get_current_config(self) -> dict:
        """Zwraca aktualną konfigurację z zakładki Ustawienia."""
        return self.settings_tab.get_config()
