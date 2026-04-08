"""Zakładka Generuj — główny workflow generowania artykułów."""

import io
import re
import time
import platform
import subprocess
import threading
import zipfile
from pathlib import Path
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import anthropic

from xlsx_parser import read_xlsx_headers, auto_detect_columns, parse_content_plan
from api_client import generate_article_with_retry, estimate_session_cost
from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER, LogConsole
from ui.tab_history import add_session
from ui.article_preview import ArticlePreviewWindow


# ===== Pomocnicze =====

def _slugify(text: str, max_len: int = 50) -> str:
    """Tworzy slug z tekstu — do nazw plików."""
    text = text.lower().strip()
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "á": "a", "é": "e", "í": "i", "ú": "u", "ñ": "n",
        "å": "a", "ě": "e", "š": "s", "č": "c", "ř": "r",
        "ž": "z", "ý": "y", "ď": "d", "ť": "t", "ů": "u",
        "ā": "a", "ē": "e", "ī": "i", "ū": "u", "ģ": "g",
        "ķ": "k", "ļ": "l", "ņ": "n",
        "ė": "e", "į": "i", "ų": "u",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text


def _send_system_notification(title: str, message: str):
    """Wysyła powiadomienie systemowe (nieblokujące)."""
    try:
        if platform.system() == "Windows":
            ps_script = (
                "[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]; "
                "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f'$template.SelectSingleNode("//text[@id=\'1\']").InnerText = "{title}"; '
                f'$template.SelectSingleNode("//text[@id=\'2\']").InnerText = "{message}"; '
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("BulkBlogWriter").Show($toast)'
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        elif platform.system() == "Darwin":
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{message}" with title "{title}"']
            )
    except Exception:
        pass  # Powiadomienie opcjonalne


# ===== Dialog mapowania kolumn =====

FIELD_LABELS = {
    "title": "Tytuł wpisu *",
    "main_kw": "Główne słowo kluczowe",
    "secondary_kw": "Słowa kluczowe poboczne",
    "notes": "Dodatkowe informacje",
    "domain": "Domena",
    "lang": "Język",
}
FIELD_ORDER = ["title", "main_kw", "secondary_kw", "notes", "domain", "lang"]


class ColumnMappingDialog(ctk.CTkToplevel):
    """Dialog do mapowania kolumn XLSX na pola content planu."""

    def __init__(self, master, headers: list[str], auto_map: dict):
        super().__init__(master)
        self.title("Mapowanie kolumn XLSX")
        self.geometry("520x440")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.result = None
        self._headers = headers
        self._vars: dict[str, ctk.StringVar] = {}
        self._none_label = "— pomiń —"
        self._options = [self._none_label] + [f"{i + 1}. {h}" for i, h in enumerate(headers)]
        self._build_ui(auto_map)
        self.after(100, self.focus_force)

    def _build_ui(self, auto_map):
        ctk.CTkLabel(
            self, text="Wskaż kolumny z pliku XLSX",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 3))
        ctk.CTkLabel(
            self,
            text="Automatyczne mapowanie — sprawdź i zmień jeśli trzeba.",
            font=ctk.CTkFont(size=12), text_color="gray50",
        ).pack(pady=(0, 10))

        self._error_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color="#EF4444"
        )
        self._error_label.pack()

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=30)

        for field_key in FIELD_ORDER:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(
                row, text=FIELD_LABELS[field_key],
                font=ctk.CTkFont(size=13), width=200, anchor="w",
            ).pack(side="left")

            detected_idx = auto_map.get(field_key)
            if detected_idx is not None and detected_idx < len(self._headers):
                default = f"{detected_idx + 1}. {self._headers[detected_idx]}"
            else:
                default = self._none_label

            var = ctk.StringVar(value=default)
            self._vars[field_key] = var
            ctk.CTkOptionMenu(row, values=self._options, variable=var, width=260).pack(side="right")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(15, 15))
        ctk.CTkButton(
            btn_frame, text="Zatwierdź",
            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER,
            text_color="black", font=ctk.CTkFont(size=14, weight="bold"),
            width=140, height=36, command=self._on_confirm,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_frame, text="Anuluj",
            fg_color="gray30", hover_color="gray40",
            width=100, height=36, command=self._on_cancel,
        ).pack(side="left")

    def _on_confirm(self):
        mapping = {}
        for field_key in FIELD_ORDER:
            val = self._vars[field_key].get()
            if val == self._none_label:
                mapping[field_key] = None
            else:
                try:
                    mapping[field_key] = int(val.split(".")[0]) - 1
                except (ValueError, IndexError):
                    mapping[field_key] = None
        if mapping.get("title") is None:
            self._error_label.configure(text="Kolumna 'Tytuł wpisu' jest wymagana!")
            return
        self.result = mapping
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


# ===== Główna zakładka =====

class GenerateTab(ctk.CTkFrame):
    """Zakładka z głównym workflow generowania artykułów."""

    def __init__(self, master, config: dict, get_config_callback):
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.get_config = get_config_callback
        self.articles: list[dict] = []
        self.checkboxes: list[ctk.BooleanVar] = []
        self.status_labels: list[ctk.CTkLabel] = []
        self.regen_btns: list[ctk.CTkButton] = []
        self.article_filepaths: list[str] = []   # ścieżka do pliku per artykuł
        self._generating = False
        self._stop_flag = False
        self._xlsx_path = ""
        self._session_dir: Path | None = None
        self._build_ui()

    def _build_ui(self):
        # ===== SEKCJA 1: Konfiguracja =====
        config_frame = ctk.CTkFrame(self, fg_color="transparent")
        config_frame.pack(fill="x", padx=20, pady=(15, 5))

        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))

        self.xlsx_btn = ctk.CTkButton(
            row1, text="Wczytaj XLSX", command=self._load_xlsx,
            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER,
            text_color="black", font=ctk.CTkFont(size=13, weight="bold"),
            width=130, height=34,
        )
        self.xlsx_btn.pack(side="left")

        self.xlsx_label = ctk.CTkLabel(
            row1, text="Nie wczytano pliku", text_color="gray50", font=ctk.CTkFont(size=12)
        )
        self.xlsx_label.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(row1, text="Język:", font=ctk.CTkFont(size=12)).pack(side="right", padx=(5, 0))
        default_lang = self.config.get("default_lang", "pl").upper()
        self.lang_var = ctk.StringVar(value=default_lang)
        ctk.CTkOptionMenu(
            row1, values=["PL", "DE", "NL", "ES", "SV", "CS", "EN", "LT", "LV"],
            variable=self.lang_var, width=70,
        ).pack(side="right")

        self.domain_entry = ctk.CTkEntry(
            row1, placeholder_text="Domena (domyślna)", width=200, font=ctk.CTkFont(size=12)
        )
        self.domain_entry.pack(side="right", padx=(0, 15))
        ctk.CTkLabel(row1, text="Domena:", font=ctk.CTkFont(size=12)).pack(side="right", padx=(5, 0))

        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 5))

        self.zaplecze_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row2, text="Artykuły zapleczowe", variable=self.zaplecze_var,
            font=ctk.CTkFont(size=12), command=self._on_zaplecze_toggle,
            checkbox_width=20, checkbox_height=20,
        ).pack(side="left")

        ctk.CTkButton(
            row2, text="Przeglądaj...", width=90, fg_color="gray30", hover_color="gray40",
            command=self._browse_output, height=28,
        ).pack(side="right")
        self.output_entry = ctk.CTkEntry(row2, width=300, font=ctk.CTkFont(size=12))
        self.output_entry.pack(side="right", padx=(5, 5))
        self.output_entry.insert(0, self.config.get("default_output_dir", "./output"))
        ctk.CTkLabel(row2, text="Katalog wyjściowy:", font=ctk.CTkFont(size=12)).pack(side="right", padx=(0, 5))

        # ===== SEKCJA 2: Tabela =====
        table_header = ctk.CTkFrame(self, fg_color="transparent")
        table_header.pack(fill="x", padx=20, pady=(10, 2))

        for text, cmd in [
            ("☑ Zaznacz wszystkie", lambda: self._set_all_checkboxes(True)),
            ("☐ Odznacz wszystkie", lambda: self._set_all_checkboxes(False)),
            ("⚠ Zaznacz błędy", self._select_errors),
        ]:
            ctk.CTkButton(
                table_header, text=text, fg_color="gray30", hover_color="gray40",
                text_color="white", font=ctk.CTkFont(size=12),
                width=145, height=28, command=cmd,
            ).pack(side="left", padx=(0, 6))

        col_header = ctk.CTkFrame(self, fg_color="gray20", corner_radius=4)
        col_header.pack(fill="x", padx=20, pady=(2, 0))
        widths = [30, 30, 210, 130, 150, 100, 35, 50, 90]
        labels = ["✓", "#", "Tytuł wpisu", "Główne KW", "Słowa poboczne", "Domena", "Jęz.", "↕", "Status"]
        for w, label in zip(widths, labels):
            ctk.CTkLabel(
                col_header, text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=w, anchor="w",
            ).pack(side="left", padx=3, pady=4)

        self.table_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=280)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        self.empty_label = ctk.CTkLabel(
            self.table_frame,
            text="Wczytaj plik XLSX z content planem, aby rozpocząć.",
            text_color="gray50", font=ctk.CTkFont(size=13),
        )
        self.empty_label.pack(pady=40)

        # ===== SEKCJA 3: Panel estymacji =====
        self.estimate_frame = ctk.CTkFrame(self, fg_color="gray17", corner_radius=6)
        # (wypełniany dynamicznie — pokazywany po wczytaniu XLSX)

        # ===== SEKCJA 4: Kontrolki =====
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(fill="x", padx=20, pady=(5, 5))

        btn_row = ctk.CTkFrame(controls_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 5))

        self.generate_btn = ctk.CTkButton(
            btn_row, text="▶  Generuj zaznaczone", command=self._start_generation,
            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER,
            text_color="black", font=ctk.CTkFont(size=14, weight="bold"),
            width=200, height=40,
        )
        self.generate_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            btn_row, text="⏹  Stop", command=self._stop_generation,
            fg_color="#EF4444", hover_color="#DC2626",
            font=ctk.CTkFont(size=13), width=100, height=40, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        self.zip_btn = ctk.CTkButton(
            btn_row, text="📦 Eksportuj ZIP", command=self._export_zip,
            fg_color="gray30", hover_color="gray40",
            font=ctk.CTkFont(size=12), width=140, height=40, state="disabled",
        )
        self.zip_btn.pack(side="left", padx=(10, 0))

        self.progress_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12), text_color="gray50"
        )
        self.progress_label.pack(side="left", padx=(15, 0))

        self.time_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=11), text_color="gray50"
        )
        self.time_label.pack(side="right")

        cost_row = ctk.CTkFrame(controls_frame, fg_color="transparent")
        cost_row.pack(fill="x", pady=(0, 3))

        self.cost_label = ctk.CTkLabel(
            cost_row, text="", font=ctk.CTkFont(size=12), text_color="#F59E0B"
        )
        self.cost_label.pack(side="left")

        self.tokens_label = ctk.CTkLabel(
            cost_row, text="", font=ctk.CTkFont(size=11), text_color="gray50"
        )
        self.tokens_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(controls_frame, progress_color=ACCENT_GREEN, height=8)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)

        self.log = LogConsole(controls_frame, height=90)
        self.log.pack(fill="x", pady=(0, 5))

    # ===== Pomocnicze UI =====

    def _on_zaplecze_toggle(self):
        if self.zaplecze_var.get():
            self.domain_entry.configure(state="disabled", fg_color="gray20")
        else:
            self.domain_entry.configure(
                state="normal",
                fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"],
            )

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    # ===== Wczytywanie XLSX =====

    def _load_xlsx(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Pliki Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")]
        )
        if not filepath:
            return
        try:
            headers = read_xlsx_headers(filepath)
        except Exception as e:
            self.log.append(f"[BŁĄD] Nie udało się wczytać pliku: {e}")
            return

        auto_map = auto_detect_columns(headers)
        dialog = ColumnMappingDialog(self, headers, auto_map)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            self.articles = parse_content_plan(filepath, dialog.result)
        except ValueError as e:
            self.log.append(f"[BŁĄD] {e}")
            return
        except Exception as e:
            self.log.append(f"[BŁĄD] Nie udało się wczytać pliku: {e}")
            return

        self._xlsx_path = filepath
        filename = Path(filepath).name
        self.xlsx_label.configure(
            text=f"{filename} ({len(self.articles)} artykułów)",
            text_color=ACCENT_GREEN,
        )
        self._populate_table()
        self._update_estimate_panel()

    def _populate_table(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        self.checkboxes = []
        self.status_labels = []
        self.regen_btns = []
        self.article_filepaths = [""] * len(self.articles)
        global_domain = self.domain_entry.get().strip()

        for i, art in enumerate(self.articles):
            row_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent", height=30)
            row_frame.pack(fill="x", pady=1)

            # Checkbox
            var = ctk.BooleanVar(value=True)
            self.checkboxes.append(var)
            ctk.CTkCheckBox(
                row_frame, text="", variable=var,
                width=30, checkbox_width=18, checkbox_height=18,
            ).pack(side="left", padx=(4, 0))

            # Numer
            ctk.CTkLabel(
                row_frame, text=str(i + 1), width=30,
                font=ctk.CTkFont(size=11), text_color="gray50", anchor="w",
            ).pack(side="left", padx=4)

            # Tytuł
            title_text = art["title"]
            if len(title_text) > 35:
                title_text = title_text[:32] + "..."
            ctk.CTkLabel(
                row_frame, text=title_text, width=210,
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(side="left", padx=3)

            # Główne KW
            kw_text = art.get("main_kw", "")
            if len(kw_text) > 20:
                kw_text = kw_text[:17] + "..."
            ctk.CTkLabel(
                row_frame, text=kw_text or "—", width=130,
                font=ctk.CTkFont(size=11),
                text_color="gray50" if not kw_text else None, anchor="w",
            ).pack(side="left", padx=3)

            # Słowa poboczne
            sec_kw_text = art.get("secondary_kw", "")
            if len(sec_kw_text) > 22:
                sec_kw_text = sec_kw_text[:19] + "..."
            ctk.CTkLabel(
                row_frame, text=sec_kw_text or "—", width=150,
                font=ctk.CTkFont(size=11),
                text_color="gray50" if not sec_kw_text else "gray70", anchor="w",
            ).pack(side="left", padx=3)

            # Domena
            domain = art.get("domain", "") or global_domain
            ctk.CTkLabel(
                row_frame, text=domain or "—", width=100,
                font=ctk.CTkFont(
                    size=11,
                    slant="italic" if not art.get("domain") and domain else "roman",
                ),
                text_color="gray50" if not domain else None, anchor="w",
            ).pack(side="left", padx=3)

            # Język
            art_lang = (art.get("lang", "") or self.lang_var.get()).upper()
            ctk.CTkLabel(
                row_frame, text=art_lang, width=35,
                font=ctk.CTkFont(size=11),
                text_color="gray60" if not art.get("lang") else "#60A5FA",
                anchor="w",
            ).pack(side="left", padx=3)

            # Przyciski ↑↓ do zmiany kolejności
            arrows_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=60)
            arrows_frame.pack(side="left", padx=2)
            ctk.CTkButton(
                arrows_frame, text="↑", width=26, height=22,
                fg_color="gray25", hover_color="gray35",
                font=ctk.CTkFont(size=11), command=lambda idx=i: self._move_article(idx, -1),
            ).pack(side="left", padx=(0, 2))
            ctk.CTkButton(
                arrows_frame, text="↓", width=26, height=22,
                fg_color="gray25", hover_color="gray35",
                font=ctk.CTkFont(size=11), command=lambda idx=i: self._move_article(idx, 1),
            ).pack(side="left")

            # Status + przycisk regeneracji
            status_label = ctk.CTkLabel(
                row_frame, text="Oczekuje", fg_color="#4B5563",
                corner_radius=6, text_color="white",
                font=ctk.CTkFont(size=10), width=80, padx=6, pady=2,
            )
            status_label.pack(side="left", padx=(4, 2))
            self.status_labels.append(status_label)

            # Przycisk podglądu/regeneracji (aktywny po wygenerowaniu)
            regen_btn = ctk.CTkButton(
                row_frame, text="👁", width=28, height=22,
                fg_color="gray25", hover_color="gray35",
                font=ctk.CTkFont(size=11), state="disabled",
                command=lambda idx=i: self._show_article_actions(idx),
            )
            regen_btn.pack(side="left", padx=(0, 4))
            self.regen_btns.append(regen_btn)

    def _move_article(self, idx: int, direction: int):
        """Przesuwa artykuł w górę (-1) lub w dół (+1)."""
        if self._generating:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.articles):
            return
        self.articles[idx], self.articles[new_idx] = self.articles[new_idx], self.articles[idx]
        self._populate_table()

    def _show_article_actions(self, idx: int):
        """Pokazuje podgląd lub menu akcji dla artykułu."""
        filepath = self.article_filepaths[idx] if idx < len(self.article_filepaths) else ""
        art = self.articles[idx]

        if filepath and Path(filepath).exists():
            preview = ArticlePreviewWindow(self, filepath, art["title"])
            preview.grab_set()
        else:
            # Brak pliku — zaoferuj regenerację przez zaznaczenie checkboxa
            self.log.append(f"[INFO] Plik dla artykułu #{idx+1} nie istnieje — zaznacz i wygeneruj ponownie.")

    # ===== Checkboxy =====

    def _set_all_checkboxes(self, value: bool):
        for var in self.checkboxes:
            var.set(value)

    def _select_errors(self):
        """Zaznacza tylko artykuły z błędem (status 'Błąd')."""
        for i, var in enumerate(self.checkboxes):
            label = self.status_labels[i]
            is_error = "Błąd" in (label.cget("text") or "")
            var.set(is_error)

    # ===== Panel estymacji =====

    def _update_estimate_panel(self):
        """Odświeża panel z estymacją kosztu."""
        self.estimate_frame.pack_forget()

        if not self.articles:
            return

        selected_count = sum(1 for var in self.checkboxes if var.get()) or len(self.articles)
        cfg = self.get_config()
        current_model = cfg.get("model", "claude-opus-4-6")

        try:
            estimates = estimate_session_cost(selected_count)
        except Exception:
            return

        # Odbuduj ramkę
        for w in self.estimate_frame.winfo_children():
            w.destroy()

        self.estimate_frame.pack(fill="x", padx=20, pady=(0, 5))

        ctk.CTkLabel(
            self.estimate_frame,
            text=f"Szacowany koszt dla {selected_count} artykułów:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(10, 15))

        for model_name, data in estimates.items():
            color = ACCENT_GREEN if model_name == current_model else "gray50"
            prefix = "▶ " if model_name == current_model else "  "
            short_name = "Opus" if "opus" in model_name else "Sonnet"
            ctk.CTkLabel(
                self.estimate_frame,
                text=f"{prefix}{short_name}: ${data['total_cost']:.2f}  (${data['cost_per_article']:.3f}/art.)",
                font=ctk.CTkFont(size=12),
                text_color=color,
            ).pack(side="left", padx=(0, 20))

    # ===== Status =====

    def _update_status(self, index: int, status: str, detail: str = ""):
        colors = {
            "waiting": "#4B5563",
            "generating": "#3B82F6",
            "success": "#22C55E",
            "warning": "#F59E0B",
            "error": "#EF4444",
        }
        texts = {
            "waiting": "Oczekuje",
            "generating": "Generowanie...",
            "success": "Gotowy",
            "warning": "Gotowy",
            "error": "Błąd",
        }
        text = texts.get(status, status)
        if detail:
            text = f"{text} ({detail})"
        self.status_labels[index].configure(text=text, fg_color=colors.get(status, "#4B5563"))

    # ===== Generowanie =====

    def _start_generation(self):
        if self._generating:
            return

        cfg = self.get_config()
        api_key = cfg.get("api_key", "")
        if not api_key:
            self.log.append("[BŁĄD] Brak API key — przejdź do zakładki Ustawienia.")
            return

        selected = [i for i, var in enumerate(self.checkboxes) if var.get()]
        if not selected:
            self.log.append("[BŁĄD] Nie zaznaczono żadnych artykułów.")
            return

        self._generating = True
        self._stop_flag = False
        self.generate_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.zip_btn.configure(state="disabled")

        model = cfg.get("model", "claude-opus-4-6")
        lang = self.lang_var.get().lower()
        is_zaplecze = self.zaplecze_var.get()
        global_domain = self.domain_entry.get().strip()
        output_base = self.output_entry.get().strip() or "./output"
        delay = cfg.get("delay_seconds", 5)

        threading.Thread(
            target=self._generation_worker,
            args=(api_key, model, lang, is_zaplecze, global_domain, output_base, delay, selected),
            daemon=True,
        ).start()

    def _stop_generation(self):
        self._stop_flag = True
        self.log.append("[INFO] Zatrzymywanie po bieżącym artykule...")
        self.stop_btn.configure(state="disabled")

    def _generation_worker(
        self,
        api_key: str, model: str, lang: str, is_zaplecze: bool,
        global_domain: str, output_base: str, delay: int, selected: list[int],
    ):
        client = anthropic.Anthropic(api_key=api_key)
        total = len(selected)
        start_time = time.time()
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0

        session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_dir = Path(output_base) / session_id

        domains_in_plan = set()
        for idx in selected:
            art = self.articles[idx]
            d = art.get("domain", "") or global_domain
            domains_in_plan.add(d or "_bez-domeny")
        use_subdirs = len(domains_in_plan) > 1

        session_dir.mkdir(parents=True, exist_ok=True)
        self._session_dir = session_dir

        session_data = {
            "id": session_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "xlsx_file": Path(self._xlsx_path).name if self._xlsx_path else "",
            "domain": global_domain,
            "language": lang,
            "model": model,
            "output_dir": str(session_dir),
            "total": total,
            "success": 0,
            "failed": 0,
            "elapsed_seconds": 0,
            "articles": [],
        }

        for count, idx in enumerate(selected):
            if self._stop_flag:
                self._log(f"[INFO] Generowanie zatrzymane po {count} artykułach.")
                break

            art = self.articles[idx]
            elapsed = time.time() - start_time
            avg_per_article = elapsed / count if count > 0 else 0
            remaining = avg_per_article * (total - count) if count > 0 else 0

            self.after(0, lambda c=count: self.progress_bar.set(c / total))
            self.after(0, lambda c=count: self.progress_label.configure(text=f"{c}/{total} artykułów..."))
            elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed))
            remaining_str = time.strftime("~%M:%S", time.gmtime(remaining))
            self.after(0, lambda e=elapsed_str, r=remaining_str: self.time_label.configure(
                text=f"Czas: {e} | Szacowany pozostały: {r}"
            ))
            self.after(0, lambda i=idx: self._update_status(i, "generating"))
            self._log(f"Generuję: \"{art['title'][:60]}\"...")

            art_lang = art.get("lang", "").strip().lower() or lang

            try:
                result = generate_article_with_retry(
                    client, art, global_domain, art_lang, is_zaplecze, model
                )
                text = result["text"]
                art_cost = result["cost"]
                art_input = result["input_tokens"]
                art_output = result["output_tokens"]
                total_cost += art_cost
                total_input_tokens += art_input
                total_output_tokens += art_output

                char_count = len(text)
                status = "success" if 8500 <= char_count <= 9500 else "warning"

                slug = _slugify(art.get("main_kw") or art["title"])
                art_domain = art.get("domain", "") or global_domain
                domain_slug = _slugify(art_domain, max_len=40) if art_domain else ""

                if use_subdirs:
                    domain_dir_name = domain_slug or "_bez-domeny"
                    file_dir = session_dir / domain_dir_name
                    file_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"{count + 1:03d}-{domain_slug}-{slug}.md" if domain_slug else f"{count + 1:03d}-{slug}.md"
                else:
                    file_dir = session_dir
                    filename = f"{count + 1:03d}-{slug}.md"

                filepath = file_dir / filename
                filepath.write_text(text, encoding="utf-8")

                # Zapisz ścieżkę per artykuł (do podglądu)
                if idx < len(self.article_filepaths):
                    self.article_filepaths[idx] = str(filepath)

                self.after(0, lambda i=idx, s=status, c=char_count: self._update_status(i, s, f"{c} zn."))
                # Aktywuj przycisk podglądu
                self.after(0, lambda i=idx: self.regen_btns[i].configure(state="normal") if i < len(self.regen_btns) else None)

                self._log(
                    f"✅ Zapisano: {filename} ({char_count} zn.) | "
                    f"Tokeny: {art_input}+{art_output} | Koszt: ${art_cost:.4f}"
                )
                self.after(0, lambda c=total_cost, ti=total_input_tokens, to=total_output_tokens: (
                    self.cost_label.configure(text=f"Koszt sesji: ${c:.4f}"),
                    self.tokens_label.configure(
                        text=f"Tokeny: {ti:,} input + {to:,} output = {ti + to:,} łącznie"
                    ),
                ))

                session_data["success"] += 1
                session_data["articles"].append({
                    "title": art["title"],
                    "main_kw": art.get("main_kw", ""),
                    "filename": filename,
                    "filepath": str(filepath),
                    "chars": char_count,
                    "status": "success",
                    "input_tokens": art_input,
                    "output_tokens": art_output,
                    "cost": round(art_cost, 4),
                })

            except anthropic.AuthenticationError:
                self.after(0, lambda i=idx: self._update_status(i, "error"))
                self._log("[BŁĄD] Nieprawidłowy API key — zatrzymuję generowanie.")
                session_data["failed"] += 1
                session_data["articles"].append({
                    "title": art["title"], "main_kw": art.get("main_kw", ""),
                    "filename": "", "filepath": "", "chars": 0, "status": "error",
                })
                break

            except Exception as e:
                self.after(0, lambda i=idx: self._update_status(i, "error"))
                self._log(f"❌ Błąd: {art['title'][:40]}... — {str(e)[:80]}")
                session_data["failed"] += 1
                session_data["articles"].append({
                    "title": art["title"], "main_kw": art.get("main_kw", ""),
                    "filename": "", "filepath": "", "chars": 0, "status": "error",
                })

            if count < total - 1 and not self._stop_flag:
                time.sleep(delay)

        # Zakończenie
        total_elapsed = time.time() - start_time
        session_data["elapsed_seconds"] = int(total_elapsed)
        session_data["total_cost"] = round(total_cost, 4)
        session_data["total_input_tokens"] = total_input_tokens
        session_data["total_output_tokens"] = total_output_tokens

        add_session(session_data)

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.after(0, lambda: self.progress_label.configure(
            text=f"{session_data['success']}/{total} zakończono"
        ))
        elapsed_str = time.strftime("%M:%S", time.gmtime(total_elapsed))
        self.after(0, lambda: self.time_label.configure(text=f"Czas całkowity: {elapsed_str}"))

        self._log(
            f"Zakończono: {session_data['success']} sukces, "
            f"{session_data['failed']} błędów, czas: {elapsed_str} | "
            f"Koszt: ${total_cost:.4f} | Tokeny: {total_input_tokens + total_output_tokens:,}"
        )

        # Powiadomienie systemowe
        _send_system_notification(
            "Bulk Blog Writer",
            f"Zakończono! {session_data['success']}/{total} artykułów w {elapsed_str}"
        )

        self.after(0, self._generation_finished)

    def _generation_finished(self):
        self._generating = False
        self._stop_flag = False
        self.generate_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if self._session_dir and self._session_dir.exists():
            self.zip_btn.configure(state="normal")

    # ===== ZIP export =====

    def _export_zip(self):
        if not self._session_dir or not self._session_dir.exists():
            return

        default_name = f"bulk-blog-{self._session_dir.name}.zip"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=default_name,
        )
        if not save_path:
            return

        try:
            md_files = list(self._session_dir.rglob("*.md"))
            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for md_file in md_files:
                    arcname = md_file.relative_to(self._session_dir.parent)
                    zf.write(md_file, arcname)
            self.log.append(f"[INFO] ZIP zapisany: {Path(save_path).name} ({len(md_files)} plików)")
        except Exception as e:
            self.log.append(f"[BŁĄD] Eksport ZIP: {e}")

    # ===== Log =====

    def _log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self.log.append(f"[{ts}] {message}"))
