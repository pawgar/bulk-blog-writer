"""Zakładka Ustawienia — API key, model, ścieżki."""

import customtkinter as ctk
from tkinter import filedialog
import threading
import anthropic

from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER


class SettingsTab(ctk.CTkFrame):
    """Zakładka z ustawieniami aplikacji."""

    def __init__(self, master, config: dict, save_callback):
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.save_callback = save_callback
        self._show_password = False
        self._build_ui()

    def _build_ui(self):
        # Kontener z marginesami
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=20)

        title = ctk.CTkLabel(
            container,
            text="Ustawienia",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 20))

        # --- API Key ---
        ctk.CTkLabel(container, text="Anthropic API Key:", font=ctk.CTkFont(size=13)).pack(
            anchor="w", pady=(10, 2)
        )
        key_frame = ctk.CTkFrame(container, fg_color="transparent")
        key_frame.pack(fill="x", pady=(0, 5))

        self.api_key_entry = ctk.CTkEntry(
            key_frame, show="•", width=500, font=ctk.CTkFont(size=13)
        )
        self.api_key_entry.pack(side="left", fill="x", expand=True)
        if self.config.get("api_key"):
            self.api_key_entry.insert(0, self.config["api_key"])

        self.toggle_pw_btn = ctk.CTkButton(
            key_frame,
            text="Pokaż",
            width=70,
            command=self._toggle_password,
            fg_color="gray30",
            hover_color="gray40",
        )
        self.toggle_pw_btn.pack(side="left", padx=(8, 0))

        # --- Model ---
        ctk.CTkLabel(container, text="Model:", font=ctk.CTkFont(size=13)).pack(
            anchor="w", pady=(15, 2)
        )
        self.model_var = ctk.StringVar(value=self.config.get("model", "claude-opus-4-6"))
        self.model_dropdown = ctk.CTkOptionMenu(
            container,
            values=["claude-opus-4-6", "claude-sonnet-4-6"],
            variable=self.model_var,
            width=250,
        )
        self.model_dropdown.pack(anchor="w")

        # --- Domyślny katalog wyjściowy ---
        ctk.CTkLabel(
            container, text="Domyślny katalog wyjściowy:", font=ctk.CTkFont(size=13)
        ).pack(anchor="w", pady=(15, 2))
        dir_frame = ctk.CTkFrame(container, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(0, 5))

        self.output_dir_entry = ctk.CTkEntry(dir_frame, width=400, font=ctk.CTkFont(size=13))
        self.output_dir_entry.pack(side="left", fill="x", expand=True)
        self.output_dir_entry.insert(
            0, self.config.get("default_output_dir", "./output")
        )

        ctk.CTkButton(
            dir_frame,
            text="Przeglądaj...",
            width=100,
            command=self._browse_output_dir,
            fg_color="gray30",
            hover_color="gray40",
        ).pack(side="left", padx=(8, 0))

        # --- Domyślny język ---
        ctk.CTkLabel(container, text="Domyślny język:", font=ctk.CTkFont(size=13)).pack(
            anchor="w", pady=(15, 2)
        )
        self.lang_var = ctk.StringVar(value=self.config.get("default_lang", "pl").upper())
        self.lang_dropdown = ctk.CTkOptionMenu(
            container,
            values=["PL", "DE", "NL", "ES", "SV", "CS", "EN"],
            variable=self.lang_var,
            width=120,
        )
        self.lang_dropdown.pack(anchor="w")

        # --- Opóźnienie między requestami ---
        ctk.CTkLabel(
            container,
            text="Opóźnienie między requestami (sekundy):",
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(15, 2))

        delay_frame = ctk.CTkFrame(container, fg_color="transparent")
        delay_frame.pack(anchor="w", pady=(0, 5))

        self.delay_var = ctk.IntVar(value=self.config.get("delay_seconds", 5))
        self.delay_slider = ctk.CTkSlider(
            delay_frame,
            from_=1,
            to=30,
            number_of_steps=29,
            variable=self.delay_var,
            width=250,
            progress_color=ACCENT_GREEN,
            button_color=ACCENT_GREEN,
            button_hover_color=ACCENT_GREEN_HOVER,
        )
        self.delay_slider.pack(side="left")

        self.delay_label = ctk.CTkLabel(
            delay_frame,
            textvariable=self.delay_var,
            font=ctk.CTkFont(size=13),
            width=30,
        )
        self.delay_label.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(delay_frame, text="s", font=ctk.CTkFont(size=13)).pack(side="left")

        # --- Przyciski ---
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(anchor="w", pady=(30, 10))

        ctk.CTkButton(
            btn_frame,
            text="Zapisz ustawienia",
            command=self._save,
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN_HOVER,
            text_color="black",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=180,
            height=38,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="Testuj połączenie z API",
            command=self._test_api,
            fg_color="gray30",
            hover_color="gray40",
            width=200,
            height=38,
        ).pack(side="left", padx=(12, 0))

        # Status label
        self.status_label = ctk.CTkLabel(
            container, text="", font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

    def _toggle_password(self):
        self._show_password = not self._show_password
        self.api_key_entry.configure(show="" if self._show_password else "•")
        self.toggle_pw_btn.configure(
            text="Ukryj" if self._show_password else "Pokaż"
        )

    def _browse_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, path)

    def _save(self):
        self.config["api_key"] = self.api_key_entry.get().strip()
        self.config["model"] = self.model_var.get()
        self.config["default_output_dir"] = self.output_dir_entry.get().strip()
        self.config["default_lang"] = self.lang_var.get().lower()
        self.config["delay_seconds"] = self.delay_var.get()
        self.save_callback(self.config)
        self.status_label.configure(text="Ustawienia zapisane.", text_color=ACCENT_GREEN)

    def _test_api(self):
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            self.status_label.configure(
                text="Podaj API key przed testowaniem.", text_color="#F59E0B"
            )
            return

        self.status_label.configure(text="Testowanie...", text_color="gray60")

        def _do_test():
            try:
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=50,
                    messages=[{"role": "user", "content": "Say OK"}],
                    timeout=15.0,
                )
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="Połączenie OK — API działa prawidłowo.",
                        text_color=ACCENT_GREEN,
                    ),
                )
            except anthropic.AuthenticationError:
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="Błąd: Nieprawidłowy API key.", text_color="#EF4444"
                    ),
                )
            except Exception as e:
                msg = str(e)[:80]
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text=f"Błąd: {msg}", text_color="#EF4444"
                    ),
                )

        threading.Thread(target=_do_test, daemon=True).start()

    def get_config(self) -> dict:
        """Zwraca aktualną konfigurację z pól formularza."""
        return {
            "api_key": self.api_key_entry.get().strip(),
            "model": self.model_var.get(),
            "default_output_dir": self.output_dir_entry.get().strip(),
            "default_lang": self.lang_var.get().lower(),
            "delay_seconds": self.delay_var.get(),
            "appearance_mode": self.config.get("appearance_mode", "dark"),
        }
