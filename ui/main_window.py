"""Główne okno aplikacji z zakładkami."""

import threading
import urllib.request
import json

import customtkinter as ctk

from config_manager import load_config, save_config
from ui.tab_generate import GenerateTab
from ui.tab_history import HistoryTab
from ui.tab_settings import SettingsTab
from ui.tab_clients import ClientsTab
from ui.components import ACCENT_GREEN

STATUS_URL = "https://status.claude.com/api/v2/status.json"
STATUS_REFRESH_MS = 60_000  # co 60 sekund


class MainWindow(ctk.CTk):
    """Główne okno Bulk Blog Writer."""

    def __init__(self):
        super().__init__()
        self.title("Bulk Blog Writer — SemTree")
        self.geometry("1100x750")
        self.minsize(900, 600)

        self.config_data = load_config()

        ctk.set_appearance_mode(self.config_data.get("appearance_mode", "dark"))
        ctk.set_default_color_theme("green")

        self._blink_state = False
        self._blink_job = None
        self._status_indicator = "unknown"  # "ok" | "degraded" | "unknown"

        self._build_ui()
        self._fetch_status()

    def _build_ui(self):
        # Pasek statusu API — nad tabview
        status_bar = ctk.CTkFrame(self, fg_color="transparent", height=28)
        status_bar.pack(fill="x", padx=12, pady=(6, 0))
        status_bar.pack_propagate(False)

        # Dioda (CTkLabel z małym kółkiem przez emoji lub kolorowy kwadrat)
        self._led = ctk.CTkLabel(
            status_bar,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color="gray40",
            width=20,
        )
        self._led.pack(side="left")

        self._status_label = ctk.CTkLabel(
            status_bar,
            text="Sprawdzanie statusu API...",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
        )
        self._status_label.pack(side="left", padx=(4, 0))

        # Czas ostatniego sprawdzenia
        self._status_time_label = ctk.CTkLabel(
            status_bar,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="gray40",
        )
        self._status_time_label.pack(side="right", padx=(0, 4))

        # Tabview
        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=ACCENT_GREEN,
            segmented_button_selected_hover_color="#25C466",
            segmented_button_unselected_color="gray20",
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.tabview.add("Generuj")
        self.tabview.add("Klienci")
        self.tabview.add("Historia")
        self.tabview.add("Ustawienia")

        self.settings_tab = SettingsTab(
            self.tabview.tab("Ustawienia"),
            config=self.config_data,
            save_callback=self._on_save_config,
        )
        self.settings_tab.pack(fill="both", expand=True)

        self.generate_tab = GenerateTab(
            self.tabview.tab("Generuj"),
            config=self.config_data,
            get_config_callback=self._get_current_config,
        )
        self.generate_tab.pack(fill="both", expand=True)

        self.clients_tab = ClientsTab(self.tabview.tab("Klienci"))
        self.clients_tab.pack(fill="both", expand=True)

        self.history_tab = HistoryTab(self.tabview.tab("Historia"))
        self.history_tab.pack(fill="both", expand=True)

        self.tabview.set("Generuj")
        self.tabview.configure(command=self._on_tab_changed)

    # ===== Status API =====

    def _fetch_status(self):
        """Pobiera status API w tle i planuje kolejne sprawdzenie."""
        threading.Thread(target=self._do_fetch, daemon=True).start()
        self.after(STATUS_REFRESH_MS, self._fetch_status)

    def _do_fetch(self):
        """Worker: pobiera JSON ze status.claude.com."""
        try:
            req = urllib.request.Request(
                STATUS_URL,
                headers={"User-Agent": "BulkBlogWriter/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            indicator = data.get("status", {}).get("indicator", "unknown")
            description = data.get("status", {}).get("description", "Nieznany status")

            if indicator == "none":
                self.after(0, lambda: self._set_status("ok", description))
            else:
                self.after(0, lambda: self._set_status("degraded", description))

        except Exception:
            self.after(0, lambda: self._set_status("unknown", "Brak połączenia ze status.claude.com"))

    def _set_status(self, state: str, description: str):
        """Aktualizuje UI i uruchamia miganie."""
        from datetime import datetime

        self._status_indicator = state
        self._status_time_label.configure(
            text=f"Sprawdzono: {datetime.now().strftime('%H:%M:%S')}"
        )

        if state == "ok":
            self._status_label.configure(
                text=f"Anthropic API: {description}",
                text_color=ACCENT_GREEN,
            )
            self._start_blink(ACCENT_GREEN, "#1a7a40")
        elif state == "degraded":
            self._status_label.configure(
                text=f"Anthropic API: {description}",
                text_color="#EF4444",
            )
            self._start_blink("#EF4444", "#7a1a1a")
        else:
            self._status_label.configure(
                text=f"Anthropic API: {description}",
                text_color="gray50",
            )
            self._stop_blink("gray40")

    def _start_blink(self, color_on: str, color_off: str):
        """Uruchamia miganie diody."""
        if self._blink_job:
            self.after_cancel(self._blink_job)
        self._blink_colors = (color_on, color_off)
        self._do_blink()

    def _do_blink(self):
        colors = getattr(self, "_blink_colors", (ACCENT_GREEN, "#1a7a40"))
        color = colors[0] if self._blink_state else colors[1]
        self._led.configure(text_color=color)
        self._blink_state = not self._blink_state
        self._blink_job = self.after(800, self._do_blink)

    def _stop_blink(self, color: str):
        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        self._led.configure(text_color=color)

    # ===== Reszta =====

    def _on_tab_changed(self):
        if self.tabview.get() == "Historia":
            self.history_tab.refresh()

    def _on_save_config(self, config: dict):
        self.config_data = config
        save_config(config)

    def _get_current_config(self) -> dict:
        return self.settings_tab.get_config()
