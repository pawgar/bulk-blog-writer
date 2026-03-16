"""Zakładka Generuj — główny workflow generowania artykułów."""

import re
import time
import threading
from pathlib import Path
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import anthropic

from xlsx_parser import parse_content_plan
from api_client import generate_article_with_retry
from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER, LogConsole
from ui.tab_history import add_session


def _slugify(text: str, max_len: int = 50) -> str:
    """Tworzy slug z tekstu — do nazw plików."""
    text = text.lower().strip()
    # Zamień polskie/czeskie/niemieckie znaki
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "á": "a", "é": "e", "í": "i", "ú": "u", "ñ": "n",
        "å": "a", "ě": "e", "š": "s", "č": "c", "ř": "r",
        "ž": "z", "ý": "y", "ď": "d", "ť": "t", "ů": "u",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text


class GenerateTab(ctk.CTkFrame):
    """Zakładka z głównym workflow generowania artykułów."""

    def __init__(self, master, config: dict, get_config_callback):
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.get_config = get_config_callback
        self.articles: list[dict] = []
        self.checkboxes: list[ctk.BooleanVar] = []
        self.status_labels: list[ctk.CTkLabel] = []
        self._generating = False
        self._stop_flag = False
        self._xlsx_path = ""
        self._build_ui()

    def _build_ui(self):
        # ===== SEKCJA 1: Konfiguracja generowania =====
        config_frame = ctk.CTkFrame(self, fg_color="transparent")
        config_frame.pack(fill="x", padx=20, pady=(15, 5))

        # Wiersz 1: XLSX + Domena + Język
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))

        self.xlsx_btn = ctk.CTkButton(
            row1,
            text="Wczytaj XLSX",
            command=self._load_xlsx,
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN_HOVER,
            text_color="black",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=130,
            height=34,
        )
        self.xlsx_btn.pack(side="left")

        self.xlsx_label = ctk.CTkLabel(
            row1, text="Nie wczytano pliku", text_color="gray50", font=ctk.CTkFont(size=12)
        )
        self.xlsx_label.pack(side="left", padx=(10, 0))

        # Język — prawa strona
        ctk.CTkLabel(row1, text="Język:", font=ctk.CTkFont(size=12)).pack(
            side="right", padx=(5, 0)
        )
        default_lang = self.config.get("default_lang", "pl").upper()
        self.lang_var = ctk.StringVar(value=default_lang)
        ctk.CTkOptionMenu(
            row1,
            values=["PL", "DE", "NL", "ES", "SV", "CS", "EN"],
            variable=self.lang_var,
            width=70,
        ).pack(side="right")

        # Domena — prawa strona
        self.domain_entry = ctk.CTkEntry(
            row1, placeholder_text="Domena (domyślna)", width=200, font=ctk.CTkFont(size=12)
        )
        self.domain_entry.pack(side="right", padx=(0, 15))
        ctk.CTkLabel(row1, text="Domena:", font=ctk.CTkFont(size=12)).pack(
            side="right", padx=(5, 0)
        )

        # Wiersz 2: Checkbox zaplecze + Katalog wyjściowy
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 5))

        self.zaplecze_var = ctk.BooleanVar(value=False)
        self.zaplecze_cb = ctk.CTkCheckBox(
            row2,
            text="Artykuły zapleczowe",
            variable=self.zaplecze_var,
            font=ctk.CTkFont(size=12),
            command=self._on_zaplecze_toggle,
            checkbox_width=20,
            checkbox_height=20,
        )
        self.zaplecze_cb.pack(side="left")

        # Katalog wyjściowy — prawa strona
        ctk.CTkButton(
            row2,
            text="Przeglądaj...",
            width=90,
            fg_color="gray30",
            hover_color="gray40",
            command=self._browse_output,
            height=28,
        ).pack(side="right")

        self.output_entry = ctk.CTkEntry(
            row2,
            width=300,
            font=ctk.CTkFont(size=12),
        )
        self.output_entry.pack(side="right", padx=(5, 5))
        self.output_entry.insert(
            0, self.config.get("default_output_dir", "./output")
        )

        ctk.CTkLabel(row2, text="Katalog wyjściowy:", font=ctk.CTkFont(size=12)).pack(
            side="right", padx=(0, 5)
        )

        # ===== SEKCJA 2: Tabela artykułów =====
        table_header = ctk.CTkFrame(self, fg_color="transparent")
        table_header.pack(fill="x", padx=20, pady=(10, 2))

        self.select_all_btn = ctk.CTkButton(
            table_header,
            text="☑ Zaznacz wszystkie",
            fg_color="gray30",
            hover_color="gray40",
            text_color="white",
            font=ctk.CTkFont(size=12),
            width=150,
            height=28,
            command=lambda: self._set_all_checkboxes(True),
        )
        self.select_all_btn.pack(side="left")

        self.deselect_all_btn = ctk.CTkButton(
            table_header,
            text="☐ Odznacz wszystkie",
            fg_color="gray30",
            hover_color="gray40",
            text_color="white",
            font=ctk.CTkFont(size=12),
            width=160,
            height=28,
            command=lambda: self._set_all_checkboxes(False),
        )
        self.deselect_all_btn.pack(side="left", padx=(8, 0))

        # Nagłówki kolumn
        col_header = ctk.CTkFrame(self, fg_color="gray20", corner_radius=4)
        col_header.pack(fill="x", padx=20, pady=(2, 0))

        widths = [30, 30, 250, 150, 180, 110, 110]
        labels = ["✓", "#", "Tytuł wpisu", "Główne KW", "Słowa poboczne", "Domena", "Status"]
        for w, label in zip(widths, labels):
            ctk.CTkLabel(
                col_header,
                text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=w,
                anchor="w",
            ).pack(side="left", padx=3, pady=4)

        # Scrollable table
        self.table_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", height=300
        )
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        self.empty_label = ctk.CTkLabel(
            self.table_frame,
            text="Wczytaj plik XLSX z content planem, aby rozpocząć.",
            text_color="gray50",
            font=ctk.CTkFont(size=13),
        )
        self.empty_label.pack(pady=40)

        # ===== SEKCJA 3: Kontrolki generowania =====
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(fill="x", padx=20, pady=(5, 5))

        btn_row = ctk.CTkFrame(controls_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 5))

        self.generate_btn = ctk.CTkButton(
            btn_row,
            text="▶  Generuj zaznaczone",
            command=self._start_generation,
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN_HOVER,
            text_color="black",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=200,
            height=40,
        )
        self.generate_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            btn_row,
            text="⏹  Stop",
            command=self._stop_generation,
            fg_color="#EF4444",
            hover_color="#DC2626",
            font=ctk.CTkFont(size=13),
            width=100,
            height=40,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        # Progress info
        self.progress_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12), text_color="gray50"
        )
        self.progress_label.pack(side="left", padx=(15, 0))

        self.time_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=11), text_color="gray50"
        )
        self.time_label.pack(side="right")

        # Wiersz kosztów
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

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            controls_frame,
            progress_color=ACCENT_GREEN,
            height=8,
        )
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)

        # Log konsola
        self.log = LogConsole(controls_frame, height=90)
        self.log.pack(fill="x", pady=(0, 5))

    def _on_zaplecze_toggle(self):
        """Wyszarza pole domeny gdy tryb zapleczowy."""
        if self.zaplecze_var.get():
            self.domain_entry.configure(state="disabled", fg_color="gray20")
        else:
            self.domain_entry.configure(state="normal", fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _load_xlsx(self):
        """Wczytuje plik XLSX i wypełnia tabelę."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Pliki Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")]
        )
        if not filepath:
            return

        try:
            self.articles = parse_content_plan(filepath)
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

    def _populate_table(self):
        """Wypełnia tabelę artykułami."""
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        self.checkboxes = []
        self.status_labels = []
        global_domain = self.domain_entry.get().strip()

        for i, art in enumerate(self.articles):
            row_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent", height=30)
            row_frame.pack(fill="x", pady=1)

            # Checkbox
            var = ctk.BooleanVar(value=True)
            self.checkboxes.append(var)
            ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=var,
                width=30,
                checkbox_width=18,
                checkbox_height=18,
            ).pack(side="left", padx=(4, 0))

            # Numer
            ctk.CTkLabel(
                row_frame,
                text=str(i + 1),
                width=30,
                font=ctk.CTkFont(size=11),
                text_color="gray50",
                anchor="w",
            ).pack(side="left", padx=4)

            # Tytuł
            title_text = art["title"]
            if len(title_text) > 45:
                title_text = title_text[:42] + "..."
            ctk.CTkLabel(
                row_frame,
                text=title_text,
                width=250,
                font=ctk.CTkFont(size=11),
                anchor="w",
            ).pack(side="left", padx=3)

            # Główne KW
            kw_text = art.get("main_kw", "")
            if len(kw_text) > 25:
                kw_text = kw_text[:22] + "..."
            ctk.CTkLabel(
                row_frame,
                text=kw_text or "—",
                width=150,
                font=ctk.CTkFont(size=11),
                text_color="gray50" if not kw_text else None,
                anchor="w",
            ).pack(side="left", padx=3)

            # Słowa poboczne
            sec_kw_text = art.get("secondary_kw", "")
            if len(sec_kw_text) > 30:
                sec_kw_text = sec_kw_text[:27] + "..."
            ctk.CTkLabel(
                row_frame,
                text=sec_kw_text or "—",
                width=180,
                font=ctk.CTkFont(size=11),
                text_color="gray50" if not sec_kw_text else "gray70",
                anchor="w",
            ).pack(side="left", padx=3)

            # Domena
            domain = art.get("domain", "") or global_domain
            domain_label = ctk.CTkLabel(
                row_frame,
                text=domain or "—",
                width=110,
                font=ctk.CTkFont(size=11, slant="italic" if not art.get("domain") and domain else "roman"),
                text_color="gray50" if not domain else None,
                anchor="w",
            )
            domain_label.pack(side="left", padx=3)

            # Status
            status_label = ctk.CTkLabel(
                row_frame,
                text="Oczekuje",
                fg_color="#4B5563",
                corner_radius=6,
                text_color="white",
                font=ctk.CTkFont(size=10),
                width=110,
                padx=6,
                pady=2,
            )
            status_label.pack(side="left", padx=4)
            self.status_labels.append(status_label)

    def _set_all_checkboxes(self, value: bool):
        for var in self.checkboxes:
            var.set(value)

    def _update_status(self, index: int, status: str, detail: str = ""):
        """Aktualizuje badge statusu w tabeli."""
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
        color = colors.get(status, "#4B5563")
        self.status_labels[index].configure(text=text, fg_color=color)

    def _start_generation(self):
        """Uruchamia generowanie zaznaczonych artykułów."""
        if self._generating:
            return

        # Pobierz aktualną konfigurację
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

        model = cfg.get("model", "claude-opus-4-6")
        lang = self.lang_var.get().lower()
        is_zaplecze = self.zaplecze_var.get()
        global_domain = self.domain_entry.get().strip()
        output_base = self.output_entry.get().strip() or "./output"
        delay = cfg.get("delay_seconds", 5)

        thread = threading.Thread(
            target=self._generation_worker,
            args=(api_key, model, lang, is_zaplecze, global_domain, output_base, delay, selected),
            daemon=True,
        )
        thread.start()

    def _stop_generation(self):
        """Ustawia flagę stopu — generowanie zatrzyma się po bieżącym artykule."""
        self._stop_flag = True
        self.log.append("[INFO] Zatrzymywanie po bieżącym artykule...")
        self.stop_btn.configure(state="disabled")

    def _generation_worker(
        self,
        api_key: str,
        model: str,
        lang: str,
        is_zaplecze: bool,
        global_domain: str,
        output_base: str,
        delay: int,
        selected: list[int],
    ):
        """Worker thread — generuje artykuły sekwencyjnie."""
        client = anthropic.Anthropic(api_key=api_key)
        total = len(selected)
        start_time = time.time()
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0

        # Przygotuj katalog sesji
        session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_dir = Path(output_base) / session_id

        # Sprawdź czy potrzebne podkatalogi per domena
        domains_in_plan = set()
        for idx in selected:
            art = self.articles[idx]
            d = art.get("domain", "") or global_domain
            domains_in_plan.add(d or "_bez-domeny")

        use_subdirs = len(domains_in_plan) > 1

        session_dir.mkdir(parents=True, exist_ok=True)

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

            # Aktualizuj UI
            self.after(0, lambda c=count: self.progress_bar.set(c / total))
            self.after(
                0,
                lambda c=count: self.progress_label.configure(
                    text=f"{c}/{total} artykułów..."
                ),
            )
            elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed))
            remaining_str = time.strftime("~%M:%S", time.gmtime(remaining))
            self.after(
                0,
                lambda e=elapsed_str, r=remaining_str: self.time_label.configure(
                    text=f"Czas: {e} | Szacowany pozostały: {r}"
                ),
            )

            self.after(0, lambda i=idx: self._update_status(i, "generating"))
            self._log(f"Generuję: \"{art['title'][:60]}\"...")

            try:
                result = generate_article_with_retry(
                    client, art, global_domain, lang, is_zaplecze, model
                )
                text = result["text"]
                art_cost = result["cost"]
                art_input = result["input_tokens"]
                art_output = result["output_tokens"]
                total_cost += art_cost
                total_input_tokens += art_input
                total_output_tokens += art_output

                # Policz znaki
                char_count = len(text)

                # Określ status na podstawie liczby znaków
                if 8500 <= char_count <= 9500:
                    status = "success"
                else:
                    status = "warning"

                # Zapisz plik
                slug = _slugify(art.get("main_kw") or art["title"])
                art_domain = art.get("domain", "") or global_domain
                domain_slug = _slugify(art_domain, max_len=40) if art_domain else ""

                if use_subdirs:
                    # Przy wielu domenach: podkatalogi + domena w nazwie pliku
                    domain_dir_name = domain_slug or "_bez-domeny"
                    file_dir = session_dir / domain_dir_name
                    file_dir.mkdir(parents=True, exist_ok=True)
                    if domain_slug:
                        filename = f"{count + 1:03d}-{domain_slug}-{slug}.md"
                    else:
                        filename = f"{count + 1:03d}-{slug}.md"
                else:
                    file_dir = session_dir
                    filename = f"{count + 1:03d}-{slug}.md"

                filepath = file_dir / filename
                filepath.write_text(text, encoding="utf-8")

                self.after(
                    0,
                    lambda i=idx, s=status, c=char_count: self._update_status(
                        i, s, f"{c} zn."
                    ),
                )
                self._log(
                    f"✅ Zapisano: {filename} ({char_count} zn.) | "
                    f"Tokeny: {art_input}+{art_output} | Koszt: ${art_cost:.4f}"
                )
                # Aktualizuj sumaryczne koszty w UI
                self.after(
                    0,
                    lambda c=total_cost, ti=total_input_tokens, to=total_output_tokens: (
                        self.cost_label.configure(text=f"Koszt sesji: ${c:.4f}"),
                        self.tokens_label.configure(
                            text=f"Tokeny: {ti:,} input + {to:,} output = {ti + to:,} łącznie"
                        ),
                    ),
                )

                session_data["success"] += 1
                session_data["articles"].append(
                    {
                        "title": art["title"],
                        "main_kw": art.get("main_kw", ""),
                        "filename": filename,
                        "chars": char_count,
                        "status": "success",
                        "input_tokens": art_input,
                        "output_tokens": art_output,
                        "cost": round(art_cost, 4),
                    }
                )

            except anthropic.AuthenticationError:
                self.after(0, lambda i=idx: self._update_status(i, "error"))
                self._log("[BŁĄD] Nieprawidłowy API key — zatrzymuję generowanie.")
                session_data["failed"] += 1
                session_data["articles"].append(
                    {
                        "title": art["title"],
                        "main_kw": art.get("main_kw", ""),
                        "filename": "",
                        "chars": 0,
                        "status": "error",
                    }
                )
                break

            except Exception as e:
                self.after(0, lambda i=idx: self._update_status(i, "error"))
                self._log(f"❌ Błąd: {art['title'][:40]}... — {str(e)[:60]}")
                session_data["failed"] += 1
                session_data["articles"].append(
                    {
                        "title": art["title"],
                        "main_kw": art.get("main_kw", ""),
                        "filename": "",
                        "chars": 0,
                        "status": "error",
                    }
                )

            # Opóźnienie między requestami (chyba że to ostatni)
            if count < total - 1 and not self._stop_flag:
                time.sleep(delay)

        # Zakończenie
        total_elapsed = time.time() - start_time
        session_data["elapsed_seconds"] = int(total_elapsed)

        # Zapisz do historii
        add_session(session_data)

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.after(
            0,
            lambda: self.progress_label.configure(
                text=f"{session_data['success']}/{total} zakończono"
            ),
        )
        elapsed_str = time.strftime("%M:%S", time.gmtime(total_elapsed))
        self.after(
            0,
            lambda: self.time_label.configure(text=f"Czas całkowity: {elapsed_str}"),
        )

        session_data["total_cost"] = round(total_cost, 4)
        session_data["total_input_tokens"] = total_input_tokens
        session_data["total_output_tokens"] = total_output_tokens

        self._log(
            f"Zakończono: {session_data['success']} sukces, "
            f"{session_data['failed']} błędów, czas: {elapsed_str} | "
            f"Koszt: ${total_cost:.4f} | Tokeny: {total_input_tokens + total_output_tokens:,}"
        )

        self.after(0, self._generation_finished)

    def _generation_finished(self):
        """Przywraca przyciski po zakończeniu generowania."""
        self._generating = False
        self._stop_flag = False
        self.generate_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _log(self, message: str):
        """Dodaje wpis do konsoli z timestampem."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self.log.append(f"[{ts}] {message}"))
